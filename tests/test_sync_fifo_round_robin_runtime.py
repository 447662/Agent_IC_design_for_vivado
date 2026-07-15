import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    return importlib.import_module("digital_ic_agent._runtime.agent")

def test_p5_2_run_sync_fifo_vivado_sim_creates_project_and_can_skip_gui(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

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
        if "run_vivado_sync_fifo.tcl" in command:
            Path(cwd, "sync_fifo_trace.vcd").write_text(
                "$date\nsync fifo\n$end\n",
                encoding="utf-8",
            )
            Path(cwd, "sync_fifo_smoke.wdb").write_text(
                "wdb placeholder",
                encoding="utf-8",
            )
            Path(cwd, "xsim.log").write_text(
                "SYNC_FIFO_SCOREBOARD_PASS\n",
                encoding="utf-8",
            )
        if "create_sync_fifo_project.tcl" in command:
            xpr = Path(cwd).parent / "vivado_project" / "sync_fifo_project.xpr"
            xpr.parent.mkdir(parents=True, exist_ok=True)
            xpr.write_text("<Project />\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="SYNC_FIFO_SCOREBOARD_PASS",
            stderr="",
        )

    def fail_if_gui_opens(*args, **kwargs):
        raise AssertionError("GUI should be skipped")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "open_sync_fifo_project_gui", fail_if_gui_opens)
    monkeypatch.setattr(
        agent,
        "collect_sync_fifo_vcd_analysis",
        lambda output_dir="outputs", limit=20, waveform_backend="auto": {
            "info": {
                "signal_count": 3,
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
        },
    )

    assert agent.run_sync_fifo_vivado_sim(
        output_dir=tmp_path,
        open_wave_gui=False,
    ) is True

    sim_dir = tmp_path / "sync-fifo" / "sim"
    assert calls == [
        ([vivado_path, "-mode", "batch", "-source", "run_vivado_sync_fifo.tcl"], sim_dir),
        (
            [
                vivado_path,
                "-mode",
                "batch",
                "-nojournal",
                "-nolog",
                "-notrace",
                "-source",
                "create_sync_fifo_project.tcl",
            ],
            sim_dir,
        ),
    ]
    assert (tmp_path / "sync-fifo" / "sim" / "sync_fifo_trace.vcd").exists()
    assert (tmp_path / "sync-fifo" / "sim" / "sync_fifo_smoke.wdb").exists()
    assert (tmp_path / "sync-fifo" / "vivado_project" / "sync_fifo_project.xpr").exists()
    assert (tmp_path / "sync-fifo" / "reports" / "sim_report.md").exists()
    assert (tmp_path / "sync-fifo" / "reports" / "sim_report.html").exists()

    agent.record_artifact_run(
        "sync-fifo",
        "sim-rtl",
        output_dir=tmp_path,
        project_dir=tmp_path / "sync-fifo",
    )
    manifest = json.loads(
        (tmp_path / "sync-fifo" / "artifacts.json").read_text(encoding="utf-8")
    )
    latest_run = manifest["runs"][-1]
    artifacts = {item["id"]: item for item in latest_run["artifacts"]}
    assert latest_run["flow"] == "sim-rtl"
    assert artifacts["vivado_project"]["path"] == "vivado_project/sync_fifo_project.xpr"
    assert artifacts["vivado_project"]["status"] == "CURRENT"
    assert artifacts["vivado_project"]["produced_by_run_id"] == latest_run["run_id"]


def test_p5_2_sync_fifo_wave_db_resolution_and_gui_paths(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    services = agent.target_services

    latest_dir = tmp_path / "latest" / "sim"
    latest_dir.mkdir(parents=True)
    latest_wdb = latest_dir / "sync_fifo_smoke_20260711.wdb"
    latest_wdb.write_text("latest", encoding="utf-8")
    (latest_dir / "latest_sync_fifo_wdb.txt").write_text(
        latest_wdb.name,
        encoding="utf-8",
    )
    assert services.resolve_sync_fifo_wave_db(latest_dir) == latest_wdb

    legacy_dir = tmp_path / "legacy" / "sim"
    legacy_dir.mkdir(parents=True)
    legacy_wdb = legacy_dir / "sync_fifo_smoke.wdb"
    legacy_wdb.write_text("legacy", encoding="utf-8")
    assert services.resolve_sync_fifo_wave_db(legacy_dir) == legacy_wdb

    candidate_dir = tmp_path / "candidate" / "sim"
    candidate_dir.mkdir(parents=True)
    old_wdb = candidate_dir / "sync_fifo_smoke_old.wdb"
    new_wdb = candidate_dir / "sync_fifo_smoke_new.wdb"
    old_wdb.write_text("old", encoding="utf-8")
    new_wdb.write_text("new", encoding="utf-8")
    os.utime(old_wdb, (1_700_000_000, 1_700_000_000))
    os.utime(new_wdb, (1_700_000_010, 1_700_000_010))
    assert services.resolve_sync_fifo_wave_db(candidate_dir) == new_wdb

    empty_dir = tmp_path / "empty" / "sim"
    empty_dir.mkdir(parents=True)
    assert services.resolve_sync_fifo_wave_db(empty_dir) == empty_dir / "sync_fifo_smoke.wdb"

    project_dir = tmp_path / "gui" / "sync-fifo"
    sim_dir = project_dir / "sim"
    sim_dir.mkdir(parents=True)
    assert services.open_sync_fifo_project_gui(project_dir) is False

    xpr_path = project_dir / "vivado_project" / "sync_fifo_project.xpr"
    xpr_path.parent.mkdir(parents=True)
    xpr_path.write_text("<Project />", encoding="utf-8")
    assert services.open_sync_fifo_project_gui(project_dir) is False

    (sim_dir / "sync_fifo_smoke.wdb").write_text("wdb", encoding="utf-8")
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: None)
    assert services.open_sync_fifo_project_gui(project_dir) is False
    assert (sim_dir / "open_sync_fifo_project_gui.tcl").exists()

    launches = []
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: "vivado")
    monkeypatch.setattr(
        agent,
        "launch_vivado_gui",
        lambda command, script, cwd: launches.append((command, script, cwd)),
    )
    assert services.open_sync_fifo_project_gui(project_dir) is True
    assert launches == [("vivado", "open_sync_fifo_project_gui.tcl", sim_dir)]


