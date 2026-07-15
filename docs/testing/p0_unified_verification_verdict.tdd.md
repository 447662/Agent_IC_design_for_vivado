# P0 Unified Verification Verdict TDD Evidence

## Scope

P0 establishes one fail-closed `VerificationVerdict` for built-in RTL simulation,
UVM smoke, UVM coverage, parameter regression, random-seed regression, runtime
manifests, the machine CLI, and the Vivado CI release gate.

## RED Evidence

- `4d5e2f452`: core verdict failure classes and artifact freshness.
- `1c8744b95`: async FIFO and round-robin scoreboard false passes.
- `940eae04a`: missing return-code, marker, coverage, and artifact policies.
- `5d0151faf`: UVM error/fatal/SVA conflicts and missing or stale evidence.
- `8f0c26b40`: manifest/verdict status, freshness, and validity contract.
- `a48707555`: CI must reject PASS-only marker scanning.
- `3635635aa`: child verdict aggregation for regression flows.
- `05dcc363d`: canonical machine `verify --json` response contract.

## GREEN Implementation

- `f148c7f96`: canonical verdict evaluator and atomic JSON/Markdown output.
- `66c1c467b`: fail-closed built-in RTL Vivado flows.
- `8ce29a23c`: unified UVM smoke and coverage verdicts.
- `7fd762278`: manifest embeds and validates the current canonical verdict.
- `4e61966d1`: Vivado CI consumes canonical verdicts instead of marker scans.
- `ee4dcdd0f`: parent verdicts aggregate RTL/UVM regression child verdicts.
- `79a1c6040`: stable machine `verify --json` command and JSON Schema.

## Acceptance Evidence

Commands were run from the repository root with `PYTHONPATH=src`.

```text
python -m ruff check .
All checks passed!

python -m mypy
Success: no issues found in 90 source files

python -m pytest -q --basetemp .tmp-pytest-p0-full-rerun -p no:cacheprovider
589 passed in 40.61s
```

The verdict fails closed on nonzero exits, missing PASS markers, failure/fatal
markers, nonzero UVM counts, SVA/assertion failures, coverage FAIL/MISSING/SKIP,
missing/empty/stale artifacts, invalid or stale verdict files, manifest mismatch,
and failed or missing child regression verdicts.
