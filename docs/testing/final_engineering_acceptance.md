# Final Engineering Acceptance

Status: **PASS with non-blocking operational risks**

Date: 2026-07-15

## Product Boundary

Codex is the only reasoning and code-generation layer. The repository provides
deterministic intent validation, governed local reference search, workspace
state, Vivado/xsim execution, canonical verdicts, diagnosis, iteration limits,
coverage closure, resumability, and machine-readable evidence. No OpenAI,
Anthropic, or other LLM API, model SDK, provider, key, embedding service, or
in-repository inference service was added or invoked.

## Implemented Surface

- One fail-closed `VerificationVerdict` contract is shared by CLI output,
  reports, manifests, regression, and CI-facing evidence.
- Codex discovers `.agents/skills/digital-ic-design/SKILL.md`; `.trae` skill and
  MCP configuration are mirrored to `.agents` and `.codex` with a zero-drift
  check.
- Versioned DesignIntent and VerificationIntent schemas validate module,
  parameters, ports, clocks, resets, protocols, timing, exceptional behavior,
  execution policy, scoreboard, SVA, coverage, iteration limits, and acceptance
  criteria.
- Reference governance supports status, indexing, FTS5/BM25 search, record
  display, reminder state, archive safety, freshness, source hashes, and
  `LICENSE_UNKNOWN` concept-only policy.
- Generic workspaces support initialize, validate, verify, diagnose, status,
  resume, and report flows with atomic state and preserved iterations.
- Verification supports direct `xvlog`/`xelab`/`xsim` execution and isolated
  Vivado project fallback. Project mode calls `launch_simulation` once and
  collects compile, elaborate, simulate, WDB, coverage database, and xcrg
  artifacts.
- P7 contains 10 generation, 10 bounded repair, and 10 contract-negative evals.
  The formal designs include synthesizable RTL and their required UVM/SVA,
  scoreboard, and functional coverage artifacts.

## Command Contract

Typical Codex-driven flow:

```text
digital-ic-agent workspace init --workspace <dir> --json
digital-ic-agent status --workspace <dir> --json
digital-ic-agent spec validate --design-intent <design.json> --verification-intent <verification.json> --json
digital-ic-agent reference status --workspace <dir> --json
digital-ic-agent reference index --workspace <dir> --json
digital-ic-agent reference search --workspace <dir> --query <query> --json
digital-ic-agent reference show --workspace <dir> --record-id <id> --json
digital-ic-agent verify --workspace <dir> --vivado-bin <bin> --vivado-launch-mode direct --json
digital-ic-agent diagnose --workspace <dir> --json
digital-ic-agent resume --workspace <dir> --json
digital-ic-agent report --workspace <dir> --json
```

Use `--vivado-launch-mode project` only after canonical diagnosis returns
`SIMULATION_ENGINE_LAUNCH_BLOCKED`.

Every machine response has stable top-level fields: `schema_version`,
`command`, `status`, `ok`, `error_code`, `message`, and `data`. PASS requires
`status=PASS`, `ok=true`, `error_code=null`, and agreement between the canonical
verdict and artifact manifest.

## Quality Evidence

| Gate | Result |
| --- | --- |
| Ruff | PASS |
| Mypy | PASS, 100 source files |
| Pytest | 676 passed, 0 failed, 0 errors, 0 skipped |
| Line coverage | 90.5%, threshold 90.0% |
| Branch coverage | 80.7%, threshold 80.0% |
| Combined pytest-cov result | 88.17%, threshold 85.0% |
| Risk-oriented coverage | PASS |
| Config mirror | PASS |
| Agent surface sync | PASS, 0 drift |
| Test module size | PASS, 100 modules, none over 1000 lines |
| Agent evaluation | PASS, 10/10 |

Primary local quality evidence is under
`.tmp/final-quality-p7-20260715-007`. The P7 machine summary is
`docs/testing/evidence/p7_real_eval_summary.json`.

## Distribution Evidence

| Artifact | SHA-256 | Smoke |
| --- | --- | --- |
| `digital_ic_agent-1.0.0-py3-none-any.whl` | `4970fee54864440a4baebe2a05e458f6c3e759af2dd27d129c7b5d3fc6f604e3` | PASS |
| `digital_ic_agent-1.0.0.tar.gz` | `113eb392f872e39b752422ce66d044f398427514b6f1d1980584c576b19ca062` | PASS |

Both artifacts were installed in fresh isolated environments. CLI import,
package data, and async-fifo, sync-fifo, and round-robin-arbiter discovery all
passed outside the source import path.

## Vivado And Eval Evidence

- Vivado 2025.2 edge-detector project mode: canonical PASS, iteration 1, all
  configured code coverage gates PASS.
- Vivado 2025.2 APB register block UVM project mode: canonical PASS, iteration 1,
  statement/branch/condition/functional/toggle gates PASS.
- Generation eval: 10/10 PASS with real Vivado evidence.
- Defect detection: 10/10 PASS.
- Repair eval: 10/10 PASS, each repaired in one iteration, exceeding the 7/10
  acceptance threshold.
- Contract-negative eval: 10/10 PASS and `vivado_invoked=false` for every case.
- Invalid-syntax Vivado checks rejected async-fifo, sync-fifo, and
  round-robin-arbiter inputs with VRFC compile errors.
- False-pass regressions reject PASS text combined with TEST_FAILED,
  UVM_ERROR/UVM_FATAL, assertion failures, stale/missing artifacts, and the two
  historical async-fifo and round-robin samples.

## References And Licenses

The governed `references/inbox/{rtl,uvm,papers,specs,licenses}` directories are
currently empty. The legacy `OpenRTLSet-main.zip` and `2606.10285v1.pdf` remain
read-only root inputs and were not moved, copied, executed, indexed into Git, or
included in distributions. OpenHWGroup was not queried because the independent
eval designs did not require external source reuse. P7 artifacts do not copy
third-party RTL. Reference boundary tests cover empty libraries, one-time
reminders, missing licenses, concept-only reuse, corrupt archives, path
traversal, absolute paths, and stale indexes.

## Codex Discovery

The current Codex task discovered and read the repository-local
`digital-ic-design` skill before using its workflow and canonical evidence.
Automated tests also validate the Codex skill surface and `.trae` mirror. No
separate noninteractive LLM-driven task was launched because the product
boundary forbids LLM API calls; the real end-to-end design evidence is the
current Codex workflow plus the Vivado-backed P7 designs.

## Residual Risks

- Vivado reports `[Common 17-1297]` for a corrupted user Tcl Store catalog and
  falls back to the installation Tcl Store. Simulations pass, but user Tcl apps
  are not persisted until that external Vivado profile is repaired.
- The local governed reference inbox is empty; users must add source materials
  and corresponding LICENSE/NOTICE files before reference-backed design work.
- SynthPilot remains an optional degraded-only capability and is WARN in the
  generated quality matrix; it is not part of the digital-IC acceptance path.
- Commit and remote SSH SHA are recorded in the final task handoff because a
  Git commit cannot contain its own final object ID.

Smart App Control, WDAC, and Defender were not changed, and no system-level
allow action was used.
