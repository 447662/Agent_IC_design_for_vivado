# P6 Generic Vivado Workspace Verification TDD Evidence

## Source And Journeys

Source objective: `C:\Users\ycy123\.codex\attachments\0b7a6331-087d-4a4c-8144-0ebe328e480d\goal-objective.md`.

- As Codex, I can declare an ordered, non-built-in RTL/UVM/SVA source set and explicit verification policy, then invoke one machine-readable workspace command.
- As a digital IC designer, I receive a fail-closed canonical verdict from real `xvlog`, `xelab`, `xsim`, and `xcrg` evidence.
- As an interrupted agent, I can inspect immutable numbered iterations, detect unchanged failed work, obey limits, and resume from atomically saved state.

## RED Evidence

Command:

```text
python -m pytest tests/test_intent_contract.py tests/test_generic_verification.py tests/test_machine_cli_verify.py --basetemp .tmp-pytest-p6-red -p no:cacheprovider -q
```

Result: collection failed with `ModuleNotFoundError: No module named 'digital_ic_agent._runtime.generic_verification'`. The test module compiled far enough to import the required P6 boundary; production implementation did not yet exist. RED checkpoint: `f32d45b53`.

A real Vivado run later exposed a second RED case: `ERROR: [Simtcl 6-50] Simulation engine failed to start` was rejected through missing markers/artifacts but was not classified as `TOOL_ERROR_FOUND`. The focused test failed with verdict `PASS`; after adding `Simtcl` to the canonical tool-error pattern, the same test passed.

## GREEN Evidence

| Guarantee | Test or command | Type | Result |
|---|---|---|---|
| Execution fields cannot be silently defaulted | `tests/test_intent_contract.py` | contract | PASS |
| Workspace escape paths are rejected | `tests/test_intent_contract.py` | security/unit | PASS |
| Declared source order drives `xvlog`; top drives `xelab` | `tests/test_generic_verification.py` | integration | PASS |
| Real xsim/xcrg scores become canonical coverage gates | `tests/test_generic_verification.py` | integration | PASS |
| Missing tools, compile failure, missing reports, markers, and artifacts fail closed | `tests/test_generic_verification.py` | negative integration | PASS |
| Max iteration and unchanged-failure limits stop without rerunning tools | `tests/test_generic_verification.py` | lifecycle | PASS |
| Numbered iterations preserve hashes, snapshots, diffs, logs, tool version, coverage, and verdict | `tests/test_generic_verification.py` | evidence | PASS |
| `verify --workspace --json` emits the stable CLI envelope | `tests/test_machine_cli_verify.py` | CLI | PASS |
| Simtcl child-engine errors are canonical tool errors even with misleading exit status | `tests/test_verification_verdict.py` | regression | PASS |
| Runtime modules remain below 800 lines after evidence, coverage, and OpenHW extraction | `tests/test_quality_config.py` | architecture | PASS |

Final full test and coverage command:

```text
$env:COVERAGE_FILE='.tmp\p6-full.coverage'; .venv\Scripts\python.exe -m pytest --cov=digital_ic_agent --cov-branch --cov-report=term --cov-report=xml:.tmp/p6-full-coverage.xml --basetemp .tmp-pytest-p6-full-cov -p no:cacheprovider -q
```

Result: `653 passed`; total branch coverage `87.8%`; `generic_verification.py` `84.1%`; `generic_verification_evidence.py` `87.4%`.

Static and policy gates:

- `ruff check .`: PASS.
- `mypy`: PASS for 97 source files.
- `scripts/check_risk_coverage.py --coverage-xml .tmp/p6-full-coverage.xml`: PASS.
- `scripts/sync_agent_config.py --check`: PASS.
- `quick_validate.py .agents/skills/digital-ic-design`: `Skill is valid!`.

## Real Vivado Evidence

Positive workspace: ignored local artifact `.tmp/p6-generic-real-pass-unsandboxed`.

Command:

```text
digital-ic-agent verify --workspace .tmp/p6-generic-real-pass-unsandboxed --vivado-bin D:\vivado\2025.2\Vivado\bin --json
```

Result: PASS through real Vivado Simulator v2025.2. The canonical evidence contains successful `xvlog`, `xelab`, `xsim`, and `xcrg`; statement `100.0`, branch `75.0`, condition `100.0`, toggle `0.0`; the explicit P6 plumbing-smoke thresholds were all `0.0`. Required pass marker, SVA result, WDB, `xsim.CCInfo`, xcrg HTML, hashes, manifest, and atomic `VERIFIED` state were present.

Negative workspace: ignored local artifact `.tmp/p6-generic-real-fail`.

Result: real `xvlog` rejected invalid SystemVerilog. The canonical verdict included `NONZERO_EXIT`, `TOOL_ERROR_FOUND`, missing pass marker, missing coverage gates, and missing required artifacts. Elaboration and simulation were not executed.

## Distribution And Known Gap

`uv build --wheel --sdist --out-dir .tmp/p6-dist` succeeded. The sdist isolated install, package-data probe, and generated CLI launcher smoke passed. The wheel isolated install, module probe, package-data probe, and `python -m digital_ic_agent --list-targets` passed; its generated Windows console-launcher executable was blocked by local application control with `WinError 4551`, including outside the Codex sandbox. This is retained as an unresolved local launcher-policy gap and is not reported as PASS.

P7 remains outside this P6 checkpoint: higher production coverage thresholds, three complete non-built-in UVM designs, 30 unseen evaluations, and 10 injected-fault repair evaluations are still required.