def test_p5_2_sync_fifo_vivado_sim_failure_and_warning_paths(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    services = agent.target_services
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: None)
    assert services.run_sync_fifo_vivado_sim(output_dir=tmp_path / "no-vivado") is False

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)
    monkeypatch.setattr(
        agent,
        "run_vivado_batch",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args,
            1,
            stdout="",
            stderr="sim failed",
        ),
    )
    assert services.run_sync_fifo_vivado_sim(output_dir=tmp_path / "sim-fail") is False

    def run_without_vcd(command, script_name, cwd, extra_args=None):
        return subprocess.CompletedProcess([command, script_name], 0, stdout="ok", stderr="")

    monkeypatch.setattr(agent, "run_vivado_batch", run_without_vcd)
    assert services.run_sync_fifo_vivado_sim(output_dir=tmp_path / "missing-vcd") is False

    def run_without_wdb(command, script_name, cwd, extra_args=None):
        if script_name == "run_vivado_sync_fifo.tcl":
            Path(cwd, "sync_fifo_trace.vcd").write_text("vcd", encoding="utf-8")
        return subprocess.CompletedProcess([command, script_name], 0, stdout="ok", stderr="")

    monkeypatch.setattr(agent, "run_vivado_batch", run_without_wdb)
    assert services.run_sync_fifo_vivado_sim(output_dir=tmp_path / "missing-wdb") is False

    def run_with_project_warning(command, script_name, cwd, extra_args=None):
        if script_name == "run_vivado_sync_fifo.tcl":
            Path(cwd, "sync_fifo_trace.vcd").write_text("vcd", encoding="utf-8")
            Path(cwd, "sync_fifo_smoke.wdb").write_text("wdb", encoding="utf-8")
            Path(cwd, "xsim.log").write_text(
                "SYNC_FIFO_SCOREBOARD_PASS\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(
                [command, script_name], 0, stdout="SYNC_FIFO_SCOREBOARD_PASS", stderr=""
            )
        return subprocess.CompletedProcess(
            [command, script_name],
            1,
            stdout="",
            stderr="project warning",
        )

    monkeypatch.setattr(agent, "run_vivado_batch", run_with_project_warning)
    monkeypatch.setattr(
        services,
        "collect_sync_fifo_vcd_analysis",
        lambda output_dir="outputs", limit=20, waveform_backend="auto": {
            "info": {"signal_count": 1},
            "write_events": {"total": 1},
            "read_events": {"total": 1},
        },
    )
    opened = []
    monkeypatch.setattr(
        services,
        "open_sync_fifo_project_gui",
        lambda _project_dir: opened.append(True),
    )
    assert services.run_sync_fifo_vivado_sim(
        output_dir=tmp_path / "project-warning",
        open_wave_gui=True,
    ) is False
    assert opened == []


