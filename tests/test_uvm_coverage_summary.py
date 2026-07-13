import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_uvm_coverage_summary_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


def _write_coverage_project_fixture(project_dir):
    sim_dir = project_dir / "sim"
    reports_dir = project_dir / "reports"
    cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
    cov_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
        "ASYNC_FIFO_UVM_TEST_DONE\n",
        encoding="utf-8",
    )
    (sim_dir / "async_fifo_uvm_coverage.wdb").write_text(
        "wdb placeholder",
        encoding="utf-8",
    )
    (cov_dir / "xsim.CCInfo").write_bytes(
        b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00"
        b"../rtl/async_fifo.v\x00tb_async_fifo_uvm.dut\x00"
    )
    return sim_dir, reports_dir, cov_dir


def test_parse_async_fifo_coverage_summary_extracts_xsim_metadata(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    ccinfo = tmp_path / "xsim.CCInfo"
    ccinfo.write_bytes(
        b"\x00xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00"
        b"../rtl/async_fifo.v\x00../uvm/tb_async_fifo_uvm.sv\x00"
        b"tb_async_fifo_uvm.dut\x00async_fifo_default\x00"
        b"wr_en && !full\x00rd_en && !empty\x00"
    )

    summary = async_fifo_plugin(agent).parse_async_fifo_coverage_summary(ccinfo)

    assert summary["available"] is True
    assert summary["coverage_types"] == ["statement", "branch", "condition", "toggle"]
    assert summary["database_name"] == "async_fifo_uvm_cov"
    assert "../rtl/async_fifo.v" in summary["source_files"]
    assert "../uvm/tb_async_fifo_uvm.sv" in summary["source_files"]
    assert "tb_async_fifo_uvm.dut" in summary["instances"]
    assert "async_fifo_default" in summary["coverage_items"]
    assert "wr_en && !full" in summary["coverage_items"]


def test_write_async_fifo_uvm_coverage_summary_report_gates_threshold(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    _, reports_dir, _ = _write_coverage_project_fixture(project_dir)
    xcrg_code_report = (
        reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html"
    )
    xcrg_func_report = (
        reports_dir
        / "uvm_coverage_xcrg"
        / "functionalCoverageReport"
        / "dashboard.html"
    )
    xcrg_code_report.parent.mkdir(parents=True, exist_ok=True)
    xcrg_func_report.parent.mkdir(parents=True, exist_ok=True)
    xcrg_code_report.write_text("<html>code coverage</html>\n", encoding="utf-8")
    xcrg_func_report.write_text("<html>functional coverage</html>\n", encoding="utf-8")
    (reports_dir / "xcrg_coverage.log").write_text("xcrg ok\n", encoding="utf-8")
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "Line Coverage Score 60.2041\n"
        "Branch Coverage Score 23.5294\n"
        "Condition Coverage Score 22\n"
        "Toggle Coverage Score 4.84\n",
        encoding="utf-8",
    )

    report = async_fifo_plugin(agent).write_async_fifo_uvm_coverage_summary_report(
        project_dir,
        coverage_threshold=80.0,
        coverage_percent=75.5,
    )

    assert report["passed"] is False
    assert report["coverage_gate_passed"] is False
    assert report["coverage_percent"] == 75.5
    assert report["coverage_threshold"] == 80.0
    assert report["coverage_gap"] == 4.5
    assert report["markdown_path"].name == "uvm_coverage_summary.md"
    assert report["html_path"].name == "uvm_coverage_summary.html"
    assert report["coverage_percent_summary"]["total_percent"] == 27.64
    assert report["coverage_percent_summary"]["metrics"]["statement"] == 60.2041
    assert report["xcrg_code_report_path"] == xcrg_code_report
    assert report["xcrg_functional_report_path"] == xcrg_func_report
    assert report["xcrg_log_path"] == reports_dir / "xcrg_coverage.log"
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    assert "FAIL" in text
    assert "75.5%" in text
    assert "80.0%" in text
    assert "statement / branch / condition / toggle" in text
    assert "../rtl/async_fifo.v" in text
    assert "tb_async_fifo_uvm.dut" in text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in text
    assert "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html" in text
    assert "xcrg_coverage.log" in text
    assert "uvm_coverage_percent.txt" in text
    assert "coverage-dashboard fail" in html_text
    assert "60.2%" in html_text
    assert "23.5%" in html_text


def test_write_async_fifo_uvm_coverage_summary_report_gates_component_thresholds(
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    _, reports_dir, _ = _write_coverage_project_fixture(project_dir)
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "Line Coverage Score 85\n"
        "Branch Coverage Score 55\n"
        "Condition Coverage Score 90\n"
        "Toggle Coverage Score 45\n"
        "Functional Coverage Score 92\n"
        "Total Coverage : 73.4%\n",
        encoding="utf-8",
    )

    report = async_fifo_plugin(agent).write_async_fifo_uvm_coverage_summary_report(
        project_dir,
        coverage_threshold=70.0,
        coverage_percent=73.4,
        coverage_thresholds={
            "statement": 80.0,
            "branch": 60.0,
            "condition": 90.0,
            "toggle": 40.0,
            "functional": 90.0,
        },
    )

    assert report["passed"] is False
    assert report["coverage_gate_passed"] is False
    assert report["coverage_gates"]["total"]["result"] == "PASS"
    assert report["coverage_gates"]["statement"]["result"] == "PASS"
    assert report["coverage_gates"]["branch"]["result"] == "FAIL"
    assert report["coverage_gates"]["branch"]["gap"] == 5.0
    assert report["coverage_gates"]["condition"]["result"] == "PASS"
    assert report["coverage_gates"]["toggle"]["result"] == "PASS"
    assert report["coverage_gates"]["functional"]["result"] == "PASS"
    markdown = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    assert "| Branch | 55.0% | 60.0% | 5.0% | FAIL |" in markdown
    assert "| Functional | 92.0% | 90.0% | -2.0% | PASS |" in markdown
    assert "P4.3 Component Coverage Gates" in html_text
    assert 'data-metric="branch"' in html_text
    assert 'class="component-gate fail"' in html_text


def test_write_async_fifo_uvm_coverage_summary_report_marks_missing_component_data(
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    _, reports_dir, _ = _write_coverage_project_fixture(project_dir)
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "Line Coverage Score 85\n",
        encoding="utf-8",
    )

    report = async_fifo_plugin(agent).write_async_fifo_uvm_coverage_summary_report(
        project_dir,
        coverage_thresholds={"functional": 90.0},
    )

    functional_gate = report["coverage_gates"]["functional"]
    assert report["passed"] is False
    assert report["coverage_gate_passed"] is False
    assert functional_gate["current"] is None
    assert functional_gate["gap"] is None
    assert functional_gate["result"] == "MISSING"
    markdown = report["markdown_path"].read_text(encoding="utf-8")
    assert "| Functional | N/A | 90.0% | N/A | MISSING |" in markdown
    assert "| Functional | 0.0%" not in markdown


def test_p4_3_coverage_gates_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/coverage_gates.py"' in pyproject


def test_write_async_fifo_uvm_coverage_summary_report_requires_percent_when_threshold_set(
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    _write_coverage_project_fixture(project_dir)

    report = async_fifo_plugin(agent).write_async_fifo_uvm_coverage_summary_report(
        project_dir,
        coverage_threshold=90.0,
        coverage_percent=None,
    )

    assert report["passed"] is False
    assert report["coverage_gate_passed"] is False
    assert report["coverage_gap"] is None
    text = report["markdown_path"].read_text(encoding="utf-8")
    assert "90.0%" in text
    assert "FAIL" in text
