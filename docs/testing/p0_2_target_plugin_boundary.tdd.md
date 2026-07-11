# P0-2 Target Plugin Boundary TDD Evidence

## Source

No upgrade plan file was read for this work. The P0-2 scope was derived from the
current runtime architecture and existing tests around target handler plugins,
`PluginServices`, and target flow dispatch.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want target plugin discovery to fail atomically, so that a
   bad plugin package cannot leave partially registered handlers in memory.
2. As an integrator, I want failed plugin discovery to be recoverable, so that
   later valid discovery/build attempts start from a clean registry state.

## Task Report

### Atomic Plugin Discovery

The plugin loader previously registered modules directly into the live
`TargetHandlerRegistry` while iterating. If a later module failed validation,
the earlier modules remained registered even though the discovery operation as a
whole failed.

Implementation:

- `load_target_handler_plugins` now imports and validates candidate plugin
  modules first.
- Registrations are staged in a temporary registry copied from the current live
  registry.
- The live registry is replaced only after the entire batch registers
  successfully.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py::test_target_plugin_discovery_failure_does_not_partially_register_handlers --basetemp .tmp-pytest-p0-2-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_architecture_runtime.py::test_target_plugin_discovery_failure_does_not_partially_register_handlers
AssertionError: assert ('first-handler',) == ()
1 failed in 0.24s
```

## GREEN Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py::test_target_plugin_discovery_failure_does_not_partially_register_handlers tests/test_architecture_runtime.py::test_target_plugins_reject_duplicate_unknown_and_mismatched_handlers tests/test_architecture_runtime.py::test_target_plugins_auto_discover_without_central_mapping tests/test_architecture_runtime.py::test_builtin_target_handlers_use_explicit_module_whitelist --basetemp .tmp-pytest-p0-2-green -p no:cacheprovider -q
```

Result:

```text
4 passed in 0.40s
```

Regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p0-2-arch -p no:cacheprovider -q
```

Result:

```text
24 passed in 2.89s
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Failed target plugin discovery does not leave partially registered handlers in the live registry | `tests/test_architecture_runtime.py::test_target_plugin_discovery_failure_does_not_partially_register_handlers` | unit | PASS | `4 passed in 0.40s` |
| 2 | Duplicate, unknown, and mismatched handlers still raise explicit diagnostics | `tests/test_architecture_runtime.py::test_target_plugins_reject_duplicate_unknown_and_mismatched_handlers` | unit | PASS | `4 passed in 0.40s` |
| 3 | Valid plugin discovery still works without central target mapping | `tests/test_architecture_runtime.py::test_target_plugins_auto_discover_without_central_mapping` | unit | PASS | `4 passed in 0.40s` |
| 4 | Built-in target handlers still load through the explicit whitelist | `tests/test_architecture_runtime.py::test_builtin_target_handlers_use_explicit_module_whitelist` | integration | PASS | `4 passed in 0.40s` |
| 5 | Architecture and reproducibility regression coverage remains green | `tests/test_architecture_runtime.py tests/test_repository_reproducibility.py` | regression | PASS | `24 passed in 2.89s` |

## Known Gaps

- The real SynthPilot MCP `initialize -> tools/list -> tools/call` path remains
  blocked by license device limit and is intentionally not claimed as complete
  here.
- This P0-2 increment hardens plugin discovery atomicity. Further P0-2 work can
  continue with additional plugin-contract checks if required.

