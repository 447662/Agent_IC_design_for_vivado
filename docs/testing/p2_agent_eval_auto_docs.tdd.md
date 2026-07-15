# P2 Agent Evaluation and Auto Documentation

## Scope

- Establish generated quality documentation from pytest JUnit XML and coverage XML artifacts.
- Keep README status inside a marker-delimited generated block instead of hand-maintained test counts or coverage percentages.
- Generate a capability matrix from repository evaluation fixtures.
- Continue splitting large test modules by domain without deleting original blocks until explicit deletion approval is given.

## Completed Evidence

| Item | Evidence | Result |
| --- | --- | --- |
| README no longer carries stale manual or volatile local test/coverage statistics | `tests/test_p2_auto_quality_docs.py::test_p2_readme_uses_generated_quality_block_without_stale_stats` requires a generated PASS/FAIL result and rejects local counts, runtime, and coverage rows | PASS |
| CI produces JUnit XML and coverage XML for documentation input | `.github/workflows/python-quality.yml` includes `--junitxml .tmp/pytest-results.xml` and `--cov-report=xml:coverage.xml` | PASS |
| CI invokes the auto-documentation generator | `.github/workflows/python-quality.yml` invokes `scripts/generate_quality_summary.py --write-readme` | PASS |
| CI verifies generated reports before upload | `.github/workflows/python-quality.yml` runs `test -s` checks for generated docs, coverage XML, and JUnit XML | PASS |
| CI uploads generated quality artifacts for review | `.github/workflows/python-quality.yml` uses pinned `actions/upload-artifact` with `docs/generated`, `coverage.xml`, and `.tmp/pytest-results.xml` | PASS |
| CI preserves reports from failed test runs without masking the quality failure | All three generators, report verification, and artifact upload use `if: ${{ !cancelled() }}` while the pytest step remains a normal failing gate | PASS |
| Generator writes `docs/generated/quality_summary.md` and `docs/generated/capability_matrix.md` | `tests/test_p2_auto_quality_docs.py::test_p2_quality_summary_generator_updates_readme_from_test_artifacts` | PASS |
| Quality generator rejects missing or insufficient evaluation fixtures | `tests/test_p2_auto_quality_docs.py::test_p2_quality_summary_rejects_missing_or_insufficient_eval_fixtures` covers missing routing data, fewer than 50 routing cases, and missing agent eval data | PASS |
| Routing evaluation fixture remains implementation-decoupled | `tests/fixtures/agent_routing_cases.json` currently has 60 cases; generated matrix references it directly | PASS |
| P2 eval fixture covers tool selection, failure handling, artifact authenticity, and multi-target consistency | `tests/test_p2_agent_eval_cases.py` | PASS |
| P2 eval fixture produces a machine-readable report for CI consumption | `tests/test_p2_agent_eval_report.py` and `scripts/generate_agent_eval_report.py` | PASS |
| Test module size report verifies the P2 1,000-line target | `docs/generated/test_module_report.json` records 69 modules, 0 over-limit modules, and a largest module of 820 lines | PASS |
| Test module report detects future over-limit and unmigrated tests through AST | `tests/test_p2_test_module_report.py` covers both unfinished module and unmigrated test reporting | PASS |
| Legacy aggregate test modules are fully removed after domain migration | `tests/test_agent.py` and `tests/test_architecture_runtime.py` are absent; generated split candidates and deletion verification are empty | PASS |
| Test module report has no pending migration work | `unfinished_items`, `unmigrated_tests`, `split_candidates`, and `deletion_verification` are all empty | PASS |
| Target registry/scaffolder tests have an independent domain module | `tests/test_target_registry_scaffolder.py` runs independently with 9 passing tests | PASS |
| Plugin security boundary tests have an independent domain module | `tests/test_plugin_security_boundary.py` runs independently with 10 passing tests | PASS |
| Target plugin registry/discovery tests have an independent domain module | `tests/test_target_plugin_registry.py` runs independently with 10 passing tests | PASS |
| Async FIFO plugin contract tests have an independent domain module | `tests/test_async_fifo_plugin_contract.py` runs independently with 4 passing tests | PASS |
| Environment report tests have an independent domain module | `tests/test_environment_report.py` runs independently with 6 passing tests | PASS |
| Project overview tests have an independent domain module | `tests/test_project_overview.py` runs independently with 7 passing tests | PASS |
| Artifact manifest tests have an independent domain module | `tests/test_artifact_manifest.py` runs independently with 14 passing tests | PASS |
| Target dashboard tests have an independent domain module | `tests/test_target_dashboard.py` runs independently with 5 passing tests | PASS |
| XCRG coverage parser tests have an independent domain module | `tests/test_xcrg_coverage.py` runs independently with 3 passing tests | PASS |
| Coverage closure tests have an independent domain module | `tests/test_coverage_closure.py` runs independently with 8 passing tests | PASS |
| Coverage recommendation tests have an independent domain module | `tests/test_coverage_recommendations.py` runs independently with 4 passing tests | PASS |
| Waveform sample tests have an independent domain module | `tests/test_waveform_samples.py` runs independently with 6 passing tests | PASS |
| Coverage history tests have an independent domain module | `tests/test_coverage_history.py` runs independently with 5 passing tests | PASS |
| Failure archive tests have an independent domain module | `tests/test_failure_archive.py` runs independently with 3 passing tests | PASS |
| Wave visibility tests have an independent domain module | `tests/test_wave_visibility.py` runs independently with 7 passing tests | PASS |
| Agent adapter tests have an independent domain module | `tests/test_agent_adapters.py` runs independently with 3 passing tests | PASS |
| UVM coverage summary tests have an independent domain module | `tests/test_uvm_coverage_summary.py` runs independently with 6 passing tests | PASS |
| UVM coverage runtime tests have an independent domain module | `tests/test_uvm_coverage_runtime.py` runs independently with 11 passing tests | PASS |
| UVM smoke/regression tests have an independent domain module | `tests/test_uvm_smoke_regression.py` runs independently with 6 passing tests | PASS |
| Async FIFO RTL flow tests have an independent domain module | `tests/test_async_fifo_rtl_flow.py` runs independently with 11 passing tests | PASS |
| Async FIFO VCD analysis tests have an independent domain module | `tests/test_async_fifo_vcd_analysis.py` runs independently with 6 passing tests | PASS |
| Async FIFO reports tests have an independent domain module | `tests/test_async_fifo_reports.py` runs independently with 6 passing tests | PASS |
| Async FIFO UVM wave tests have an independent domain module | `tests/test_async_fifo_uvm_wave.py` runs independently with 4 passing tests | PASS |
| Agent runtime boundary tests have an independent domain module | `tests/test_agent_runtime_boundaries.py` runs independently with 11 passing tests | PASS |
| Agent CLI routing tests have an independent domain module | `tests/test_agent_cli_routing.py` runs independently with 14 passing tests | PASS |
| Agent sim smoke runtime tests have an independent domain module | `tests/test_agent_sim_smoke_runtime.py` runs independently with 11 passing tests | PASS |
| Agent Vivado diagnostics have an independent domain module | `tests/test_agent_vivado_diagnostics.py` runs independently with 3 passing tests | PASS |
| Agent waveform runtime tests have an independent domain module | `tests/test_agent_waveform_runtime.py` runs independently with 5 passing tests | PASS |
| Project text encoding tests have an independent domain module | `tests/test_project_text_encoding.py` runs independently with 1 passing test | PASS |
| Project documentation status tests have an independent domain module | `tests/test_project_documentation_status.py` runs independently with 1 passing test | PASS |
| Target registry runtime tests have an independent domain module | `tests/test_target_registry_runtime.py` runs independently with 6 passing tests | PASS |
| Target report rendering tests have an independent domain module | `tests/test_target_report_rendering.py` runs independently with 5 passing tests | PASS |
| Sync FIFO and round-robin RTL flow generation tests have an independent domain module | `tests/test_sync_fifo_round_robin_rtl_flow.py` runs independently with 4 passing tests | PASS |
| Sync FIFO and round-robin runtime tests have an independent domain module | `tests/test_sync_fifo_round_robin_runtime.py` runs independently with 6 passing tests | PASS |
| Sync FIFO and round-robin VCD analysis tests have an independent domain module | `tests/test_sync_fifo_round_robin_vcd_analysis.py` runs independently with 5 passing tests | PASS |
| Skill runtime contract tests have an independent domain module | `tests/test_skill_runtime_contract.py` runs independently with 6 passing tests | PASS |
| Target flow runtime tests have an independent domain module | `tests/test_target_flow_runtime.py` runs independently with 1 passing test | PASS |
| Agent workflow contract tests have an independent domain module | `tests/test_agent_workflow_contract.py` runs independently with 6 passing tests | PASS |

