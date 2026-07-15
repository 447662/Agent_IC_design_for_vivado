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
`run_id`, each flow-owned manifest artifact listed as `CURRENT`, and
`produced_by_run_id` populated. Required artifacts still receive direct
freshness checks, while `ManifestCurrentArtifacts` separates current-flow
outputs from reused inputs such as UVM flows reusing freshly generated RTL. The
runner also checks that every flow declares and refreshes at least one required
WDB artifact.

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

### Protected Branch Gate

The repository now includes an auditable ruleset source at:

```text
.github/branch-protection/vivado-release-gate.json
```

The ruleset targets protected branches, requires pull request review, and makes
the `Vivado integration / vivado-integration` status check mandatory with strict
up-to-date status checks. This keeps the P0-3 release gate tied to branch
protection configuration instead of leaving it only as a workflow convention.

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

Additional RED evidence for the protected-branch gate source:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_vivado_integration_workflow.py::test_vivado_release_gate_is_required_for_protected_branches --basetemp .tmp-pytest-p0-3-branch-protection-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_vivado_integration_workflow.py::test_vivado_release_gate_is_required_for_protected_branches
AssertionError: assert False
1 failed in 0.10s
```

Additional GREEN evidence after adding `.github/branch-protection/vivado-release-gate.json`:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_vivado_integration_workflow.py::test_vivado_release_gate_is_required_for_protected_branches --basetemp .tmp-pytest-p0-3-branch-protection-green -p no:cacheprovider -q; uv run --offline --frozen pytest tests/test_vivado_integration_workflow.py --basetemp .tmp-pytest-p0-3-release-gate-reconfirm -p no:cacheprovider -q
```

Result:

```text
1 passed in 0.04s
6 passed in 0.03s
```

Latest repository-side P0-3 confirmation on 2026-07-12:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_vivado_integration_workflow.py --basetemp .tmp-pytest-p0-3-current -p no:cacheprovider -q
```

Result:

```text
6 passed in 0.04s
```

Latest P0-3 runner-focused confirmation after adding explicit Vivado path
resolution, repository-local `UV_CACHE_DIR`, UVM manifest-current artifact
semantics, and async FIFO UVM artifact contract entries:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_vivado_integration_workflow.py tests/test_agent.py::test_generate_async_fifo_project_creates_rtl_tb_sim_reports tests/test_agent.py::test_async_fifo_manifest_declares_uvm_flow_artifacts tests/test_architecture_runtime.py::test_plugin_service_allows_vivado_executable_and_checks_batch_cwd --basetemp .tmp-pytest-p0-3-contract-current -p no:cacheprovider -q
```

Result:

```text
9 passed in 0.85s
```

Scoped Ruff confirmation:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check tests/test_vivado_integration_workflow.py
```

Result:

```text
All checks passed!
```

Scoped Ruff confirmation after the same P0-3 runner and async FIFO artifact
contract changes:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check tests/test_vivado_integration_workflow.py tests/test_agent.py tests/test_architecture_runtime.py .trae/agent/agent_runtime.py .trae/agent/agent_async_fifo_render.py
```

Result:

```text
All checks passed!
```

PowerShell parse confirmation:

```powershell
$null = [scriptblock]::Create((Get-Content .github/scripts/run-vivado-integration.ps1 -Raw)); 'PowerShell parse OK'
```

Result:

```text
PowerShell parse OK
```

Local Vivado availability check on 2026-07-12:

```powershell
$cmd = Get-Command vivado -ErrorAction SilentlyContinue; if ($cmd) { $cmd | Select-Object Source,Path,Version | Format-List } else { Write-Output 'vivado command not found on PATH' }
```

Result:

```text
vivado command not found on PATH
```

Latest local Vivado availability reconfirmation on 2026-07-12:

```powershell
$cmd = Get-Command vivado -ErrorAction SilentlyContinue; if ($cmd) { $cmd | Select-Object Source,Path,Version | Format-List } else { Write-Output 'vivado command not found on PATH' }
```

Result:

```text
vivado command not found on PATH
```

User-provided Vivado executable path on 2026-07-12:

```text
D:\vivado\2025.2\Vivado\bin\unwrapped\win64.o\vivado.exe
```

The runner resolves this unwrapped executable to the supported Vivado wrapper
at:

```text
D:\vivado\2025.2\Vivado\bin\vivado.bat
```

Real Vivado P0-3 integration gate confirmation on 2026-07-12:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .github/scripts/run-vivado-integration.ps1 -VivadoPath 'D:\vivado\2025.2\Vivado\bin\unwrapped\win64.o\vivado.exe' -ArtifactsRoot '.tmp\vivado-integration-p0-3-real-check7'
```

Result:

```text
Vivado integration PASS
Targets: sync-fifo, async-fifo, round-robin-arbiter
Artifacts: .tmp\vivado-integration-p0-3-real-check7\20260712-014219-4e90085eae2945ce9e3df99763d30885
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
| 11 | Protected branches require the Vivado integration status check through an auditable ruleset source | `tests/test_vivado_integration_workflow.py::test_vivado_release_gate_is_required_for_protected_branches` | CI/static | PASS | `6 passed in 0.03s` |
| 12 | Current repository-side P0-3 gate definition remains green | `tests/test_vivado_integration_workflow.py` plus scoped Ruff | CI/static/quality | PASS | `6 passed in 0.04s`; `All checks passed!` |
| 13 | The runner accepts a user-provided unwrapped Vivado executable and resolves it to the supported wrapper | `tests/test_vivado_integration_workflow.py::test_vivado_runner_executes_real_flow_and_rejects_false_passes` plus real runner command | static/real Vivado | PASS | `Vivado integration PASS`; wrapper path resolved from the provided unwrapped path |
| 14 | UVM flows keep direct freshness checks for reused RTL but only require current-flow outputs in runtime manifest `CURRENT` checks | `tests/test_vivado_integration_workflow.py::test_vivado_runner_covers_p0_3_release_gate_matrix` | CI/static | PASS | `ManifestCurrentArtifacts` asserted for smoke and coverage |
| 15 | Async FIFO runtime manifest declares UVM smoke and coverage WDB/report artifacts | `tests/test_agent.py::test_async_fifo_manifest_declares_uvm_flow_artifacts` | unit/contract | PASS | `9 passed in 0.85s` |

## Known Gaps

- The P0-3 gate has now passed against the local Vivado 2025.2 installation via
  the user-provided executable path. `vivado` is still not required to be present
  on `PATH` because the runner accepts `-VivadoPath` and `$env:VIVADO_EXECUTABLE`.
- The GitHub environment named `vivado-trusted-runner` must still be configured in
  repository settings with the intended reviewers/protection rules before the
  branch protection policy can rely on it.
- P0-3 now provides an auditable branch-protection ruleset source, but importing
  or applying that ruleset in GitHub remains a repository settings action outside
  this local codebase.
- SynthPilot remains intentionally ignored for this phase; the license device
  limit is still tracked in the P0-1 follow-up document.
