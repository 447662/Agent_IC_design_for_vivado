# Agent Skill Runtime Hardening TDD Evidence

## Scope

The user journeys for this change were derived from the implementation request:

1. A configured RTL target can run through the default skill loop and return
   validator-approved RTL and testbench artifacts.
2. A UVM request runs the target UVM flow when prerequisites are available, or
   returns a validated verification plan as a partial result when they are not.
3. SynthPilot license failure is represented consistently as optional-capability
   degradation rather than a required-capability failure.
4. An external target plugin cannot run forever and reports timeout failures as
   structured `ToolExecutionError` data.
5. The touched skill and legacy facade boundaries contain no `Any` annotations.
6. External `search_path` plugins are rejected before import unless both a
   manifest and explicit allowlist are supplied.
7. CLI waveform, simulation smoke, and capability-preflight failures return a
   stable user-visible error instead of a traceback.
8. MCP protocol, timeout, and process failures remain visible in failed tool
   results and the enclosing agent-run failure reason.
9. Runtime Python files are valid UTF-8 and do not contain runs of question-mark
   replacement placeholders.
10. CI and the documented local gate lint and measure the same runtime sources.

## RED Evidence

Command:

```text
uv --cache-dir .tmp/uv-cache run --frozen pytest tests/test_skill_target_execution.py tests/test_synthpilot_semantics.py tests/test_external_plugin_timeout.py::test_external_plugin_subprocess_passes_timeout_and_raises_structured_error tests/test_quality_config.py::test_priority_type_boundaries_have_explicit_any_budgets --basetemp .tmp-pytest-skill-loop-red -p no:cacheprovider -q
```

Result: `6 failed in 0.84s`. The failures showed the old `BLOCKED` skill
results, required SynthPilot configuration, missing plugin timeout, and the old
`Any` budgets.

The follow-up hardening cycles captured these additional RED results:

| Boundary | RED result | Intended failure |
| --- | ---: | --- |
| External plugin discovery | `2 failed, 24 passed` | Missing manifest/allowlist was accepted |
| User-visible runtime failures | `5 failed, 45 passed` | CLI/workflow exceptions escaped and `???` placeholders remained |
| Priority type boundaries | `1 failed` | CLI/workflow/public package contained `45/9/3` `Any` references |
| CI/local scope parity | `1 failed` | CI omitted public package and scripts from quality scope |

## GREEN Evidence

Focused results included `29 passed` for plugin isolation, `50 passed` for
runtime failure paths, and `11 passed` for typed CLI/workflow boundaries.

Related regression result: `54 passed in 2.51s`.

Final quality gates:

```text
ruff: All checks passed!
mypy: Success: no issues found in 65 source files
pytest: 432 passed in 57.88s
coverage: 87.12% (required minimum: 85.0%)
```

No checkpoint commit was created because the task started from a user-owned
dirty worktree and the user did not request commits. RED/GREEN evidence is
preserved here and in the named tests instead.

## Guarantees

| Guarantee | Evidence | Type |
| --- | --- | --- |
| Default sync-fifo RTL skill generates non-empty RTL/TB and passes `SkillResultValidator` | `tests/test_skill_target_execution.py` | Integration |
| Missing Vivado yields a validated `verification_plan.md` partial result | `tests/test_skill_target_execution.py` | Integration |
| Successful UVM flow requires UVM source, log, report, and successful tool record | `tests/test_skill_target_execution.py` | Integration |
| SynthPilot is optional in config, preflight, diagnostic, and failure evidence | `tests/test_synthpilot_semantics.py` | Contract |
| A dead-loop external plugin is terminated and returns structured timeout data | `tests/test_external_plugin_timeout.py` | Integration |
| Normal target-flow recording preserves the plugin timeout reason and stage | `tests/test_external_plugin_timeout.py` | Integration |
| Skill execution and legacy facade modules have zero `Any` budget | `tests/test_quality_config.py` | Static contract |
| External search paths require manifest plus allowlist and do not import in the main process | `tests/test_plugin_security_boundary.py` | Security contract |
| CLI waveform and sim-smoke exceptions become stable exit code 1 failures | `tests/test_agent_cli_failure_paths.py` | Integration |
| Capability preflight configuration failures are reported without a traceback | `tests/test_agent_workflow_contract.py` | Integration |
| MCP protocol/timeout/process errors survive into failed tool results | `tests/test_agent_execution.py` | Integration |
| Runtime source has valid UTF-8 and no `???` replacement runs | `tests/test_project_text_encoding.py` | Static contract |
| CLI dispatch, workflow, and public package wrapper have zero `Any` budget | `tests/test_quality_config.py` | Static contract |
| CI and local gates cover `.trae/agent`, tests, public package, and scripts | `tests/test_quality_config.py` | CI contract |

## Known Gap

The successful UVM branch is validator-tested with an injected target-flow
result. A physical Vivado UVM smoke run was intentionally not started in this
change, and no GUI process was launched.
