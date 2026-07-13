import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_uvm_coverage_runtime_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


def _patch_vivado_success(monkeypatch, module, plugin, *, percent_text=None):
    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: "vivado")

    def fake_run(
        command,
        cwd=None,
        capture_output=False,
        text=False,
        encoding=None,
        errors=None,
        timeout=None,
        check=False,
        env=None,
    ):
        sim_dir = Path(cwd)
        reports_dir = sim_dir.parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n"
            "ASYNC_FIFO_UVM_FCOV_PASS full=1 empty=1 reset=1 mixed=1\n"
            "ASYNC_FIFO_UVM_ASSERT_PASS\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text(
            "wdb placeholder",
            encoding="utf-8",
        )
        cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
        cov_dir.mkdir(parents=True, exist_ok=True)
        (cov_dir / "xsim.CCInfo").write_bytes(
            b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00"
            b"../rtl/async_fifo.v\x00tb_async_fifo_uvm.dut\x00"
        )
        if percent_text is not None:
            (reports_dir / "uvm_coverage_percent.txt").write_text(
                percent_text,
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)


def test_run_async_fifo_uvm_coverage_fails_when_threshold_not_met(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    _patch_vivado_success(monkeypatch, module, plugin)

    assert plugin.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_threshold=80.0,
        coverage_percent=75.5,
    ) is False

    summary = tmp_path / "async-fifo" / "reports" / "uvm_coverage_summary.md"
    assert summary.exists()
    assert "FAIL" in summary.read_text(encoding="utf-8")


def test_run_async_fifo_uvm_coverage_uses_auto_percent_report(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    _patch_vivado_success(
        monkeypatch,
        module,
        plugin,
        percent_text=(
            "Code Coverage Summary\n"
            "Statement Coverage : 91.5%\n"
            "Branch Coverage    : 84.0%\n"
            "Condition Coverage : 79.5%\n"
            "Toggle Coverage    : 66.0%\n"
            "Total Coverage     : 80.25%\n"
        ),
    )

    assert plugin.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_threshold=80.0,
        coverage_percent=None,
    ) is True

    text = (tmp_path / "async-fifo" / "reports" / "uvm_coverage_summary.md").read_text(
        encoding="utf-8"
    )
    assert "80.2%" in text
    assert "Gate" in text
    assert "PASS" in text


def test_run_async_fifo_uvm_coverage_fails_when_component_gate_not_met(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    _patch_vivado_success(
        monkeypatch,
        module,
        plugin,
        percent_text=(
            "Line Coverage Score 91.5\n"
            "Branch Coverage Score 48\n"
            "Condition Coverage Score 79.5\n"
            "Toggle Coverage Score 66\n"
            "Functional Coverage Score 95\n"
            "Total Coverage : 80.0%\n"
        ),
    )

    assert plugin.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_thresholds={"branch": 50.0},
    ) is False

    project_dir = tmp_path / "async-fifo"
    summary = project_dir / "reports" / "uvm_coverage_summary.md"
    reports_index = project_dir / "reports" / "index.md"
    assert "| Branch | 48.0% | 50.0% | 2.0% | FAIL |" in summary.read_text(
        encoding="utf-8"
    )
    assert reports_index.exists()


