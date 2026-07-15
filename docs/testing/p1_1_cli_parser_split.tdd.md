# P1-1 CLI Parser Split TDD Evidence

## Source

No upgrade plan file was read for this work. This P1-1 slice was derived from
the current code shape, the active P1-1 acceptance criteria, and the post-dispatch
module-size scan showing `agent_cli.parse_args()` as a remaining oversized
entrypoint-adjacent function.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want CLI parser construction split from `parse_args()`, so
   the CLI entry helpers stay small and reviewable.
2. As a CLI user, I want all existing flags and mutually exclusive mode behavior
   to remain compatible after parser construction is moved.
3. As a reviewer, I want the new parser module included in quality and
   reproducibility gates, so the refactor remains covered by CI.

## Task Report

### RED - Missing Parser Module

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_cli_dispatch.py --basetemp .tmp-pytest-p1-1-cli-parser-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_cli_dispatch.py::test_cli_parser_construction_is_split_from_parse_args
AssertionError: assert False
where False = is_file()
where is_file = WindowsPath('F:/My_code/Agent_design_for_vivado/.trae/agent/agent_cli_parser.py').is_file
1 failed, 2 passed in 0.07s
```

### GREEN Implementation

Implementation:

- Added `.trae/agent/agent_cli_parser.py` with parser construction helpers.
- Reduced `.trae/agent/agent_cli.py` from 283 lines to 58 lines.
- Reduced `agent_cli.parse_args()` from 257 lines to 31 lines.
- Added `agent_cli_parser` to the legacy local preload list in `.trae/agent/agent.py`.
- Added the new module to mypy scope and tracked-runtime reproducibility checks.

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_cli_dispatch.py --basetemp .tmp-pytest-p1-1-cli-parser-green -p no:cacheprovider -q
```

Result:

```text
3 passed in 0.03s
```

CLI smoke commands:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; uv run --offline --frozen python -B .trae/agent/agent.py --list-targets
$env:PYTHONPATH='F:\My_code\Agent_design_for_vivado\src'; uv run --offline --frozen python -B -m digital_ic_agent --list-targets
```

Both commands listed the three registered targets:

```text
async-fifo
round-robin-arbiter
sync-fifo
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | CLI parser construction is split into `.trae/agent/agent_cli_parser.py` | `tests/test_p1_1_cli_dispatch.py::test_cli_parser_construction_is_split_from_parse_args` | architecture/unit | PASS | `3 passed in 0.03s` |
| 2 | `agent_cli.parse_args()` stays within the P1-1 100-line function budget | `tests/test_p1_1_cli_dispatch.py::test_cli_parser_construction_is_split_from_parse_args` | architecture/unit | PASS | `parse_args` length is 31 lines in size scan |
| 3 | New parser module is included in mypy quality scope | `tests/test_quality_config.py::test_p1_1_cli_parser_is_in_mypy_scope` | quality/unit | PASS | Included in focused P1-1 run |
| 4 | New parser module is a tracked runtime architecture file | `tests/test_repository_reproducibility.py::test_required_runtime_and_architecture_files_are_tracked` | reproducibility/unit | PASS | Included in focused P1-1 run after staging |
| 5 | Legacy and `src` package CLI entrypoints still list the same built-in targets | CLI smoke commands above | smoke/integration | PASS | Both listed `async-fifo`, `round-robin-arbiter`, and `sync-fifo` |

## Verification

Focused P1-1 command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p1-1-cli-parser-focused -p no:cacheprovider -q
```

Result:

```text
22 passed in 2.20s
```

Quality commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

Results:

```text
All checks passed!
Success: no issues found in 57 source files
```

## Known Gaps

- P1-1 is not complete overall. Large modules still remain, including
  `.trae/agent/agent.py`, async FIFO report/render/runtime modules, project
  overview, coverage closure, and target-specific renderers.
- This slice only completes the CLI parser-construction split after the CLI
  command-dispatch split. Additional P1-1 slices are still required before
  claiming the full module-size acceptance criteria.