def test_sync_fifo_sim_rejects_scoreboard_false_pass_and_writes_fail_reports(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    services = agent.target_services
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: "vivado")

    def false_pass_run(_command, script_name, cwd, **_kwargs):
        sim_dir = Path(cwd)
        if script_name == "run_vivado_sync_fifo.tcl":
            (sim_dir / "sync_fifo_trace.vcd").write_text("vcd\n", encoding="utf-8")
            (sim_dir / "sync_fifo_smoke.wdb").write_text("wdb\n", encoding="utf-8")
            evidence = (
                "SYNC_FIFO_SCOREBOARD_PASS writes=8 reads=8\n"
                "Fatal: SYNC_FIFO_SCOREBOARD_FAIL errors=1\n"
            )
            (sim_dir / "xsim.log").write_text(evidence, encoding="utf-8")
            return subprocess.CompletedProcess([script_name], 0, stdout=evidence, stderr="")
        raise AssertionError("Project generation must not run after a failed verdict")

    monkeypatch.setattr(agent, "run_vivado_batch", false_pass_run)
    monkeypatch.setattr(
        services,
        "collect_sync_fifo_vcd_analysis",
        lambda **_kwargs: {
            "info": {},
            "write_events": {"total": 0},
            "read_events": {"total": 0},
        },
    )

    assert services.run_sync_fifo_vivado_sim(output_dir=tmp_path, open_wave_gui=False) is False

    project_dir = tmp_path / "sync-fifo"
    assert "- 状态：FAIL" in (project_dir / "reports" / "sim_report.md").read_text(
        encoding="utf-8"
    )
    verdict = json.loads(
        (project_dir / "reports" / "verification_verdict.json").read_text(
            encoding="utf-8"
        )
    )
    assert verdict["status"] == "FAIL"
    assert "FAIL_MARKER_FOUND" in {reason["code"] for reason in verdict["reasons"]}


def test_p5_3_run_round_robin_arbiter_vivado_sim_creates_project_and_can_skip_gui(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

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
        if "run_vivado_round_robin_arbiter.tcl" in command:
            Path(cwd, "round_robin_arbiter_trace.vcd").write_text(
                "$date\nround robin arbiter\n$end\n",
                encoding="utf-8",
            )
            Path(cwd, "round_robin_arbiter_smoke.wdb").write_text(
                "wdb placeholder",
                encoding="utf-8",
            )
            Path(cwd, "xsim.log").write_text(
                "ROUND_ROBIN_ARBITER_SCOREBOARD_PASS\n",
                encoding="utf-8",
            )
        if "create_round_robin_arbiter_project.tcl" in command:
            xpr = (
                Path(cwd).parent
                / "vivado_project"
                / "round_robin_arbiter_project.xpr"
            )
            xpr.parent.mkdir(parents=True, exist_ok=True)
            xpr.write_text("<Project />\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="ROUND_ROBIN_ARBITER_SCOREBOARD_PASS",
            stderr="",
        )

    def fail_if_gui_opens(*args, **kwargs):
        raise AssertionError("GUI should be skipped")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "open_round_robin_arbiter_project_gui", fail_if_gui_opens)
    monkeypatch.setattr(
        agent,
        "collect_round_robin_arbiter_vcd_analysis",
        lambda output_dir="outputs", limit=20, waveform_backend="auto": {
            "info": {
                "signal_count": 4,
                "time_min_h": "0 ns",
                "time_max_h": "100 ns",
                "duration_h": "100 ns",
                "timescale": "1 ns",
            },
            "grant_events": {
                "total": 4,
                "events": [{"time_h": "20 ns", "values": {"grant": "0x1"}}],
            },
            "fairness_events": {
                "total": 4,
                "events": [{"time_h": "30 ns", "values": {"grant_count": "1"}}],
            },
        },
    )

    assert agent.run_round_robin_arbiter_vivado_sim(
        output_dir=tmp_path,
        open_wave_gui=False,
    ) is True

    sim_dir = tmp_path / "round-robin-arbiter" / "sim"
    assert calls == [
        (
            [
                vivado_path,
                "-mode",
                "batch",
                "-source",
                "run_vivado_round_robin_arbiter.tcl",
            ],
            sim_dir,
        ),
        (
            [
                vivado_path,
                "-mode",
                "batch",
                "-nojournal",
                "-nolog",
                "-notrace",
                "-source",
                "create_round_robin_arbiter_project.tcl",
            ],
            sim_dir,
        ),
    ]
    assert (
        tmp_path / "round-robin-arbiter" / "sim" / "round_robin_arbiter_trace.vcd"
    ).exists()
    assert (
        tmp_path / "round-robin-arbiter" / "sim" / "round_robin_arbiter_smoke.wdb"
    ).exists()
    assert (
        tmp_path
        / "round-robin-arbiter"
        / "vivado_project"
        / "round_robin_arbiter_project.xpr"
    ).exists()
    assert (tmp_path / "round-robin-arbiter" / "reports" / "sim_report.md").exists()
    assert (tmp_path / "round-robin-arbiter" / "reports" / "sim_report.html").exists()

    agent.record_artifact_run(
        "round-robin-arbiter",
        "sim-rtl",
        output_dir=tmp_path,
        project_dir=tmp_path / "round-robin-arbiter",
    )
    manifest = json.loads(
        (tmp_path / "round-robin-arbiter" / "artifacts.json").read_text(
            encoding="utf-8"
        )
    )
    latest_run = manifest["runs"][-1]
    artifacts = {item["id"]: item for item in latest_run["artifacts"]}
    assert latest_run["flow"] == "sim-rtl"
    assert artifacts["vivado_project"]["path"] == (
        "vivado_project/round_robin_arbiter_project.xpr"
    )
    assert artifacts["vivado_project"]["status"] == "CURRENT"
    assert artifacts["vivado_project"]["produced_by_run_id"] == latest_run["run_id"]


