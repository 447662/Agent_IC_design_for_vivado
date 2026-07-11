import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
REPORTS_PATH = AGENT_DIR / "agent_reports.py"
TEMPLATES_PATH = AGENT_DIR / "report_templates.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_report_shell_template_is_split_from_markdown_renderer():
    assert REPORTS_PATH.exists()
    assert TEMPLATES_PATH.exists()

    reports_source = REPORTS_PATH.read_text(encoding="utf-8")
    templates_source = TEMPLATES_PATH.read_text(encoding="utf-8")

    assert "from report_templates import render_report_html_shell" in reports_source
    assert "<!doctype html>" not in reports_source
    assert "<!doctype html>" in templates_source
    assert "def render_markdown_body_html" in reports_source
    assert "def render_report_html_shell" in templates_source


def test_report_renderer_preserves_document_and_scenario_variants():
    templates = _load_module("report_templates", TEMPLATES_PATH)
    reports = _load_module("agent_reports", REPORTS_PATH)

    markdown = "# Title\n\n| Name | Status |\n| --- | --- |\n| smoke | PASS |\n"
    doc_html = reports.render_markdown_document_html(
        "Doc Report",
        markdown,
    )
    scenario_html = reports.render_markdown_document_html(
        "Scenario Report",
        markdown,
        variant="scenario",
    )

    assert "<title>Doc Report</title>" in doc_html
    assert '<section class="doc-card">' in doc_html
    assert "<th>Name</th>" in doc_html
    assert "<td>PASS</td>" in doc_html
    assert '<section class="scenario-card">' in scenario_html
    assert templates.REPORT_CARD_CLASSES["scenario"] == "scenario-card"
