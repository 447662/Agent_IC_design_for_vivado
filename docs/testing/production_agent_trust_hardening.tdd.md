# Production Agent Trust Hardening TDD Evidence

## Source

The user goal defines P0, P1, and P2 production hardening requirements. Current
code, tests, configuration, CI workflows, package artifacts, and runtime results
are authoritative. Roadmap and backlog documents are excluded from evidence.

## User Journeys

- A quality reviewer can see every agent eval case execute and fail when an
  expected behavior is deliberately corrupted.
- An operator can run an MCP server without leaking unrelated environment
  secrets or persisting sensitive tool data.
- A repository maintainer can prevent fork and untrusted-author code from
  reaching the licensed self-hosted Vivado runner.
- A release reviewer can trace quality evidence to its exact source and commit.
- A package consumer receives an explicit, tested Python support contract and
  complete non-license package metadata.

## P0 RED And GREEN Evidence

| Work item | RED | GREEN | Guarantee |
|---|---|---|---|
| Executable agent eval | `tests/test_p2_agent_eval_report.py`: missing execution counts; corrupted expected tool incorrectly returned 0 | P0 target set: 92 passed | All 10 cases execute; expected tools, forbidden tools, error category/exit code, artifacts, manifest fields, and multi-target contracts are asserted |
| MCP redaction | MCP evidence, metadata, result text, and exception text retained test secrets | P0 target set: 92 passed | Sensitive key variants, bearer headers, embedded JSON, evidence, ToolResult, metadata, stderr, and errors share recursive sanitization |
| MCP containment | No minimal environment API, no size/pending bounds, timeout process remained alive | P0 target set: 92 passed | Child environment is allowlisted; stdout queue, message, stderr, and pending responses are bounded; protocol failures and timeouts close the process |
| Vivado runner trust | Workflow lacked repository/author checks, checkout credential hardening, and runner security contract | P0 target set: 92 passed | Fork and untrusted-author PRs cannot schedule the self-hosted Vivado job; checkout credentials are not persisted |

RED command result: `11 failed, 79 passed`.

GREEN commands:

- `uv run --frozen pytest tests/test_p2_agent_eval_cases.py tests/test_p2_agent_eval_report.py tests/test_p1_3_error_model.py tests/test_agent_execution.py tests/test_mcp_client_branches.py tests/test_mcp_protocol_messages.py tests/test_vivado_integration_workflow.py -q`: `92 passed`.
- Related configuration/plugin/release set: `64 passed`.
- `uv run --frozen ruff check .trae/agent tests src/digital_ic_agent scripts`: PASS.
- `uv run --frozen mypy`: PASS, 88 source files.
- Generated agent eval report: PASS, 10 executed, 10 passed, 0 failed.

## P1 Evidence

Pending.

## P2 Evidence

Pending.

## Final Verification

Pending full coverage, distributions, real Vivado gate, and SSH publication.

## Known External Decisions

- The repository license is intentionally not selected. This remains the sole
  owner decision and must not be guessed by automation.
- GitHub protected-environment required reviewers and runner ephemerality are
  external settings; the repository records and enforces the locally testable
  parts of that contract.