## Verification Commands

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'
uv run --offline --frozen pytest tests/test_p2_auto_quality_docs.py tests/test_quality_config.py --basetemp .tmp-pytest-p2-quality-gates-2 -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_p2_agent_eval_cases.py --basetemp .tmp-pytest-p2-agent-eval-cases -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_p2_agent_eval_report.py --basetemp .tmp-pytest-p2-agent-eval-report -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_p2_test_module_report.py --basetemp .tmp-pytest-p2-test-module-report -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_target_registry_scaffolder.py --basetemp .tmp-pytest-p2-target-registry-split-2 -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_plugin_security_boundary.py --basetemp .tmp-pytest-p2-plugin-security-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_target_plugin_registry.py --basetemp .tmp-pytest-p2-target-plugin-registry-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_async_fifo_plugin_contract.py --basetemp .tmp-pytest-p2-async-fifo-plugin-contract-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_environment_report.py --basetemp .tmp-pytest-p2-environment-report-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_project_overview.py --basetemp .tmp-pytest-p2-project-overview-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_artifact_manifest.py --basetemp .tmp-pytest-p2-artifact-manifest-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_target_dashboard.py --basetemp .tmp-pytest-p2-target-dashboard-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_xcrg_coverage.py --basetemp .tmp-pytest-p2-xcrg-coverage-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_coverage_closure.py --basetemp .tmp-pytest-p2-coverage-closure-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_coverage_recommendations.py --basetemp .tmp-pytest-p2-coverage-recommendations-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_waveform_samples.py --basetemp .tmp-pytest-p2-waveform-samples-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_coverage_history.py --basetemp .tmp-pytest-p2-coverage-history-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_failure_archive.py --basetemp .tmp-pytest-p2-failure-archive-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_wave_visibility.py --basetemp .tmp-pytest-p2-wave-visibility-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_agent_adapters.py --basetemp .tmp-pytest-p2-agent-adapters-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_uvm_coverage_summary.py --basetemp .tmp-pytest-p2-uvm-coverage-summary-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_uvm_coverage_runtime.py --basetemp .tmp-pytest-p2-uvm-coverage-runtime-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_uvm_smoke_regression.py --basetemp .tmp-pytest-p2-uvm-smoke-regression-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_async_fifo_rtl_flow.py --basetemp .tmp-pytest-p2-async-fifo-rtl-flow-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_async_fifo_vcd_analysis.py --basetemp .tmp-pytest-p2-async-fifo-vcd-analysis-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_async_fifo_reports.py --basetemp .tmp-pytest-p2-async-fifo-reports-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_async_fifo_uvm_wave.py --basetemp .tmp-pytest-p2-async-fifo-uvm-wave-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_agent_runtime_boundaries.py --basetemp .tmp-pytest-p2-agent-runtime-boundaries-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_agent_cli_routing.py --basetemp .tmp-pytest-p2-agent-cli-routing-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_agent_sim_smoke_runtime.py --basetemp .tmp-pytest-p2-agent-sim-smoke-runtime-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_agent_vivado_diagnostics.py --basetemp .tmp-pytest-p2-agent-vivado-diagnostics-valid -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_agent_waveform_runtime.py --basetemp .tmp-pytest-p2-agent-waveform-runtime-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_project_text_encoding.py --basetemp .tmp-pytest-p2-project-text-encoding-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_project_documentation_status.py --basetemp .tmp-pytest-p2-project-documentation-status-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_target_registry_runtime.py --basetemp .tmp-pytest-p2-target-registry-runtime-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_target_report_rendering.py --basetemp .tmp-pytest-p2-target-report-rendering-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_sync_fifo_round_robin_rtl_flow.py --basetemp .tmp-pytest-p2-sync-fifo-round-robin-rtl-flow-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_sync_fifo_round_robin_runtime.py --basetemp .tmp-pytest-p2-sync-fifo-round-robin-runtime-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_sync_fifo_round_robin_vcd_analysis.py --basetemp .tmp-pytest-p2-sync-fifo-round-robin-vcd-analysis-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_skill_runtime_contract.py --basetemp .tmp-pytest-p2-skill-runtime-contract-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_target_flow_runtime.py --basetemp .tmp-pytest-p2-target-flow-runtime-split -p no:cacheprovider -q
uv run --offline --frozen pytest tests/test_agent_workflow_contract.py --basetemp .tmp-pytest-p2-agent-workflow-contract-split -p no:cacheprovider -q
uv run --offline --frozen ruff check scripts tests
uv run --offline --frozen mypy
```

Latest observed results after all currently valid domain pre-splits and the
test-module report refresh:

- Full repository test suite after aggregate deletion: `406 passed in 50.49s`.
- P2 focused gate covering auto-doc, agent-eval fixture, agent-eval report, quality-config, and all independent domain modules: `276 passed in 43.88s`.
- Both legacy aggregate test modules and the stale hard-coded Vivado fallback test were deleted after explicit approval.
- Ruff: `All checks passed!`.
- Mypy: `Success: no issues found in 62 source files`.
- Quality-summary artifacts retain full JUnit and coverage metrics, while the tracked README generated block exposes only stable PASS/FAIL status and fixture counts so local sample numbers cannot become stale.

## Known Gaps

- Test-module domain splitting is complete: the generated report records 69 modules, 0 over-limit modules, 0 split candidates, 0 unmigrated tests, and status `PASS`.
- Broader P1-2 coverage and `Any` reduction targets remain paused by user request and are classified as unfinished rather than active work.
- Broader P1-3 end-to-end validation for every flow's full `run_id` timeline and distinct CLI exit codes for timeout/tool-missing/configuration-error/simulation-failure remains paused by user request and is classified as unfinished rather than active work.
