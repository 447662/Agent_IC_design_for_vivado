# P1-1 Agent Skill Listing Split TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
current P1-1 modularization target and the remaining direct responsibilities in
`.trae/agent/agent.py`.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want skill path resolution to live outside the core Agent
   class, so diagnostics can reuse it without expanding `DigitalICAgent`.
2. As a CLI user, I want `--list-skills` output to remain compatible after the
   module split.
3. As a workflow user, I want skill recommendation behavior to stay unchanged
   while the display logic moves out of `agent.py`.
4. As a refactoring reviewer, I want the core Agent methods to delegate to a
   dedicated module rather than directly formatting skill listing output.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_skill_listing.py --basetemp .tmp-pytest-p1-1-skill-listing-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_agent_skill_listing.py::test_agent_skill_listing_is_split_from_core_agent
AssertionError: assert False
1 failed in 0.10s
```

The failure confirmed that `.trae/agent/agent_skill_listing.py` did not exist
and `DigitalICAgent` still owned skill listing output directly.

## GREEN Evidence

Focused command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_skill_listing.py tests/test_agent.py::test_cli_list_skills_succeeds tests/test_p1_1_agent_diagnostics.py --basetemp .tmp-pytest-p1-1-skill-listing-green -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/agent.py .trae/agent/agent_skill_listing.py tests/test_p1_1_agent_skill_listing.py
```

Result:

```text
3 passed in 0.25s
All checks passed!
```

P1-1 focused regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py tests/test_agent.py::test_cli_list_skills_succeeds --basetemp .tmp-pytest-p1-1-skill-listing-focused -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent src tests/test_p1_1_agent_skill_listing.py tests/test_p1_1_agent_target_flow.py tests/test_p1_1_agent_waveform_analysis.py tests/test_p1_1_agent_sim_smoke.py tests/test_p1_1_agent_design_spec.py tests/test_p1_1_agent_diagnostics.py tests/test_p1_1_cli_dispatch.py tests/test_p1_1_package_layout.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py; uv run --offline --frozen mypy
```

Result:

```text
32 passed in 2.49s
All checks passed!
Success: no issues found in 60 source files
```

Syntax check:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen python -m py_compile .trae/agent/agent.py .trae/agent/agent_skill_listing.py
```

Result:

```text
passed
```

## Implementation Notes

- Added `.trae/agent/agent_skill_listing.py`.
- Moved `resolve_skill_path`, `list_skills`, and `recommend_skills` behavior
  behind module-level operations.
- Kept `DigitalICAgent` public methods as compatibility delegates.
- Preserved existing CLI `--list-skills` behavior.
- Reduced `.trae/agent/agent.py` from 904 to 894 lines.

## Acceptance Mapping

| Requirement | Evidence |
| --- | --- |
| Skill listing responsibility is split from core Agent | `tests/test_p1_1_agent_skill_listing.py::test_agent_skill_listing_is_split_from_core_agent` |
| CLI skill listing remains compatible | `tests/test_agent.py::test_cli_list_skills_succeeds` |
| Diagnostics still resolve skill paths through Agent facade | `tests/test_p1_1_agent_diagnostics.py` |
| P1-1 focused surface remains GREEN | `32 passed in 2.49s`; Ruff and Mypy zero errors |

## Status

This P1-1 slice is complete. The wider P1-1 requirement remains open because
`.trae/agent/agent.py` is still above the preferred 600-line target and several
target/report modules remain oversized.
