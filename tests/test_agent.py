import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / ".trae" / "agent" / "agent.py"
AGENT_CONFIG_PATH = ROOT / ".trae" / "agent" / "agent.json"
TRAE_CONFIG_PATH = ROOT / ".trae" / "config.json"
HANDSHAKE_VCD_PATH = (
    ROOT
    / "VCD_ANALYZER-main"
    / "VCD_ANALYZER-main"
    / "verify"
    / "fixtures"
    / "handshake_trace.vcd"
)


def load_agent_module():
    spec = importlib.util.spec_from_file_location("digital_ic_agent", AGENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_agent(*args):
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_config_uses_portable_synthpilot_command():
    agent_config = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
    trae_config = json.loads(TRAE_CONFIG_PATH.read_text(encoding="utf-8"))

    assert agent_config["mcpServers"]["synthpilot"]["command"] == "uvx"
    assert trae_config["mcpServers"]["synthpilot"]["command"] == "uvx"


def test_cli_check_commands_are_arrays():
    agent_config = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))

    for tool in agent_config["cliTools"]:
        assert isinstance(tool["checkCommand"], list)
        assert all(isinstance(part, str) for part in tool["checkCommand"])
        assert tool["checkCommand"]


def test_analyze_requirement_matches_design_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("请生成这个模块的设计文档") == ["digital-ic-designer"]


def test_analyze_requirement_matches_rtl_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("实现 UART 的 Verilog RTL 代码") == ["digital-ic-rtl-designer"]


def test_analyze_requirement_matches_uvm_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert "digital-ic-verifier" in agent.analyze_requirement("使用 UVM 做前仿和覆盖率验证")


def test_analyze_requirement_defaults_to_rtl_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("做一个计数器") == ["digital-ic-rtl-designer"]


def test_cli_list_skills_succeeds():
    result = run_agent("--list-skills")

    assert result.returncode == 0, result.stderr
    assert "digital-ic-designer" in result.stdout
    assert "digital-ic-rtl-designer" in result.stdout
    assert "digital-ic-verifier" in result.stdout


def test_cli_diagnostic_runs_as_independent_mode():
    result = run_agent("--diagnostic")

    assert result.returncode in (0, 1)
    assert "环境诊断" in result.stdout
    assert "CLI工具检查" in result.stdout
    assert "MCP服务器检查" in result.stdout


def test_cli_rejects_conflicting_modes():
    result = run_agent("--diagnostic", "--list-skills")

    assert result.returncode != 0
    assert "not allowed with argument" in result.stderr or "不能" in result.stderr or "conflict" in result.stderr.lower()


