# P1-1 Report Template Split TDD Evidence

## Source

No upgrade plan file was read for this work. The scope came from the active
P1-1 requirement that report renderers should be split by responsibility, with
HTML templates separated from business/report logic.

## User Journeys

1. As a maintainer, I want the Markdown parser separated from the HTML shell
   template, so future report types can reuse a common shell without copying
   renderer internals.
2. As a reviewer, I want existing `render_markdown_document_html()` behavior to
   remain compatible, so current design-spec, verification-plan, environment,
   and overview reports do not regress.
3. As a quality reviewer, I want the new template module covered by tracked-file
   and mypy gates, so template extraction cannot be omitted from reproducibility
   checks.

## Task Report

The previous `agent_reports.py` mixed three responsibilities in one function:

- Markdown-like line parsing
- body HTML generation
- full HTML shell/CSS template rendering

This slice adds `report_templates.py` with:

- `REPORT_CARD_CLASSES`
- `REPORT_SHELL_CSS`
- `render_report_html_shell()`

`agent_reports.py` now exposes `render_markdown_body_html()` for Markdown body
conversion and keeps the existing `render_markdown_document_html()` API as a
compatibility wrapper around `render_report_html_shell()`.

The legacy Agent bootstrap preloads `report_templates`, and the new module is
included in mypy and tracked-runtime reproducibility checks.

## RED Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_report_rendering.py --basetemp .tmp-pytest-p1-1-report-red -p no:cacheprovider -q
```

Result:

```text
FAILED tests/test_p1_1_report_rendering.py::test_report_shell_template_is_split_from_markdown_renderer
AssertionError: assert False

FAILED tests/test_p1_1_report_rendering.py::test_report_renderer_preserves_document_and_scenario_variants
FileNotFoundError: report_templates.py

2 failed in 0.08s
```

## GREEN Evidence

Focused command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_report_rendering.py --basetemp .tmp-pytest-p1-1-report-green -p no:cacheprovider -q
```

Focused result:

```text
2 passed in 0.04s
```

Regression command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_1_report_rendering.py tests/test_p1_1_package_layout.py tests/test_architecture_runtime.py tests/test_repository_reproducibility.py tests/test_quality_config.py tests/test_agent.py::test_report_renderer_lives_in_dedicated_module --basetemp .tmp-pytest-p1-1-report-final -p no:cacheprovider -q
```

Regression result:

```text
48 passed in 5.37s
```

Ruff command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/agent.py .trae/agent/agent_reports.py .trae/agent/report_templates.py tests/test_p1_1_report_rendering.py tests/test_quality_config.py tests/test_repository_reproducibility.py
```

Ruff result:

```text
All checks passed!
```

Mypy command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

Mypy result:

```text
Success: no issues found in 55 source files
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | HTML shell and CSS template live in `report_templates.py`, not `agent_reports.py` | `tests/test_p1_1_report_rendering.py::test_report_shell_template_is_split_from_markdown_renderer` | architecture/static | PASS | `2 passed in 0.04s` |
| 2 | `agent_reports.py` exposes `render_markdown_body_html()` and delegates shell rendering | `tests/test_p1_1_report_rendering.py::test_report_shell_template_is_split_from_markdown_renderer` | architecture/static | PASS | source assertions passed |
| 3 | Existing document variant still renders title, table header, and body cells | `tests/test_p1_1_report_rendering.py::test_report_renderer_preserves_document_and_scenario_variants` | unit | PASS | document HTML assertions passed |
| 4 | Scenario variant still uses `scenario-card` | `tests/test_p1_1_report_rendering.py::test_report_renderer_preserves_document_and_scenario_variants` | unit | PASS | scenario HTML assertions passed |
| 5 | `report_templates.py` is covered by mypy and tracked-runtime reproducibility gates | `tests/test_quality_config.py`, `tests/test_repository_reproducibility.py` | quality/static | PASS | `48 passed in 5.37s` |
| 6 | Changed files pass Ruff and full configured mypy | Ruff and mypy commands above | lint/typecheck | PASS | `All checks passed!`; `Success: no issues found in 55 source files` |

## Known Gaps

- This slice separates the common Markdown report shell. More specialized
  renderers such as environment, project overview, coverage closure, and target
  dashboards still contain their own HTML generation and should be split in
  later P1-1/P1-3 work.
- The compatibility API remains `render_markdown_document_html()` to avoid
  breaking current report writers while the broader package migration continues.
