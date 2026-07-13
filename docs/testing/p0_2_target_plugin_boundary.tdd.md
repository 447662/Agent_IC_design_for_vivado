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
3. As a plugin integrator, I want target plugins to receive only declared
   service facades, so they cannot reach the raw command runner or project root.
4. As a security reviewer, I want every plugin service denial to be structured,
   so unauthorized access attempts are auditable.
5. As an external plugin integrator, I want plugin search paths to load only
   manifest-listed and allowlisted modules without mutating global `sys.path`.
6. As a build operator, I want plugin service calls restricted to the current
   target output root, so a plugin cannot write outside the requested run
   directory.
7. As a security reviewer, I want manifest-backed third-party plugins to be
   represented by subprocess proxies, so module import side effects do not run
   in the main Agent process.
8. As a maintainer, I want external plugin subprocesses to reject direct command
   execution and root-directory reads/writes, so plugins cannot bypass declared
   service facades.

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

### Secure Plugin Boundary

`PluginServices` no longer exposes raw `CommandRunner`, unrestricted
`project_root`, or the parent agent object. Plugins receive only explicit
operation mappings plus `VivadoService`, `WaveformService`, and
`ArtifactService` facades. Calls to undeclared services raise
`PluginServiceDenied` and record a structured `plugin_service_denied` event.

Target handler execution now scopes plugin service paths to the active
`output_dir`. Direct or service-mediated attempts to write outside that output
root return `output_dir_outside_allowed_root`; attempts to read repository files
from a manifest-backed external plugin subprocess return
`read_outside_allowed_root`.

Manifest-backed external plugin discovery requires both a manifest and an
allowlist. The main process registers only a subprocess proxy factory; it does
not import the third-party plugin module. External plugin flow execution runs in
a child Python process with guarded file and command APIs. Attempts to call
`subprocess.*` or `os.system` from the external plugin return
`unauthorized_command`.

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

Additional P0-2 boundary command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py::test_external_target_plugins_require_manifest_allowlist tests/test_architecture_runtime.py::test_plugin_services_expose_only_explicit_operations tests/test_architecture_runtime.py::test_plugin_services_have_explicit_service_facades tests/test_architecture_runtime.py::test_plugin_service_rejects_output_dir_escape_during_target_run tests/test_architecture_runtime.py::test_target_plugin_discovery_search_path_does_not_mutate_sys_path tests/test_architecture_runtime.py::test_async_fifo_example_is_installed_by_plugin_not_core_agent_mixin tests/test_architecture_runtime.py::test_target_plugin_discovery_failure_does_not_partially_register_handlers --basetemp .tmp-pytest-p0-2-manifest-green -p no:cacheprovider -q
```

Result:

```text
7 passed in 0.40s
```

External plugin isolation command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py::test_manifest_external_plugin_subprocess_rejects_unauthorized_commands tests/test_architecture_runtime.py::test_manifest_external_plugin_subprocess_rejects_direct_file_escape tests/test_architecture_runtime.py::test_manifest_external_plugin_flow_runs_through_subprocess_proxy tests/test_architecture_runtime.py::test_manifest_external_plugins_are_not_imported_in_main_process --basetemp .tmp-pytest-p0-2-command-guard -p no:cacheprovider -q
```

Result:

```text
4 passed in 0.76s
```

Final P0-2 regression and lint command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p0-2-final -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent_runtime.py .trae/agent/target_flows.py .trae/agent/target_plugins.py .trae/agent/target_examples/async_fifo.py tests/test_architecture_runtime.py
```

Result:

```text
32 passed in 4.71s
All checks passed!
```

Latest confirmation on 2026-07-11 after deferring SynthPilot:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p0-2-confirm -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent_runtime.py .trae/agent/target_flows.py .trae/agent/target_plugins.py .trae/agent/target_examples/async_fifo.py tests/test_architecture_runtime.py
```

Result:

```text
33 passed in 4.39s
All checks passed!
```

Latest reconfirmation on 2026-07-11 after continuing to defer SynthPilot:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p0-2-reconfirm-now -p no:cacheprovider -q
```

Result:

```text
40 passed in 4.29s
```

Scoped Ruff reconfirmation:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/agent_runtime.py .trae/agent/target_flows.py .trae/agent/target_plugins.py tests/test_architecture_runtime.py tests/test_repository_reproducibility.py
```

Result:

```text
All checks passed!
```