def test_cli_no_tool_check_generates_design_spec(tmp_path):
    result = run_agent(
        "--no-tool-check",
        "--output-dir",
        str(tmp_path),
        "设计一个UART控制器",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    spec_files = list(tmp_path.glob("*/design_spec.md"))
    assert len(spec_files) == 1

    content = spec_files[0].read_text(encoding="utf-8")
    assert "设计一个UART控制器" in content
    assert "digital-ic-rtl-designer" in content
    assert "初始设计说明模板" in content
    assert "后续人工确认项" in content


def test_cli_no_tool_check_is_invalid_for_diagnostic():
    result = run_agent("--diagnostic", "--no-tool-check")

    assert result.returncode != 0


def test_cli_analyze_vcd_reports_handshake_summary():
    result = run_agent(
        "--analyze-vcd",
        str(HANDSHAKE_VCD_PATH),
        "--vcd-condition",
        "valid=1,ready=1",
        "--vcd-show",
        "data",
        "--vcd-limit",
        "5",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VCD 分析报告" in result.stdout
    assert "handshake_trace.vcd" in result.stdout
    assert "valid=1,ready=1" in result.stdout
    assert "0xaa" in result.stdout
    assert "0x55" in result.stdout


def test_cli_analyze_vcd_rejects_missing_file(tmp_path):
    missing_vcd = tmp_path / "missing.vcd"

    result = run_agent("--analyze-vcd", str(missing_vcd))

    assert result.returncode != 0
    assert "VCD file not found" in result.stderr


def test_cli_smoke_loop_generates_and_analyzes_vcd(tmp_path):
    result = run_agent("--smoke-loop", "--output-dir", str(tmp_path), "--vcd-limit", "5")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Smoke loop completed" in result.stdout
    assert "VCD" in result.stdout
    assert "tb.valid=1,tb.ready=1" in result.stdout
    assert "0xaa" in result.stdout
    assert "0x55" in result.stdout
    assert (tmp_path / "smoke-loop" / "handshake_trace.vcd").exists()


def test_detect_simulator_returns_none_when_tools_missing(monkeypatch):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: None)

    assert agent.detect_simulator() is None


def test_detect_simulator_prefers_vivado(monkeypatch):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    def fake_which(name):
        return "C:/tools/{}.exe".format(name) if name in {"vivado", "iverilog", "vvp"} else None

    monkeypatch.setattr(module.shutil, "which", fake_which)

    assert agent.detect_simulator() == "vivado"


def test_resolve_vivado_command_uses_known_install_path(monkeypatch):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(module.Path, "exists", lambda self: str(self) == r"D:\vivado\2025.2\Vivado\bin\vivado.bat")

    assert agent.resolve_vivado_command() == r"D:\vivado\2025.2\Vivado\bin\vivado.bat"


def test_run_sim_smoke_reports_missing_simulator(monkeypatch, capsys, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    monkeypatch.setattr(agent, "detect_simulator", lambda: None)

    assert agent.run_sim_smoke(output_dir=tmp_path, limit=5) is False

    captured = capsys.readouterr()
    assert "No supported Verilog simulator found" in captured.err
    assert "iverilog" in captured.err


def test_cli_sim_smoke_rejects_no_tool_check():
    result = run_agent("--sim-smoke", "--no-tool-check")

    assert result.returncode != 0


def test_cli_sim_smoke_accepts_no_wave_gui():
    result = run_agent("--sim-smoke", "--no-wave-gui", "--no-tool-check")

    assert result.returncode != 0
    assert "no-tool-check" in result.stderr


def test_run_sim_smoke_uses_icarus_and_analyzes_vcd(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    calls = []

    monkeypatch.setattr(agent, "detect_simulator", lambda: "icarus")

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        calls.append([str(part) for part in command])
        if command[0] == "iverilog":
            assert "-o" in command
        elif command[0] == "vvp":
            vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
            vcd_path.write_text("$date\nsim smoke test\n$end\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    analyzed = {}

    def fake_analyze_vcd(vcd_path, condition=None, show=None, limit=20):
        analyzed["vcd_path"] = Path(vcd_path)
        analyzed["condition"] = condition
        analyzed["show"] = show
        analyzed["limit"] = limit
        return True

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "analyze_vcd", fake_analyze_vcd)

    assert agent.run_sim_smoke(output_dir=tmp_path, limit=7) is True
    assert calls[0][0] == "iverilog"
    assert calls[1][0] == "vvp"
    assert analyzed["vcd_path"] == tmp_path / "sim-smoke" / "handshake_trace.vcd"
    assert analyzed["condition"] == "tb.valid=1,tb.ready=1"
    assert analyzed["show"] == "tb.data"
    assert analyzed["limit"] == 7


def test_run_sim_smoke_uses_vivado_and_analyzes_vcd(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    calls = []
    gui_calls = []

    monkeypatch.setattr(agent, "detect_simulator", lambda: "vivado")
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat")
    monkeypatch.setattr(agent, "open_vivado_wave_gui", lambda sim_dir, vcd_path: gui_calls.append((Path(sim_dir), Path(vcd_path))) or True)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        calls.append([str(part) for part in command])
        assert command[0] == r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
        assert "-mode" in command
        assert "-source" in command
        assert command[command.index("-source") + 1] == "run_vivado_sim.tcl"
        vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
        vcd_path.write_text("$date\nvivado sim smoke test\n$end\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="Vivado simulation done", stderr="")

    analyzed = {}

    def fake_analyze_vcd(vcd_path, condition=None, show=None, limit=20):
        analyzed["vcd_path"] = Path(vcd_path)
        analyzed["condition"] = condition
        analyzed["show"] = show
        analyzed["limit"] = limit
        return True

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "analyze_vcd", fake_analyze_vcd)

    assert agent.run_sim_smoke(output_dir=tmp_path, limit=9) is True
    assert calls[0][0] == r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    assert (tmp_path / "sim-smoke" / "run_vivado_sim.tcl").exists()
    script = (tmp_path / "sim-smoke" / "run_vivado_sim.tcl").read_text(encoding="utf-8")
    assert "exec xvlog" in script
    assert "exec xelab" in script
    assert "exec xsim handshake_smoke -R" in script
    assert analyzed["vcd_path"] == tmp_path / "sim-smoke" / "handshake_trace.vcd"
    assert analyzed["condition"] == "tb.valid=1,tb.ready=1"
    assert analyzed["show"] == "tb.data"
    assert analyzed["limit"] == 9
    assert gui_calls == [(tmp_path / "sim-smoke", tmp_path / "sim-smoke" / "handshake_trace.vcd")]


def test_run_vivado_sim_smoke_can_skip_wave_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat")

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
        vcd_path.write_text("$date\nvivado sim smoke test\n$end\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="Vivado simulation done", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "analyze_vcd", lambda *args, **kwargs: True)
    monkeypatch.setattr(agent, "open_vivado_wave_gui", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GUI should be skipped")))

    assert agent.run_vivado_sim_smoke(output_dir=tmp_path, limit=9, open_wave_gui=False) is True


def test_open_vivado_wave_gui_uses_wdb_database(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    calls = []

    (tmp_path / "handshake_smoke.wdb").write_text("wdb placeholder", encoding="utf-8")
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat")
    monkeypatch.setattr(module.subprocess, "Popen", lambda command, cwd=None: calls.append((command, Path(cwd))) or None)

    assert agent.open_vivado_wave_gui(tmp_path, tmp_path / "handshake_trace.vcd") is True

    script = (tmp_path / "open_vivado_wave.tcl").read_text(encoding="utf-8")
    assert "set wave_db handshake_smoke.wdb" in script
    assert "open_wave_database $wave_db" in script
    assert "open_wave_database handshake_trace.vcd" not in script
    assert calls == [([r"D:\vivado\2025.2\Vivado\bin\vivado.bat", "-mode", "gui", "-source", "open_vivado_wave.tcl"], tmp_path)]


def test_diagnostic_uses_resolved_vivado_command(monkeypatch):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    seen = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, **_kwargs):
        seen.append([str(part) for part in command])
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert agent.check_cli_tool("vivado", ["vivado", "-version"]) is True
    assert seen == [[vivado_path, "-version"]]


def test_readmes_document_current_vivado_and_async_fifo_flow():
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agent_readme = (ROOT / ".trae" / "agent" / "README.md").read_text(encoding="utf-8")
    lessons = (ROOT / "docs" / "vivado_async_fifo_lessons_learned.md").read_text(encoding="utf-8")
    combined = root_readme + "\n" + agent_readme + "\n" + lessons

    assert "--sim-smoke" in combined
    assert "--no-wave-gui" in combined
    assert "--generate-rtl async-fifo" in combined
    assert "--sim-rtl async-fifo" in combined
    assert "--analyze-rtl-vcd async-fifo" in combined
    assert "--check-rtl async-fifo" in combined
    assert "--open-wave async-fifo" in combined
    assert "handshake_smoke.wdb" in combined
    assert "async_fifo.v" in combined
    assert "async_fifo_smoke.wdb" in combined
    assert "create_async_fifo_project.tcl" in combined
    assert "open_async_fifo_project_gui.tcl" in combined
    assert "--regress-rtl async-fifo" in combined
    assert "regression_summary.html" in combined
    assert "wave_visibility.html" in combined
    assert "P2.9" in combined
    assert "P2.10" in combined
    assert "P2.11" in combined
    assert "P2.12" in combined
    assert "wave_screenshot.html" in combined
    assert "reports/index.html" in combined
    assert "问题复盘" in combined
    assert "仿真摘要" in combined
    mojibake_tokens = ["浠跨湡", "鎽樿", "闂", "鍦烘", "锛"]
    assert not any(token in combined for token in mojibake_tokens)


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
    readme_path = project_dir / "README.md"

    for path in [rtl_path, tb_path, sim_script_path, project_script_path, gui_script_path, project_dir / "reports", readme_path]:
        assert path.exists()

    rtl = rtl_path.read_text(encoding="utf-8")
    assert "module async_fifo" in rtl
    assert "parameter DATA_WIDTH = 8" in rtl
    assert "parameter ADDR_WIDTH = 4" in rtl
    assert "bin_to_gray" in rtl
    assert "(* async_reg = \"true\" *)" in rtl
    assert "reg full_reg" in rtl
    assert "reg empty_reg" in rtl
    assert "assign full = full_reg" in rtl
    assert "assign empty = empty_reg" in rtl
    assert "wire full_next" in rtl
    assert "wire empty_next" in rtl

    tb = tb_path.read_text(encoding="utf-8")
    assert "module tb_async_fifo" in tb
    assert "wr_clk" in tb
    assert "rd_clk" in tb
    assert "$dumpfile(\"async_fifo_trace.vcd\")" in tb
    assert "expected_data" in tb
    assert "scenario_id" in tb
    assert "task automatic try_write" in tb
    assert "ASYNC_FIFO_SCENARIO basic_ordered PASS" in tb
    assert "ASYNC_FIFO_SCENARIO full_boundary PASS" in tb
    assert "ASYNC_FIFO_SCENARIO empty_boundary PASS" in tb
    assert "ASYNC_FIFO_SCENARIO reset_recovery PASS" in tb
    assert "ASYNC_FIFO_SCENARIO mixed_stress PASS" in tb
    assert "ASYNC_FIFO_SCOREBOARD_PASS" in tb
    assert "$fatal(1, \"ASYNC_FIFO_SCOREBOARD_FAIL" in tb

    sim_script = sim_script_path.read_text(encoding="utf-8")
    assert "async_fifo.v" in sim_script
    assert "tb_async_fifo.v" in sim_script
    assert "async_fifo_smoke" in sim_script

    project_script = project_script_path.read_text(encoding="utf-8")
    assert "create_project async_fifo_project" in project_script
    assert "async_fifo_project.xpr" in project_script
    assert "package require ::tclapp::xilinx::xsim" in project_script

    gui_script = gui_script_path.read_text(encoding="utf-8")
    assert "open_project $xpr_path" in gui_script
    assert "open_wave_database $wave_db" in gui_script
    assert "async_fifo_smoke.wdb" in gui_script
    assert "async_fifo_debug.wcfg" in gui_script
    assert "open_wave_config $wave_cfg" not in gui_script
    assert "close_wave_config [current_wave_config]" in gui_script
    assert "create_wave_config async_fifo_debug" in gui_script
    assert "add_wave_divider {Scenario}" in gui_script
    assert "add_wave {{/tb_async_fifo/scenario_id}}" in gui_script
    assert "add_wave_divider {Write Domain}" in gui_script
    assert "add_wave_divider {Read Domain}" in gui_script
    assert "add_wave_divider {Scoreboard}" in gui_script
    assert "add_wave_divider {DUT Pointers}" in gui_script
    assert "add_wave_divider {DUT Status}" in gui_script
    assert "add_wave_divider {DUT Sync}" in gui_script
    assert "add_wave -radix hex {{/tb_async_fifo/wr_data}}" in gui_script
    assert "save_wave_config $wave_cfg" in gui_script


def test_cli_generate_rtl_async_fifo_creates_project(tmp_path):
    result = run_agent(
        "--generate-rtl",
        "async-fifo",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "async_fifo.v" in result.stdout
    assert (tmp_path / "async-fifo" / "rtl" / "async_fifo.v").exists()
    assert (tmp_path / "async-fifo" / "tb" / "tb_async_fifo.v").exists()


def test_run_async_fifo_vivado_sim_creates_project_and_can_skip_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        calls.append(([str(part) for part in command], Path(cwd)))
        if "run_vivado_async_fifo.tcl" in command:
            (Path(cwd) / "async_fifo_trace.vcd").write_text("$date\nasync fifo\n$end\n", encoding="utf-8")
            (Path(cwd) / "async_fifo_smoke.wdb").write_text("wdb placeholder", encoding="utf-8")
        if "create_async_fifo_project.tcl" in command:
            xpr = Path(cwd).parent / "vivado_project" / "async_fifo_project.xpr"
            xpr.parent.mkdir(parents=True, exist_ok=True)
            xpr.write_text("<Project />\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "open_async_fifo_project_gui", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GUI should be skipped")))
    monkeypatch.setattr(
        agent,
        "collect_async_fifo_vcd_analysis",
        lambda output_dir="outputs", limit=20: {
            "info": {"signal_count": 3, "time_min_h": "0 ns", "time_max_h": "10 ns", "duration_h": "10 ns", "timescale": "1 ns"},
            "write_events": {"total": 1, "events": [{"time_h": "1 ns", "values": {"wr_data": "0x11"}}]},
            "read_events": {"total": 1, "events": [{"time_h": "2 ns", "values": {"rd_data": "0x11"}}]},
        },
    )

    assert agent.run_async_fifo_vivado_sim(output_dir=tmp_path, open_wave_gui=False) is True
    report_text = (tmp_path / "async-fifo" / "reports" / "sim_report.md").read_text(encoding="utf-8")
    assert "full_boundary" in report_text
    assert "empty_boundary" in report_text
    assert "reset_recovery" in report_text
    assert "mixed_stress" in report_text

    sim_dir = tmp_path / "async-fifo" / "sim"
    assert calls == [
        ([vivado_path, "-mode", "batch", "-source", "run_vivado_async_fifo.tcl"], sim_dir),
        ([vivado_path, "-mode", "batch", "-nojournal", "-nolog", "-notrace", "-source", "create_async_fifo_project.tcl"], sim_dir),
    ]


def test_async_fifo_wcfg_validation_detects_required_wave_objects(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    wcfg_path = project_dir / "sim" / "async_fifo_debug.wcfg"
    required_objects = [
        "/tb_async_fifo/scenario_id",
        "/tb_async_fifo/wr_clk",
        "/tb_async_fifo/rd_clk",
        "/tb_async_fifo/write_count",
        "/tb_async_fifo/read_count",
        "/tb_async_fifo/dut/full_reg",
        "/tb_async_fifo/dut/empty_reg",
    ]
    wcfg_path.write_text(
        "\n".join([
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<wave_config>",
            "<WVObjectSize size=\"31\" />",
            *["<wvobject fp_name=\"{}\" />".format(name) for name in required_objects],
            "</wave_config>",
            "",
        ]),
        encoding="utf-8",
    )

    summary = agent.parse_async_fifo_wcfg_summary(project_dir)

    assert summary["exists"] is True
    assert summary["object_count"] == 31
    assert summary["valid"] is True
    assert summary["missing_required"] == []
    assert "/tb_async_fifo/scenario_id" in summary["required_objects"]


def test_async_fifo_wcfg_validation_rejects_empty_wave_config(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    wcfg_path = project_dir / "sim" / "async_fifo_debug.wcfg"
    wcfg_path.write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<WVObjectSize size=\"0\" />\n",
        encoding="utf-8",
    )

    summary = agent.parse_async_fifo_wcfg_summary(project_dir)

    assert summary["exists"] is True
    assert summary["object_count"] == 0
    assert summary["valid"] is False
    assert "/tb_async_fifo/scenario_id" in summary["missing_required"]


def test_async_fifo_regression_matrix_report_documents_parameter_sweeps(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    report_path = agent.write_async_fifo_regression_matrix(project_dir)
    text = report_path.read_text(encoding="utf-8")

    assert report_path.name == "regression_matrix.md"
    assert "| DATA_WIDTH | ADDR_WIDTH | Scenario coverage | Status |" in text
    assert "| 8 | 4 | basic/full/empty/reset/mixed | baseline-pass |" in text
    assert "| 16 | 4 | basic/full/empty/reset/mixed | planned |" in text
    assert "| 8 | 3 | basic/full/empty/reset/mixed | planned |" in text


def test_async_fifo_regression_runs_parameter_matrix_and_writes_summary(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        calls.append(([str(part) for part in command], Path(cwd)))
        if "run_vivado_async_fifo.tcl" in command:
            (Path(cwd) / "async_fifo_trace.vcd").write_text("$date\nasync fifo\n$end\n", encoding="utf-8")
            (Path(cwd) / "async_fifo_smoke.wdb").write_text("wdb placeholder", encoding="utf-8")
        if "create_async_fifo_project.tcl" in command:
            xpr = Path(cwd).parent / "vivado_project" / "async_fifo_project.xpr"
            xpr.parent.mkdir(parents=True, exist_ok=True)
            xpr.write_text("<Project />\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        agent,
        "collect_async_fifo_vcd_analysis",
        lambda output_dir="outputs", limit=20: {
            "info": {"signal_count": 4, "time_min_h": "0 ns", "time_max_h": "100 ns", "duration_h": "100 ns", "timescale": "1 ns"},
            "write_events": {"total": 2, "events": []},
            "read_events": {"total": 2, "events": []},
        },
    )

    assert agent.run_async_fifo_regression(output_dir=tmp_path, open_wave_gui=False) is True

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
    assert "\u56de\u5f52\u6458\u8981" in html_text
    assert "class=\"regression-card pass\"" in html_text
    assert len([call for call in calls if "run_vivado_async_fifo.tcl" in call[0]]) == 3
    assert "parameter DATA_WIDTH = 16" in (
        tmp_path / "async-fifo" / "regression" / "dw16_aw4" / "async-fifo" / "rtl" / "async_fifo.v"
    ).read_text(encoding="utf-8")
    assert "localparam ADDR_WIDTH = 3;" in (
        tmp_path / "async-fifo" / "regression" / "dw8_aw3" / "async-fifo" / "tb" / "tb_async_fifo.v"
    ).read_text(encoding="utf-8")


def test_async_fifo_wave_visibility_report_validates_gui_preflight(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    sim_dir = project_dir / "sim"
    xpr = project_dir / "vivado_project" / "async_fifo_project.xpr"
    xpr.parent.mkdir(parents=True, exist_ok=True)
    xpr.write_text("<Project />\n", encoding="utf-8")
    (sim_dir / "async_fifo_smoke_20260709_000000.wdb").write_text("wdb", encoding="utf-8")
    (sim_dir / "latest_async_fifo_wdb.txt").write_text("async_fifo_smoke_20260709_000000.wdb\n", encoding="utf-8")
    (sim_dir / "async_fifo_debug.wcfg").write_text(
        "\n".join([
            "<WVObjectSize size=\"31\" />",
            "<wvobject fp_name=\"/tb_async_fifo/scenario_id\" />",
            "<wvobject fp_name=\"/tb_async_fifo/wr_clk\" />",
            "<wvobject fp_name=\"/tb_async_fifo/rd_clk\" />",
            "<wvobject fp_name=\"/tb_async_fifo/write_count\" />",
            "<wvobject fp_name=\"/tb_async_fifo/read_count\" />",
            "<wvobject fp_name=\"/tb_async_fifo/dut/full_reg\" />",
            "<wvobject fp_name=\"/tb_async_fifo/dut/empty_reg\" />",
        ]),
        encoding="utf-8",
    )

    report = agent.write_async_fifo_wave_visibility_report(project_dir)
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")

    assert report["visible"] is True
    assert "\u6ce2\u5f62\u53ef\u89c1\u6027\u9a8c\u6536" in text
    assert "open_project" in text
    assert "open_wave_database" in text
    assert "- WCFG \u72b6\u6001\uff1aPASS" in text
    assert "class=\"visibility-card pass\"" in html_text


def test_async_fifo_wave_screenshot_report_embeds_png_and_capture_script(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = reports_dir / "wave_visibility.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-png")

    report = agent.write_async_fifo_wave_screenshot_report(project_dir)
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    script_text = report["capture_script_path"].read_text(encoding="utf-8")

    assert report["captured"] is True
    assert "GUI 波形截图验收" in text
    assert "- 状态：PASS" in text
    assert "wave_visibility.png" in text
    assert "CopyFromScreen" in script_text
    assert "class=\"screenshot-card pass\"" in html_text
    assert "<img" in html_text
    assert "wave_visibility.png" in html_text


def test_async_fifo_reports_index_links_core_reports_and_lessons(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "sim_summary.html",
        "regression_summary.html",
        "wave_visibility.html",
        "wave_screenshot.html",
        "uvm_coverage_summary.html",
    ]:
        (reports_dir / name).write_text("<html></html>\n", encoding="utf-8")
    xcrg_code_report = reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html"
    xcrg_func_report = reports_dir / "uvm_coverage_xcrg" / "functionalCoverageReport" / "dashboard.html"
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

    report = agent.write_async_fifo_reports_index(project_dir)
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")

    assert report["ready_count"] >= 4
    assert "async-fifo 报告总览" in text
    assert "sim_summary.html" in text
    assert "regression_summary.html" in text
    assert "wave_visibility.html" in text
    assert "wave_screenshot.html" in text
    assert "docs/vivado_async_fifo_lessons_learned.md" in text
    assert "<h1>async-fifo 报告总览</h1>" in html_text
    assert "class=\"report-card ready\"" in html_text
    assert "sim_summary.html" in html_text
    assert "regression_summary.html" in html_text
    assert "wave_visibility.html" in html_text
    assert "wave_screenshot.html" in html_text
    assert "uvm_coverage_summary.html" in text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in text
    assert "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html" in text
    assert "xcrg_coverage.log" in text
    assert "uvm_coverage_percent.txt" in text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in html_text
    assert "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html" in html_text
    assert "xcrg_coverage.log" in html_text


def test_async_fifo_summary_report_includes_wcfg_scenarios_and_commands(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    sim_dir = project_dir / "sim"
    vcd_path = sim_dir / "async_fifo_trace.vcd"
    wdb_path = sim_dir / "async_fifo_smoke_20260709_000000.wdb"
    vcd_path.write_text("$date\nasync fifo\n$end\n", encoding="utf-8")
    wdb_path.write_text("wdb", encoding="utf-8")
    (sim_dir / "latest_async_fifo_wdb.txt").write_text(wdb_path.name + "\n", encoding="utf-8")
    (sim_dir / "async_fifo_debug.wcfg").write_text(
        "\n".join([
            "<WVObjectSize size=\"31\" />",
            "<wvobject fp_name=\"/tb_async_fifo/scenario_id\" />",
            "<wvobject fp_name=\"/tb_async_fifo/wr_clk\" />",
            "<wvobject fp_name=\"/tb_async_fifo/rd_clk\" />",
            "<wvobject fp_name=\"/tb_async_fifo/write_count\" />",
            "<wvobject fp_name=\"/tb_async_fifo/read_count\" />",
            "<wvobject fp_name=\"/tb_async_fifo/dut/full_reg\" />",
            "<wvobject fp_name=\"/tb_async_fifo/dut/empty_reg\" />",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        agent,
        "collect_async_fifo_vcd_analysis",
        lambda output_dir="outputs", limit=20: {
            "info": {"signal_count": 48, "time_min_h": "0 ns", "time_max_h": "1200 ns", "duration_h": "1200 ns", "timescale": "1 ns"},
            "write_events": {"total": 70, "events": []},
            "read_events": {"total": 70, "events": []},
        },
    )

    report_path = agent.write_async_fifo_sim_report(project_dir, vcd_path, wdb_path)
    summary_path = project_dir / "reports" / "sim_summary.md"
    html_path = project_dir / "reports" / "sim_summary.html"
    summary_text = summary_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")

    assert report_path.exists()
    assert "# async-fifo 仿真摘要" in summary_text
    assert "## WCFG 波形配置验收" in summary_text
    assert "- WCFG 状态：PASS" in summary_text
    assert "- 波形对象数：31" in summary_text
    assert "basic_ordered" in summary_text
    assert "mixed_stress" in summary_text
    assert "`python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs`" in summary_text
    assert "regression_matrix.md" in summary_text
    assert "<html lang=\"zh-CN\">" in html_text
    assert "<h1>async-fifo 仿真摘要</h1>" in html_text
    assert "class=\"metric-card\"" in html_text
    assert "class=\"status-pill pass\"" in html_text
    assert "font-family:" in html_text
    assert "场景覆盖" in html_text
    mojibake_tokens = ["浠跨湡", "鎽樿", "闂", "鍦烘", "锛"]
    assert not any(token in summary_text for token in mojibake_tokens)
    assert not any(token in html_text for token in mojibake_tokens)


def test_cli_sim_rtl_async_fifo_invokes_runner(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_rtl_sim(self, target, output_dir="outputs", open_wave_gui=True):
        calls.append((target, output_dir, open_wave_gui))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "run_rtl_sim", fake_run_rtl_sim)

    assert module.main(["--sim-rtl", "async-fifo", "--no-wave-gui", "--output-dir", str(tmp_path)]) == 0
    assert calls == [("async-fifo", str(tmp_path), False)]


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


def test_analyze_async_fifo_vcd_reports_write_and_read_handshakes(monkeypatch, tmp_path, capsys):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "async-fifo" / "sim" / "async_fifo_trace.vcd"
    vcd_path.parent.mkdir(parents=True)
    vcd_path.write_text("$date\nasync fifo\n$end\n", encoding="utf-8")
    calls = []

    def fake_run_vcd_analyzer_json(*args):
        calls.append(args)
        if args[0] == "info":
            return {
                "signal_count": 12,
                "time_min_h": "0 ns",
                "time_max_h": "240 ns",
                "duration_h": "240 ns",
                "timescale": "1 ns",
            }
        return {
            "total": 2,
            "events": [
                {"time_h": "50 ns", "values": {"data": "0x11"}},
                {"time_h": "60 ns", "values": {"data": "0x22"}},
            ],
        }

    monkeypatch.setattr(agent, "run_vcd_analyzer_json", fake_run_vcd_analyzer_json)

    assert agent.analyze_async_fifo_vcd(output_dir=tmp_path, limit=4) is True

    captured = capsys.readouterr()
    assert "Async FIFO VCD analysis" in captured.out
    assert "Write handshakes: 2" in captured.out
    assert "Read handshakes: 2" in captured.out
    assert calls[0] == ("info", vcd_path)
    assert "tb_async_fifo.full=0" in calls[1]
    assert "tb_async_fifo.write_count" in calls[1]
    assert "tb_async_fifo.error_count=0" in calls[2]
    assert "tb_async_fifo.read_count" in calls[2]


def test_cli_analyze_rtl_vcd_async_fifo_invokes_analyzer(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_analyze_async_fifo_vcd(self, output_dir="outputs", limit=20):
        calls.append((output_dir, limit))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "analyze_async_fifo_vcd", fake_analyze_async_fifo_vcd)

    assert module.main(["--analyze-rtl-vcd", "async-fifo", "--output-dir", str(tmp_path), "--vcd-limit", "6"]) == 0
    assert calls == [(str(tmp_path), 6)]


def test_check_async_fifo_rtl_reports_complete_project(monkeypatch, tmp_path, capsys):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    sim_dir = project_dir / "sim"
    (sim_dir / "async_fifo_trace.vcd").write_text("$date\nasync fifo\n$end\n", encoding="utf-8")
    (sim_dir / "async_fifo_smoke_20260709_000000.wdb").write_text("wdb", encoding="utf-8")
    (sim_dir / "latest_async_fifo_wdb.txt").write_text("async_fifo_smoke_20260709_000000.wdb\n", encoding="utf-8")
    xpr = project_dir / "vivado_project" / "async_fifo_project.xpr"
    xpr.parent.mkdir(parents=True)
    xpr.write_text("<Project />\n", encoding="utf-8")
    report = project_dir / "reports" / "sim_report.md"
    report.write_text("# report\n", encoding="utf-8")
    agent.write_async_fifo_regression_summary(
        project_dir,
        [
            {"name": "dw8_aw4", "data_width": 8, "addr_width": 4, "status": "PASS", "output_dir": project_dir},
            {"name": "dw16_aw4", "data_width": 16, "addr_width": 4, "status": "PASS", "output_dir": project_dir},
            {"name": "dw8_aw3", "data_width": 8, "addr_width": 3, "status": "PASS", "output_dir": project_dir},
        ],
    )

    assert agent.check_async_fifo_rtl(output_dir=tmp_path) is True
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


def test_generate_async_fifo_uvm_smoke_creates_minimal_environment(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    uvm_dir = agent.write_async_fifo_uvm_smoke_project(project_dir)

    expected_files = [
        uvm_dir / "async_fifo_if.sv",
        uvm_dir / "async_fifo_uvm_pkg.sv",
        uvm_dir / "tb_async_fifo_uvm.sv",
        project_dir / "sim" / "run_vivado_async_fifo_uvm.tcl",
    ]
    for path in expected_files:
        assert path.exists()

    pkg = (uvm_dir / "async_fifo_uvm_pkg.sv").read_text(encoding="utf-8")
    top = (uvm_dir / "tb_async_fifo_uvm.sv").read_text(encoding="utf-8")
    script = (project_dir / "sim" / "run_vivado_async_fifo_uvm.tcl").read_text(encoding="utf-8")

    assert "import uvm_pkg::*;" in pkg
    assert "`include \"uvm_macros.svh\"" in pkg
    assert "class async_fifo_driver extends uvm_driver" in pkg
    assert "class async_fifo_monitor extends uvm_component" in pkg
    assert "read_pending = vif.rd_en && !vif.empty" in pkg
    assert "class async_fifo_scoreboard extends uvm_component" in pkg
    assert "class async_fifo_env extends uvm_env" in pkg
    assert "class async_fifo_basic_test extends uvm_test" in pkg
    assert "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in pkg
    assert "module tb_async_fifo_uvm" in top
    assert ".wr_rst_n(fifo_if.wr_rst_n)" in top
    assert ".rd_rst_n(fifo_if.rd_rst_n)" in top
    assert ".rst_n(" not in top
    assert "run_test(\"async_fifo_basic_test\")" in top
    assert "ASYNC_FIFO_UVM_TEST_DONE" in top
    assert "uvm_pkg" in script
    assert "-l uvm" in script.lower()
    assert "-timescale 1ns/1ps" in script
    assert "async_fifo_uvm_smoke" in script


def test_run_async_fifo_uvm_smoke_writes_report_and_can_skip_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        calls.append(([str(part) for part in command], Path(cwd)))
        (Path(cwd) / "async_fifo_uvm_smoke.log").write_text(
            "UVM_INFO async FIFO smoke\nASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\nASYNC_FIFO_UVM_TEST_DONE\n",
            encoding="utf-8",
        )
        (Path(cwd) / "async_fifo_uvm_smoke.wdb").write_text("wdb placeholder", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ASYNC_FIFO_UVM_SCOREBOARD_PASS\nASYNC_FIFO_UVM_TEST_DONE\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "open_async_fifo_project_gui", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GUI should be skipped")))

    assert agent.run_async_fifo_uvm_smoke(output_dir=tmp_path, open_wave_gui=False) is True

    project_dir = tmp_path / "async-fifo"
    report = project_dir / "reports" / "uvm_smoke_report.md"
    html_report = project_dir / "reports" / "uvm_smoke_report.html"
    assert report.exists()
    assert html_report.exists()
    text = report.read_text(encoding="utf-8")
    html_text = html_report.read_text(encoding="utf-8")
    assert "async-fifo UVM smoke 报告" in text
    assert "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in text
    assert "覆盖率统计：未启用" in text
    assert "class=\"uvm-card pass\"" in html_text
    assert calls == [([vivado_path, "-mode", "batch", "-source", "run_vivado_async_fifo_uvm.tcl"], project_dir / "sim")]


def test_cli_uvm_smoke_async_fifo_invokes_runner(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_uvm_smoke(self, target, output_dir="outputs", open_wave_gui=True):
        calls.append((target, output_dir, open_wave_gui))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "run_uvm_smoke", fake_run_uvm_smoke)

    assert module.main(["--uvm-smoke", "async-fifo", "--no-wave-gui", "--output-dir", str(tmp_path)]) == 0
    assert calls == [("async-fifo", str(tmp_path), False)]


def test_generate_async_fifo_uvm_coverage_script_enables_xsim_code_coverage(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    agent.write_async_fifo_uvm_coverage_project(project_dir)

    script = (project_dir / "sim" / "run_vivado_async_fifo_uvm_coverage.tcl").read_text(encoding="utf-8")
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
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        calls.append(([str(part) for part in command], Path(cwd)))
        sim_dir = Path(cwd)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\nASYNC_FIFO_UVM_TEST_DONE\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb placeholder", encoding="utf-8")
        cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
        cov_dir.mkdir(parents=True, exist_ok=True)
        (cov_dir / "xsim.CCInfo").write_text("coverage placeholder", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ASYNC_FIFO_UVM_SCOREBOARD_PASS\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert agent.run_async_fifo_uvm_coverage(output_dir=tmp_path) is True

    project_dir = tmp_path / "async-fifo"
    report = project_dir / "reports" / "uvm_coverage_report.md"
    html_report = project_dir / "reports" / "uvm_coverage_report.html"
    assert report.exists()
    assert html_report.exists()
    text = report.read_text(encoding="utf-8")
    html_text = html_report.read_text(encoding="utf-8")
    assert "async-fifo UVM 覆盖率报告" in text
    assert "覆盖率统计：已启用" in text
    assert "xsim.codeCov" in text
    assert "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in text
    assert "class=\"coverage-card pass\"" in html_text
    assert calls == [([vivado_path, "-mode", "batch", "-source", "run_vivado_async_fifo_uvm_coverage.tcl"], project_dir / "sim")]


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

    summary = agent.parse_async_fifo_coverage_summary(ccinfo)

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
    sim_dir = project_dir / "sim"
    cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
    cov_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
        "ASYNC_FIFO_UVM_TEST_DONE\n",
        encoding="utf-8",
    )
    (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb placeholder", encoding="utf-8")
    (cov_dir / "xsim.CCInfo").write_bytes(
        b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00"
        b"../rtl/async_fifo.v\x00tb_async_fifo_uvm.dut\x00"
    )
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    xcrg_code_report = reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html"
    xcrg_func_report = reports_dir / "uvm_coverage_xcrg" / "functionalCoverageReport" / "dashboard.html"
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

    report = agent.write_async_fifo_uvm_coverage_summary_report(
        project_dir,
        coverage_threshold=80.0,
        coverage_percent=75.5,
    )

    assert report["passed"] is False
    assert report["coverage_gate_passed"] is False
    assert report["coverage_percent"] == 75.5
    assert report["coverage_threshold"] == 80.0
    assert report["coverage_gap"] == 4.5
    assert "低于阈值 80.0%" in report["gate_diagnostic"]
    assert "差距 4.5%" in report["gate_diagnostic"]
    assert report["markdown_path"].name == "uvm_coverage_summary.md"
    assert report["html_path"].name == "uvm_coverage_summary.html"
    assert report["coverage_percent_summary"]["total_percent"] == 27.64
    assert report["coverage_percent_summary"]["metrics"]["statement"] == 60.2041
    assert report["xcrg_code_report_path"] == xcrg_code_report
    assert report["xcrg_functional_report_path"] == xcrg_func_report
    assert report["xcrg_log_path"] == reports_dir / "xcrg_coverage.log"
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    assert "# async-fifo UVM 覆盖率摘要" in text
    assert "总体状态：FAIL" in text
    assert "覆盖率阈值：80.0%" in text
    assert "当前覆盖率：75.5%" in text
    assert "Gate 结果：FAIL" in text
    assert "Gate 诊断：当前覆盖率 75.5% 低于阈值 80.0%，差距 4.5%" in text
    assert "优先查看 `uvm_coverage_report.html`" in text
    assert "statement / branch / condition / toggle" in text
    assert "../rtl/async_fifo.v" in text
    assert "tb_async_fifo_uvm.dut" in text
    assert "60.2%" in text
    assert "23.5%" in text
    assert "22.0%" in text
    assert "4.8%" in text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in text
    assert "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html" in text
    assert "xcrg_coverage.log" in text
    assert "uvm_coverage_percent.txt" in text
    assert "覆盖率摘要" in html_text
    assert "coverage-dashboard fail" in html_text
    assert "60.2%" in html_text
    assert "23.5%" in html_text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in html_text
    assert "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html" in html_text
    assert "差距 4.5%" in html_text


def test_write_async_fifo_uvm_coverage_summary_report_requires_percent_when_threshold_set(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
    cov_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\nASYNC_FIFO_UVM_TEST_DONE\n",
        encoding="utf-8",
    )
    (cov_dir / "xsim.CCInfo").write_bytes(b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00")

    report = agent.write_async_fifo_uvm_coverage_summary_report(
        project_dir,
        coverage_threshold=90.0,
        coverage_percent=None,
    )

    assert report["passed"] is False
    assert report["coverage_gate_passed"] is False
    assert report["coverage_gap"] is None
    assert "未提供可比较的覆盖率百分比" in report["gate_diagnostic"]
    text = report["markdown_path"].read_text(encoding="utf-8")
    assert "Gate 诊断：已设置覆盖率阈值 90.0%，但未提供可比较的覆盖率百分比。" in text


def test_run_async_fifo_uvm_coverage_fails_when_threshold_not_met(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        sim_dir = Path(cwd)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\nASYNC_FIFO_UVM_TEST_DONE\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb placeholder", encoding="utf-8")
        cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
        cov_dir.mkdir(parents=True, exist_ok=True)
        (cov_dir / "xsim.CCInfo").write_bytes(b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert agent.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_threshold=80.0,
        coverage_percent=75.5,
    ) is False

    summary = tmp_path / "async-fifo" / "reports" / "uvm_coverage_summary.md"
    assert summary.exists()
    assert "Gate 结果：FAIL" in summary.read_text(encoding="utf-8")


def test_run_async_fifo_uvm_coverage_uses_auto_percent_report(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, check=False):
        sim_dir = Path(cwd)
        project_dir = sim_dir.parent
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n"
            "ASYNC_FIFO_UVM_FCOV_PASS full=1 empty=1 reset=1 mixed=1\n"
            "ASYNC_FIFO_UVM_ASSERT_PASS\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb placeholder", encoding="utf-8")
        cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
        cov_dir.mkdir(parents=True, exist_ok=True)
        (cov_dir / "xsim.CCInfo").write_bytes(
            b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00"
            b"../rtl/async_fifo.v\x00tb_async_fifo_uvm.dut\x00"
        )
        (reports_dir / "uvm_coverage_percent.txt").write_text(
            "Code Coverage Summary\n"
            "Statement Coverage : 91.5%\n"
            "Branch Coverage    : 84.0%\n"
            "Condition Coverage : 79.5%\n"
            "Toggle Coverage    : 66.0%\n"
            "Total Coverage     : 80.25%\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert agent.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_threshold=80.0,
        coverage_percent=None,
    ) is True

    summary = tmp_path / "async-fifo" / "reports" / "uvm_coverage_summary.md"
    text = summary.read_text(encoding="utf-8")
    assert "80.2%" in text
    assert "Gate" in text
    assert "PASS" in text


def test_cli_uvm_coverage_async_fifo_invokes_runner(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_uvm_coverage(self, target, output_dir="outputs", coverage_threshold=None, coverage_percent=None):
        calls.append((target, output_dir, coverage_threshold, coverage_percent))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "run_uvm_coverage", fake_run_uvm_coverage)

    assert module.main([
        "--uvm-coverage",
        "async-fifo",
        "--coverage-threshold",
        "80",
        "--coverage-percent",
        "82.5",
        "--output-dir",
        str(tmp_path),
    ]) == 0
    assert calls == [("async-fifo", str(tmp_path), 80.0, 82.5)]


def test_cli_uvm_coverage_async_fifo_keeps_threshold_optional(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_uvm_coverage(self, target, output_dir="outputs", coverage_threshold=None, coverage_percent=None):
        calls.append((target, output_dir, coverage_threshold, coverage_percent))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "run_uvm_coverage", fake_run_uvm_coverage)

    assert module.main(["--uvm-coverage", "async-fifo", "--output-dir", str(tmp_path)]) == 0
    assert calls == [("async-fifo", str(tmp_path), None, None)]


def test_run_async_fifo_uvm_coverage_refreshes_reports_index(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    reports_dir = project_dir / "reports"
    sim_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / "run_vivado_async_fifo_uvm_coverage.tcl").write_text("run\n", encoding="utf-8")
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
        "ASYNC_FIFO_UVM_TEST_DONE\n"
        "ASYNC_FIFO_UVM_FCOV_PASS samples=18\n"
        "ASYNC_FIFO_SVA_PASS\n",
        encoding="utf-8",
    )
    (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb\n", encoding="utf-8")
    coverage_db = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
    coverage_db.mkdir(parents=True, exist_ok=True)
    (coverage_db / "xsim.CCInfo").write_text("async_fifo\n", encoding="utf-8")
    xcrg_code_report = reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html"
    xcrg_func_report = reports_dir / "uvm_coverage_xcrg" / "functionalCoverageReport" / "dashboard.html"
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

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: "vivado")
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: FakeResult())

    assert agent.run_async_fifo_uvm_coverage(output_dir=tmp_path, coverage_threshold=1) is True

    index = reports_dir / "index.md"
    html_index = reports_dir / "index.html"
    assert index.exists()
    assert html_index.exists()
    text = index.read_text(encoding="utf-8")
    html_text = html_index.read_text(encoding="utf-8")
    assert "uvm_coverage_summary.html" in text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in text
    assert "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html" in text
    assert "xcrg_coverage.log" in text
    assert "uvm_coverage_percent.txt" in text
    assert "uvm_coverage_summary.html" in html_text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in html_text


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

    summary = agent.extract_async_fifo_coverage_percent(report)

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
        "Vivado coverage export status : PASS\n",
        encoding="utf-8",
    )

    summary = agent.extract_async_fifo_coverage_percent(report)

    assert summary["available"] is True
    assert summary["total_percent"] == 27.64
    assert summary["metrics"]["statement"] == 60.2041
    assert summary["metrics"]["branch"] == 23.5294
    assert summary["metrics"]["condition"] == 22.0
    assert summary["metrics"]["toggle"] == 4.84


def test_generate_async_fifo_uvm_environment_includes_functional_coverage_and_sva(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    agent.write_async_fifo_uvm_coverage_project(project_dir)

    pkg = (project_dir / "uvm" / "async_fifo_uvm_pkg.sv").read_text(encoding="utf-8")
    sva = (project_dir / "uvm" / "async_fifo_sva.sv").read_text(encoding="utf-8")
    top = (project_dir / "uvm" / "tb_async_fifo_uvm.sv").read_text(encoding="utf-8")
    script = (project_dir / "sim" / "run_vivado_async_fifo_uvm_coverage.tcl").read_text(encoding="utf-8")

    assert "covergroup async_fifo_cg" in pkg
    assert "ASYNC_FIFO_UVM_FCOV_SAMPLE" in pkg
    assert "ASYNC_FIFO_UVM_FCOV_PASS" in pkg
    assert "ASYNC_FIFO_UVM_FCOV summary" in pkg
    assert "module async_fifo_sva" in sva
    assert "p_no_write_when_full" in sva
    assert "p_no_read_when_empty" in sva
    assert "ASYNC_FIFO_SVA_BOUND" in top
    assert "async_fifo_sva.sv" in script


def test_write_async_fifo_uvm_functional_coverage_report(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    sim_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
        "ASYNC_FIFO_UVM_FCOV_SAMPLE full=1 empty=1 reset=1 mixed=1\n"
        "ASYNC_FIFO_UVM_FCOV_PASS samples=18\n"
        "ASYNC_FIFO_UVM_ASSERT_PASS\n",
        encoding="utf-8",
    )

    report = agent.write_async_fifo_uvm_functional_coverage_report(project_dir)

    assert report["passed"] is True
    assert report["markdown_path"].name == "uvm_functional_coverage.md"
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    assert "# async-fifo UVM 功能覆盖率摘要" in text
    assert "full_boundary：FOUND" in text
    assert "empty_boundary：FOUND" in text
    assert "reset_recovery：FOUND" in text
    assert "mixed_traffic：FOUND" in text
    assert "功能覆盖率摘要" in html_text
    assert "functional-card pass" in html_text


def test_run_async_fifo_uvm_random_regression_writes_seed_report(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    calls = []

    def fake_run(output_dir="outputs", data_width=8, addr_width=4, coverage_threshold=None, coverage_percent=None, seed=None):
        calls.append((seed, Path(output_dir)))
        project_dir = Path(output_dir) / "async-fifo"
        sim_dir = project_dir / "sim"
        sim_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n"
            "ASYNC_FIFO_UVM_FCOV_PASS samples=18\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb", encoding="utf-8")
        return True

    monkeypatch.setattr(agent, "run_async_fifo_uvm_coverage", fake_run)

    assert agent.run_async_fifo_uvm_random_regression(output_dir=tmp_path, seeds=[11, 22, 33]) is True

    report = tmp_path / "async-fifo" / "reports" / "uvm_random_regression.md"
    html_report = tmp_path / "async-fifo" / "reports" / "uvm_random_regression.html"
    assert calls == [
        (11, tmp_path / "async-fifo" / "uvm_regression" / "seed_11"),
        (22, tmp_path / "async-fifo" / "uvm_regression" / "seed_22"),
        (33, tmp_path / "async-fifo" / "uvm_regression" / "seed_33"),
    ]
    assert report.exists()
    assert html_report.exists()
    text = report.read_text(encoding="utf-8")
    assert "Seed | Status" in text
    assert "| 11 | PASS |" in text
    assert "| 22 | PASS |" in text
    assert "| 33 | PASS |" in text
    assert "uvm_regression" in text
    assert "seed_11" in text
    assert (tmp_path / "async-fifo" / "uvm_regression" / "seed_11" / "async-fifo" / "sim" / "async_fifo_uvm_coverage.log").exists()


def test_open_async_fifo_uvm_wave_gui_uses_uvm_wdb(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    sim_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb", encoding="utf-8")
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)
    monkeypatch.setattr(module.subprocess, "Popen", lambda command, cwd=None: calls.append(([str(part) for part in command], Path(cwd))))

    assert agent.open_async_fifo_uvm_wave_gui(project_dir, wave_kind="coverage") is True

    script = sim_dir / "open_async_fifo_uvm_coverage_wave.tcl"
    script_text = script.read_text(encoding="utf-8")
    assert "async_fifo_uvm_coverage.wdb" in script_text
    assert "open_wave_database $wave_db" in script_text
    assert "add_wave -r /tb_async_fifo_uvm" in script_text
    assert calls == [([vivado_path, "-mode", "gui", "-source", script.name], sim_dir)]


def test_async_fifo_uvm_wave_screenshot_report_embeds_png_and_capture_script(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    reports_dir = project_dir / "reports"
    sim_dir = project_dir / "sim"
    reports_dir.mkdir(parents=True)
    sim_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb", encoding="utf-8")
    (reports_dir / "uvm_wave_visibility.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

    report = agent.write_async_fifo_uvm_wave_screenshot_report(project_dir, wave_kind="coverage")

    assert report["captured"] is True
    assert report["markdown_path"].name == "uvm_wave_screenshot.md"
    assert report["html_path"].name == "uvm_wave_screenshot.html"
    assert report["capture_script_path"].name == "capture_uvm_wave_screenshot.ps1"
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    script_text = report["capture_script_path"].read_text(encoding="utf-8")
    assert "async-fifo UVM GUI 波形截图验收" in text
    assert "--open-uvm-wave async-fifo --uvm-wave-kind coverage" in text
    assert "uvm_wave_visibility.png" in text
    assert "uvm_wave_visibility.png" in html_text
    assert "capture_uvm_wave_screenshot.ps1" in script_text


def test_cli_uvm_random_regress_and_open_uvm_wave(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_random(self, target, output_dir="outputs", seeds=None):
        calls.append(("random", target, output_dir, seeds))
        return True

    def fake_open(self, target, output_dir="outputs", wave_kind="coverage"):
        calls.append(("open", target, output_dir, wave_kind))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "run_uvm_random_regression", fake_random)
    monkeypatch.setattr(module.DigitalICAgent, "open_uvm_wave", fake_open)

    assert module.main(["--uvm-random-regress", "async-fifo", "--uvm-seeds", "1,2,3", "--output-dir", str(tmp_path)]) == 0
    assert module.main(["--open-uvm-wave", "async-fifo", "--uvm-wave-kind", "smoke", "--output-dir", str(tmp_path)]) == 0
    assert calls == [
        ("random", "async-fifo", str(tmp_path), [1, 2, 3]),
        ("open", "async-fifo", str(tmp_path), "smoke"),
    ]


def test_cli_check_rtl_async_fifo_invokes_checker(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_check_async_fifo_rtl(self, output_dir="outputs"):
        calls.append(output_dir)
        return True

    monkeypatch.setattr(module.DigitalICAgent, "check_async_fifo_rtl", fake_check_async_fifo_rtl)

    assert module.main(["--check-rtl", "async-fifo", "--output-dir", str(tmp_path)]) == 0
    assert calls == [str(tmp_path)]


def test_cli_open_wave_async_fifo_invokes_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_open_rtl_wave(self, target, output_dir="outputs"):
        calls.append((target, output_dir))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "open_rtl_wave", fake_open_rtl_wave)

    assert module.main(["--open-wave", "async-fifo", "--output-dir", str(tmp_path)]) == 0
    assert calls == [("async-fifo", str(tmp_path))]


def test_sim_smoke_rtl_and_testbench_use_same_timescale(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    _sim_dir, rtl_path, tb_path, _vcd_path = agent.write_sim_smoke_sources(tmp_path)

    assert rtl_path.read_text(encoding="utf-8").startswith("`timescale 1ns/1ps")
    assert tb_path.read_text(encoding="utf-8").startswith("`timescale 1ns/1ps")
