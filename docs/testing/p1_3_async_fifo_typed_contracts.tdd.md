# P1-3 Async FIFO Typed Contracts TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from current
P1-2/P1-3 typed-contract gaps, the existing async FIFO runtime/report modules,
and the runtime facade boundary tests.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want async FIFO VCD analysis and WCFG summaries to expose
   typed contracts, so downstream reports do not rely on anonymous dictionaries.
2. As a reviewer, I want runtime facade functions to advertise small Protocol
   boundaries, so plugin/facade calls remain thin but less dependent on `Any`.
3. As a release owner, I want the typed contract slice to preserve existing
   async FIFO report/runtime behavior without requiring a live Vivado run.

## Task Report

### RED Evidence

A new P1-3 structure/behavior test was added for the async FIFO typed contract
slice:

- `WaveEventRow`, `WaveSearchResult`, `WaveInfo`, `AsyncFifoVcdAnalysis`, and
  `AsyncFifoRegressionCase` in `agent_async_fifo_runtime.py`
- `CompletedProcessLike` and `AsyncFifoWcfgSummary` in
  `agent_async_fifo_reports.py`
- `ProjectOverviewAgent`, `ArtifactRefreshAgent`, `WaveResolverAgent`, and
  `TargetFlowAgent` Protocols in `agent_runtime_facades.py`
- WCFG parsing behavior for missing, declared-size, and fallback object-count
  cases

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_3_async_fifo_typed_contracts.py --basetemp .tmp-pytest-p1-3-async-fifo-types-red -p no:cacheprovider -q
```

Result:

```text
FFF...                                                                   [100%]
FAILED tests/test_p1_3_async_fifo_typed_contracts.py::test_async_fifo_runtime_exposes_typed_analysis_contracts
FAILED tests/test_p1_3_async_fifo_typed_contracts.py::test_async_fifo_report_exposes_typed_wcfg_contract
FAILED tests/test_p1_3_async_fifo_typed_contracts.py::test_runtime_facades_expose_protocol_boundaries
3 failed, 3 passed in 0.33s
```

The failures were the intended RED signal: the typed contract names and Protocol
facade boundaries did not exist yet, while the WCFG behavior tests already
captured the current parsing behavior.

### GREEN Evidence

The implementation now adds typed contracts and narrows key signatures without
changing async FIFO report text or Vivado/runtime behavior:

- `resolve_async_fifo_vcd_path(...) -> Path`
- `collect_async_fifo_vcd_analysis(...) -> AsyncFifoVcdAnalysis`
- `collect_async_fifo_vcd_analysis_with_rwave_batch(...) -> AsyncFifoVcdAnalysis`
- `async_fifo_required_wcfg_objects() -> list[str]`
- `async_fifo_regression_cases() -> list[AsyncFifoRegressionCase]`
- `parse_async_fifo_wcfg_summary(...) -> AsyncFifoWcfgSummary`
- `write_async_fifo_sim_report(...) -> Path`
- runtime facade functions now use narrow Protocol boundaries where possible

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_3_async_fifo_typed_contracts.py --basetemp .tmp-pytest-p1-3-async-fifo-types-green -p no:cacheprovider -q
```

Result:

```text
6 passed in 0.28s
```

### Regression Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/agent_async_fifo_runtime.py .trae/agent/agent_async_fifo_reports.py .trae/agent/agent_runtime_facades.py tests/test_p1_3_async_fifo_typed_contracts.py; uv run --offline --frozen mypy .trae/agent/agent_async_fifo_runtime.py .trae/agent/agent_async_fifo_reports.py .trae/agent/agent_runtime_facades.py; uv run --offline --frozen pytest tests/test_p1_3_async_fifo_typed_contracts.py tests/test_agent.py::test_collect_async_fifo_vcd_analysis_falls_back_from_rwave tests/test_agent.py::test_collect_async_fifo_vcd_analysis_rwave_backend_reraises tests/test_agent.py::test_run_async_fifo_uvm_smoke_writes_report_and_can_skip_gui tests/test_agent.py::test_run_async_fifo_uvm_coverage_writes_report tests/test_p1_1_agent_runtime_facades_split.py --basetemp .tmp-pytest-p1-3-async-fifo-types-regression-2 -p no:cacheprovider -q
```

Result:

```text
All checks passed!
Success: no issues found in 3 source files
11 passed in 0.86s
```

### Runtime Facade Target Flow Boundary Slice Evidence

The next P1-2/P1-3 slice tightened the runtime facade target-flow boundary:

- `TargetMetadata` is now exported as the `TargetFlowAgent.get_target(...)`
  return contract.
- target-flow facade helpers that return flow success now advertise `bool`
  instead of `Any`.
- `normalize_rtl_target(...) -> str` now relies on `TargetMetadata["name"]`
  instead of a broad cast.

RED command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_3_async_fifo_typed_contracts.py::test_runtime_facades_expose_protocol_boundaries --basetemp .tmp-pytest-p1-3-runtime-facades-red -p no:cacheprovider -q
```

