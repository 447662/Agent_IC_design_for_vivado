# P1-1 Agent Diagnostics Split TDD Evidence

## Source

No upgrade plan file was read for this work. This P1-1 slice was derived from
the current core-agent module shape and the active P1-1 acceptance criteria
requiring CLI parsing, command dispatch, Agent core, and supporting concerns to
be split into focused modules.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want diagnostic rendering and capability diagnostic logic
   split out of `DigitalICAgent`, so the core Agent class keeps shrinking toward
   the P1-1 module-size target.
2. As a CLI user, I want `--diagnostic` output and flow-aware required/optional
   behavior to remain compatible after the split.
3. As a reviewer, I want the diagnostics module included in quality and
   reproducibility gates, so the refactor cannot drift out of CI coverage.

## Task Report

### RED - Missing Diagnostics Module

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_diagnostics.py --basetemp .tmp-pytest-p1-1-diagnostics-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_agent_diagnostics.py::test_agent_diagnostics_are_split_from_core_agent
AssertionError: assert False
where False = is_file()
where is_file = WindowsPath('F:/My_code/Agent_design_for_vivado/.trae/agent/agent_diagnostics.py').is_file
1 failed in 0.07s
```

### GREEN Implementation

Implementation:

- Added `.trae/agent/agent_diagnostics.py`.
- Moved diagnostic status text, capability diagnostic classification, CLI/MCP
  diagnostic rendering, skill-file diagnostic rendering, and final diagnostic
  result aggregation out of `DigitalICAgent`.
- Kept `DigitalICAgent.run_diagnostic()` as a compatibility wrapper delegating
  to `run_agent_diagnostic()`.
- Added `agent_diagnostics` to the legacy local preload list in
  `.trae/agent/agent.py`.
- Added the new module to mypy scope and tracked-runtime reproducibility checks.

Focused GREEN commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_diagnostics.py --basetemp .tmp-pytest-p1-1-diagnostics-green-7 -p no:cacheprovider -q
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py::test_diagnostic_reports_required_optional_and_not_applicable tests/test_agent.py::test_cli_diagnostic_runs_as_independent_mode --basetemp .tmp-pytest-p1-1-diagnostics-behavior-7 -p no:cacheprovider -q
```

Results:

```text
1 passed in 0.03s
2 passed in 0.86s
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Agent diagnostics logic is split into `.trae/agent/agent_diagnostics.py` | `tests/test_p1_1_agent_diagnostics.py::test_agent_diagnostics_are_split_from_core_agent` | architecture/unit | PASS | `1 passed in 0.03s` |
| 2 | `DigitalICAgent` no longer owns `_diagnostic_status_text()` or `_capability_diagnostic()` methods | `tests/test_p1_1_agent_diagnostics.py::test_agent_diagnostics_are_split_from_core_agent` | architecture/unit | PASS | AST method check passes |
| 3 | Flow-aware diagnostics still distinguish not-applicable, required, and optional capabilities | `tests/test_architecture_runtime.py::test_diagnostic_reports_required_optional_and_not_applicable` | behavior/unit | PASS | Included in focused diagnostic behavior run |
| 4 | `--diagnostic` remains an independent CLI mode | `tests/test_agent.py::test_cli_diagnostic_runs_as_independent_mode` | CLI/integration | PASS | Included in focused diagnostic behavior run |
| 5 | New diagnostics module is included in mypy quality scope | `tests/test_quality_config.py::test_p1_1_agent_diagnostics_is_in_mypy_scope` | quality/unit | PASS | Included in focused P1-1 run |
| 6 | New diagnostics module is a tracked runtime architecture file | `tests/test_repository_reproducibility.py::test_required_runtime_and_architecture_files_are_tracked` | reproducibility/unit | PASS | Included in focused P1-1 run after staging |

## Verification

Focused P1-1 command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_architecture_runtime.py::test_diagnostic_reports_required_optional_and_not_applicable tests/test_agent.py::test_cli_diagnostic_runs_as_independent_mode --basetemp .tmp-pytest-p1-1-diagnostics-focused -p no:cacheprovider -q
```

Result:

```text
26 passed in 2.84s
```

Quality commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

Results:

```text
All checks passed!
Success: no issues found in 58 source files
```

## Known Gaps

- P1-1 is not complete overall. `.trae/agent/agent.py` is smaller after this
  slice but still exceeds the target module-size budget.
- Larger target/report modules remain above the P1-1 size target, including
  async FIFO report/render/runtime modules, project overview, coverage closure,
  and target-specific renderers.

