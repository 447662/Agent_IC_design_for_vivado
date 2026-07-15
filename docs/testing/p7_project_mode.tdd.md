# P7 Vivado Project Mode TDD

## Scope

Add a deterministic `verify --vivado-launch-mode direct|project` contract while
keeping `direct` as the backward-compatible default. Project mode is eligible
only after canonical diagnosis reports `SIMULATION_ENGINE_LAUNCH_BLOCKED`; it
must not weaken artifact, freshness, coverage, iteration, or no-progress gates.

## RED

- Added parser and machine-CLI tests that required the new launch-mode option.
- Added project-mode verification tests that required one `vivado.bat -mode
  batch` invocation and exactly one `launch_simulation` command.
- Added fail-closed tests for missing Vivado tools, compile failure, absent
  coverage reports, stopped iterations, and simulation-engine launch blocking.
- Added tests requiring compile, elaborate, simulate, WDB, coverage database,
  xcrg report, canonical verdict, iteration record, and manifest lineage.

The tests initially failed because generic verification only knew the direct
`xvlog`/`xelab`/`xsim` path and did not accept or record a launch mode.

## GREEN

- Added `--vivado-launch-mode direct|project` to the machine command contract.
- Kept direct mode unchanged as the default.
- Added isolated Vivado project generation through `vivado.bat -mode batch`.
- Generated Tcl with one `launch_simulation`, explicit source ordering, include
  directories, UVM flags, timescale, runtime, and coverage configuration.
- Copied project-generated compile, elaborate, simulate, WDB, coverage, and xcrg
  evidence into the canonical iteration layout.
- Added exact `SIMULATION_ENGINE_LAUNCH_BLOCKED` classification and actionable
  diagnostics without changing Smart App Control, WDAC, or Defender.

## REFACTOR

- Moved Vivado tool resolution, Tcl rendering, and project artifact helpers to
  `generic_verification_vivado.py`.
- Kept `generic_verification.py` below the runtime migration size limit.
- Added both runtime modules to the migration manifest.
- Added strict summary count normalization so JSON totals cannot contain Boolean
  values through Python's `bool`-is-`int` behavior.

## Evidence

| Check | Evidence | Result |
| --- | --- | --- |
| Edge detector project mode | `.tmp/p7-project-smoke-edge-20260715-002` | PASS |
| APB UVM project mode | `.tmp/p7-project-smoke-apb-20260715-001` | PASS |
| Vivado version | iteration `tool_version` | 2025.2 (64-bit) |
| Project invocation | iteration `commands` | one Vivado batch command |
| Simulation launch | generated Tcl and tests | exactly one |
| Edge code coverage gates | canonical iteration JSON | all PASS |
| APB code and functional gates | canonical iteration JSON | all PASS |
| Repair evaluation | `docs/testing/evidence/p7_real_eval_summary.json` | 10/10 PASS |
| Generation evaluation | same summary | 10/10 PASS |
| Contract-negative evaluation | same summary | 10/10 PASS, no Vivado call |
| Full regression | `.tmp/final-quality-p7-20260715-007` | 676 PASS |

No system security control was disabled or bypassed during implementation or
verification.
