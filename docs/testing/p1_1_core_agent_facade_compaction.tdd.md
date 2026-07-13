# P1-1 Core Agent Facade Compaction TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
current P1-1 acceptance criteria and the existing facade split tests around
`DigitalICAgent`.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want `DigitalICAgent` to keep compatibility methods while
   delegating implementation to split modules, so the core agent stays small.
2. As a reviewer, I want facade split tests to assert the current module alias
   boundaries, so refactors are not blocked by stale import-string expectations.
3. As a release owner, I want the P1-1 focused regression, Ruff, Mypy, and
   compile checks to stay green after compaction.

## Task Report

### RED Evidence

The implementation had already moved operation imports to module aliases such
as `import agent_runtime_facades as runtime_facades`, but six structure tests
still required old `from ... import ... as ..._operation` strings.

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_document_facades_split.py tests/test_p1_1_agent_skill_execution_split.py tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py --basetemp .tmp-pytest-p1-1-alias-red -p no:cacheprovider -q
```

Result:

```text
6 failed in 0.12s
```

The failures were the intended RED signal: each test failed on stale import
expectations such as `from agent_runtime_facades import`.

### GREEN Evidence

The structure tests now assert module alias imports and explicit facade calls:

- `import agent_capabilities as capabilities`
- `import agent_document_facades as document_facades`
- `import agent_runtime_facades as runtime_facades`
- `import agent_skill_execution as skill_execution`
- `import agent_skill_listing as skill_listing`
- `import agent_workflow as workflow`

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_document_facades_split.py tests/test_p1_1_agent_skill_execution_split.py tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py --basetemp .tmp-pytest-p1-1-alias-green -p no:cacheprovider -q
```

Result:

```text
6 passed in 0.25s
```

### Core Size Check

`agent.py` was compacted to the P1-1 core threshold:

```powershell
(Get-Content -LiteralPath .trae/agent/agent.py).Count
```

Result:

```text
600
```

After adding P1-2 legacy target compatibility facades, the core facade was
recompacted by moving legacy Sync FIFO / Arbiter method installation into
`agent_legacy_target_facades.install_legacy_target_facades()`.

Command:

```powershell
(Get-Content -LiteralPath .trae/agent/agent.py).Count
```

Result:

```text
595
```

Latest size reconfirmation after P0-3 runner and async FIFO UVM artifact
contract work:

```powershell
(Get-Content -LiteralPath .trae/agent/agent.py).Count; Select-String -Path .trae/agent/agent.py -Pattern '^class DigitalICAgent'
```

Result:

```text
598

.trae\agent\agent.py:157:class DigitalICAgent:
```

### Focused Regression

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_bootstrap_split.py tests/test_p1_1_agent_document_facades_split.py tests/test_p1_1_agent_skill_execution_split.py tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_runtime_components_live_in_dedicated_module tests/test_agent.py::test_cli_helpers_live_in_dedicated_module tests/test_agent.py::test_p5_9_adapter_modules_own_extracted_agent_methods tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools --basetemp .tmp-pytest-p1-1-core-600 -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_*.py tests/test_quality_config.py tests/test_repository_reproducibility.py; uv run --offline --frozen mypy; uv run --offline --frozen python -m py_compile .trae/agent/agent.py
```

Result:

```text
41 passed in 2.54s
All checks passed!
Success: no issues found in 60 source files
```

`py_compile` completed with exit code 0.

Latest focused reconfirmation after the legacy facade installation move:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_bootstrap_split.py tests/test_p1_1_agent_document_facades_split.py tests/test_p1_1_agent_skill_execution_split.py tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_runtime_components_live_in_dedicated_module tests/test_agent.py::test_cli_helpers_live_in_dedicated_module tests/test_agent.py::test_p5_9_adapter_modules_own_extracted_agent_methods tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools tests/test_agent.py::test_p5_2_run_sync_fifo_vivado_sim_creates_project_and_can_skip_gui tests/test_agent.py::test_p5_3_run_round_robin_arbiter_vivado_sim_creates_project_and_can_skip_gui --basetemp .tmp-pytest-p1-1-core-595-reconfirm -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent.py .trae/agent/agent_legacy_target_facades.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_*.py tests/test_quality_config.py tests/test_repository_reproducibility.py
```

Result:

```text
45 passed in 2.72s
All checks passed!
```

Latest focused reconfirmation on 2026-07-12 after P0-3 runner and async FIFO
UVM artifact contract work:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_bootstrap_split.py tests/test_p1_1_agent_document_facades_split.py tests/test_p1_1_agent_skill_execution_split.py tests/test_p1_1_agent_runtime_facades_split.py tests/test_p1_1_agent_capabilities_split.py tests/test_p1_1_agent_workflow_split.py tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_runtime_components_live_in_dedicated_module tests/test_agent.py::test_cli_helpers_live_in_dedicated_module tests/test_agent.py::test_p5_9_adapter_modules_own_extracted_agent_methods tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools tests/test_agent.py::test_p5_2_run_sync_fifo_vivado_sim_creates_project_and_can_skip_gui tests/test_agent.py::test_p5_3_run_round_robin_arbiter_vivado_sim_creates_project_and_can_skip_gui --basetemp .tmp-pytest-p1-1-current-doc -p no:cacheprovider -q
```

Result:

```text
45 passed in 3.39s
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Document facade methods delegate through `agent_document_facades` module alias | `tests/test_p1_1_agent_document_facades_split.py` | structure/unit | PASS | `6 passed in 0.25s` |
| 2 | Skill execution methods delegate through `agent_skill_execution` module alias | `tests/test_p1_1_agent_skill_execution_split.py` | structure/unit | PASS | `6 passed in 0.25s` |
| 3 | Runtime facade methods delegate through `agent_runtime_facades` module alias | `tests/test_p1_1_agent_runtime_facades_split.py` | structure/unit | PASS | `6 passed in 0.25s` |
| 4 | Capability checks delegate through `agent_capabilities` module alias | `tests/test_p1_1_agent_capabilities_split.py` | structure/unit | PASS | `6 passed in 0.25s` |
| 5 | Default workflow delegates through `agent_workflow` module alias | `tests/test_p1_1_agent_workflow_split.py` | structure/unit | PASS | `6 passed in 0.25s` |
| 6 | Skill listing methods delegate through `agent_skill_listing` module alias | `tests/test_p1_1_agent_skill_listing.py` | structure/unit | PASS | `6 passed in 0.25s` |
| 7 | Core `agent.py` stays within the P1-1 size threshold | `(Get-Content -LiteralPath .trae/agent/agent.py).Count` | static check | PASS | `598` |
| 8 | P1-1 focused regression remains green after compaction | focused pytest command above | regression | PASS | `45 passed in 3.39s` |
| 9 | Ruff, Mypy, and Python compile checks remain green | quality command above | quality/typecheck | PASS | Ruff PASS, Mypy PASS, `py_compile` exit code 0 |

## Known Gaps

- This slice preserves the existing compatibility facade shape. It does not
  remove compatibility exports from `agent.py`; later P1-2 typing work can
  reduce `Any` usage and tighten public contracts.
- SynthPilot real MCP validation is intentionally not claimed here because it
  remains blocked by the license device limit recorded in the P0-1 follow-up.
