# P0-1 Agent Execution Loop TDD Evidence

## Scope

P0-1 establishes a real Agent execution loop with typed requests, typed plans,
tool-call execution, result validation, artifact evidence, deterministic offline
provider support, and natural-language skill-routing evals.

This report records current evidence only. It does not claim P0-1 is complete,
because the real SynthPilot MCP server exits before `initialize` when no
`license_key` is configured.

## User Journeys

1. As a user, I can submit a natural-language digital-IC task and receive a
   code-constrained execution plan instead of an unverified success statement.
2. As a developer, I can run deterministic offline provider tests without
   external model access.
3. As a reviewer, I can verify every successful Agent run against real
   `ToolResult` objects, return codes, and non-empty artifact paths.
4. As a maintainer, I can measure skill-selection behavior against a
   versioned natural-language eval suite.
5. As an integrator, I can attempt a real SynthPilot MCP stdio connection and
   preserve the exact failure or success evidence.

## RED Evidence

| Item | Command | Result | Evidence |
|---|---|---:|---|
| Routing eval suite before fix | `uv run --offline --frozen pytest -q tests/test_agent_evaluation.py --basetemp .tmp-pytest-p0-1-eval-red -p no:cacheprovider` | FAIL | 40/60 correct, accuracy 66.67%, threshold 95% |

The RED checkpoint was committed as:

```text
8e379474 test: add RED routing evals for agent skills
```

## GREEN Evidence

| Guarantee | Command | Result | Evidence |
|---|---|---:|---|
| At least 50 natural-language routing evals exist | `uv run --offline --frozen pytest -q tests/test_agent_evaluation.py --basetemp .tmp-pytest-p0-1-eval-green -p no:cacheprovider` | PASS | `2 passed in 0.03s`; fixture contains 60 cases |
| Skill-selection accuracy is at least 95% | Same as above | PASS | 60/60 exact-match cases pass after router fix |
| Router fix preserves Agent execution contracts | `uv run --offline --frozen pytest -q tests/test_agent_evaluation.py tests/test_agent_execution.py tests/test_agent.py -k "analyze_requirement or p0_1 or agent_execution or configured_provider or deterministic_provider or mcp" --basetemp .tmp-pytest-p0-1-focused-green -p no:cacheprovider` | PASS | `29 passed, 187 deselected in 2.51s` |
| CLI contract still blocks missing RTL execution | `uv run --offline --frozen pytest -q tests/test_agent_evaluation.py tests/test_agent.py::test_cli_no_tool_check_generates_design_spec_but_fails_without_rtl_execution --basetemp .tmp-pytest-p0-1-routing-cli-green-2 -p no:cacheprovider` | PASS | `3 passed in 0.67s`; stderr includes `blocked` and `No RTL generator` |
| Full regression suite | `uv run --offline --frozen pytest -q --basetemp .tmp-pytest-p0-1-full-2 -p no:cacheprovider` | PASS | `268 passed in 38.30s` |
| Coverage gate | `uv run --offline --frozen pytest --cov=.trae/agent --cov-branch --cov-report=term-missing --basetemp .tmp-pytest-p0-1-coverage -p no:cacheprovider` | PASS | `268 passed in 47.64s`; total coverage 82.77%; required 68.0% reached |
| Ruff gate | `uv run --offline --frozen ruff check .trae/agent tests` | PASS | `All checks passed!` |
| Mypy gate | `uv run --offline --frozen mypy` | PASS | `Success: no issues found in 47 source files` |

The GREEN router checkpoint was committed as:

