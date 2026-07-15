# P1-1 Agent Target Flow Split TDD Evidence

## Source

- Task: P1-1 modular refactor, target registry / handler / flow orchestration split.
- Existing upgrade planning files were not read during this slice.
- SynthPilot follow-up remains blocked by license device limit and is recorded separately in `docs/testing/p0_1_synthpilot_follow_up.md` and `docs/testing/evidence/synthpilot_tools_list.json`.

## User Journey

As a maintainer, I want target registry lookup, handler construction, handler validation, target listing, and target flow execution moved out of `DigitalICAgent`, so that the core agent stays smaller while target flow behavior and artifact manifests remain compatible.

## RED Evidence

| Guarantee | Command | Result | Evidence |
|---|---|---:|---|
| Target flow orchestration must live in `.trae/agent/target_flows.py`; `DigitalICAgent` must keep only short compatibility wrappers. | `uv run --offline --frozen pytest tests/test_p1_1_agent_target_flow.py --basetemp .tmp-pytest-p1-1-target-flow-red -p no:cacheprovider -q` | FAIL | RED reproducer added in commit `cf44ac7f9`; failure was caused by missing `run_target_flow as run_target_flow_operation` import and inline registry / flow strings still present in `agent.py`. |

## GREEN Evidence

| Guarantee | Command | Result | Evidence |
|---|---|---:|---|
| Core agent delegates target registry, target listing, handler build, handler validation, and target flow execution to `.trae/agent/target_flows.py`. | `uv run --offline --frozen pytest tests/test_p1_1_agent_target_flow.py --basetemp .tmp-pytest-p1-1-target-flow-green -p no:cacheprovider -q` | PASS | `1 passed in 0.04s` |
| Target flow behavior still records failure manifests, stale artifacts, top-level overview refreshes, target registry validation, and preflight blocking. | `uv run --offline --frozen pytest tests/test_p1_1_agent_target_flow.py tests/test_agent.py::test_target_flow_builder_lives_in_dedicated_module tests/test_agent.py::test_p5_8_failed_target_flow_records_failure tests/test_agent.py::test_failed_target_flow_marks_preexisting_artifact_stale tests/test_agent.py::test_p5_target_registry_rejects_invalid_target_config tests/test_agent.py::test_p5_11_target_flow_refreshes_top_level_overview tests/test_architecture_runtime.py::test_target_flow_preflight_blocks_before_handler_execution --basetemp .tmp-pytest-p1-1-target-flow-behavior -p no:cacheprovider -q` | PASS | `7 passed in 0.82s` |
| P1-1 focused architecture gates, quality config, and repository reproducibility checks remain green. | `uv run --offline --frozen pytest tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p1-1-target-flow-focused -p no:cacheprovider -q` | PASS | `30 passed in 2.65s` |
| Python lint remains clean for agent, src package, and focused tests. | `uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py` | PASS | `All checks passed!` |
| Mypy remains green after moving target flow orchestration into `target_flows.py`. | `uv run --offline --frozen mypy` | PASS | `Success: no issues found in 60 source files` |

## Implementation Summary

- Moved target registry wrappers, target listing output, handler construction side effects, handler validation, and target flow execution into `.trae/agent/target_flows.py`.
- Updated `DigitalICAgent` target methods to remain short compatibility wrappers.
- Preserved artifact manifest recording, stale artifact detection, preflight blocking, failure propagation, and target plugin registration behavior.

## Known Gaps

- P1-1 modular refactor is still incomplete. `agent.py` remains above the final target and other large modules still need follow-up slices.
- Remaining oversized or high-complexity modules include async FIFO render/report/runtime, target plugins, coverage closure, project overview, wave visibility, and XCRG coverage.
- SynthPilot verification remains blocked by license device limit; this slice intentionally ignored SynthPilot per user direction and preserved the issue for follow-up.
