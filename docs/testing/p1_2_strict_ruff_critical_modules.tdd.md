# P1-2 Strict Ruff Critical Modules TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
P1-2 requirement to enable Ruff `I/B/UP/SIM/C90` rules while avoiding a single
large mechanical rewrite. This slice applies the expanded rule set to the typed
configuration, artifact manifest, and core Agent execution contract modules
already being hardened in P1-2.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a maintainer, I want newly typed critical modules to satisfy the expanded
   Ruff rule families, so P1-2 quality gates can be raised incrementally.
2. As a reviewer, I want the strict Ruff scope to fail before cleanup and pass
   after cleanup, so the rule expansion has concrete evidence.
3. As a release owner, I want behavior tests and Mypy to stay green after style
   modernization.

## Task Report

### RED Evidence

The selected P1-2 critical modules were checked with the expanded Ruff rule
families:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/agent_contracts.py .trae/agent/agent_config.py .trae/agent/artifact_manifest.py .trae/agent/agent_provider.py .trae/agent/agent_skill_tool.py tests/test_p1_2_*.py --select I,B,UP,SIM,C90 --statistics
```

Result:

```text
23 UP032 f-string
5 I001 unsorted-imports
4 UP038 non-pep604-isinstance
2 UP017 datetime-timezone-utc
1 UP035 deprecated-import
Found 35 errors.
```

This was the intended RED signal for the strict Ruff slice.

### GREEN Evidence

The modules were modernized with sorted imports, f-strings, `datetime.UTC`,
`collections.abc.Mapping`, and PEP 604 `isinstance` unions.

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/agent_contracts.py .trae/agent/agent_config.py .trae/agent/artifact_manifest.py .trae/agent/agent_provider.py .trae/agent/agent_skill_tool.py tests/test_p1_2_*.py --select I,B,UP,SIM,C90; uv run --offline --frozen pytest tests/test_p1_2_agent_contracts_typed_payloads.py tests/test_p1_2_artifact_manifest_typed_contract.py tests/test_config_schema.py::test_agent_config_exposes_typed_contracts tests/test_agent_execution.py tests/test_architecture_runtime.py::test_default_document_workflow_executes_loaded_skill_without_external_tools tests/test_architecture_runtime.py::test_default_document_workflow_records_real_agent_run tests/test_architecture_runtime.py::test_workflow_rejects_empty_skill_selection tests/test_architecture_runtime.py::test_default_rtl_and_verification_skills_do_not_report_success tests/test_architecture_runtime.py::test_workflow_rejects_partial_result_from_custom_executor --basetemp .tmp-pytest-p1-2-strict-ruff-slice -p no:cacheprovider -q; uv run --offline --frozen mypy
```

Result:

```text
All checks passed!
28 passed in 2.47s
Success: no issues found in 60 source files
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Selected P1-2 config, artifact, and execution contract modules satisfy `I/B/UP/SIM/C90` | strict Ruff command above | quality/lint | PASS | `All checks passed!` |
| 2 | P1-2 typed contract tests remain green after Ruff modernization | `tests/test_p1_2_*.py` subset | structure/unit | PASS | included in `28 passed in 2.47s` |
| 3 | Agent execution workflow behavior remains compatible | selected `tests/test_agent_execution.py` and workflow tests | regression | PASS | included in `28 passed in 2.47s` |
| 4 | Full Mypy scope remains green | `uv run --offline --frozen mypy` | typecheck | PASS | `Success: no issues found in 60 source files` |

## Known Gaps

- This slice does not yet enable `I/B/UP/SIM/C90` globally in `pyproject.toml`.
  A full-repository precheck still reports hundreds of legacy findings, so the
  rule families should continue to roll out module-by-module.
- This slice does not yet satisfy the full P1-2 acceptance criteria of reducing
  `Any` by at least 80%, raising total coverage to 85%, or setting independent
  per-module coverage thresholds.
