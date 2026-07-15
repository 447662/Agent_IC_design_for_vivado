# P1-1 Agent Runtime Facades Split TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
current P1-1 modularization target and the remaining waveform, simulation, RTL,
and artifact facade methods in `.trae/agent/agent.py`.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want runtime facade methods to live outside the core Agent
   class, so `DigitalICAgent` stays a narrow compatibility facade.
2. As a waveform user, I want VCD/waveform analysis behavior to remain
   compatible after the facade split.
3. As a simulation user, I want smoke simulation and Vivado smoke commands to
   keep their existing behavior and public Agent methods.
4. As a target-flow user, I want RTL, UVM, coverage, regression, and wave-open
   public methods to keep delegating to the unified target flow system.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_runtime_facades_split.py --basetemp .tmp-pytest-p1-1-runtime-facades-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_agent_runtime_facades_split.py::test_agent_runtime_facades_are_split_from_core_agent
AssertionError: assert False
1 failed in 0.08s
```

The failure confirmed that `.trae/agent/agent_runtime_facades.py` did not exist
and `DigitalICAgent` still owned runtime facade wiring directly.

## GREEN Evidence

Focused command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_target_flow.py tests/test_agent.py::test_diagnostic_uses_resolved_vivado_command tests/test_agent.py::test_capability_preflight_accepts_vivado_banner_on_nonzero_exit --basetemp .tmp-pytest-p1-1-runtime-facades-green -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent.py .trae/agent/agent_runtime_facades.py tests/test_p1_1_agent_runtime_facades_split.py
```

Result:

```text
6 passed in 0.23s
All checks passed!
```

P1-1 focused regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_diagnostic_uses_resolved_vivado_command tests/test_agent.py::test_capability_preflight_accepts_vivado_banner_on_nonzero_exit tests/test_architecture_runtime.py::test_diagnostic_reports_required_optional_and_not_applicable tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools --basetemp .tmp-pytest-p1-1-runtime-facades-focused -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py; uv run --offline --frozen mypy; uv run --offline --frozen python -m py_compile .trae/agent/agent.py .trae/agent/agent_runtime_facades.py
```

Result:

```text
38 passed in 2.57s
All checks passed!
Success: no issues found in 60 source files
```

## Implementation Notes

- Added `.trae/agent/agent_runtime_facades.py`.
- Moved artifact refresh, waveform resolution, waveform analysis, smoke
  simulation, RTL project checking, and target runtime facade wiring into
  module-level operations.
- Kept `DigitalICAgent` public methods as compatibility delegates.
- Preserved existing P1-1 waveform and sim-smoke split assertions.
- Reduced `.trae/agent/agent.py` from 804 to 790 lines.

## Acceptance Mapping

| Requirement | Evidence |
| --- | --- |
| Runtime facade wiring is split from core Agent | `tests/test_p1_1_agent_runtime_facades_split.py::test_agent_runtime_facades_are_split_from_core_agent` |
| Existing waveform split remains compatible | `tests/test_p1_1_agent_waveform_analysis.py` |
| Existing sim-smoke split remains compatible | `tests/test_p1_1_agent_sim_smoke.py` |
| Target-flow facade behavior remains compatible | `tests/test_p1_1_agent_target_flow.py` |
| P1-1 focused surface remains GREEN | `38 passed in 2.57s`; Ruff and Mypy zero errors |

## Status

This P1-1 slice is complete. The wider P1-1 requirement remains open because
`.trae/agent/agent.py` is still above the preferred 600-line target and several
target/report modules remain oversized.