RED result:

```text
1 failed in 0.12s
```

The intended failure showed `agent_runtime_facades.TargetMetadata` did not yet
exist.

GREEN and quality commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_3_async_fifo_typed_contracts.py::test_runtime_facades_expose_protocol_boundaries --basetemp .tmp-pytest-p1-3-runtime-facades-green2 -p no:cacheprovider -q
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/agent_runtime_facades.py tests/test_p1_3_async_fifo_typed_contracts.py
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

GREEN and quality results:

```text
1 passed in 2.08s
All checks passed!
Success: no issues found in 61 source files
```

## Type Debt Snapshot

Current focused `Any` counts after this slice:

| File | `Any` count | Lines |
|---|---:|---:|
| `.trae/agent/agent_async_fifo_runtime.py` | 62 | 716 |
| `.trae/agent/agent_async_fifo_reports.py` | 87 | 1910 |
| `.trae/agent/agent_runtime_facades.py` | 31 | 366 |

This is intentionally a narrow typed-boundary slice. It does not claim to
complete the full P1-2 target of reducing global `Any` usage by at least 80%.

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Async FIFO VCD analysis exposes named `TypedDict` contracts | `tests/test_p1_3_async_fifo_typed_contracts.py::test_async_fifo_runtime_exposes_typed_analysis_contracts` | structure/unit | PASS | `6 passed in 0.28s` |
| 2 | Async FIFO WCFG summaries expose a typed report contract | `tests/test_p1_3_async_fifo_typed_contracts.py::test_async_fifo_report_exposes_typed_wcfg_contract` | structure/unit | PASS | `6 passed in 0.28s` |
| 3 | Runtime facade agent parameters expose narrow Protocol boundaries | `tests/test_p1_3_async_fifo_typed_contracts.py::test_runtime_facades_expose_protocol_boundaries` | structure/unit | PASS | `6 passed in 0.28s` |
| 4 | WCFG parsing handles missing files, declared object size, and fallback signal counting | WCFG behavior tests in `tests/test_p1_3_async_fifo_typed_contracts.py` | unit | PASS | `6 passed in 0.28s` |
| 5 | Existing async FIFO VCD fallback and UVM report behavior remains compatible | selected `tests/test_agent.py` async FIFO tests | regression | PASS | included in `11 passed in 0.86s` |
| 6 | Focused files pass Ruff and Mypy | quality command above | quality/typecheck | PASS | Ruff PASS, Mypy PASS |
| 7 | Runtime facade target metadata and target-flow helpers expose concrete return contracts | `tests/test_p1_3_async_fifo_typed_contracts.py::test_runtime_facades_expose_protocol_boundaries` | structure/unit | PASS | `1 passed in 2.08s` |
| 8 | Runtime facade target-flow boundary tightening remains accepted by Ruff and project Mypy scope | quality commands above | quality/typecheck | PASS | Ruff PASS, Mypy PASS |

## Known Gaps

- This slice keeps dynamic analyzer and report payloads flexible with
  `TypedDict(total=False)` and local casts. A stricter schema should wait until
  the waveform analyzer payloads are stable.
- `agent.py`, `project_overview.py`, and broader report modules still carry the
  largest `Any` debt and should be handled as later focused slices, not folded
  into this async FIFO boundary change.
- This slice does not add live Vivado tests; it relies on fake-agent and
  temporary-file tests because P0-3 already covers the real Vivado gate.