def test_round_robin_sim_rejects_scoreboard_false_pass_and_writes_fail_reports(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    services = agent.target_services
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: "vivado")

    def false_pass_run(_command, script_name, cwd, **_kwargs):
        sim_dir = Path(cwd)
        if script_name == "run_vivado_round_robin_arbiter.tcl":
            (sim_dir / "round_robin_arbiter_trace.vcd").write_text(
                "vcd\n", encoding="utf-8"
            )
            (sim_dir / "round_robin_arbiter_smoke.wdb").write_text(
                "wdb\n", encoding="utf-8"
            )
            evidence = (
                "ROUND_ROBIN_ARBITER_SCOREBOARD_PASS\n"
                "Fatal: ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL errors=5\n"
            )
            (sim_dir / "xsim.log").write_text(evidence, encoding="utf-8")
            return subprocess.CompletedProcess([script_name], 0, stdout=evidence, stderr="")
        raise AssertionError("Project generation must not run after a failed verdict")

    monkeypatch.setattr(agent, "run_vivado_batch", false_pass_run)
    monkeypatch.setattr(
        services,
        "collect_round_robin_arbiter_vcd_analysis",
        lambda **_kwargs: {
            "info": {},
            "grant_events": {"total": 0},
            "fairness_events": {"total": 0},
        },
    )

    assert services.run_round_robin_arbiter_vivado_sim(
        output_dir=tmp_path,
        open_wave_gui=False,
    ) is False

    project_dir = tmp_path / "round-robin-arbiter"
    assert "- 状态：FAIL" in (project_dir / "reports" / "sim_report.md").read_text(
        encoding="utf-8"
    )
    verdict = json.loads(
        (project_dir / "reports" / "verification_verdict.json").read_text(
            encoding="utf-8"
        )
    )
    assert verdict["status"] == "FAIL"
    assert "FAIL_MARKER_FOUND" in {reason["code"] for reason in verdict["reasons"]}

