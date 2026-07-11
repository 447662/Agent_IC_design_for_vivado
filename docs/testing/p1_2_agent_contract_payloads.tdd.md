# P1-2 Agent Contract Payloads TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
P1-2 requirement to replace generic dictionaries and `Any` with typed contracts,
continuing into the core Agent execution contract after the config and artifact
manifest typed slices.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want Agent request, tool call, and tool result payloads to
   use a JSON-like typed contract, so execution metadata does not depend on
   `Mapping[str, Any]`.
2. As a reviewer, I want the provider and skill-tool paths to validate payload
   shapes before using them, so invalid `selected_skills` values fail clearly.
3. As a release owner, I want existing Agent execution behavior to remain green
   while typed payload contracts are introduced incrementally.

## Task Report

### RED Evidence

A new structure test was added to require JSON-like payload type aliases on the
core Agent contracts.

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_agent_contracts_typed_payloads.py --basetemp .tmp-pytest-p1-2-contract-payloads-red -p no:cacheprovider -q
```

Result:

```text
1 failed in 0.10s
```

The failure was the intended RED signal: `agent_contracts` did not yet expose
`JsonScalar`, `JsonValue`, `JsonObject`, or `PayloadMapping`.

### GREEN Evidence

`agent_contracts.py` now exports:

- `JsonScalar`
- `JsonObject`
- `JsonValue`
- `PayloadMapping`

`AgentRequest.context`, `ToolCall.arguments`, and `ToolResult.metadata` now use
`PayloadMapping`. `ConfiguredAgentProvider` now rejects non-string
`selected_skills` entries, and `SkillExecutionTool` records diagnostics as a
tuple to satisfy the JSON-like immutable payload contract.

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_agent_contracts_typed_payloads.py --basetemp .tmp-pytest-p1-2-contract-payloads-green-5 -p no:cacheprovider -q; uv run --offline --frozen mypy .trae/agent/agent_contracts.py .trae/agent/agent_provider.py .trae/agent/agent_execution.py .trae/agent/agent_skill_tool.py
```

Result:

```text
1 passed in 0.08s
Success: no issues found in 4 source files
```

### Regression Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_agent_contracts_typed_payloads.py tests/test_agent_execution.py tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools tests/test_architecture_runtime.py::test_default_document_workflow_records_real_agent_run tests/test_architecture_runtime.py::test_workflow_rejects_empty_skill_selection tests/test_architecture_runtime.py::test_default_rtl_and_verification_skills_do_not_report_success tests/test_architecture_runtime.py::test_workflow_rejects_partial_result_from_custom_executor --basetemp .tmp-pytest-p1-2-contract-payloads-regression -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent_contracts.py .trae/agent/agent_provider.py .trae/agent/agent_execution.py .trae/agent/agent_skill_tool.py tests/test_p1_2_agent_contracts_typed_payloads.py; uv run --offline --frozen mypy
```

Result:

```text
26 passed in 1.65s
All checks passed!
Success: no issues found in 60 source files
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Agent contract payload aliases expose JSON-like scalar, tuple, and mapping branches | `tests/test_p1_2_agent_contracts_typed_payloads.py` | structure/unit | PASS | `1 passed in 0.08s` |
| 2 | `AgentRequest.context` uses `PayloadMapping` semantics | `tests/test_p1_2_agent_contracts_typed_payloads.py` | structure/unit | PASS | payload mapping asserted |
| 3 | `ToolCall.arguments` uses `PayloadMapping` semantics | `tests/test_p1_2_agent_contracts_typed_payloads.py` | structure/unit | PASS | payload mapping asserted |
| 4 | `ToolResult.metadata` uses `PayloadMapping` semantics | `tests/test_p1_2_agent_contracts_typed_payloads.py` | structure/unit | PASS | payload mapping asserted |
| 5 | Existing Agent execution and workflow behavior remains compatible | selected Agent execution and workflow tests | regression | PASS | `26 passed in 1.65s` |
| 6 | Core execution contracts stay covered by Ruff and Mypy | quality command above | quality/typecheck | PASS | Ruff PASS, Mypy PASS |

## Known Gaps

- This is the third P1-2 typed slice. It does not yet satisfy the full P1-2
  acceptance criteria of reducing `Any` by at least 80%, raising coverage to
  85%, or enabling the full Ruff `I/B/UP/SIM/C90` rule set.
- Remaining P1-2 work should continue through plugin boundary protocols,
  runtime facade signatures, and broader artifact internals before tightening
  global gates.
