# P1-1 Agent Capabilities Split TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
current P1-1 modularization target and the remaining capability/preflight
responsibilities in `.trae/agent/agent.py`.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want CLI and MCP capability checks to live outside the
   core Agent class, so `DigitalICAgent` stays a compatibility facade.
2. As a runtime user, I want Vivado command resolution and version-banner
   handling to remain compatible after the module split.
3. As a diagnostics user, I want install-guide lookup and preflight behavior to
   remain unchanged.
4. As a refactoring reviewer, I want subprocess and regex based probing logic
   removed from the core Agent method bodies.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_capabilities_split.py --basetemp .tmp-pytest-p1-1-capabilities-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_agent_capabilities_split.py::test_agent_capability_checks_are_split_from_core_agent
AssertionError: assert False
1 failed in 0.08s
```

The failure confirmed that `.trae/agent/agent_capabilities.py` did not exist and
`DigitalICAgent` still owned CLI/MCP capability probing and install-guide logic.

## GREEN Evidence

Focused command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_capabilities_split.py tests/test_agent.py::test_diagnostic_uses_resolved_vivado_command tests/test_agent.py::test_capability_preflight_accepts_vivado_banner_on_nonzero_exit tests/test_architecture_runtime.py::test_diagnostic_reports_required_optional_and_not_applicable tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools --basetemp .tmp-pytest-p1-1-capabilities-green -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent.py .trae/agent/agent_capabilities.py tests/test_p1_1_agent_capabilities_split.py
```

Result:

```text
5 passed in 0.21s
All checks passed!
```

P1-1 focused regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_diagnostic_uses_resolved_vivado_command tests/test_agent.py::test_capability_preflight_accepts_vivado_banner_on_nonzero_exit tests/test_architecture_runtime.py::test_diagnostic_reports_required_optional_and_not_applicable tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools --basetemp .tmp-pytest-p1-1-capabilities-focused -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py; uv run --offline --frozen mypy; uv run --offline --frozen python -m py_compile .trae/agent/agent.py .trae/agent/agent_capabilities.py
```

Result:

```text
37 passed in 3.44s
All checks passed!
Success: no issues found in 60 source files
```

## Implementation Notes

- Added `.trae/agent/agent_capabilities.py`.
- Moved `check_capability`, `run_preflight`, `normalize_command`,
  `check_cli_tool`, `check_mcp_server`, and `get_install_guide` behavior behind
  module-level operations.
- Kept `DigitalICAgent` public methods as compatibility delegates.
- Preserved legacy `agent.subprocess` monkeypatch compatibility by re-exporting
  the capability module's subprocess object from `agent.py`.
- Reduced `.trae/agent/agent.py` from 838 to 804 lines.

## Acceptance Mapping

| Requirement | Evidence |
| --- | --- |
| Capability checks are split from core Agent | `tests/test_p1_1_agent_capabilities_split.py::test_agent_capability_checks_are_split_from_core_agent` |
| Vivado command resolution remains compatible | `tests/test_agent.py::test_diagnostic_uses_resolved_vivado_command` |
| Vivado banner fallback remains compatible | `tests/test_agent.py::test_capability_preflight_accepts_vivado_banner_on_nonzero_exit` |
| Diagnostics and default workflow remain compatible | `tests/test_architecture_runtime.py::test_diagnostic_reports_required_optional_and_not_applicable`; `tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools` |
| P1-1 focused surface remains GREEN | `37 passed in 3.44s`; Ruff and Mypy zero errors |

## Status

This P1-1 slice is complete. The wider P1-1 requirement remains open because
`.trae/agent/agent.py` is still above the preferred 600-line target and several
target/report modules remain oversized.