def test_cli_uvm_coverage_async_fifo_invokes_runner(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_uvm_coverage(
        self,
        target,
        output_dir="outputs",
        coverage_threshold=None,
        coverage_percent=None,
        coverage_thresholds=None,
    ):
        calls.append(
            (
                target,
                output_dir,
                coverage_threshold,
                coverage_percent,
                coverage_thresholds,
            )
        )
        return True

    monkeypatch.setattr(
        module.DigitalICAgent,
        "run_uvm_coverage",
        fake_run_uvm_coverage,
    )

    assert module.main(
        [
            "--uvm-coverage",
            "async-fifo",
            "--coverage-threshold",
            "80",
            "--coverage-percent",
            "82.5",
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    assert calls == [("async-fifo", str(tmp_path), 80.0, 82.5, {})]


def test_cli_uvm_coverage_async_fifo_keeps_threshold_optional(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_uvm_coverage(
        self,
        target,
        output_dir="outputs",
        coverage_threshold=None,
        coverage_percent=None,
        coverage_thresholds=None,
    ):
        calls.append(
            (
                target,
                output_dir,
                coverage_threshold,
                coverage_percent,
                coverage_thresholds,
            )
        )
        return True

    monkeypatch.setattr(
        module.DigitalICAgent,
        "run_uvm_coverage",
        fake_run_uvm_coverage,
    )

    assert module.main(
        ["--uvm-coverage", "async-fifo", "--output-dir", str(tmp_path)]
    ) == 0
    assert calls == [("async-fifo", str(tmp_path), None, None, {})]


def test_cli_uvm_coverage_async_fifo_forwards_component_thresholds(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_uvm_coverage(
        self,
        target,
        output_dir="outputs",
        coverage_threshold=None,
        coverage_percent=None,
        coverage_thresholds=None,
    ):
        calls.append(
            (
                target,
                output_dir,
                coverage_threshold,
                coverage_percent,
                coverage_thresholds,
            )
        )
        return True

    monkeypatch.setattr(
        module.DigitalICAgent,
        "run_uvm_coverage",
        fake_run_uvm_coverage,
    )

    assert module.main(
        [
            "--uvm-coverage",
            "async-fifo",
            "--coverage-line-threshold",
            "80",
            "--coverage-branch-threshold",
            "50",
            "--coverage-condition-threshold",
            "75",
            "--coverage-toggle-threshold",
            "40",
            "--coverage-functional-threshold",
            "90",
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    assert calls == [
        (
            "async-fifo",
            str(tmp_path),
            None,
            None,
            {
                "statement": 80.0,
                "branch": 50.0,
                "condition": 75.0,
                "toggle": 40.0,
                "functional": 90.0,
            },
        )
    ]


def test_extract_async_fifo_coverage_percent_parses_text_report(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    report = tmp_path / "coverage_report.txt"
    report.write_text(
        "Code Coverage Summary\n"
        "Statement Coverage : 91.5%\n"
        "Branch Coverage    : 84.0%\n"
        "Condition Coverage : 79.5%\n"
        "Toggle Coverage    : 66.0%\n"
        "Total Coverage     : 80.25%\n",
        encoding="utf-8",
    )

    summary = async_fifo_plugin(agent).extract_async_fifo_coverage_percent(report)

    assert summary["available"] is True
    assert summary["total_percent"] == 80.25
    assert summary["metrics"]["statement"] == 91.5
    assert summary["metrics"]["branch"] == 84.0
    assert summary["metrics"]["condition"] == 79.5
    assert summary["metrics"]["toggle"] == 66.0


def test_extract_async_fifo_coverage_percent_parses_xcrg_scores(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    report = tmp_path / "uvm_coverage_percent.txt"
    report.write_text(
        "Code Coverage Report\n"
        "Line Coverage Score 60.2041\n"
        "Branch Coverage Score 23.5294\n"
        "Condition Coverage Score 22\n"
        "Toggle Coverage Score 4.84\n"
        "Functional Coverage Score 88\n"
        "Vivado coverage export status : PASS\n",
        encoding="utf-8",
    )

    summary = async_fifo_plugin(agent).extract_async_fifo_coverage_percent(report)

    assert summary["available"] is True
    assert summary["total_percent"] == 27.64
    assert summary["metrics"]["statement"] == 60.2041
    assert summary["metrics"]["branch"] == 23.5294
    assert summary["metrics"]["condition"] == 22.0
    assert summary["metrics"]["toggle"] == 4.84
    assert summary["metrics"]["functional"] == 88.0


def test_generate_async_fifo_uvm_coverage_script_enables_xsim_code_coverage(
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    async_fifo_plugin(agent).write_async_fifo_uvm_coverage_project(project_dir)

    script = (
        project_dir / "sim" / "run_vivado_async_fifo_uvm_coverage.tcl"
    ).read_text(encoding="utf-8")
    assert "async_fifo_uvm_coverage" in script
    assert "-cc_type sbct" in script
    assert "-cov_db_dir coverage" in script
    assert "-cov_db_name async_fifo_uvm_cov" in script
    assert "-timescale 1ns/1ps" in script
    assert "xsim.codeCov" in script
    assert "async_fifo_uvm_coverage.log" in script
    assert "async_fifo_uvm_coverage.wdb" in script
    assert "uvm_coverage_percent.txt" in script
    assert "xcrg" in script
    assert "-report_dir $xcrg_report_dir" in script
    assert "xcrg_coverage.log" in script
    assert "Vivado coverage export status" in script


def test_run_async_fifo_uvm_coverage_writes_report(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(
        command,
        cwd=None,
        capture_output=False,
        text=False,
        encoding=None,
        errors=None,
        timeout=None,
        check=False,
    ):
        calls.append(([str(part) for part in command], Path(cwd)))
        sim_dir = Path(cwd)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text(
            "wdb placeholder",
            encoding="utf-8",
        )
        cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
        cov_dir.mkdir(parents=True, exist_ok=True)
        (cov_dir / "xsim.CCInfo").write_text(
            "coverage placeholder",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="ASYNC_FIFO_UVM_SCOREBOARD_PASS\n",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert (
        plugin.run_async_fifo_uvm_coverage(output_dir=tmp_path) is True
    )

    project_dir = tmp_path / "async-fifo"
    report = project_dir / "reports" / "uvm_coverage_report.md"
    html_report = project_dir / "reports" / "uvm_coverage_report.html"
    assert report.exists()
    assert html_report.exists()
    report_text = report.read_text(encoding="utf-8")
    html_text = html_report.read_text(encoding="utf-8")
    assert "async-fifo UVM 覆盖率报告" in report_text
    assert "覆盖率统计：已启用" in report_text
    assert "xsim.codeCov" in report_text
    assert "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in report_text
    assert 'class="coverage-card pass"' in html_text
    assert calls == [
        (
            [
                vivado_path,
                "-mode",
                "batch",
                "-source",
                "run_vivado_async_fifo_uvm_coverage.tcl",
            ],
            project_dir / "sim",
        )
    ]


def test_run_async_fifo_uvm_coverage_refreshes_reports_index(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    reports_dir = project_dir / "reports"
    sim_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / "run_vivado_async_fifo_uvm_coverage.tcl").write_text(
        "run\n",
        encoding="utf-8",
    )
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
        "ASYNC_FIFO_UVM_TEST_DONE\n"
        "ASYNC_FIFO_UVM_FCOV_PASS samples=18\n"
        "ASYNC_FIFO_SVA_PASS\n",
        encoding="utf-8",
    )
    (sim_dir / "async_fifo_uvm_coverage.wdb").write_text(
        "wdb\n",
        encoding="utf-8",
    )
    coverage_db = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
    coverage_db.mkdir(parents=True, exist_ok=True)
    (coverage_db / "xsim.CCInfo").write_text("async_fifo\n", encoding="utf-8")
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
    xcrg_code_report.write_text("<html>code</html>\n", encoding="utf-8")
    xcrg_func_report.write_text("<html>functional</html>\n", encoding="utf-8")
    (reports_dir / "xcrg_coverage.log").write_text("xcrg ok\n", encoding="utf-8")
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "Line Coverage Score 60.2041\n"
        "Branch Coverage Score 23.5294\n"
        "Condition Coverage Score 22\n"
        "Toggle Coverage Score 4.84\n",
        encoding="utf-8",
    )

    class FakeResult:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: "vivado")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: FakeResult(),
    )

    assert (
        plugin.run_async_fifo_uvm_coverage(
            output_dir=tmp_path,
            coverage_threshold=1,
        )
        is True
    )

    index = reports_dir / "index.md"
    html_index = reports_dir / "index.html"
    assert index.exists()
    assert html_index.exists()
    index_text = index.read_text(encoding="utf-8")
    html_text = html_index.read_text(encoding="utf-8")
    assert "uvm_coverage_summary.html" in index_text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in index_text
    assert "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html" in index_text
    assert "xcrg_coverage.log" in index_text
    assert "uvm_coverage_percent.txt" in index_text
    assert "uvm_coverage_summary.html" in html_text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in html_text
