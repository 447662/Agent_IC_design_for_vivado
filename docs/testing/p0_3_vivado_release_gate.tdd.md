# P0-3 Vivado Release Gate TDD Evidence

## Source

No upgrade plan file was read for this work. The P0-3 scope was derived from
the current GitHub Actions workflow, Vivado runner script, target registry, and
target handler implementations.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want the real Vivado gate to run only on a trusted runner
   environment, so hardware-license CI cannot be triggered without environment
   approval.
2. As a release owner, I want the Vivado gate to exercise sync FIFO, async FIFO,
   and round-robin arbiter targets, so protected branches cannot pass with only
   one sample design.
3. As a verification owner, I want async FIFO RTL simulation, UVM smoke, and UVM
   coverage to run in CI, so async-clock verification regressions are caught
   before release.
4. As a build operator, I want every checked artifact to be generated during
   the current run, so stale RTL, TB, XPR, VCD, WDB, report, or manifest files
   cannot produce a false pass.
5. As a verification owner, I want scoreboard markers to be required for each
   target and UVM flow, so a tool invocation without simulator PASS evidence
   fails the gate.
6. As a release owner, I want each target to reject intentionally broken RTL, so
   the gate proves real Vivado syntax/elaboration failure detection.

## Task Report

### Release Gate Matrix

The previous runner executed only `--sim-rtl sync-fifo`. P0-3 expands the gate
to a declarative `$targetGates` matrix:

- `sync-fifo`: `--sim-rtl`
- `async-fifo`: `--sim-rtl`, `--uvm-smoke`, `--uvm-coverage`
- `round-robin-arbiter`: `--sim-rtl`

Each flow runs with `--no-wave-gui` under the per-run artifact directory and
then checks required RTL, TB, VCD, WDB, Vivado XPR, report, and
`artifacts.json` outputs.

### False-Pass Rejection

The runner now centralizes validation in:

- `Assert-FreshFile`
- `Assert-ScoreboardMarker`
- `Assert-RuntimeManifest`

The manifest check requires latest run `PASS`, matching flow name, non-empty
`run_id`, each required artifact listed as `CURRENT`, and
`produced_by_run_id` populated. The runner also keeps a `*.wdb` freshness sweep
for every project `sim` directory.

The negative syntax test now iterates every target in `$targetGates`, copies
the freshly generated project into `negative-syntax-<target>`, appends
`THIS_TOKEN_IS_INTENTIONALLY_INVALID_VERILOG` to that target's RTL, and requires
the relevant Vivado simulation TCL script to fail.

### Trusted Runner Environment

The GitHub Actions job now declares:

```yaml
environment: vivado-trusted-runner
```

This is the repository-side hook for configuring environment protection and
approval rules around the self-hosted Windows Vivado runner.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_vivado_integration_workflow.py --basetemp .tmp-pytest-p0-3-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_vivado_integration_workflow.py::test_vivado_integration_workflow_uses_controlled_self_hosted_runner
AssertionError: assert 'environment:' in workflow

FAILED tests/test_vivado_integration_workflow.py::test_vivado_runner_covers_p0_3_release_gate_matrix
AssertionError: assert '$targetGates' in script

FAILED tests/test_vivado_integration_workflow.py::test_vivado_runner_rejects_false_passes_for_each_release_gate_target
AssertionError: assert 'foreach ($negativeGate in $targetGates)' in script

3 failed, 2 passed in 0.07s
```

## GREEN Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_vivado_integration_workflow.py --basetemp .tmp-pytest-p0-3-green -p no:cacheprovider -q
```

Result:

```text
5 passed in 0.02s
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Vivado integration can run manually and only on labeled PRs or the integration branch | `tests/test_vivado_integration_workflow.py::test_vivado_integration_workflow_uses_controlled_self_hosted_runner` | CI/static | PASS | `5 passed in 0.02s` |
| 2 | The job uses the self-hosted Windows Vivado runner and trusted environment hook | `tests/test_vivado_integration_workflow.py::test_vivado_integration_workflow_uses_controlled_self_hosted_runner` | CI/static | PASS | `environment: vivado-trusted-runner` asserted |
| 3 | The runner invokes real Vivado version and license/startup preflight before target work | `tests/test_vivado_integration_workflow.py::test_vivado_runner_executes_real_flow_and_rejects_false_passes` | CI/static | PASS | `Get-Command vivado`, `-version`, and preflight asserted |
| 4 | The release matrix includes sync FIFO, async FIFO, and round-robin arbiter | `tests/test_vivado_integration_workflow.py::test_vivado_runner_covers_p0_3_release_gate_matrix` | CI/static | PASS | `$targetGates` and all targets asserted |
| 5 | Async FIFO CI includes RTL sim, UVM smoke, and UVM coverage | `tests/test_vivado_integration_workflow.py::test_vivado_runner_covers_p0_3_release_gate_matrix` | CI/static | PASS | `--sim-rtl`, `--uvm-smoke`, `--uvm-coverage` asserted |
| 6 | Each target requires fresh RTL, TB, VCD, XPR, report, WDB, and manifest outputs as applicable | `tests/test_vivado_integration_workflow.py::test_vivado_runner_covers_p0_3_release_gate_matrix` | CI/static | PASS | required artifact paths asserted |
| 7 | Runtime manifests must report latest `PASS`, matching flow, `run_id`, `CURRENT` artifacts, and `produced_by_run_id` | `tests/test_vivado_integration_workflow.py::test_vivado_runner_covers_p0_3_release_gate_matrix` | CI/static | PASS | `Assert-RuntimeManifest` asserted |
| 8 | Scoreboard markers are mandatory for RTL sim and async FIFO UVM flows | `tests/test_vivado_integration_workflow.py::test_vivado_runner_covers_p0_3_release_gate_matrix` | CI/static | PASS | scoreboard tokens asserted |
| 9 | Every matrix target runs a negative syntax test against its Vivado simulation TCL script | `tests/test_vivado_integration_workflow.py::test_vivado_runner_rejects_false_passes_for_each_release_gate_target` | CI/static | PASS | `foreach ($negativeGate in $targetGates)` asserted |
| 10 | The runner does not create fake output files or delete project artifacts to force a pass | `tests/test_vivado_integration_workflow.py::test_vivado_runner_executes_real_flow_and_rejects_false_passes` | CI/static | PASS | `New-Item -ItemType File`, `Set-Content`, and `Remove-Item` absent |

## Known Gaps

- This TDD run validates the repository CI gate definition and runner logic
  statically. It does not claim a live Vivado execution because this environment
  does not expose the self-hosted Vivado runner.
- The GitHub environment named `vivado-trusted-runner` must be configured in
  repository settings with the intended reviewers/protection rules before the
  branch protection policy can rely on it.
- P0-3 provides the branch-protection status check surface, but enabling a
  required status check on protected branches is a repository settings action
  outside the codebase.
- SynthPilot remains intentionally ignored for this phase; the license device
  limit is still tracked in the P0-1 follow-up document.
