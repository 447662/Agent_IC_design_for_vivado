# Release Closure And Production Hardening TDD Evidence

## Source

The user goal supplied the T1-T6 release closure and production hardening requirements. Current code, tests, configuration, Git state, package artifacts, and runtime results were treated as authoritative. Roadmap and backlog documents were not used as implementation evidence.

## User Journeys

- A release maintainer can review an explicit migration map instead of inferring moves from a dirty worktree.
- A package consumer can install either the wheel or sdist outside the source tree and use all three built-in targets.
- A protected branch receives one deterministic Vivado required context for unlabeled, labeled, skipped, failed, and successful PR states.
- A maintainer cannot grow a production runtime module beyond 800 physical lines unnoticed.
- A plugin consumer sees an accurate trusted-local, non-sandbox security contract.
- A quality reviewer sees SynthPilot source failure, optional degradation, capture time, and retry policy without repeated external calls.

## RED And GREEN Evidence

| Task | RED evidence | GREEN evidence | Guarantee |
|---|---|---|---|
| T1/T2 | `tests/test_runtime_package_migration.py`: 3 failed, 4 passed | Migration/release/quality set: 36 passed | Migration inventory, local `dist/` policy, and CI distribution smoke contract are explicit |
| T2 runtime | Distribution smoke script absent before implementation | Wheel and sdist each reported `cli: PASS`, `package_data: PASS`, and three targets | Installed artifacts do not rely on the source tree |
| T3 | `tests/test_vivado_integration_workflow.py`: 2 failed, 5 passed | 7 passed | Final required context fails closed for missing label or non-success real gate |
| T4 | Runtime line-budget test failed on seven modules, maximum 1909 lines | Budget test passed; maximum production module is 760 lines; contract set 81 passed | Every production Python module is at most 800 lines and public facades remain available |
| T5/T6 | Security/SynthPilot set: 6 failed, 9 passed | 15 passed; unchanged blocker execution returned `SKIPPED` | Plugin terminology is non-sandbox and SynthPilot retry/status semantics are consistent |
| Full suite | First full run: 499 passed, 1 stale metadata assertion failed | Final full run: 500 passed | All repository behavior and architecture tests pass after the terminology migration |

## Final Verification

| Command or artifact | Result |
|---|---|
| `uv run --frozen ruff check .trae/agent tests src/digital_ic_agent scripts` | PASS |
| `uv run --frozen mypy` | PASS, 88 source files |
| Full pytest with branch coverage and no cache provider | PASS, 500 tests |
| Coverage XML | Line 90.3%, branch 80.4%, configured gates passed |
| Wheel build and outside-source install smoke | PASS |
| Sdist build and outside-source install smoke | PASS |
| Real Vivado integration gate | PASS for `sync-fifo`, `async-fifo`, and `round-robin-arbiter`; run `20260713-220711-6f928243cb394c69b0ad942dc8d22610` |
| `git diff --check` | PASS; line-ending normalization warnings only |

## Known External Acceptance Gaps

- `scripts/check_release_tree.py --phase source` and `--phase generated` require a clean committed checkout. The current repository was intentionally not staged or committed without user approval.
- The workflow and ruleset tests prove deterministic configuration semantics, but the required context still needs one real GitHub PR run after the user authorizes staging, commit, and push.
- SynthPilot remains an optional external license/device blocker. The evidence command now skips the unchanged fingerprint unless `--force` is supplied after confirming external state changed.
