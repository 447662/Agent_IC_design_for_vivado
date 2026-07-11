# P1-1 Source Package Layout TDD Evidence

## Source

No upgrade plan file was read for this work. The scope came from the active
P1-1 requirement to migrate toward `src/digital_ic_agent/` while preserving the
existing CLI surface.

## User Journeys

1. As a maintainer, I want a `src/digital_ic_agent` package to exist, so the
   project has a standard importable package path for the ongoing modular
   migration.
2. As an existing user, I want the new package to export `DigitalICAgent`,
   `create_agent`, `main`, CLI parsing, and entrypoint helpers without breaking
   the legacy `.trae/agent/agent.py` entrypoint.
3. As a quality reviewer, I want the new package included in mypy and coverage
   scope, so future migration work is not invisible to quality gates.

## Task Report

This slice adds a compatibility package under `src/digital_ic_agent/`:

- `digital_ic_agent.__init__` exports `DigitalICAgent`, `create_agent`, and
  `main`.
- `digital_ic_agent.agent` bridges to the current legacy Agent implementation.
- `digital_ic_agent.cli` exports the existing CLI parser helpers.
- `digital_ic_agent.entrypoint` exports the existing `run_cli` entrypoint.
- `digital_ic_agent.__main__` supports `python -m digital_ic_agent`.

The package is intentionally a compatibility bridge, not a wholesale move of
all modules. It gives P1-1 a real `src/` package surface while keeping the
current legacy CLI and tests working.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_package_layout.py --basetemp .tmp-pytest-p1-1-package-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_package_layout.py::test_src_package_exports_core_agent_entrypoints_without_path_insertion
AssertionError: assert False

FAILED tests/test_p1_1_package_layout.py::test_src_package_is_in_quality_and_coverage_scope
AssertionError: assert 'src/digital_ic_agent' in [...]

2 failed in 0.08s
```

## GREEN Evidence

Focused command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_package_layout.py --basetemp .tmp-pytest-p1-1-package-green -p no:cacheprovider -q
```

Focused result:

```text
2 passed in 0.13s
```

Regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_package_layout.py tests/test_architecture_runtime.py tests/test_repository_reproducibility.py tests/test_quality_config.py --basetemp .tmp-pytest-p1-1-package-final -p no:cacheprovider -q
```

Regression result:

```text
43 passed in 5.64s
```

Lint command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check src/digital_ic_agent tests/test_p1_1_package_layout.py .trae/agent/agent.py .trae/agent/target_flows.py .trae/agent/target_plugins.py .trae/agent/target_service_host.py tests/test_architecture_runtime.py tests/test_quality_config.py tests/test_repository_reproducibility.py
```

Lint result:

```text
All checks passed!
```

Mypy command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

Mypy result:

```text
Success: no issues found in 54 source files
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | `src/digital_ic_agent` exists with package, module, CLI, entrypoint, and `__main__` files | `tests/test_p1_1_package_layout.py::test_src_package_exports_core_agent_entrypoints_without_path_insertion` | package/static | PASS | `2 passed in 0.13s` |
| 2 | The new package exports `DigitalICAgent`, `create_agent`, and `main` from `digital_ic_agent.agent` | `tests/test_p1_1_package_layout.py::test_src_package_exports_core_agent_entrypoints_without_path_insertion` | package/import | PASS | package import assertions passed |
| 3 | The new CLI compatibility module preserves `parse_args(["--list-targets"])` behavior | `tests/test_p1_1_package_layout.py::test_src_package_exports_core_agent_entrypoints_without_path_insertion` | package/import | PASS | CLI parser assertion passed |
| 4 | The new package source does not contain `sys.path.insert` | `tests/test_p1_1_package_layout.py::test_src_package_exports_core_agent_entrypoints_without_path_insertion` | architecture/static | PASS | source scan assertion passed |
| 5 | `src/digital_ic_agent` is included in mypy file scope and coverage source scope | `tests/test_p1_1_package_layout.py::test_src_package_is_in_quality_and_coverage_scope` | quality/static | PASS | quality scope assertions passed |
| 6 | Architecture, reproducibility, and quality regressions stay green | package final pytest command | regression | PASS | `43 passed in 5.64s` |
| 7 | Changed source and tests pass Ruff | Ruff command above | lint | PASS | `All checks passed!` |
| 8 | Full configured mypy scope passes with the new package included | Mypy command above | typecheck | PASS | `Success: no issues found in 54 source files` |

## Known Gaps

- This is a compatibility package slice. Most implementation modules still live
  under `.trae/agent/` and continue to be migrated in later P1-1 steps.
- The legacy `.trae/agent/agent.py` still contains its own compatibility
  `sys.path.insert()` bootstrap. Removing that bootstrap is a separate P1-1
  follow-up because tests and local script execution still import legacy modules
  by their historical top-level names.
- The report-template split and hard module/function size gates remain active
  P1-1 follow-up work.
