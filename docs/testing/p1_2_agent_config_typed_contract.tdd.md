# P1-2 Agent Config Typed Contract TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
P1-2 requirement to replace generic dictionaries and `Any` with typed contracts,
starting with configuration because it feeds the entrypoint, plugin selection,
runtime capability checks, and artifact-producing flows.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want `load_agent_config()` to return a typed configuration
   contract, so callers no longer depend on a generic `dict[str, Any]`.
2. As a reviewer, I want skill actions to be restricted by a `Literal` union, so
   invalid action names are visible in the Python type surface.
3. As a release owner, I want the existing schema validation and quality gates
   to stay green while typing is introduced incrementally.

## Task Report

### RED Evidence

A new structure test was added to require exported typed contracts and a typed
`load_agent_config()` signature.

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_config_schema.py::test_agent_config_exposes_typed_contracts --basetemp .tmp-pytest-p1-2-config-types-red -p no:cacheprovider -q
```

Result:

```text
1 failed in 0.10s
```

The failure was the intended RED signal: `load_agent_config()` still accepted
`config_path: Any` and returned `dict[str, Any]`.

### GREEN Evidence

`agent_config.py` now exports typed configuration contracts:

- `SkillAction = Literal["design-document", "rtl-implementation", "verification-plan"]`
- `ConfiguredCommand = str | list[str]`
- `SkillConfig`, `MCPServerConfig`, `CLIToolConfig`, `WorkflowConfig`,
  `RequirementAnalysisConfig`, and `AgentConfig` as `TypedDict` contracts
- `load_agent_config(config_path: str | Path) -> AgentConfig`

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_config_schema.py::test_agent_config_exposes_typed_contracts --basetemp .tmp-pytest-p1-2-config-types-green-2 -p no:cacheprovider -q; uv run --offline --frozen mypy .trae/agent/agent_config.py
```

Result:

```text
1 passed in 0.07s
Success: no issues found in 1 source file
```

### Regression Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_config_schema.py tests/test_quality_config.py tests/test_agent.py::test_config_helpers_live_in_dedicated_module tests/test_agent.py::test_config_uses_portable_synthpilot_command tests/test_agent.py::test_cli_check_commands_are_arrays --basetemp .tmp-pytest-p1-2-config-types-regression -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent_config.py tests/test_config_schema.py; uv run --offline --frozen mypy
```

Result:

```text
28 passed in 0.42s
All checks passed!
Success: no issues found in 60 source files
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | `load_agent_config()` accepts `str | Path` and returns `AgentConfig` | `tests/test_config_schema.py::test_agent_config_exposes_typed_contracts` | structure/unit | PASS | `1 passed in 0.07s` |
| 2 | Skill actions are restricted by a `Literal` union | `tests/test_config_schema.py::test_agent_config_exposes_typed_contracts` | structure/unit | PASS | `SkillAction` args asserted |
| 3 | Agent config exposes typed top-level fields through `TypedDict` | `tests/test_config_schema.py::test_agent_config_exposes_typed_contracts` | structure/unit | PASS | `AgentConfig.__annotations__` asserted |
| 4 | Existing config schema validation remains compatible | `tests/test_config_schema.py` | regression | PASS | included in `28 passed in 0.42s` |
| 5 | Config helpers remain covered by Ruff and Mypy | quality command above | quality/typecheck | PASS | Ruff PASS, Mypy PASS |

## Known Gaps

- This is the first P1-2 typed slice. It does not yet satisfy the full P1-2
  acceptance criteria of reducing `Any` by at least 80%, raising coverage to
  85%, or enabling the full Ruff `I/B/UP/SIM/C90` rule set.
- The next P1-2 slices should continue through entrypoint, plugin boundary,
  runtime facade, and artifact contract types before tightening global gates.
