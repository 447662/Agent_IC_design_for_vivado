# P1-1 Target Mixin Decoupling TDD Evidence

## Source

No upgrade plan file was read for this work. The scope came from the active
P1-1 requirement: `DigitalICAgent` must not inherit target-specific mixins while
existing CLI and target plugin behavior remain compatible.

## User Journeys

1. As a maintainer, I want sync FIFO and round-robin arbiter implementation
   methods outside the core Agent inheritance chain, so target-specific logic
   can continue migrating into the plugin system.
2. As an existing CLI user, I want `--generate-rtl`, `--sim-rtl`,
   `--analyze-rtl-vcd`, `--check-rtl`, and `--open-wave` to keep dispatching
   through the same target handlers after the core class is decoupled.
3. As a release reviewer, I want the new service host covered by mypy and the
   tracked-runtime snapshot gate, so the decoupling module cannot be omitted
   from quality and reproducibility checks.

## Task Report

`DigitalICAgent` previously inherited `SyncFifoMixin` and
`RoundRobinArbiterMixin`, which kept two target implementations attached to the
core Agent class. This slice introduces `TargetServiceHost`, a small
composition object that owns those legacy service methods while delegating
shared Agent capabilities such as Vivado execution, waveform analysis, report
rendering, and RTL project checks back to the Agent.

`target_flows.build_plugin_services()` now resolves declared plugin operations
from `agent.target_services` first and falls back to Agent-level shared
operations. The sync FIFO and round-robin handlers still receive the same
service names, but `DigitalICAgent` no longer imports or inherits the target
mixins directly.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py::test_sync_fifo_and_arbiter_are_installed_by_plugins_not_core_agent_mixins --basetemp .tmp-pytest-p1-1-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_architecture_runtime.py::test_sync_fifo_and_arbiter_are_installed_by_plugins_not_core_agent_mixins
AssertionError: assert 'agent_sync_fifo' not in imported_modules
1 failed in 0.16s
```

## GREEN Evidence

Focused command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py::test_sync_fifo_and_arbiter_are_installed_by_plugins_not_core_agent_mixins --basetemp .tmp-pytest-p1-1-green -p no:cacheprovider -q
```

Focused result:

```text
1 passed in 0.12s
```

Regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p1-1-arch -p no:cacheprovider -q
```

Regression result:

```text
33 passed in 3.77s
```

Lint command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/agent.py .trae/agent/target_flows.py .trae/agent/target_service_host.py tests/test_architecture_runtime.py
```

Lint result:

```text
All checks passed!
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | `DigitalICAgent` no longer imports `agent_sync_fifo` or `agent_round_robin_arbiter` directly | `tests/test_architecture_runtime.py::test_sync_fifo_and_arbiter_are_installed_by_plugins_not_core_agent_mixins` | architecture/static | PASS | `1 passed in 0.12s` |
| 2 | `DigitalICAgent` no longer inherits `SyncFifoMixin` or `RoundRobinArbiterMixin` | `tests/test_architecture_runtime.py::test_sync_fifo_and_arbiter_are_installed_by_plugins_not_core_agent_mixins` | architecture/static | PASS | base-class assertions passed |
| 3 | Sync FIFO and round-robin arbiter handlers still exist and dispatch through target handlers | `tests/test_architecture_runtime.py::test_sync_fifo_and_arbiter_are_installed_by_plugins_not_core_agent_mixins` | integration/static | PASS | handler assertions passed |
| 4 | The core Agent no longer exposes `write_sync_fifo_project` or `write_round_robin_arbiter_project` methods | `tests/test_architecture_runtime.py::test_sync_fifo_and_arbiter_are_installed_by_plugins_not_core_agent_mixins` | architecture/static | PASS | forbidden method assertions passed |
| 5 | Architecture and reproducibility regression remains green | `tests/test_architecture_runtime.py tests/test_repository_reproducibility.py` | regression | PASS | `33 passed in 3.77s` |
| 6 | Changed files pass Ruff | Ruff command above | lint | PASS | `All checks passed!` |

## Known Gaps

- This is a P1-1 slice, not the full `src/digital_ic_agent/` migration. The
  package-layout migration, `sys.path.insert()` removal, report-template split,
  and module-size limits remain active P1-1 follow-up work.
- `TargetServiceHost` intentionally keeps the legacy sync FIFO and arbiter
  mixin code alive behind composition so behavior stays compatible while the
  larger package migration proceeds.
