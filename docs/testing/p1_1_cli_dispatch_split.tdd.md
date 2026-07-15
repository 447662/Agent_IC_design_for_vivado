# P1-1 CLI Dispatch Split TDD Evidence

## Source

No upgrade plan file was read for this work. This P1-1 slice was derived from
the current code shape, the active P1-1 acceptance criteria, and the module-size
scan of the existing runtime.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want CLI parsing and CLI command dispatch separated, so
   the entrypoint stays small and the dispatch logic can be refactored safely.
2. As a CLI user, I want existing legacy and `src/digital_ic_agent` entrypoints
   to keep the same arguments and behavior after the split.
3. As a reviewer, I want the new dispatch module included in quality and
   reproducibility gates, so the refactor cannot silently drift out of CI scope.
4. As a maintainer, I want new CLI dispatch functions to stay below the P1-1
   100-line function budget, so the split is real rather than just moving a
   long function to another file.

## Task Report

### RED 1 - Missing Dispatch Module

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_cli_dispatch.py --basetemp .tmp-pytest-p1-1-cli-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_cli_dispatch.py::test_cli_command_dispatch_is_split_from_entrypoint
AssertionError: assert False
where False = is_file()
where is_file = WindowsPath('F:/My_code/Agent_design_for_vivado/.trae/agent/agent_cli_dispatch.py').is_file
1 failed in 0.06s
```

### RED 2 - Oversized Dispatch Function

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_cli_dispatch.py --basetemp .tmp-pytest-p1-1-cli-size-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_cli_dispatch.py::test_cli_dispatch_functions_stay_within_p1_1_size_budget
AssertionError: assert not ['agent_cli_dispatch.py:dispatch_cli_command lines=335']
1 failed, 1 passed in 0.08s
```

### GREEN Implementation

Implementation:

- Added `.trae/agent/agent_cli_dispatch.py`.
- Reduced `.trae/agent/agent_entrypoint.py` to parse arguments, create the
  agent, and delegate to `dispatch_cli_command()`.
- Split CLI command dispatch into category handlers for listing/scaffolding,
  reports, smoke/generation, RTL/UVM flows, target analysis, waveform analysis,
  and the default natural-language workflow path.
- Added `agent_cli_dispatch` to the legacy local preload list in
  `.trae/agent/agent.py`.
- Added the new module to mypy scope and tracked-runtime reproducibility checks.

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_cli_dispatch.py --basetemp .tmp-pytest-p1-1-cli-dispatch-green -p no:cacheprovider -q
```

Result:

```text
2 passed in 0.03s
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
| 1 | CLI command dispatch is split from the entrypoint into `.trae/agent/agent_cli_dispatch.py` | `tests/test_p1_1_cli_dispatch.py::test_cli_command_dispatch_is_split_from_entrypoint` | architecture/unit | PASS | `2 passed in 0.03s` |
| 2 | `agent_entrypoint.run_cli()` stays within the P1-1 100-line function budget | `tests/test_p1_1_cli_dispatch.py::test_cli_command_dispatch_is_split_from_entrypoint` | architecture/unit | PASS | `run_cli` length is 12 lines in size scan |
| 3 | CLI dispatch helpers stay within the P1-1 100-line function budget | `tests/test_p1_1_cli_dispatch.py::test_cli_dispatch_functions_stay_within_p1_1_size_budget` | architecture/unit | PASS | No oversized functions reported for `agent_cli_dispatch.py` |
| 4 | New dispatch module is included in mypy quality scope | `tests/test_quality_config.py::test_p1_1_cli_dispatch_is_in_mypy_scope` | quality/unit | PASS | Included in focused P1-1 run |
| 5 | New dispatch module is a tracked runtime architecture file | `tests/test_repository_reproducibility.py::test_required_runtime_and_architecture_files_are_tracked` | reproducibility/unit | PASS | Included in focused P1-1 run after staging |
| 6 | Legacy and `src` package CLI entrypoints still list the same built-in targets | CLI smoke commands above | smoke/integration | PASS | Both listed `async-fifo`, `round-robin-arbiter`, and `sync-fifo` |

## Verification

Focused P1-1 command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p1-1-cli-final -p no:cacheprovider -q
```

Result:

```text
20 passed in 1.99s
```

Quality commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

Results:

```text
All checks passed!
Success: no issues found in 56 source files
```

## Known Gaps

- P1-1 is not complete overall. The latest module scan still shows large
  modules such as `.trae/agent/agent.py`, async FIFO report/render/runtime
  modules, project overview, coverage closure, and target-specific renderers.
- This slice only completes the CLI command-dispatch split. Additional P1-1
  slices are still required before claiming the full module-size acceptance
  criteria.