def test_p5_3_round_robin_wave_db_resolution_and_gui_paths(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    services = agent.target_services

    latest_dir = tmp_path / "latest" / "sim"
    latest_dir.mkdir(parents=True)
    latest_wdb = latest_dir / "round_robin_arbiter_smoke_20260711.wdb"
    latest_wdb.write_text("latest", encoding="utf-8")
    (latest_dir / "latest_round_robin_arbiter_wdb.txt").write_text(
        latest_wdb.name,
        encoding="utf-8",
    )
    assert services.resolve_round_robin_arbiter_wave_db(latest_dir) == latest_wdb

    legacy_dir = tmp_path / "legacy" / "sim"
    legacy_dir.mkdir(parents=True)
    legacy_wdb = legacy_dir / "round_robin_arbiter_smoke.wdb"
    legacy_wdb.write_text("legacy", encoding="utf-8")
    assert services.resolve_round_robin_arbiter_wave_db(legacy_dir) == legacy_wdb

    candidate_dir = tmp_path / "candidate" / "sim"
    candidate_dir.mkdir(parents=True)
    old_wdb = candidate_dir / "round_robin_arbiter_smoke_old.wdb"
    new_wdb = candidate_dir / "round_robin_arbiter_smoke_new.wdb"
    old_wdb.write_text("old", encoding="utf-8")
    new_wdb.write_text("new", encoding="utf-8")
    os.utime(old_wdb, (1_700_000_000, 1_700_000_000))
    os.utime(new_wdb, (1_700_000_010, 1_700_000_010))
    assert services.resolve_round_robin_arbiter_wave_db(candidate_dir) == new_wdb

    empty_dir = tmp_path / "empty" / "sim"
    empty_dir.mkdir(parents=True)
    assert (
        services.resolve_round_robin_arbiter_wave_db(empty_dir)
        == empty_dir / "round_robin_arbiter_smoke.wdb"
    )

    project_dir = tmp_path / "gui" / "round-robin-arbiter"
    sim_dir = project_dir / "sim"
    sim_dir.mkdir(parents=True)
    assert services.open_round_robin_arbiter_project_gui(project_dir) is False

    xpr_path = project_dir / "vivado_project" / "round_robin_arbiter_project.xpr"
    xpr_path.parent.mkdir(parents=True)
    xpr_path.write_text("<Project />", encoding="utf-8")
    assert services.open_round_robin_arbiter_project_gui(project_dir) is False

    (sim_dir / "round_robin_arbiter_smoke.wdb").write_text("wdb", encoding="utf-8")
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: None)
    assert services.open_round_robin_arbiter_project_gui(project_dir) is False
    assert (sim_dir / "open_round_robin_arbiter_project_gui.tcl").exists()

    launches = []
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: "vivado")
    monkeypatch.setattr(
        agent,
        "launch_vivado_gui",
        lambda command, script, cwd: launches.append((command, script, cwd)),
    )
    assert services.open_round_robin_arbiter_project_gui(project_dir) is True
    assert launches == [("vivado", "open_round_robin_arbiter_project_gui.tcl", sim_dir)]


def test_p5_3_round_robin_vivado_sim_failure_and_warning_paths(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    services = agent.target_services
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: None)
    assert (
        services.run_round_robin_arbiter_vivado_sim(output_dir=tmp_path / "no-vivado")
        is False
    )

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)
    monkeypatch.setattr(
        agent,
        "run_vivado_batch",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args,
            1,
            stdout="",
            stderr="sim failed",
        ),
    )
    assert (
        services.run_round_robin_arbiter_vivado_sim(output_dir=tmp_path / "sim-fail")
        is False
    )

    def run_without_vcd(command, script_name, cwd, extra_args=None):
        return subprocess.CompletedProcess([command, script_name], 0, stdout="ok", stderr="")

    monkeypatch.setattr(agent, "run_vivado_batch", run_without_vcd)
    assert (
        services.run_round_robin_arbiter_vivado_sim(
            output_dir=tmp_path / "missing-vcd"
        )
        is False
    )

    def run_without_wdb(command, script_name, cwd, extra_args=None):
        if script_name == "run_vivado_round_robin_arbiter.tcl":
            Path(cwd, "round_robin_arbiter_trace.vcd").write_text(
                "vcd",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess([command, script_name], 0, stdout="ok", stderr="")

    monkeypatch.setattr(agent, "run_vivado_batch", run_without_wdb)
    assert (
        services.run_round_robin_arbiter_vivado_sim(
            output_dir=tmp_path / "missing-wdb"
        )
        is False
    )

    def run_with_project_warning(command, script_name, cwd, extra_args=None):
        if script_name == "run_vivado_round_robin_arbiter.tcl":
            Path(cwd, "round_robin_arbiter_trace.vcd").write_text(
                "vcd",
                encoding="utf-8",
            )
            Path(cwd, "round_robin_arbiter_smoke.wdb").write_text(
                "wdb",
                encoding="utf-8",
            )
            Path(cwd, "xsim.log").write_text(
                "ROUND_ROBIN_ARBITER_SCOREBOARD_PASS\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(
                [command, script_name],
                0,
                stdout="ROUND_ROBIN_ARBITER_SCOREBOARD_PASS",
                stderr="",
            )
        return subprocess.CompletedProcess(
            [command, script_name],
            1,
            stdout="",
            stderr="project warning",
        )

    monkeypatch.setattr(agent, "run_vivado_batch", run_with_project_warning)
    monkeypatch.setattr(
        services,
        "collect_round_robin_arbiter_vcd_analysis",
        lambda output_dir="outputs", limit=20, waveform_backend="auto": {
            "info": {"signal_count": 1},
            "grant_events": {"total": 1},
            "fairness_events": {"total": 1},
        },
    )
    opened = []
    monkeypatch.setattr(
        services,
        "open_round_robin_arbiter_project_gui",
        lambda _project_dir: opened.append(True),
    )
    assert services.run_round_robin_arbiter_vivado_sim(
        output_dir=tmp_path / "project-warning",
        open_wave_gui=True,
    ) is False
    assert opened == []
