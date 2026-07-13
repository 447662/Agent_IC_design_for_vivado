import importlib.util
import json
import os
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
        "digital_ic_agent_async_fifo_rtl_flow_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


def _vcd_summary(signal_count=3):
    return {
        "info": {
            "signal_count": signal_count,
            "time_min_h": "0 ns",
            "time_max_h": "10 ns",
            "duration_h": "10 ns",
            "timescale": "1 ns",
        },
        "write_events": {
            "total": 1,
            "events": [{"time_h": "1 ns", "values": {"wr_data": "0x11"}}],
        },
        "read_events": {
            "total": 1,
            "events": [{"time_h": "2 ns", "values": {"rd_data": "0x11"}}],
        },
    }


def test_generate_async_fifo_project_creates_rtl_tb_sim_reports(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    assert project_dir == tmp_path / "async-fifo"
    rtl_path = project_dir / "rtl" / "async_fifo.v"
    tb_path = project_dir / "tb" / "tb_async_fifo.v"
    sim_script_path = project_dir / "sim" / "run_vivado_async_fifo.tcl"
    project_script_path = project_dir / "sim" / "create_async_fifo_project.tcl"
    gui_script_path = project_dir / "sim" / "open_async_fifo_project_gui.tcl"

    for path in [
        rtl_path,
        tb_path,
        sim_script_path,
        project_script_path,
        gui_script_path,
        project_dir / "reports",
        project_dir / "README.md",
    ]:
        assert path.exists()

    rtl = rtl_path.read_text(encoding="utf-8")
    assert "module async_fifo" in rtl
    assert "parameter DATA_WIDTH = 8" in rtl
    assert "parameter ADDR_WIDTH = 4" in rtl
    assert "bin_to_gray" in rtl
    assert "(* async_reg = \"true\" *)" in rtl
    assert "reg full_reg" in rtl
    assert "reg empty_reg" in rtl
    assert "wire full_next" in rtl
    assert "wire empty_next" in rtl

    tb = tb_path.read_text(encoding="utf-8")
    assert "module tb_async_fifo" in tb
    assert "$dumpfile(\"async_fifo_trace.vcd\")" in tb
    assert "expected_data" in tb
    assert "scenario_id" in tb
    assert "task automatic try_write" in tb
    assert "ASYNC_FIFO_SCENARIO full_boundary PASS" in tb
    assert "ASYNC_FIFO_SCENARIO empty_boundary PASS" in tb
    assert "ASYNC_FIFO_SCENARIO reset_recovery PASS" in tb
    assert "ASYNC_FIFO_SCENARIO mixed_stress PASS" in tb
    assert "ASYNC_FIFO_SCOREBOARD_PASS" in tb

    sim_script = sim_script_path.read_text(encoding="utf-8")
    assert "async_fifo.v" in sim_script
    assert "tb_async_fifo.v" in sim_script
    assert "async_fifo_smoke" in sim_script
    assert "set fixed_wdb async_fifo_smoke.wdb" in sim_script

    project_script = project_script_path.read_text(encoding="utf-8")
    assert "create_project async_fifo_project" in project_script
    assert "async_fifo_project.xpr" in project_script

    gui_script = gui_script_path.read_text(encoding="utf-8")
    assert "open_project $xpr_path" in gui_script
    assert "open_wave_database $wave_db" in gui_script
    assert "async_fifo_smoke.wdb" in gui_script
    assert "async_fifo_debug.wcfg" in gui_script
    assert "add_wave_divider {Scenario}" in gui_script
    assert "add_wave_divider {Write Domain}" in gui_script
    assert "add_wave_divider {Read Domain}" in gui_script
    assert "add_wave_divider {Scoreboard}" in gui_script


def test_cli_generate_rtl_async_fifo_creates_project(tmp_path):
    module = load_agent_module()

    assert module.main(["--generate-rtl", "async-fifo", "--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "async-fifo" / "rtl" / "async_fifo.v").exists()
    assert (tmp_path / "async-fifo" / "tb" / "tb_async_fifo.v").exists()


def test_run_async_fifo_vivado_sim_creates_project_and_can_skip_gui(
    monkeypatch,
    tmp_path,
):
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
        if "run_vivado_async_fifo.tcl" in command:
            Path(cwd, "async_fifo_trace.vcd").write_text(
                "$date\nasync fifo\n$end\n",
                encoding="utf-8",
            )
            Path(cwd, "async_fifo_smoke.wdb").write_text(
                "wdb placeholder",
                encoding="utf-8",
            )
        if "create_async_fifo_project.tcl" in command:
            xpr = Path(cwd).parent / "vivado_project" / "async_fifo_project.xpr"
            xpr.parent.mkdir(parents=True, exist_ok=True)
            xpr.write_text("<Project />\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    def fail_if_gui_opens(*args, **kwargs):
        raise AssertionError("GUI should be skipped")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(plugin, "open_async_fifo_project_gui", fail_if_gui_opens)
    monkeypatch.setattr(plugin, "collect_async_fifo_vcd_analysis", lambda **_kwargs: _vcd_summary())

    assert plugin.run_async_fifo_vivado_sim(
        output_dir=tmp_path,
        open_wave_gui=False,
    ) is True

    project_dir = tmp_path / "async-fifo"
    report_text = (project_dir / "reports" / "sim_report.md").read_text(
        encoding="utf-8"
    )
    assert "full_boundary" in report_text
    assert "empty_boundary" in report_text
    assert "reset_recovery" in report_text
    assert "mixed_stress" in report_text

    sim_dir = project_dir / "sim"
    assert calls == [
        ([vivado_path, "-mode", "batch", "-source", "run_vivado_async_fifo.tcl"], sim_dir),
        (
            [
                vivado_path,
                "-mode",
                "batch",
                "-nojournal",
                "-nolog",
                "-notrace",
                "-source",
                "create_async_fifo_project.tcl",
            ],
            sim_dir,
        ),
    ]
    agent.record_artifact_run(
        "async-fifo",
        "sim-rtl",
        output_dir=tmp_path,
        project_dir=project_dir,
    )
    manifest = json.loads((project_dir / "artifacts.json").read_text(encoding="utf-8"))
    latest_run = manifest["runs"][-1]
    artifacts = {item["id"]: item for item in latest_run["artifacts"]}
    assert latest_run["flow"] == "sim-rtl"
    assert artifacts["vivado_project"]["path"] == "vivado_project/async_fifo_project.xpr"
    assert artifacts["vivado_project"]["status"] == "CURRENT"
    assert artifacts["vivado_project"]["produced_by_run_id"] == latest_run["run_id"]


def test_open_async_fifo_project_gui_handles_missing_inputs_and_launches(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
    sim_dir.mkdir(parents=True)

    assert plugin.open_async_fifo_project_gui(project_dir) is False
    xpr_path.parent.mkdir(parents=True)
    xpr_path.write_text("<Project />\n", encoding="utf-8")
    assert plugin.open_async_fifo_project_gui(project_dir) is False
    (sim_dir / "async_fifo_smoke.wdb").write_text("wdb", encoding="utf-8")
    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: None)
    assert plugin.open_async_fifo_project_gui(project_dir) is False

    launches = []
    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: "vivado")
    monkeypatch.setattr(
        plugin,
        "launch_vivado_gui",
        lambda command, script_name, cwd: launches.append((command, script_name, cwd)),
    )

    assert plugin.open_async_fifo_project_gui(project_dir) is True
    assert launches == [("vivado", "open_async_fifo_project_gui.tcl", sim_dir)]
    assert (sim_dir / "open_async_fifo_project_gui.tcl").exists()


def test_resolve_async_fifo_wave_db_prefers_latest_then_legacy_then_newest(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    sim_dir = tmp_path / "sim"
    sim_dir.mkdir()

    fallback = sim_dir / "async_fifo_smoke.wdb"
    assert plugin.resolve_async_fifo_wave_db(sim_dir) == fallback

    old_wdb = sim_dir / "async_fifo_smoke_20260709_000000.wdb"
    new_wdb = sim_dir / "async_fifo_smoke_20260710_000000.wdb"
    old_wdb.write_text("old", encoding="utf-8")
    new_wdb.write_text("new", encoding="utf-8")
    os.utime(old_wdb, (1_700_000_000, 1_700_000_000))
    os.utime(new_wdb, (1_700_000_100, 1_700_000_100))
    assert plugin.resolve_async_fifo_wave_db(sim_dir) == new_wdb

    fallback.write_text("legacy", encoding="utf-8")
    assert plugin.resolve_async_fifo_wave_db(sim_dir) == fallback

    latest = sim_dir / "async_fifo_smoke_latest.wdb"
    latest.write_text("latest", encoding="utf-8")
    (sim_dir / "latest_async_fifo_wdb.txt").write_text(latest.name, encoding="utf-8")
    assert plugin.resolve_async_fifo_wave_db(sim_dir) == latest


def test_run_async_fifo_vivado_sim_failure_paths_and_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)

    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: None)
    assert plugin.run_async_fifo_vivado_sim(output_dir=tmp_path / "no-vivado") is False

    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: "vivado")
    monkeypatch.setattr(
        plugin,
        "run_vivado_batch",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args,
            1,
            stdout="",
            stderr="sim failed",
        ),
    )
    assert plugin.run_async_fifo_vivado_sim(output_dir=tmp_path / "sim-fail") is False

    def missing_vcd_run(_command, script_name, cwd, **_kwargs):
        Path(cwd).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess([script_name], 0, stdout="ok", stderr="")

    monkeypatch.setattr(plugin, "run_vivado_batch", missing_vcd_run)
    assert plugin.run_async_fifo_vivado_sim(output_dir=tmp_path / "missing-vcd") is False

    def missing_wdb_run(_command, script_name, cwd, **_kwargs):
        sim_dir = Path(cwd)
        sim_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "async_fifo_trace.vcd").write_text(
            "$date\nasync fifo\n$end\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess([script_name], 0, stdout="ok", stderr="")

    monkeypatch.setattr(plugin, "run_vivado_batch", missing_wdb_run)
    assert plugin.run_async_fifo_vivado_sim(output_dir=tmp_path / "missing-wdb") is False

    def project_fail_run(_command, script_name, cwd, **_kwargs):
        sim_dir = Path(cwd)
        sim_dir.mkdir(parents=True, exist_ok=True)
        if script_name == "run_vivado_async_fifo.tcl":
            (sim_dir / "async_fifo_trace.vcd").write_text(
                "$date\nasync fifo\n$end\n",
                encoding="utf-8",
            )
            (sim_dir / "async_fifo_smoke.wdb").write_text("wdb", encoding="utf-8")
            return subprocess.CompletedProcess([script_name], 0, stdout="ok", stderr="")
        return subprocess.CompletedProcess(
            [script_name],
            1,
            stdout="",
            stderr="project failed",
        )

    monkeypatch.setattr(plugin, "run_vivado_batch", project_fail_run)
    assert plugin.run_async_fifo_vivado_sim(output_dir=tmp_path / "project-fail") is False

    opened = []

    def success_run(_command, script_name, cwd, **_kwargs):
        sim_dir = Path(cwd)
        sim_dir.mkdir(parents=True, exist_ok=True)
        if script_name == "run_vivado_async_fifo.tcl":
            (sim_dir / "async_fifo_trace.vcd").write_text(
                "$date\nasync fifo\n$end\n",
                encoding="utf-8",
            )
            (sim_dir / "async_fifo_smoke.wdb").write_text("wdb", encoding="utf-8")
        return subprocess.CompletedProcess([script_name], 0, stdout="ok", stderr="")

    monkeypatch.setattr(plugin, "run_vivado_batch", success_run)
    monkeypatch.setattr(
        plugin,
        "open_async_fifo_project_gui",
        lambda project_dir: opened.append(project_dir),
    )
    monkeypatch.setattr(plugin, "collect_async_fifo_vcd_analysis", lambda **_kwargs: _vcd_summary(1))
    assert plugin.run_async_fifo_vivado_sim(
        output_dir=tmp_path / "success",
        open_wave_gui=True,
    ) is True
    assert opened == [tmp_path / "success" / "async-fifo"]


def test_async_fifo_regression_matrix_report_documents_parameter_sweeps(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    report_path = async_fifo_plugin(agent).write_async_fifo_regression_matrix(project_dir)
    text = report_path.read_text(encoding="utf-8")

    assert report_path.name == "regression_matrix.md"
    assert "| DATA_WIDTH | ADDR_WIDTH | Scenario coverage | Status |" in text
    assert "| 8 | 4 | basic/full/empty/reset/mixed | baseline-pass |" in text
    assert "| 16 | 4 | basic/full/empty/reset/mixed | planned |" in text
    assert "| 8 | 3 | basic/full/empty/reset/mixed | planned |" in text


def test_async_fifo_regression_runs_parameter_matrix_and_writes_summary(
    monkeypatch,
    tmp_path,
):
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
        if "run_vivado_async_fifo.tcl" in command:
            Path(cwd, "async_fifo_trace.vcd").write_text(
                "$date\nasync fifo\n$end\n",
                encoding="utf-8",
            )
            Path(cwd, "async_fifo_smoke.wdb").write_text(
                "wdb placeholder",
                encoding="utf-8",
            )
        if "create_async_fifo_project.tcl" in command:
            xpr = Path(cwd).parent / "vivado_project" / "async_fifo_project.xpr"
            xpr.parent.mkdir(parents=True, exist_ok=True)
            xpr.write_text("<Project />\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(plugin, "collect_async_fifo_vcd_analysis", lambda **_kwargs: _vcd_summary(4))

    assert plugin.run_async_fifo_regression(
        output_dir=tmp_path,
        open_wave_gui=False,
    ) is True

    summary_md = tmp_path / "async-fifo" / "reports" / "regression_summary.md"
    summary_html = tmp_path / "async-fifo" / "reports" / "regression_summary.html"
    assert summary_md.exists()
    assert summary_html.exists()
    text = summary_md.read_text(encoding="utf-8")
    html_text = summary_html.read_text(encoding="utf-8")
    assert "dw8_aw4" in text
    assert "dw16_aw4" in text
    assert "dw8_aw3" in text
    assert "| dw16_aw4 | 16 | 4 | PASS |" in text
    assert "class=\"regression-card pass\"" in html_text
    assert len([call for call in calls if "run_vivado_async_fifo.tcl" in call[0]]) == 3
    assert "parameter DATA_WIDTH = 16" in (
        tmp_path
        / "async-fifo"
        / "regression"
        / "dw16_aw4"
        / "async-fifo"
        / "rtl"
        / "async_fifo.v"
    ).read_text(encoding="utf-8")
    assert "localparam ADDR_WIDTH = 3;" in (
        tmp_path
        / "async-fifo"
        / "regression"
        / "dw8_aw3"
        / "async-fifo"
        / "tb"
        / "tb_async_fifo.v"
    ).read_text(encoding="utf-8")


def test_cli_regress_rtl_async_fifo_invokes_regression(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_regress_rtl(self, target, output_dir="outputs", open_wave_gui=False):
        calls.append((target, output_dir, open_wave_gui))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "regress_rtl", fake_regress_rtl)

    assert module.main(["--regress-rtl", "async-fifo", "--output-dir", str(tmp_path)]) == 0
    assert calls == [("async-fifo", str(tmp_path), False)]


def test_check_async_fifo_rtl_reports_complete_project(monkeypatch, tmp_path, capsys):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    sim_dir = project_dir / "sim"
    (sim_dir / "async_fifo_trace.vcd").write_text(
        "$date\nasync fifo\n$end\n",
        encoding="utf-8",
    )
    (sim_dir / "async_fifo_smoke_20260709_000000.wdb").write_text(
        "wdb",
        encoding="utf-8",
    )
    (sim_dir / "latest_async_fifo_wdb.txt").write_text(
        "async_fifo_smoke_20260709_000000.wdb\n",
        encoding="utf-8",
    )
    xpr = project_dir / "vivado_project" / "async_fifo_project.xpr"
    xpr.parent.mkdir(parents=True)
    xpr.write_text("<Project />\n", encoding="utf-8")
    (project_dir / "reports" / "sim_report.md").write_text("# report\n", encoding="utf-8")
    plugin.write_async_fifo_regression_summary(
        project_dir,
        [
            {
                "name": "dw8_aw4",
                "data_width": 8,
                "addr_width": 4,
                "status": "PASS",
                "output_dir": project_dir,
            },
            {
                "name": "dw16_aw4",
                "data_width": 16,
                "addr_width": 4,
                "status": "PASS",
                "output_dir": project_dir,
            },
            {
                "name": "dw8_aw3",
                "data_width": 8,
                "addr_width": 3,
                "status": "PASS",
                "output_dir": project_dir,
            },
        ],
    )

    assert plugin.check_async_fifo_rtl(output_dir=tmp_path) is True
    captured = capsys.readouterr()
    assert "Async FIFO RTL check" in captured.out
    assert "[OK] WDB exists" in captured.out
    assert "[OK] Regression summary exists" in captured.out
    assert "[OK] Wave screenshot report exists" in captured.out
    assert "[OK] Reports index exists" in captured.out
    assert "[OK] TB covers full boundary scenario" in captured.out
    assert "[OK] TB covers empty boundary scenario" in captured.out
    assert "[OK] TB covers reset recovery scenario" in captured.out
    assert "[OK] TB covers mixed stress scenario" in captured.out
    assert "[OK] Wave visibility report exists" in captured.out
    assert (project_dir / "reports" / "wave_visibility.md").exists()
    assert (project_dir / "reports" / "wave_visibility.html").exists()
    assert (project_dir / "reports" / "wave_screenshot.md").exists()
    assert (project_dir / "reports" / "wave_screenshot.html").exists()
    assert (project_dir / "reports" / "index.md").exists()
    assert (project_dir / "reports" / "index.html").exists()


def test_cli_check_rtl_async_fifo_invokes_checker(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)

    monkeypatch.setattr(module, "create_agent", lambda: agent)

    def fake_check_async_fifo_rtl(output_dir="outputs"):
        calls.append(output_dir)
        return True

    monkeypatch.setattr(plugin, "check_async_fifo_rtl", fake_check_async_fifo_rtl)

    assert module.main(["--check-rtl", "async-fifo", "--output-dir", str(tmp_path)]) == 0
    assert calls == [str(tmp_path)]