Latest P0-2 verification on 2026-07-12 after explicitly deferring SynthPilot:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_architecture_runtime.py tests/test_repository_reproducibility.py --basetemp .tmp-pytest-p0-2-verify -p no:cacheprovider -q
```

Result:

```text
40 passed in 4.24s
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Failed target plugin discovery does not leave partially registered handlers in the live registry | `tests/test_architecture_runtime.py::test_target_plugin_discovery_failure_does_not_partially_register_handlers` | unit | PASS | `4 passed in 0.40s` |
| 2 | Duplicate, unknown, and mismatched handlers still raise explicit diagnostics | `tests/test_architecture_runtime.py::test_target_plugins_reject_duplicate_unknown_and_mismatched_handlers` | unit | PASS | `4 passed in 0.40s` |
| 3 | Valid plugin discovery still works without central target mapping | `tests/test_architecture_runtime.py::test_target_plugins_auto_discover_without_central_mapping` | unit | PASS | `4 passed in 0.40s` |
| 4 | Built-in target handlers still load through the explicit whitelist | `tests/test_architecture_runtime.py::test_builtin_target_handlers_use_explicit_module_whitelist` | integration | PASS | `4 passed in 0.40s` |
| 5 | Architecture and reproducibility regression coverage remains green | `tests/test_architecture_runtime.py tests/test_repository_reproducibility.py` | regression | PASS | `24 passed in 2.89s` |
| 6 | Plugin services do not expose raw `CommandRunner`, `project_root`, or the parent agent object | `tests/test_architecture_runtime.py::test_plugin_services_expose_only_explicit_operations` | security/unit | PASS | `7 passed in 0.40s` |
| 7 | Undeclared plugin service calls raise `PluginServiceDenied` and record structured denial events | `tests/test_architecture_runtime.py::test_plugin_services_expose_only_explicit_operations` | security/unit | PASS | `plugin_service_denied` event asserted |
| 8 | Plugin services expose explicit `VivadoService`, `WaveformService`, and `ArtifactService` facades | `tests/test_architecture_runtime.py::test_plugin_services_have_explicit_service_facades` | unit | PASS | `7 passed in 0.40s` |
| 9 | Plugin service calls cannot write outside the active target output root | `tests/test_architecture_runtime.py::test_plugin_service_rejects_output_dir_escape_during_target_run` | security/unit | PASS | `output_dir_outside_allowed_root` asserted |
| 10 | Search-path plugin discovery does not mutate global `sys.path` | `tests/test_architecture_runtime.py::test_target_plugin_discovery_search_path_does_not_mutate_sys_path` | security/unit | PASS | `sys.path` snapshot unchanged |
| 11 | External search-path plugins require a manifest and module allowlist | `tests/test_architecture_runtime.py::test_external_target_plugins_require_manifest_allowlist` | security/unit | PASS | `not allowlisted` rejection asserted |
| 12 | Manifest-backed external plugin modules are not imported in the main process | `tests/test_architecture_runtime.py::test_manifest_external_plugins_are_not_imported_in_main_process` | security/unit | PASS | import side-effect sentinel absent |
| 13 | Manifest-backed external plugin flows execute through a subprocess proxy | `tests/test_architecture_runtime.py::test_manifest_external_plugin_flow_runs_through_subprocess_proxy` | integration | PASS | subprocess marker written under allowed output root |
| 14 | External plugin subprocesses reject direct file read/write escapes | `tests/test_architecture_runtime.py::test_manifest_external_plugin_subprocess_rejects_direct_file_escape` | security/unit | PASS | `read_outside_allowed_root` and `output_dir_outside_allowed_root` asserted |
| 15 | External plugin subprocesses reject unauthorized command execution | `tests/test_architecture_runtime.py::test_manifest_external_plugin_subprocess_rejects_unauthorized_commands` | security/unit | PASS | `unauthorized_command` asserted |
| 16 | Final P0-2 architecture regression and Ruff checks are green | `tests/test_architecture_runtime.py tests/test_repository_reproducibility.py` plus Ruff | regression/quality | PASS | `40 passed in 4.29s`; `All checks passed!` |
| 17 | P0-2 remains green after SynthPilot is explicitly deferred for later completion | `tests/test_architecture_runtime.py tests/test_repository_reproducibility.py` | regression | PASS | `40 passed in 4.24s` |

## Known Gaps

- The real SynthPilot MCP `initialize -> tools/list -> tools/call` path remains
  blocked by license device limit and is intentionally not claimed as complete
  here.
- P0-2 is complete against the current repository test surface. The subprocess
  sandbox is a Python-level guard for this project, not an OS-level sandbox; a
  future hardening pass can replace it with a lower-level process policy if the
  external plugin threat model expands.
