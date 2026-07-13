import importlib.util
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

def run_agent(*args):
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_p5_2_generate_sync_fifo_project_creates_rtl_tb_sim_reports(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    project_dir = agent.generate_rtl_project("sync-fifo", tmp_path)

    assert project_dir == tmp_path / "sync-fifo"
    rtl_path = project_dir / "rtl" / "sync_fifo.v"
    tb_path = project_dir / "tb" / "tb_sync_fifo.v"
    sim_script_path = project_dir / "sim" / "run_vivado_sync_fifo.tcl"
    project_script_path = project_dir / "sim" / "create_sync_fifo_project.tcl"
    gui_script_path = project_dir / "sim" / "open_sync_fifo_project_gui.tcl"

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
    assert "module sync_fifo" in rtl
    assert "parameter DATA_WIDTH = 8" in rtl
    assert "parameter ADDR_WIDTH = 4" in rtl
    assert "reg [DATA_WIDTH-1:0] mem" in rtl
    assert "assign full" in rtl
    assert "assign empty" in rtl
    assert "wire wr_fire" in rtl
    assert "wire rd_fire" in rtl

    tb = tb_path.read_text(encoding="utf-8")
    assert "module tb_sync_fifo" in tb
    assert "$dumpfile(\"sync_fifo_trace.vcd\")" in tb
    assert "expected_data" in tb
    assert "scenario_id" in tb
    assert "SYNC_FIFO_SCENARIO basic_ordered PASS" in tb
    assert "SYNC_FIFO_SCENARIO full_boundary PASS" in tb
    assert "SYNC_FIFO_SCENARIO empty_boundary PASS" in tb
    assert "SYNC_FIFO_SCENARIO mixed_stress PASS" in tb
    assert "SYNC_FIFO_SCOREBOARD_PASS" in tb
    assert "$fatal(1, \"SYNC_FIFO_SCOREBOARD_FAIL" in tb

    sim_script = sim_script_path.read_text(encoding="utf-8")
    assert "sync_fifo.v" in sim_script
    assert "tb_sync_fifo.v" in sim_script
    assert "sync_fifo_smoke" in sim_script

    project_script = project_script_path.read_text(encoding="utf-8")
    assert "create_project sync_fifo_project" in project_script
    assert "sync_fifo_project.xpr" in project_script

    gui_script = gui_script_path.read_text(encoding="utf-8")
    assert "open_project $xpr_path" in gui_script
    assert "open_wave_database $wave_db" in gui_script
    assert "sync_fifo_smoke.wdb" in gui_script
    assert "sync_fifo_debug.wcfg" in gui_script
    assert "add_wave_divider {Control}" in gui_script
    assert "add_wave_divider {Data}" in gui_script
    assert "save_wave_config $wave_cfg" in gui_script


def test_p5_3_generate_round_robin_arbiter_project_creates_rtl_tb_sim_reports(
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    project_dir = agent.generate_rtl_project("round-robin-arbiter", tmp_path)

    assert project_dir == tmp_path / "round-robin-arbiter"
    rtl_path = project_dir / "rtl" / "round_robin_arbiter.v"
    tb_path = project_dir / "tb" / "tb_round_robin_arbiter.v"
    sim_script_path = project_dir / "sim" / "run_vivado_round_robin_arbiter.tcl"
    project_script_path = project_dir / "sim" / "create_round_robin_arbiter_project.tcl"
    gui_script_path = project_dir / "sim" / "open_round_robin_arbiter_project_gui.tcl"

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
    assert "module round_robin_arbiter" in rtl
    assert "parameter REQUESTERS = 4" in rtl
    assert "input  wire [REQUESTERS-1:0] req" in rtl
    assert "output reg  [REQUESTERS-1:0] grant" in rtl
    assert "output wire grant_valid" in rtl
    assert "reg [REQUESTERS-1:0] pointer" in rtl
    assert "wire [REQUESTERS-1:0] grant_next" in rtl
    assert "assign grant_valid = |grant" in rtl

    tb = tb_path.read_text(encoding="utf-8")
    assert "module tb_round_robin_arbiter" in tb
    assert "$dumpfile(\"round_robin_arbiter_trace.vcd\")" in tb
    assert "scenario_id" in tb
    assert "grant_count" in tb
    assert "error_count" in tb
    assert "task automatic expect_grant" in tb
    assert "ROUND_ROBIN_ARBITER_SCENARIO single_request PASS" in tb
    assert "ROUND_ROBIN_ARBITER_SCENARIO multiple_requests PASS" in tb
    assert "ROUND_ROBIN_ARBITER_SCENARIO rotating_grant PASS" in tb
    assert "ROUND_ROBIN_ARBITER_SCENARIO reset_recovery PASS" in tb
    assert "ROUND_ROBIN_ARBITER_SCENARIO fairness_window PASS" in tb
    assert "ROUND_ROBIN_ARBITER_SCOREBOARD_PASS" in tb
    assert "$fatal(1, \"ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL" in tb

    sim_script = sim_script_path.read_text(encoding="utf-8")
    assert "round_robin_arbiter.v" in sim_script
    assert "tb_round_robin_arbiter.v" in sim_script
    assert "round_robin_arbiter_smoke" in sim_script

    project_script = project_script_path.read_text(encoding="utf-8")
    assert "create_project round_robin_arbiter_project" in project_script
    assert "round_robin_arbiter_project.xpr" in project_script

    gui_script = gui_script_path.read_text(encoding="utf-8")
    assert "open_project $xpr_path" in gui_script
    assert "open_wave_database $wave_db" in gui_script
    assert "round_robin_arbiter_smoke.wdb" in gui_script
    assert "round_robin_arbiter_debug.wcfg" in gui_script
    assert "add_wave_divider {Control}" in gui_script
    assert "add_wave_divider {Requests And Grants}" in gui_script
    assert "add_wave_divider {Fairness}" in gui_script
    assert "save_wave_config $wave_cfg" in gui_script


def test_p5_2_cli_generate_rtl_sync_fifo_creates_project(tmp_path):
    result = run_agent(
        "--generate-rtl",
        "sync-fifo",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "sync_fifo.v" in result.stdout
    assert "tb_sync_fifo.v" in result.stdout
    assert "run_vivado_sync_fifo.tcl" in result.stdout
    assert (tmp_path / "sync-fifo" / "rtl" / "sync_fifo.v").exists()
    assert (tmp_path / "sync-fifo" / "tb" / "tb_sync_fifo.v").exists()


def test_p5_3_cli_generate_rtl_round_robin_arbiter_creates_project(tmp_path):
    result = run_agent(
        "--generate-rtl",
        "round-robin-arbiter",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "round_robin_arbiter.v" in result.stdout
    assert "tb_round_robin_arbiter.v" in result.stdout
    assert "run_vivado_round_robin_arbiter.tcl" in result.stdout
    assert (
        tmp_path / "round-robin-arbiter" / "rtl" / "round_robin_arbiter.v"
    ).exists()
    assert (
        tmp_path / "round-robin-arbiter" / "tb" / "tb_round_robin_arbiter.v"
    ).exists()
