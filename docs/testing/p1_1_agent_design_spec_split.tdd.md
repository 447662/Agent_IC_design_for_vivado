# P1-1 Agent Design Spec Split TDD Evidence

## Source

No upgrade plan file was read for this work. This P1-1 slice was derived from
the current core-agent module shape and the active P1-1 acceptance criteria
requiring Agent core responsibilities to be split into focused modules.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want default design-spec rendering split out of
   `DigitalICAgent`, so the core Agent class keeps shrinking toward the P1-1
   module-size target.
2. As a workflow user, I want the no-tool-check/default design-spec path to keep
   generating the same `design_spec.md` artifact after the split.
3. As a reviewer, I want the new design-spec module included in quality and
   reproducibility gates, so the refactor remains covered by CI.

## Task Report

### RED - Missing Design Spec Module

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_design_spec.py --basetemp .tmp-pytest-p1-1-design-spec-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_agent_design_spec.py::test_default_design_spec_rendering_is_split_from_core_agent
AssertionError: assert False
where False = is_file()
where is_file = WindowsPath('F:/My_code/Agent_design_for_vivado/.trae/agent/agent_design_spec.py').is_file
1 failed in 0.06s
```

### GREEN Implementation

Implementation:

- Added `.trae/agent/agent_design_spec.py`.
- Moved default project slug generation, default design-spec Markdown rendering,
  and default design-spec file writing out of `DigitalICAgent`.
- Kept `DigitalICAgent.build_project_slug()`, `render_design_spec()`, and
  `generate_design_spec()` as compatibility wrappers.
- Added `agent_design_spec` to the legacy local preload list in
  `.trae/agent/agent.py`.
- Added the new module to mypy scope and tracked-runtime reproducibility checks.

Focused GREEN commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_design_spec.py --basetemp .tmp-pytest-p1-1-design-spec-green -p no:cacheprovider -q
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_agent.py::test_cli_no_tool_check_generates_design_spec_but_fails_without_rtl_execution tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools --basetemp .tmp-pytest-p1-1-design-spec-behavior -p no:cacheprovider -q
```

Results:

```text
1 passed in 0.04s
2 passed in 0.36s
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Default design-spec rendering is split into `.trae/agent/agent_design_spec.py` | `tests/test_p1_1_agent_design_spec.py::test_default_design_spec_rendering_is_split_from_core_agent` | architecture/unit | PASS | `1 passed in 0.04s` |
| 2 | Core Agent design-spec wrappers stay within the P1-1 function-size budget | `tests/test_p1_1_agent_design_spec.py::test_default_design_spec_rendering_is_split_from_core_agent` | architecture/unit | PASS | wrapper methods are each <= 20 lines |
| 3 | The default `--no-tool-check` design-spec path still writes `design_spec.md` | `tests/test_agent.py::test_cli_no_tool_check_generates_design_spec_but_fails_without_rtl_execution` | CLI/integration | PASS | Included in focused behavior run |
| 4 | Loaded skill execution still receives the generated design-spec path | `tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools` | behavior/unit | PASS | Included in focused behavior run |
| 5 | New design-spec module is included in mypy quality scope | `tests/test_quality_config.py::test_p1_1_agent_design_spec_is_in_mypy_scope` | quality/unit | PASS | Included in focused P1-1 run |
| 6 | New design-spec module is a tracked runtime architecture file | `tests/test_repository_reproducibility.py::test_required_runtime_and_architecture_files_are_tracked` | reproducibility/unit | PASS | Included in focused P1-1 run after staging |

## Verification

Focused P1-1 command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_cli_no_tool_check_generates_design_spec_but_fails_without_rtl_execution tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools --basetemp .tmp-pytest-p1-1-design-spec-focused -p no:cacheprovider -q
```

Result:

```text
28 passed in 2.28s
```

Quality commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

Results:

```text
All checks passed!
Success: no issues found in 59 source files
```

## Known Gaps

- P1-1 is not complete overall. `.trae/agent/agent.py` is smaller after this
  slice but still exceeds the target module-size budget.
- Larger target/report modules remain above the P1-1 size target, including
  async FIFO report/render/runtime modules, project overview, coverage closure,
  and target-specific renderers.

