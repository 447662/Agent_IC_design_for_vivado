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

| Work item | RED | GREEN | Guarantee |
|---|---|---|---|
| Quality provenance | Missing validation API/JSON output; workflow still labeled local generation as a CI full artifact | P1 contract set: 50 passed | Markdown and JSON record `source`, `commit_sha`, `generated_at`, `run_id`, and `run_url`; CI identity is mandatory and local evidence cannot claim a CI run |
| Risk-oriented coverage | No per-module gate; six baseline branch rates ranged from 64.29% to 86.67% | Risk coverage gate PASS after 528-test coverage run | Security and orchestration modules have independent line/branch thresholds that fail closed on missing or low coverage |
| Python and uv support | Python 3.12 absent, upper Python bound absent, setup-uv selected an implicit tool version | P1 contract set: 50 passed; frozen lock resolved | CI covers Python 3.11/3.12/3.13, package support is `>=3.11,<3.14`, and both workflows install uv 0.11.26 |

RED command result: `10 failed, 6 passed`. The failures were missing
provenance behavior, missing risk-coverage gate, and incomplete CI/Python/uv
configuration; all six new runtime branch tests executed successfully.

GREEN evidence:

- P1 provenance/configuration contract set: `50 passed`.
- Full suite with coverage: `528 passed`; total coverage `88.79%`.
- Risk module line/branch results: provider `95.00%/92.86%`, MCP
  `94.62%/89.19%`, plugin guard `87.18%/78.57%`, execution
  `96.23%/96.67%`, CLI dispatch `85.33%/75.00%`, async FIFO flows
  `71.01%/84.00%`.
- `uv run --frozen python scripts/check_risk_coverage.py`: PASS.
- Ruff: PASS. Mypy: PASS, 88 source files.
- `uv lock` with uv 0.11.26: resolved 17 packages; Python 3.14-only wheels
  are excluded by the declared support range.

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
