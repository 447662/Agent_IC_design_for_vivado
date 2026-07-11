# P1-1 Agent Bootstrap Split TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
current P1-1 modularization target and the large local module bootstrap block in
`.trae/agent/agent.py`.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want the legacy local-module bootstrap list to live
   outside `agent.py`, so the core Agent file is smaller and easier to review.
2. As a package user, I want `src/digital_ic_agent` imports to keep working
   without `sys.path.insert()`.
3. As a compatibility reviewer, I want adapter, handler, and target example
   modules to load through the same file-based mechanism as before.
4. As a P1-1 reviewer, I want the bootstrap module to own the local module,
   adapter, handler, and example module lists.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_bootstrap_split.py --basetemp .tmp-pytest-p1-1-bootstrap-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_agent_bootstrap_split.py::test_agent_local_module_bootstrap_is_split_from_core_agent
FileNotFoundError: ... .trae\agent\agent_bootstrap.py
1 failed in 0.10s
```

The failure confirmed that `.trae/agent/agent_bootstrap.py` did not exist and
the legacy bootstrap lists were still embedded in `agent.py`.

## GREEN Evidence

Focused command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_bootstrap_split.py tests/test_p1_1_agent_document_facades_split.py tests/test_p1_1_package_layout.py tests/test_agent.py::test_runtime_components_live_in_dedicated_module tests/test_agent.py::test_cli_helpers_live_in_dedicated_module tests/test_agent.py::test_p5_9_adapter_modules_own_extracted_agent_methods --basetemp .tmp-pytest-p1-1-bootstrap-green -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent.py .trae/agent/agent_bootstrap.py .trae/agent/agent_document_facades.py tests/test_p1_1_agent_bootstrap_split.py tests/test_p1_1_agent_document_facades_split.py; uv run --offline --frozen python -m py_compile .trae/agent/agent.py .trae/agent/agent_bootstrap.py .trae/agent/agent_document_facades.py
```

Result:

```text
8 passed in 0.25s
All checks passed!
```

P1-1 focused regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_bootstrap_split.py tests/test_p1_1_agent_document_facades_split.py tests/test_p1_1_agent_skill_execution_split.py tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_runtime_components_live_in_dedicated_module tests/test_agent.py::test_cli_helpers_live_in_dedicated_module tests/test_agent.py::test_p5_9_adapter_modules_own_extracted_agent_methods tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools --basetemp .tmp-pytest-p1-1-bootstrap-focused -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_bootstrap_split.py tests/test_p1_1_agent_document_facades_split.py tests/test_p1_1_agent_skill_execution_split.py tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py; uv run --offline --frozen mypy; uv run --offline --frozen python -m py_compile .trae/agent/agent.py .trae/agent/agent_bootstrap.py .trae/agent/agent_document_facades.py
```

Result:

```text
41 passed in 2.50s
All checks passed!
Success: no issues found in 60 source files
```

## Implementation Notes

- Added `.trae/agent/agent_bootstrap.py`.
- Moved local module, adapter, target example, and handler module lists out of
  `.trae/agent/agent.py`.
- Kept file-based loading and avoided `sys.path.insert()`.
- Preserved package import and adapter identity compatibility.
- Reduced `.trae/agent/agent.py` from 727 to 668 lines.

## Acceptance Mapping

| Requirement | Evidence |
| --- | --- |
| Local module bootstrap is split from core Agent | `tests/test_p1_1_agent_bootstrap_split.py::test_agent_local_module_bootstrap_is_split_from_core_agent` |
| `src/digital_ic_agent` imports remain compatible | `tests/test_p1_1_package_layout.py` |
| Legacy module exports remain compatible | `tests/test_agent.py::test_runtime_components_live_in_dedicated_module`; `tests/test_agent.py::test_cli_helpers_live_in_dedicated_module` |
| Adapter identity compatibility remains intact | `tests/test_agent.py::test_p5_9_adapter_modules_own_extracted_agent_methods` |
| P1-1 focused surface remains GREEN | `41 passed in 2.50s`; Ruff and Mypy zero errors |

## Status

This P1-1 slice is complete. The wider P1-1 requirement remains open because
`.trae/agent/agent.py` is still above the preferred 600-line target and several
target/report modules remain oversized.
