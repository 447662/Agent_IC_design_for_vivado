# P1-1 Agent Sim Smoke Split TDD Evidence

## Source

- Task: P1-1 modular refactor, sim smoke flow split.
- Existing upgrade planning files were not read during this slice.
- SynthPilot follow-up remains blocked by license device limit and is recorded separately in `docs/testing/p0_1_synthpilot_follow_up.md` and `docs/testing/evidence/synthpilot_tools_list.json`.

## User Journey

As a maintainer, I want the built-in Verilog/Vivado/Icarus simulation smoke flows split out of `DigitalICAgent`, so that the core agent stays smaller while preserving existing smoke-loop and simulator behavior.

## RED Evidence

| Guarantee | Command | Result | Evidence |
|---|---|---:|---|
| Sim smoke flow logic must live outside `.trae/agent/agent.py`; wrapper methods in `DigitalICAgent` must stay short. | `uv run --offline --frozen pytest tests/test_p1_1_agent_sim_smoke.py --basetemp .tmp-pytest-p1-1-sim-smoke-red -p no:cacheprovider -q` | FAIL | RED reproducer added in commit `5649a0ab2`; failure was caused by missing `.trae/agent/agent_sim_smoke.py` and long inline methods/string literals still present in `agent.py`. |

## GREEN Evidence

| Guarantee | Command | Result | Evidence |
|---|---|---:|---|
| Core agent delegates sim smoke helpers to `.trae/agent/agent_sim_smoke.py`; large RTL/VCD/Tcl literals no longer live in `agent.py`. | `uv run --offline --frozen pytest tests/test_p1_1_agent_sim_smoke.py --basetemp .tmp-pytest-p1-1-sim-smoke-green -p no:cacheprovider -q` | PASS | `1 passed in 0.03s` |
| Smoke-loop, simulator detection, Icarus, Vivado, wave GUI, and generated timescale behavior remain compatible. | `uv run --offline --frozen pytest tests/test_agent.py::test_cli_smoke_loop_generates_and_analyzes_vcd tests/test_agent.py::test_detect_simulator_returns_none_when_tools_missing tests/test_agent.py::test_detect_simulator_prefers_vivado tests/test_agent.py::test_run_sim_smoke_reports_missing_simulator tests/test_agent.py::test_run_sim_smoke_uses_icarus_and_analyzes_vcd tests/test_agent.py::test_run_sim_smoke_uses_vivado_and_analyzes_vcd tests/test_agent.py::test_run_vivado_sim_smoke_can_skip_wave_gui tests/test_agent.py::test_open_vivado_wave_gui_uses_wdb_database tests/test_agent.py::test_sim_smoke_rtl_and_testbench_use_same_timescale --basetemp .tmp-pytest-p1-1-sim-smoke-behavior -p no:cacheprovider -q` | PASS | `9 passed in 1.91s` |
| P1-1 focused architecture gates, quality config, and repository reproducibility checks pass with the new tracked module. | `uv run --offline --frozen pytest tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p1-1-sim-smoke-focused -p no:cacheprovider -q` | PASS | `28 passed in 2.85s` |
| Python lint remains clean for agent, src package, and focused tests. | `uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py` | PASS | `All checks passed!` |
| Mypy covers the new sim smoke module and the tracked source set. | `uv run --offline --frozen mypy` | PASS | `Success: no issues found in 60 source files` |

## Implementation Summary

- Added `.trae/agent/agent_sim_smoke.py` for built-in VCD smoke loop, simulator detection, Icarus smoke, Vivado smoke, wave GUI launch, and TclStore bootstrap rendering.
- Updated `.trae/agent/agent.py` to preload/import `agent_sim_smoke` and keep `DigitalICAgent` sim smoke methods as short compatibility wrappers.
- Adjusted local module preload ordering so repeated isolated imports keep split modules available without reintroducing global `sys.path.insert()`.
- Added `.trae/agent/agent_sim_smoke.py` to mypy scope and repository reproducibility tracking.

## Known Gaps

- P1-1 modular refactor is not complete. `agent.py` is smaller after this slice but still above the final target.
- Remaining oversized or high-complexity modules still need later P1-1 slices, including async FIFO render/report/runtime, target plugins, coverage closure, project overview, wave visibility, and XCRG coverage.
- SynthPilot verification remains blocked by license device limit; this task intentionally ignored SynthPilot per user direction and preserved the issue for follow-up.