```text
4b3bb812 fix: improve agent skill routing accuracy
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result |
|---|---|---|---|---|
| 1 | Natural-language routing eval suite has at least 50 cases | `tests/test_agent_evaluation.py::test_p0_1_routing_eval_suite_has_at_least_50_cases` | eval/unit | PASS |
| 2 | Skill selection reaches at least 95% exact-match accuracy | `tests/test_agent_evaluation.py::test_p0_1_skill_selection_accuracy_is_at_least_95_percent` | eval/unit | PASS |
| 3 | Deterministic provider returns typed offline plans | `tests/test_agent_execution.py::test_deterministic_provider_returns_typed_plan_offline` | unit | PASS |
| 4 | Configured provider converts skills into code-constrained tool calls | `tests/test_agent_execution.py::test_configured_provider_builds_code_constrained_skill_plan` | unit | PASS |
| 5 | Engine correlates tool call and result identities | `tests/test_agent_execution.py::test_engine_correlates_tool_call_and_result_ids` | unit | PASS |
| 6 | Success without artifact list is rejected | `tests/test_agent_execution.py::test_engine_rejects_success_without_artifact_list` | unit | PASS |
| 7 | Failed or incomplete tool result cannot become Agent success | `tests/test_agent_execution.py::test_engine_never_succeeds_without_successful_tool_result` | unit | PASS |
| 8 | Empty execution plans are rejected | `tests/test_agent_execution.py::test_engine_rejects_zero_step_plan` | unit | PASS |
| 9 | Missing or empty artifacts are rejected | `tests/test_agent_execution.py::test_engine_rejects_missing_or_empty_success_artifacts` | unit | PASS |
| 10 | Mismatched tool-result identity is rejected | `tests/test_agent_execution.py::test_engine_rejects_mismatched_tool_result_identity` | unit | PASS |
| 11 | Fake MCP stdio client initializes, lists tools, and calls a tool | `tests/test_agent_execution.py::test_stdio_mcp_client_initializes_lists_and_calls_tools` | integration | PASS |
| 12 | MCP tool success persists an evidence artifact | `tests/test_agent_execution.py::test_mcp_tool_success_persists_evidence_artifact` | integration | PASS |
| 13 | MCP protocol, timeout, invalid JSON, and process-exit errors are surfaced | `tests/test_agent_execution.py::test_stdio_mcp_client_reports_protocol_timeout_and_exit_errors` | integration | PASS |
| 14 | MCP failures become failed tool results with non-zero return codes | `tests/test_agent_execution.py::test_mcp_failures_become_failed_tool_results` | integration | PASS |

## Routing Eval Coverage

The fixture `tests/fixtures/agent_routing_cases.json` contains 60 cases covering:

- Single-skill routing for design, RTL implementation, and verification.
- Multi-skill combinations for design + RTL, design + verification, RTL +
  verification, and full flow.
- Chinese, English, mixed case, and conversational phrasing.
- Negation and exclusion phrasing such as no UVM, no RTL, no simulation, and
  verification-only requests.
- Specific overlap cases: `SystemVerilog` versus `Verilog`, `前仿` versus
  ordinary `仿真`, complete flow / full flow / end-to-end phrasing, assertions,
  scoreboard, coverage, module design, interface/timing analysis, and UART
  module wording.

Current measured accuracy is 60/60 exact-match cases, or 100%.

## Error-Success Rate

The local test suite proves the current execution engine has 0 observed
false-success cases for covered contracts:

- Failed tool result: rejected.
- `returncode=None`: rejected.
- Non-zero return code: rejected.
- No artifact list: rejected.
- Missing artifact path: rejected.
- Empty artifact: rejected.
- Artifact outside output directory: rejected by engine path validation.
- Tool result with mismatched `tool_call_id` or `tool_name`: rejected.
- Empty execution plan: rejected.
- MCP protocol, timeout, invalid JSON, and process-exit failures: converted to
  failed tool results.

The observed false-success rate in the covered tests is 0.

## Real SynthPilot MCP Attempt

The real SynthPilot stdio command was attempted with repository-local uv
runtime directories:

```text
uvx --python F:\My_code\Agent_design_for_vivado\.venv\Scripts\python.exe synthpilot
```

The first attempt failed before protocol startup because `uvx` tried to use a
user-level tools directory. The retry set these local directories:

- `UV_CACHE_DIR=.tmp\uv-cache-synthpilot`
- `UV_PYTHON_INSTALL_DIR=.tmp\uv-python`
- `UV_TOOL_DIR=.tmp\uv-tools`
- `UV_TOOL_BIN_DIR=.tmp\uv-tool-bin`

After that, the real SynthPilot program started but exited before MCP
`initialize` with:

```text
Please set license_key in config.yaml

Config file locations:
1. Same directory as program
2. ~/.synthpilot/config.yaml
```

Non-secret configuration probing found no SynthPilot config file at:

- `F:\My_code\Agent_design_for_vivado\config.yaml`
- `C:\Users\ycy123\.synthpilot\config.yaml`

The preserved evidence file is:

```text
docs/testing/evidence/synthpilot_tools_list.json
```

The reusable evidence collector is:

```text
scripts/p0_1_synthpilot_mcp_evidence.py
```

Current rerun command:

```text
uv run --offline --frozen python scripts/p0_1_synthpilot_mcp_evidence.py
```

Status: blocked by missing SynthPilot license configuration. No tool names or
schemas were guessed, and no fake SynthPilot success is claimed.

## Current P0-1 Acceptance Status

| Requirement | Status | Evidence |
|---|---|---|
| `AgentRequest`, `ExecutionPlan`, `ToolCall`, `ToolResult`, `AgentRun` types | PASS | `tests/test_agent_execution.py`; full pytest PASS |
| Provider and MCP Client interfaces | PASS | `agent_provider.py`, `mcp_client.py`; unit/integration tests PASS |
| Skills converted to code-constrained execution plans | PASS | `ConfiguredAgentProvider` tests verify `skill:<action>` tool calls |
| Model cannot directly declare success | PASS | Engine requires successful `ToolResult`, return code 0, and artifacts |
| Success tied to tool results, return codes, and artifact lists | PASS | Engine tests reject missing, empty, mismatched, and failed tool outputs |
| Deterministic offline Provider support | PASS | Deterministic provider tests PASS |
| At least 50 natural-language evals | PASS | 60-case fixture |
| Skill-selection accuracy >= 95% | PASS | 60/60, 100% |
| Error-success rate 0 | PASS for covered contracts | Full local suite and execution tests PASS |
| Real SynthPilot initialize, tools/list, tool call | BLOCKED | Real process exits before `initialize`; missing `license_key` |

## Known Gap

P0-1 cannot be declared complete until a valid SynthPilot `license_key` is
available in one of SynthPilot's supported config locations and the real MCP
server completes:

1. `initialize`
2. `tools/list`
3. one safe, non-destructive `tools/call` selected from the real tool schema

After license configuration is available, rerun the real SynthPilot evidence
script and append the successful request, response, return status, and artifact
evidence to this report.
