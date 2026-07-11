# P1-1 Agent Workflow Split TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
current P1-1 modularization target and the remaining default workflow execution
logic in `.trae/agent/agent.py`.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want default workflow execution to live outside the core
   Agent class, so `DigitalICAgent` can remain a compatibility facade.
2. As a CLI user, I want the default `--no-tool-check` workflow behavior to stay
   compatible after the module split.
3. As a runtime reviewer, I want execution plan creation and execution engine
   calls to be localized in a workflow module rather than embedded in
   `agent.py`.
4. As a future observability implementer, I want the direct workflow output
   surface separated from core Agent state to prepare for P1-3 structured
   logging and CLI rendering.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_workflow_split.py --basetemp .tmp-pytest-p1-1-workflow-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_agent_workflow_split.py::test_agent_default_workflow_is_split_from_core_agent
AssertionError: assert False
1 failed in 0.10s
```

The failure confirmed that `.trae/agent/agent_workflow.py` did not exist and
`DigitalICAgent.execute_workflow()` still owned request construction, execution
engine dispatch, and direct workflow output.

## GREEN Evidence

Focused command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_workflow_split.py tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools tests/test_architecture_runtime.py::test_default_document_workflow_records_real_agent_run tests/test_architecture_runtime.py::test_workflow_rejects_empty_skill_selection tests/test_architecture_runtime.py::test_workflow_rejects_partial_result_from_custom_executor tests/test_agent.py::test_cli_no_tool_check_generates_design_spec_but_fails_without_rtl_execution --basetemp .tmp-pytest-p1-1-workflow-green -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent.py .trae/agent/agent_workflow.py tests/test_p1_1_agent_workflow_split.py
```

Result:

```text
6 passed in 0.63s
All checks passed!
```

P1-1 focused regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_cli_list_skills_succeeds tests/test_agent.py::test_cli_no_tool_check_generates_design_spec_but_fails_without_rtl_execution tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools tests/test_architecture_runtime.py::test_default_document_workflow_records_real_agent_run tests/test_architecture_runtime.py::test_workflow_rejects_empty_skill_selection tests/test_architecture_runtime.py::test_workflow_rejects_partial_result_from_custom_executor --basetemp .tmp-pytest-p1-1-workflow-focused -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py; uv run --offline --frozen mypy; uv run --offline --frozen python -m py_compile .trae/agent/agent.py .trae/agent/agent_workflow.py
```

Result:

```text
38 passed in 2.55s
All checks passed!
Success: no issues found in 60 source files
```

## Implementation Notes

- Added `.trae/agent/agent_workflow.py`.
- Moved default workflow request construction, preflight gating, execution
  engine dispatch, and result display into `execute_workflow()`.
- Kept `DigitalICAgent.execute_workflow()` as a compatibility delegate.
- Preserved default workflow behavior and failure semantics.
- Reduced `.trae/agent/agent.py` from 894 to 838 lines.

## Acceptance Mapping

| Requirement | Evidence |
| --- | --- |
| Default workflow responsibility is split from core Agent | `tests/test_p1_1_agent_workflow_split.py::test_agent_default_workflow_is_split_from_core_agent` |
| Existing no-tool-check CLI workflow remains compatible | `tests/test_agent.py::test_cli_no_tool_check_generates_design_spec_but_fails_without_rtl_execution` |
| Real AgentRun recording behavior remains intact | `tests/test_architecture_runtime.py::test_default_document_workflow_records_real_agent_run` |
| Partial or invalid workflow results still fail | `tests/test_architecture_runtime.py::test_workflow_rejects_empty_skill_selection`; `tests/test_architecture_runtime.py::test_workflow_rejects_partial_result_from_custom_executor` |
| P1-1 focused surface remains GREEN | `38 passed in 2.55s`; Ruff and Mypy zero errors |

## Status

This P1-1 slice is complete. The wider P1-1 requirement remains open because
`.trae/agent/agent.py` is still above the preferred 600-line target and several
target/report modules remain oversized.
