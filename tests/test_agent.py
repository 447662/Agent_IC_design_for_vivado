import gzip
import importlib
import importlib.util
import json
import pytest
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / ".trae" / "agent" / "agent.py"
AGENT_RUNTIME_PATH = ROOT / ".trae" / "agent" / "agent_runtime.py"
AGENT_CLI_PATH = ROOT / ".trae" / "agent" / "agent_cli.py"
AGENT_ENTRYPOINT_PATH = ROOT / ".trae" / "agent" / "agent_entrypoint.py"
AGENT_COMPOSITION_PATH = ROOT / ".trae" / "agent" / "agent_composition.py"
AGENT_CONFIG_HELPERS_PATH = ROOT / ".trae" / "agent" / "agent_config.py"
AGENT_REPORTS_PATH = ROOT / ".trae" / "agent" / "agent_reports.py"
AGENT_WAVEFORM_PATH = ROOT / ".trae" / "agent" / "agent_waveform.py"
TARGET_REGISTRY_PATH = ROOT / ".trae" / "agent" / "target_registry.py"
TARGET_SCAFFOLDER_PATH = ROOT / ".trae" / "agent" / "target_scaffolder.py"
ARTIFACT_MANIFEST_PATH = ROOT / ".trae" / "agent" / "artifact_manifest.py"
ENVIRONMENT_REPORT_PATH = ROOT / ".trae" / "agent" / "environment_report.py"
PROJECT_OVERVIEW_PATH = ROOT / ".trae" / "agent" / "project_overview.py"
WAVEFORM_SAMPLES_PATH = ROOT / ".trae" / "agent" / "waveform_samples.py"
COVERAGE_CLOSURE_PATH = ROOT / ".trae" / "agent" / "coverage_closure.py"
COVERAGE_HISTORY_PATH = ROOT / ".trae" / "agent" / "coverage_history.py"
FAILURE_ARCHIVE_PATH = ROOT / ".trae" / "agent" / "failure_archive.py"
WAVE_VISIBILITY_PATH = ROOT / ".trae" / "agent" / "wave_visibility.py"
XCRG_COVERAGE_PATH = ROOT / ".trae" / "agent" / "xcrg_coverage.py"
COVERAGE_RECOMMENDATIONS_PATH = (
    ROOT / ".trae" / "agent" / "coverage_recommendations.py"
)
TARGET_CHECKS_PATH = ROOT / ".trae" / "agent" / "target_checks.py"
TARGET_FLOWS_PATH = ROOT / ".trae" / "agent" / "target_flows.py"
ADAPTERS_DIR = ROOT / ".trae" / "agent" / "adapters"
REPORT_ADAPTER_PATH = ADAPTERS_DIR / "report.py"
WAVEFORM_ADAPTER_PATH = ADAPTERS_DIR / "waveform.py"
VIVADO_ADAPTER_PATH = ADAPTERS_DIR / "vivado.py"
AGENT_CONFIG_PATH = ROOT / ".trae" / "agent" / "agent.json"
AGENT_TARGETS_DIR = ROOT / ".trae" / "agent" / "targets"
TRAE_CONFIG_PATH = ROOT / ".trae" / "config.json"
HANDSHAKE_VCD_PATH = (
    ROOT
    / "VCD_ANALYZER-main"
    / "VCD_ANALYZER-main"
    / "verify"
    / "fixtures"
    / "handshake_trace.vcd"
)
WAVEFORM_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "waveforms"
P5_12_VCD_PATH = WAVEFORM_FIXTURES_DIR / "handshake_trace.vcd"
P5_12_FST_PATH = WAVEFORM_FIXTURES_DIR / "handshake_trace.fst"
P5_12_GHW_PATH = WAVEFORM_FIXTURES_DIR / "time_test.ghw"


def load_agent_module():
    spec = importlib.util.spec_from_file_location("digital_ic_agent", AGENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_local_module(module_name, module_path):
    module_dir = str(module_path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
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


def write_round_robin_vcd_fixture(path):
    scenario_bits = format(int.from_bytes(b"fairness_window", "big"), "0128b")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """$date
    P0 integration fixture
$end
$version
    DigitalICAgent tests
$end
$timescale 1ns $end
$scope module tb_round_robin_arbiter $end
$var wire 1 ! grant_valid $end
$var integer 32 " grant_count $end
$var wire 4 # req [3:0] $end
$var wire 4 $ grant [3:0] $end
$var reg 128 % scenario_id [127:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b0 "
b0000 #
b0000 $
b0 %
#10
1!
b1 "
b1111 #
b0001 $
b__SCENARIO__ %
#20
b10 "
b0010 $
#30
0!
""".replace("__SCENARIO__", scenario_bits),
        encoding="utf-8",
    )


def test_configure_text_stream_uses_utf8_replacement_mode():
    module = load_agent_module()
    calls = []

    class FakeStream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    module._configure_text_stream(FakeStream())

    assert calls == [{
        "encoding": "utf-8",
        "errors": "replace",
        "write_through": True,
    }]


def test_command_runner_applies_timeout_and_utf8_defaults(monkeypatch):
    module = load_agent_module()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="完成", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    runner = module.CommandRunner(default_timeout=17)

    result = runner.run(["tool", "--version"], capture_output=True, text=True)

    assert result.returncode == 0
    assert captured["command"] == ["tool", "--version"]
    assert captured["kwargs"]["timeout"] == 17
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"


def test_command_runner_converts_timeout_to_failed_result(monkeypatch):
    module = load_agent_module()

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output="partial")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    runner = module.CommandRunner(default_timeout=9)

    result = runner.run(["slow-tool"], capture_output=True, text=True)

    assert result.returncode == 124
    assert "timed out after 9 seconds" in result.stderr
    assert result.stdout == "partial"


def test_runtime_components_live_in_dedicated_module():
    assert AGENT_RUNTIME_PATH.exists()

    runtime = load_local_module("agent_runtime", AGENT_RUNTIME_PATH)
    module = load_agent_module()

    assert module.CommandRunner is runtime.CommandRunner
    assert module.TargetHandler is runtime.TargetHandler


def test_cli_helpers_live_in_dedicated_module():
    assert AGENT_CLI_PATH.exists()

    cli = load_local_module("agent_cli", AGENT_CLI_PATH)
    module = load_agent_module()

    assert module.parse_args is cli.parse_args
    assert module.parse_seed_list is cli.parse_seed_list
    assert module.build_requirement is cli.build_requirement

    args = cli.parse_args(["--list-targets"])
    assert args.list_targets is True
    assert cli.parse_seed_list("1, 2,3") == [1, 2, 3]


def test_cli_entrypoint_and_composition_live_in_dedicated_modules(monkeypatch):
    assert AGENT_ENTRYPOINT_PATH.exists()
    assert AGENT_COMPOSITION_PATH.exists()

    entrypoint = load_local_module("agent_entrypoint", AGENT_ENTRYPOINT_PATH)
    composition = load_local_module("agent_composition", AGENT_COMPOSITION_PATH)
    module = load_agent_module()

    assert module.run_cli is entrypoint.run_cli
    assert module.build_agent is composition.build_agent

    calls = []

    def fake_run_cli(argv, agent_factory):
        calls.append((argv, agent_factory))
        return 7

    monkeypatch.setattr(module, "run_cli", fake_run_cli)

    assert module.main(["--list-targets"]) == 7
    assert calls == [(["--list-targets"], module.create_agent)]


def test_config_helpers_live_in_dedicated_module():
    assert AGENT_CONFIG_HELPERS_PATH.exists()

    config_helpers = load_local_module(
        "agent_config",
        AGENT_CONFIG_HELPERS_PATH,
    )
    module = load_agent_module()

    assert module.load_agent_config is config_helpers.load_agent_config
    assert (
        module.normalize_configured_command
        is config_helpers.normalize_configured_command
    )
    assert config_helpers.load_agent_config(AGENT_CONFIG_PATH) == json.loads(
        AGENT_CONFIG_PATH.read_text(encoding="utf-8")
    )
    assert config_helpers.normalize_configured_command("uvx synthpilot") == [
        "uvx",
        "synthpilot",
    ]
    assert config_helpers.normalize_configured_command(["uvx", "synthpilot"]) == [
        "uvx",
        "synthpilot",
    ]


def test_report_renderer_lives_in_dedicated_module():
    assert AGENT_REPORTS_PATH.exists()

    reports = load_local_module("agent_reports", AGENT_REPORTS_PATH)
    module = load_agent_module()

    assert (
        module.render_markdown_html_document
        is reports.render_markdown_document_html
    )
    html_text = reports.render_markdown_document_html(
        "验证报告",
        "# 标题\n\n| 项目 | 状态 |\n| --- | --- |\n| smoke | PASS |\n",
    )
    assert "<title>验证报告</title>" in html_text
    assert "<th>项目</th>" in html_text
    assert "<td>PASS</td>" in html_text


def test_waveform_resolvers_live_in_dedicated_module(tmp_path):
    assert AGENT_WAVEFORM_PATH.exists()

    waveform = load_local_module("agent_waveform", AGENT_WAVEFORM_PATH)
    module = load_agent_module()

    assert module.get_vcd_analyzer_path is waveform.resolve_vcd_analyzer_path
    assert module.get_rwave_source_dir is waveform.resolve_rwave_source_dir
    assert module.get_rwave_command is waveform.resolve_rwave_command

    source_dir = tmp_path / "RWaveAnalyzer-main" / "RWaveAnalyzer-main"
    (source_dir / "crates" / "rwave").mkdir(parents=True)
    (source_dir / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    binary = source_dir / "target" / "release" / "rwave.exe"
    binary.parent.mkdir(parents=True)
    binary.write_text("binary", encoding="utf-8")

    assert waveform.resolve_rwave_source_dir(tmp_path) == source_dir
    assert waveform.resolve_rwave_command(
        tmp_path,
        env={},
        which=lambda _: None,
    ) == str(binary)


def test_target_flow_builder_lives_in_dedicated_module():
    assert TARGET_FLOWS_PATH.exists()

    flows = load_local_module("target_flows", TARGET_FLOWS_PATH)
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert (
        module.build_registered_target_handlers
        is flows.build_target_handlers
    )
    assert set(flows.build_target_handlers(agent)) == {
        "async-fifo",
        "round-robin-arbiter",
        "sync-fifo",
    }


def test_generic_target_checks_live_in_dedicated_module(tmp_path):
    assert TARGET_CHECKS_PATH.exists()

    target_checks = load_local_module("target_checks", TARGET_CHECKS_PATH)
    module = load_agent_module()

    assert module.run_rtl_project_checks is target_checks.check_rtl_project

    project_dir = tmp_path / "demo"
    rtl_path = project_dir / "rtl" / "demo.v"
    tb_path = project_dir / "tb" / "tb_demo.v"
    sim_dir = project_dir / "sim"
    vivado_dir = project_dir / "vivado_project"
    reports_dir = project_dir / "reports"
    for directory in (rtl_path.parent, tb_path.parent, sim_dir, vivado_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)
    rtl_path.write_text("module demo; endmodule\n", encoding="utf-8")
    tb_path.write_text("module tb_demo; endmodule\n", encoding="utf-8")
    for name in ("run.tcl", "project.tcl", "gui.tcl", "trace.vcd", "trace.wdb"):
        (sim_dir / name).write_text("fixture\n", encoding="utf-8")
    (vivado_dir / "demo.xpr").write_text("<Project />\n", encoding="utf-8")
    (reports_dir / "sim_report.md").write_text("# PASS\n", encoding="utf-8")

    assert target_checks.check_rtl_project(
        target_name="demo",
        output_dir=tmp_path,
        rtl_name="demo.v",
        tb_name="tb_demo.v",
        sim_script_name="run.tcl",
        project_script_name="project.tcl",
        gui_script_name="gui.tcl",
        xpr_name="demo.xpr",
        vcd_name="trace.vcd",
        wave_db_resolver=lambda current_sim_dir: current_sim_dir / "trace.wdb",
        rtl_markers=[("RTL marker", "module demo")],
        tb_markers=[("TB marker", "module tb_demo")],
    ) is True


def test_p5_9_adapter_modules_own_extracted_agent_methods():
    assert REPORT_ADAPTER_PATH.exists()
    assert WAVEFORM_ADAPTER_PATH.exists()
    assert VIVADO_ADAPTER_PATH.exists()

    module = load_agent_module()
    report_adapter = importlib.import_module("adapters.report")
    waveform_adapter = importlib.import_module("adapters.waveform")
    vivado_adapter = importlib.import_module("adapters.vivado")

    assert module.DigitalICAgent.target_spec_catalog is report_adapter.target_spec_catalog
    assert (
        module.DigitalICAgent.target_scenario_catalog
        is report_adapter.target_scenario_catalog
    )
    assert (
        module.DigitalICAgent.render_target_design_spec
        is report_adapter.render_target_design_spec
    )
    assert (
        module.DigitalICAgent.write_target_design_spec
        is report_adapter.write_target_design_spec
    )
    assert (
        module.DigitalICAgent.render_target_verification_plan
        is report_adapter.render_target_verification_plan
    )
    assert (
        module.DigitalICAgent.write_target_verification_plan
        is report_adapter.write_target_verification_plan
    )
    assert module.DigitalICAgent.run_rwave_json is waveform_adapter.run_rwave_json
    assert (
        module.DigitalICAgent.run_rwave_batch_json
        is waveform_adapter.run_rwave_batch_json
    )
    assert (
        module.DigitalICAgent.run_vcd_analyzer_json
        is waveform_adapter.run_vcd_analyzer_json
    )
    assert (
        module.DigitalICAgent.run_waveform_analyzer_json
        is waveform_adapter.run_waveform_analyzer_json
    )
    assert (
        module.DigitalICAgent.resolve_vivado_command
        is vivado_adapter.resolve_vivado_command
    )
    assert module.DigitalICAgent.run_vivado_batch is vivado_adapter.run_vivado_batch
    assert module.DigitalICAgent.launch_vivado_gui is vivado_adapter.launch_vivado_gui


def test_p5_9_waveform_adapter_reports_rwave_and_batch_errors(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: None)
    with pytest.raises(FileNotFoundError, match="rwave binary not found"):
        agent.run_rwave_batch_json(tmp_path / "trace.vcd", ["info"])

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: "rwave")
    monkeypatch.setattr(
        agent.command_runner,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr="rwave failed",
        ),
    )
    with pytest.raises(RuntimeError, match="rwave failed"):
        agent.run_rwave_json("info", tmp_path / "trace.vcd")
    with pytest.raises(RuntimeError, match="rwave failed"):
        agent.run_rwave_batch_json(tmp_path / "trace.vcd", ["info"])

    monkeypatch.setattr(
        agent.command_runner,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout="not-json",
            stderr="",
        ),
    )
    with pytest.raises(RuntimeError, match="invalid JSON"):
        agent.run_rwave_json("info", tmp_path / "trace.vcd")
    with pytest.raises(RuntimeError, match="invalid JSON"):
        agent.run_rwave_batch_json(tmp_path / "trace.vcd", ["info"])

    monkeypatch.setattr(
        agent.command_runner,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout='{"result": {}}\n',
            stderr="",
        ),
    )
    with pytest.raises(RuntimeError, match="missing id"):
        agent.run_rwave_batch_json(tmp_path / "trace.vcd", ["info"])

    monkeypatch.setattr(
        agent.command_runner,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout='{"id": "info", "ok": false, "error": "bad command"}\n',
            stderr="",
        ),
    )
    with pytest.raises(RuntimeError, match="info: bad command"):
        agent.run_rwave_batch_json(tmp_path / "trace.vcd", ["info"])


def test_p5_9_waveform_adapter_handles_vcd_and_fallback_errors(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    analyzer_path = tmp_path / "vcd_analyzer.py"

    monkeypatch.setattr(agent, "resolve_vcd_analyzer_path", lambda: analyzer_path)
    with pytest.raises(FileNotFoundError, match="VCD analyzer not found"):
        agent.run_vcd_analyzer_json("info", tmp_path / "trace.vcd")

    analyzer_path.write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setattr(
        agent.command_runner,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr="analyzer failed",
        ),
    )
    with pytest.raises(RuntimeError, match="analyzer failed"):
        agent.run_vcd_analyzer_json("info", tmp_path / "trace.vcd")

    monkeypatch.setattr(
        agent.command_runner,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout="not-json",
            stderr="",
        ),
    )
    with pytest.raises(RuntimeError, match="invalid JSON"):
        agent.run_vcd_analyzer_json("info", tmp_path / "trace.vcd")
    with pytest.raises(ValueError, match="Unsupported waveform backend"):
        agent.run_waveform_analyzer_json("info", backend="unknown")

    monkeypatch.setattr(
        agent,
        "run_rwave_json",
        lambda *args: (_ for _ in ()).throw(RuntimeError("rwave crashed")),
    )
    monkeypatch.setattr(
        agent,
        "run_vcd_analyzer_json",
        lambda *args: {"signal_count": 1, "_waveform_backend": "vcd_analyzer"},
    )
    result = agent.run_waveform_analyzer_json("info", backend="auto")
    assert result["_waveform_backend_fallback_reason"] == "rwave crashed"

    monkeypatch.setattr(
        agent,
        "run_vcd_analyzer_json",
        lambda *args: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )
    with pytest.raises(RuntimeError, match="rwave crashed"):
        agent.run_waveform_analyzer_json("info", backend="auto")


def test_project_owned_text_files_are_valid_utf8():
    paths = [ROOT / "README.md"]
    paths.extend((ROOT / ".trae").rglob("*.py"))
    paths.extend((ROOT / ".trae").rglob("*.json"))
    paths.extend((ROOT / ".trae").rglob("*.md"))
    paths.extend(
        path
        for path in (ROOT / "docs").rglob("*.md")
        if "tools_archive" not in path.parts
    )

    for path in paths:
        text = path.read_bytes().decode("utf-8")
        assert "\ufffd" not in text, path


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


@pytest.mark.parametrize(
    ("requirement", "expected_skills"),
    [
        ("不需要UVM，只做RTL", ["digital-ic-rtl-designer"]),
        ("不要设计文档，只实现RTL", ["digital-ic-rtl-designer"]),
        ("只生成设计文档，不要RTL和仿真", ["digital-ic-designer"]),
    ],
)
def test_analyze_requirement_respects_negated_skill_keywords(
    requirement,
    expected_skills,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement(requirement) == expected_skills


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


def test_waveform_analyzer_prefers_rwave_when_available(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "wave.vcd"
    vcd_path.write_text("$date\nwave\n$end\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: "rwave")

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = '{"signal_count":3,"duration_h":"20 ns"}'
            stderr = ""

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = agent.run_waveform_analyzer_json("info", vcd_path)

    assert result["signal_count"] == 3
    assert result["_waveform_backend"] == "rwave"
    assert calls == [["rwave", "--json", "info", str(vcd_path)]]


def test_waveform_analyzer_falls_back_to_vcd_analyzer(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "wave.vcd"
    vcd_path.write_text("$date\nwave\n$end\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: None)

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = '{"signal_count":2,"duration_h":"10 ns"}'
            stderr = ""

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = agent.run_waveform_analyzer_json("info", vcd_path)

    assert result["signal_count"] == 2
    assert result["_waveform_backend"] == "vcd_analyzer"
    assert calls == [[sys.executable, str(agent.resolve_vcd_analyzer_path()), "--json", "info", str(vcd_path)]]


def test_waveform_analyzer_can_force_vcd_analyzer(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "wave.vcd"
    vcd_path.write_text("$date\nwave\n$end\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: "rwave")

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = '{"signal_count":4,"duration_h":"30 ns"}'
            stderr = ""

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = agent.run_waveform_analyzer_json("info", vcd_path, backend="vcd-analyzer")

    assert result["signal_count"] == 4
    assert result["_waveform_backend"] == "vcd_analyzer"
    assert calls == [[sys.executable, str(agent.resolve_vcd_analyzer_path()), "--json", "info", str(vcd_path)]]


def test_waveform_analyzer_can_require_rwave(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "wave.vcd"
    vcd_path.write_text("$date\nwave\n$end\n", encoding="utf-8")

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: None)

    try:
        agent.run_waveform_analyzer_json("info", vcd_path, backend="rwave")
    except FileNotFoundError as exc:
        assert "rwave" in str(exc).lower()
    else:
        raise AssertionError("Expected forced rwave backend to fail when rwave is missing")


def test_rwave_batch_json_parses_ndjson_results(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "wave.vcd"
    vcd_path.write_text("$date\nwave\n$end\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: "rwave")

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

        class Result:
            returncode = 0
            stdout = "\n".join([
                '{"id":"info","ok":true,"result":{"signal_count":12}}',
                '{"id":"write_events","ok":true,"result":{"total":2,"events":[]}}',
                '{"id":"read_events","ok":true,"result":{"total":3,"events":[]}}',
            ])
            stderr = ""

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = agent.run_rwave_batch_json(vcd_path, [
        "info #info",
        "search --condition tb_async_fifo.full=0 --changed tb_async_fifo.write_count #write_events",
        "search --condition tb_async_fifo.error_count=0 --changed tb_async_fifo.read_count #read_events",
    ])

    assert result["info"]["signal_count"] == 12
    assert result["write_events"]["total"] == 2
    assert result["read_events"]["total"] == 3
    assert calls[0][0] == ["rwave", "--batch", "--json", str(vcd_path)]
    assert "info #info" in calls[0][1]["input"]
    assert "tb_async_fifo.write_count" in calls[0][1]["input"]
    assert "tb_async_fifo.read_count" in calls[0][1]["input"]


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

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
        calls.append([str(part) for part in command])
        if command[0] == "iverilog":
            assert "-o" in command
        elif command[0] == "vvp":
            vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
            vcd_path.write_text("$date\nsim smoke test\n$end\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    analyzed = {}

    def fake_analyze_vcd(vcd_path, condition=None, show=None, limit=20, waveform_backend="auto"):
        analyzed["vcd_path"] = Path(vcd_path)
        analyzed["condition"] = condition
        analyzed["show"] = show
        analyzed["limit"] = limit
        analyzed["waveform_backend"] = waveform_backend
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
    assert analyzed["waveform_backend"] == "auto"


def test_run_sim_smoke_uses_vivado_and_analyzes_vcd(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    calls = []
    gui_calls = []

    monkeypatch.setattr(agent, "detect_simulator", lambda: "vivado")
    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat")
    monkeypatch.setattr(agent, "open_vivado_wave_gui", lambda sim_dir, vcd_path: gui_calls.append((Path(sim_dir), Path(vcd_path))) or True)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
        calls.append([str(part) for part in command])
        assert command[0] == r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
        assert "-mode" in command
        assert "-source" in command
        assert command[command.index("-source") + 1] == "run_vivado_sim.tcl"
        vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
        vcd_path.write_text("$date\nvivado sim smoke test\n$end\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="Vivado simulation done", stderr="")

    analyzed = {}

    def fake_analyze_vcd(vcd_path, condition=None, show=None, limit=20, waveform_backend="auto"):
        analyzed["vcd_path"] = Path(vcd_path)
        analyzed["condition"] = condition
        analyzed["show"] = show
        analyzed["limit"] = limit
        analyzed["waveform_backend"] = waveform_backend
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
    assert analyzed["waveform_backend"] == "auto"
    assert gui_calls == [(tmp_path / "sim-smoke", tmp_path / "sim-smoke" / "handshake_trace.vcd")]


def test_run_vivado_sim_smoke_can_skip_wave_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat")

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
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


def test_p5_10_environment_report_writes_chinese_markdown_html_and_manifest(tmp_path):
    module = load_local_module("environment_report_complete", ENVIRONMENT_REPORT_PATH)

    class FakeRunner:
        def run(self, command, **_kwargs):
            output = {
                "git": "git version 2.50.0",
                "vivado": "Vivado v2025.2",
                "rwave": "rwave 0.4.0",
            }.get(Path(str(command[0])).stem.lower(), "tool 1.0")
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    class FakeAgent:
        project_root = ROOT
        command_runner = FakeRunner()

        def resolve_vivado_command(self):
            return "vivado"

        def resolve_rwave_command(self):
            return "rwave"

        def resolve_vcd_analyzer_path(self):
            return ROOT / "VCD_ANALYZER-main" / "VCD_ANALYZER-main" / "vcd_analyzer.py"

    result = module.write_environment_report(
        FakeAgent(),
        output_dir=tmp_path,
        env={"SESSIONNAME": "Console"},
        which=lambda name: name if name == "git" else None,
        platform_system=lambda: "Windows",
        version_info=(3, 11, 9),
        python_executable="C:/Python311/python.exe",
    )

    assert result["status"] == "PASS"
    assert result["markdown_path"] == tmp_path / "environment-report" / "environment_report.md"
    assert result["html_path"] == tmp_path / "environment-report" / "environment_report.html"
    assert result["manifest_path"] == tmp_path / "environment-report" / "artifacts.json"

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))

    assert "# 数字 IC Agent 环境预检报告" in markdown
    assert "Python" in markdown
    assert "Git" in markdown
    assert "Vivado" in markdown
    assert "RWave" in markdown
    assert "输出目录权限" in markdown
    assert "GUI 前置条件" in markdown
    assert "环境预检报告" in html_text
    assert "乱码" not in html_text
    assert manifest["scope"] == "environment"
    assert manifest["runs"][-1]["status"] == "PASS"
    assert {
        item["path"]
        for item in manifest["runs"][-1]["artifacts"]
    } == {"environment_report.md", "environment_report.html"}


def test_history_rotation_archives_environment_manifest_runs(tmp_path):
    module = load_local_module(
        "environment_report_rotation",
        ENVIRONMENT_REPORT_PATH,
    )
    report_dir = tmp_path / "environment-report"
    report_dir.mkdir()
    report_paths = [
        report_dir / "environment_report.md",
        report_dir / "environment_report.html",
    ]
    for path in report_paths:
        path.write_text(path.name, encoding="utf-8")

    manifest_path = report_dir / "artifacts.json"
    for index in range(4):
        module.write_environment_manifest(
            manifest_path,
            tmp_path,
            "PASS",
            "2026-07-11T00:0{}:00.000Z".format(index),
            [{"name": "sequence", "status": "PASS", "detail": index}],
            report_paths,
            max_active_runs=2,
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [
        run["checks"][0]["detail"]
        for run in manifest["runs"]
    ] == [2, 3]
    assert manifest["history"] == {
        "active_limit": 2,
        "archive_path": "artifacts.archive.jsonl.gz",
        "archived_runs": 2,
    }

    archive_path = report_dir / "artifacts.archive.jsonl.gz"
    with gzip.open(archive_path, "rt", encoding="utf-8") as stream:
        archived = [
            json.loads(line)
            for line in stream.read().splitlines()
        ]
    assert [
        run["checks"][0]["detail"]
        for run in archived
    ] == [0, 1]


def test_p5_10_environment_report_warns_for_missing_optional_tools(tmp_path):
    module = load_local_module("environment_report_missing_tools", ENVIRONMENT_REPORT_PATH)

    class FakeRunner:
        def run(self, command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="git version 2.50.0",
                stderr="",
            )

    class FakeAgent:
        project_root = ROOT
        command_runner = FakeRunner()

        def resolve_vivado_command(self):
            return None

        def resolve_rwave_command(self):
            return None

        def resolve_vcd_analyzer_path(self):
            return tmp_path / "missing-vcd-analyzer.py"

    result = module.write_environment_report(
        FakeAgent(),
        output_dir=tmp_path,
        env={},
        which=lambda name: "git" if name == "git" else None,
        platform_system=lambda: "Windows",
        version_info=(3, 11, 9),
        python_executable="C:/Python311/python.exe",
    )

    assert result["status"] == "WARN"
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    assert "| Vivado | WARN |" in markdown
    assert "| RWave / VCD_ANALYZER | WARN |" in markdown
    assert "| GUI 前置条件 | WARN |" in markdown
    assert "修复建议" in markdown
    assert "未检测到 Vivado" in markdown
    assert "未检测到 RWave" in markdown


def test_p5_10_environment_report_accepts_vivado_version_banner_on_nonzero_exit():
    module = load_local_module(
        "environment_report_vivado_banner",
        ENVIRONMENT_REPORT_PATH,
    )

    class FakeRunner:
        def run(self, command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="Vivado v2025.2 (64-bit) SW Build 6299465",
                stderr="",
            )

    class FakeAgent:
        command_runner = FakeRunner()

        def resolve_vivado_command(self):
            return r"D:\vivado\2025.2\Vivado\bin\vivado.bat"

    check = module._check_vivado(FakeAgent())

    assert check["status"] == "PASS"
    assert "Vivado v2025.2" in check["detail"]


def test_p5_10_environment_report_rejects_unwritable_output_path(tmp_path):
    module = load_local_module("environment_report_unwritable", ENVIRONMENT_REPORT_PATH)
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("blocked", encoding="utf-8")

    class FakeAgent:
        project_root = ROOT
        command_runner = None

    with pytest.raises(OSError):
        module.write_environment_report(FakeAgent(), output_dir=output_file)


def test_p5_10_cli_reports_output_failure_without_traceback(tmp_path):
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("blocked", encoding="utf-8")

    result = run_agent(
        "--environment-report",
        "--output-dir",
        str(output_file),
    )

    assert result.returncode == 1
    assert "环境预检报告生成失败" in result.stderr
    assert "Traceback" not in result.stderr


def test_p5_11_project_overview_aggregates_targets_environment_and_links(tmp_path):
    module = load_local_module("project_overview_complete", PROJECT_OVERVIEW_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                },
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                },
            ]

    async_dir = tmp_path / "async-fifo"
    sync_dir = tmp_path / "sync-fifo"
    environment_dir = tmp_path / "environment-report"
    for report_path in [
        async_dir / "reports" / "design_spec.html",
        async_dir / "reports" / "sim_report.html",
        async_dir / "reports" / "wave_visibility.html",
        sync_dir / "reports" / "design_spec.html",
        sync_dir / "reports" / "sim_report.html",
        environment_dir / "environment_report.html",
    ]:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("<html lang=\"zh-CN\"></html>\n", encoding="utf-8")

    (async_dir / "artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target": "async-fifo",
                "updated_at": "2026-07-10T12:00:00.000Z",
                "runs": [
                    {
                        "flow": "generate-spec",
                        "status": "PASS",
                        "recorded_at": "2026-07-10T10:00:00.000Z",
                        "error": None,
                    },
                    {
                        "flow": "sim-rtl",
                        "status": "FAIL",
                        "recorded_at": "2026-07-10T12:00:00.000Z",
                        "error": "simulation failed",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sync_dir / "artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target": "sync-fifo",
                "updated_at": "2026-07-10T11:00:00.000Z",
                "runs": [
                    {
                        "flow": "sim-rtl",
                        "status": "PASS",
                        "recorded_at": "2026-07-10T11:00:00.000Z",
                        "error": None,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (environment_dir / "artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": "environment",
                "updated_at": "2026-07-10T09:00:00.000Z",
                "runs": [
                    {
                        "flow": "environment-report",
                        "status": "WARN",
                        "recorded_at": "2026-07-10T09:00:00.000Z",
                        "error": None,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = module.write_project_overview(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "FAIL"
    assert result["target_count"] == 2
    assert result["ready_target_count"] == 1
    assert result["failed_target_count"] == 1
    assert result["environment_status"] == "WARN"
    assert [item["name"] for item in result["targets"]] == [
        "async-fifo",
        "sync-fifo",
    ]

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "# 数字 IC Agent 多目标项目总览" in markdown
    assert "| async-fifo | Asynchronous FIFO | FAIL | sim-rtl | FAIL |" in markdown
    assert "| sync-fifo | Synchronous FIFO | PASS | sim-rtl | PASS |" in markdown
    assert "simulation failed" in markdown
    assert "environment-report/environment_report.html" in markdown
    assert 'href="async-fifo/reports/design_spec.html"' in html_text
    assert 'href="async-fifo/reports/sim_report.html"' in html_text
    assert 'href="async-fifo/reports/wave_visibility.html"' in html_text
    assert 'href="sync-fifo/reports/design_spec.html"' in html_text
    assert 'class="target-card fail"' in html_text
    assert 'class="target-card pass"' in html_text
    assert "乱码" not in html_text


def test_p5_11_project_overview_handles_empty_output_as_not_run(tmp_path):
    module = load_local_module("project_overview_empty", PROJECT_OVERVIEW_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                },
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                },
            ]

    result = module.write_project_overview(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "WARN"
    assert result["target_count"] == 2
    assert result["ready_target_count"] == 0
    assert result["failed_target_count"] == 0
    assert result["environment_status"] == "MISSING"
    assert [item["status"] for item in result["targets"]] == [
        "NOT_RUN",
        "NOT_RUN",
    ]
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "尚无运行记录" in markdown
    assert "NOT_RUN" in markdown
    assert markdown.count("manifest 尚未生成") == 3
    assert html_text.count("manifest 尚未生成") == 3
    for missing_href in [
        "environment-report/artifacts.json",
        "async-fifo/artifacts.json",
        "sync-fifo/artifacts.json",
    ]:
        assert missing_href not in markdown
        assert missing_href not in html_text


def test_p5_11_project_overview_keeps_other_targets_when_manifest_is_invalid(tmp_path):
    module = load_local_module("project_overview_invalid", PROJECT_OVERVIEW_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                },
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                },
            ]

    async_dir = tmp_path / "async-fifo"
    sync_dir = tmp_path / "sync-fifo"
    async_dir.mkdir(parents=True)
    sync_dir.mkdir(parents=True)
    (async_dir / "artifacts.json").write_text("{broken", encoding="utf-8")
    (sync_dir / "artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target": "sync-fifo",
                "updated_at": "2026-07-10T11:00:00.000Z",
                "runs": [
                    {
                        "flow": "generate-rtl",
                        "status": "PASS",
                        "recorded_at": "2026-07-10T11:00:00.000Z",
                        "error": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = module.write_project_overview(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "FAIL"
    assert result["targets"][0]["status"] == "INVALID"
    assert result["targets"][1]["status"] == "PASS"
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    assert "artifacts.json" in markdown
    assert "INVALID" in markdown
    assert "manifest JSON 无效" in markdown
    assert "sync-fifo" in markdown


def test_p4_7_target_dashboard_groups_stages_recent_run_and_failure_entry(tmp_path):
    module = load_local_module("project_overview_p4_7", PROJECT_OVERVIEW_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                },
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                },
            ]

    project_dir = tmp_path / "async-fifo"
    reports_dir = project_dir / "reports"
    (project_dir / "rtl").mkdir(parents=True)
    (project_dir / "uvm").mkdir()
    reports_dir.mkdir()
    (project_dir / "rtl" / "async_fifo.v").write_text(
        "module async_fifo; endmodule\n",
        encoding="utf-8",
    )
    (project_dir / "uvm" / "tb_async_fifo_uvm.sv").write_text(
        "module tb_async_fifo_uvm; endmodule\n",
        encoding="utf-8",
    )
    (project_dir / "README.md").write_text("# async-fifo\n", encoding="utf-8")
    for relative_path in [
        "design_spec.html",
        "sim_summary.html",
        "uvm_coverage_summary.html",
        "wave_visibility.html",
        "coverage_trend.html",
    ]:
        (reports_dir / relative_path).write_text(
            "<html></html>\n",
            encoding="utf-8",
        )
    xcrg_dashboard = (
        reports_dir
        / "uvm_coverage_xcrg"
        / "codeCoverageReport"
        / "dashboard.html"
    )
    xcrg_detail = xcrg_dashboard.parent / "modules" / "detail.html"
    xcrg_detail.parent.mkdir(parents=True)
    xcrg_dashboard.write_text("<html>dashboard</html>\n", encoding="utf-8")
    xcrg_detail.write_text("<html>detail</html>\n", encoding="utf-8")
    (project_dir / "artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target": "async-fifo",
                "updated_at": "2026-07-10T12:03:00Z",
                "runs": [
                    {
                        "flow": "sim-rtl",
                        "status": "PASS",
                        "recorded_at": "2026-07-10T12:00:00Z",
                        "command": ["python", "agent.py", "--sim-rtl", "async-fifo"],
                        "error": None,
                    },
                    {
                        "flow": "uvm-coverage",
                        "status": "FAIL",
                        "recorded_at": "2026-07-10T12:01:00Z",
                        "command": ["python", "agent.py", "--uvm-coverage", "async-fifo"],
                        "error": "coverage gate failed",
                    },
                    {
                        "flow": "check-rtl",
                        "status": "PASS",
                        "recorded_at": "2026-07-10T12:03:00Z",
                        "command": ["python", "agent.py", "--check-rtl", "async-fifo"],
                        "error": None,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    failure_manifest = (
        project_dir
        / "failure_archives"
        / "uvm-coverage"
        / "seed_22"
        / "failure_archive.json"
    )
    failure_manifest.parent.mkdir(parents=True)
    failure_manifest.write_text("{}\n", encoding="utf-8")
    (tmp_path / "sync-fifo" / "reports").mkdir(parents=True)

    result = module.write_target_dashboard(FakeAgent(), project_dir)

    assert result["target_count"] == 2
    assert result["stage_count"] == 7
    assert result["ready_stage_count"] == 7
    assert result["latest_run"]["flow"] == "check-rtl"
    assert result["latest_run"]["status"] == "PASS"
    assert result["last_failure"]["flow"] == "uvm-coverage"
    assert result["failure_href"] == (
        "../failure_archives/uvm-coverage/seed_22/failure_archive.json"
    )

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "## 阶段状态" in markdown
    assert "## 最近运行" in markdown
    assert "## 最近失败" in markdown
    assert "coverage gate failed" in markdown
    assert "coverage_trend.html" in markdown
    assert 'class="target-selector"' in html_text
    assert 'aria-current="page">async-fifo</a>' in html_text
    assert 'href="../../index.html#target-sync-fifo"' in html_text
    for stage in [
        "Spec",
        "RTL",
        "Simulation",
        "UVM",
        "Coverage",
        "Wave",
        "Lessons",
    ]:
        assert 'data-stage="{}"'.format(stage) in html_text
    assert 'class="failure-entry fail"' in html_text
    assert "coverage gate failed" in html_text
    assert "failure_archive.json" in html_text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in html_text
    assert "uvm_coverage_xcrg/codeCoverageReport/modules/detail.html" not in html_text
    assert "乱码" not in html_text


def test_p4_7_target_dashboard_handles_not_run_without_failure_archive(tmp_path):
    module = load_local_module("project_overview_p4_7_empty", PROJECT_OVERVIEW_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                }
            ]

    project_dir = tmp_path / "sync-fifo"
    (project_dir / "rtl").mkdir(parents=True)
    (project_dir / "rtl" / "sync_fifo.v").write_text(
        "module sync_fifo; endmodule\n",
        encoding="utf-8",
    )

    result = module.write_target_dashboard(FakeAgent(), project_dir)

    assert result["status"] == "NOT_RUN"
    assert result["latest_run"] is None
    assert result["last_failure"] is None
    assert result["failure_href"] == "../artifacts.json"
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "尚无运行记录" in markdown
    assert "尚无失败运行" in markdown
    assert 'class="failure-entry clear"' in html_text
    assert 'data-stage="RTL"' in html_text
    assert "NOT_RUN" in html_text


def test_p5_11_cli_generates_empty_project_overview(tmp_path):
    result = run_agent(
        "--generate-overview",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "项目总览状态: WARN" in result.stdout
    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "index.html").exists()
    assert "NOT_RUN" in (tmp_path / "index.md").read_text(encoding="utf-8")


def test_p5_11_cli_reports_output_failure_without_traceback(tmp_path):
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("blocked", encoding="utf-8")

    result = run_agent(
        "--generate-overview",
        "--output-dir",
        str(output_file),
    )

    assert result.returncode == 1
    assert "项目总览生成失败" in result.stderr
    assert "Traceback" not in result.stderr


def test_p5_11_target_flow_refreshes_top_level_overview(tmp_path):
    result = run_agent(
        "--generate-rtl",
        "sync-fifo",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    overview_path = tmp_path / "index.md"
    assert overview_path.exists()
    overview = overview_path.read_text(encoding="utf-8")
    assert "| sync-fifo | Synchronous FIFO | PASS | generate-rtl | PASS |" in overview
    assert "| async-fifo | Asynchronous FIFO | NOT_RUN |" in overview


def test_p5_11_environment_report_refreshes_top_level_overview(tmp_path):
    result = run_agent(
        "--environment-report",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    overview_path = tmp_path / "index.md"
    assert overview_path.exists()
    overview = overview_path.read_text(encoding="utf-8")
    assert "环境预检：WARN" in overview
    assert "environment-report/environment_report.html" in overview


@pytest.mark.parametrize(
    ("waveform_path", "expected_suffix"),
    [
        (P5_12_VCD_PATH, ".vcd"),
        (P5_12_FST_PATH, ".fst"),
        (P5_12_GHW_PATH, ".ghw"),
    ],
)
def test_p5_12_cli_accepts_generic_waveform_formats(waveform_path, expected_suffix):
    cli_module = load_local_module("agent_cli_p5_12_waveform", AGENT_CLI_PATH)

    args = cli_module.parse_args(["--analyze-waveform", str(waveform_path)])

    assert Path(args.analyze_waveform).suffix == expected_suffix
    assert args.analyze_vcd is None


def test_p5_12_cli_exposes_waveform_sample_verification_mode():
    cli_module = load_local_module("agent_cli_p5_12_samples", AGENT_CLI_PATH)

    args = cli_module.parse_args(["--verify-waveform-samples"])

    assert args.verify_waveform_samples is True
    assert args.analyze_waveform is None


@pytest.mark.parametrize("waveform_path", [P5_12_FST_PATH, P5_12_GHW_PATH])
def test_p5_12_binary_waveforms_never_fall_back_to_vcd_analyzer(
    monkeypatch,
    waveform_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    fallback_calls = []

    monkeypatch.setattr(
        agent,
        "run_rwave_json",
        lambda *args: (_ for _ in ()).throw(
            FileNotFoundError("RWaveAnalyzer rwave binary not found")
        ),
    )
    monkeypatch.setattr(
        agent,
        "run_vcd_analyzer_json",
        lambda *args: fallback_calls.append(args),
    )

    with pytest.raises(FileNotFoundError, match="requires RWaveAnalyzer"):
        agent.run_waveform_analyzer_json("info", waveform_path, backend="auto")

    with pytest.raises(ValueError, match="only supports VCD"):
        agent.run_waveform_analyzer_json(
            "info",
            waveform_path,
            backend="vcd-analyzer",
        )

    assert fallback_calls == []


def test_p5_12_generic_waveform_report_uses_detected_format(monkeypatch, capsys):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    calls = []

    def fake_run(*args, backend="auto"):
        calls.append((args, backend))
        return {
            "signal_count": 3,
            "time_min_h": "0s",
            "time_max_h": "30ns",
            "duration_h": "30ns",
            "timescale": "1ns",
            "scopes": ["tb"],
            "_waveform_backend": "rwave",
        }

    monkeypatch.setattr(agent, "run_waveform_analyzer_json", fake_run)

    assert agent.analyze_waveform(P5_12_FST_PATH, waveform_backend="auto") is True

    captured = capsys.readouterr()
    assert "波形分析报告" in captured.out
    assert "格式: FST" in captured.out
    assert "Backend: rwave" in captured.out
    assert calls == [(("info", P5_12_FST_PATH), "auto")]


def test_p5_12_waveform_sample_matrix_covers_vcd_fst_and_ghw(tmp_path):
    module = load_local_module("waveform_samples_p5_12", WAVEFORM_SAMPLES_PATH)

    class FakeAgent:
        project_root = ROOT

        def run_waveform_analyzer_json(self, *args, backend="auto"):
            waveform_path = Path(args[1])
            if waveform_path.suffix == ".ghw":
                return {
                    "signal_count": 3,
                    "time_min_h": "0s",
                    "time_max_h": "10ns",
                    "duration_h": "10ns",
                    "timescale": "1fs",
                    "scopes": ["time_test"],
                    "_waveform_backend": "rwave",
                }
            return {
                "signal_count": 3,
                "time_min_h": "0s",
                "time_max_h": "30ns",
                "duration_h": "30ns",
                "timescale": "1ns",
                "scopes": ["tb"],
                "_waveform_backend": "rwave",
            }

    result = module.write_waveform_sample_report(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "PASS"
    assert [item["format"] for item in result["samples"]] == ["VCD", "FST", "GHW"]
    assert all(item["backend"] == "rwave" for item in result["samples"])
    assert all(item["status"] == "PASS" for item in result["samples"])
    assert result["markdown_path"] == (
        tmp_path / "waveform-samples" / "format_matrix.md"
    )
    assert result["html_path"] == (
        tmp_path / "waveform-samples" / "format_matrix.html"
    )

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "# VCD/FST/GHW 统一波形后端验证" in markdown
    assert "| VCD | handshake_trace.vcd | PASS | rwave | 3 | 1ns | 0s - 30ns |" in markdown
    assert "| FST | handshake_trace.fst | PASS | rwave | 3 | 1ns | 0s - 30ns |" in markdown
    assert "| GHW | time_test.ghw | PASS | rwave | 3 | 1fs | 0s - 10ns |" in markdown
    assert '<html lang="zh-CN">' in html_text
    assert "统一波形后端验证" in html_text
    assert "\ufffd" not in markdown
    assert "\ufffd" not in html_text


def test_p5_12_waveform_samples_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/waveform_samples.py"' in pyproject


def _write_p4_1_xcrg_fixture(project_dir):
    code_dir = (
        project_dir
        / "reports"
        / "uvm_coverage_xcrg"
        / "codeCoverageReport"
    )
    functional_dir = (
        project_dir
        / "reports"
        / "uvm_coverage_xcrg"
        / "functionalCoverageReport"
    )
    code_dir.mkdir(parents=True)
    functional_dir.mkdir(parents=True)
    project_path = project_dir.as_posix()

    (code_dir / "files.html").write_text(
        f"""
<table class="fileInfosTable">
<tr>
<td>File ID</td><td>File Path</td><td>Modules Count</td>
<td>Total Instances Count</td><td>Statement Coverage Score</td>
<td>Lines Count</td><td>Statements Count</td>
<td>Branch Coverage Score</td><td>Condition Coverage Score</td>
<td>Toggle Coverage Score</td>
</tr>
<tr>
<td>1</td><td><a href="file1.html">{project_path}/rtl/async_fifo.v</a></td>
<td>1</td><td>1</td><td>100</td><td>30</td><td>30</td>
<td>100</td><td>100</td><td>17.01</td>
</tr>
<tr>
<td>2</td><td><a href="file2.html">{project_path}/uvm/async_fifo_uvm_pkg.sv</a></td>
<td>1</td><td>1</td><td>54.7337</td><td>20</td><td>20</td>
<td>18.1818</td><td>15.2174</td><td>0</td>
</tr>
<tr>
<td>3</td><td><a href="file3.html">D:/Vivado/data/system_verilog/uvm_1.2/xlnx_uvm_package.sv</a></td>
<td>1</td><td>1</td><td>0</td><td>20</td><td>20</td>
<td>0</td><td>0</td><td>0</td>
</tr>
</table>
""",
        encoding="utf-8",
    )
    (code_dir / "modules.html").write_text(
        f"""
<table class="moduleInfosTable">
<tr>
<td>Module ID</td><td>Module Name</td><td>Instance[s] Count</td>
<td>Hierarchical Instance[s]</td><td>Statement Score</td>
<td>Branch Score</td><td>Condition Score</td><td>Toggle Score</td>
<td>Module definition in File</td><td>File ID</td>
</tr>
<tr>
<td>1</td><td><a href="mod1.html">async_fifo_default</a></td><td>1</td>
<td>tb_async_fifo_uvm.dut</td><td>100</td><td>100</td><td>100</td>
<td>17.01</td>
<td><span class="tooltiptext">{project_path}/rtl/async_fifo.v</span></td><td>1</td>
</tr>
<tr>
<td>2</td><td><a href="mod2.html">async_fifo_uvm_pkg</a></td><td>1</td>
<td>async_fifo_uvm_pkg</td><td>54.7337</td><td>18.1818</td>
<td>15.2174</td><td>0</td>
<td><span class="tooltiptext">{project_path}/uvm/async_fifo_uvm_pkg.sv</span></td>
<td>2</td>
</tr>
</table>
""",
        encoding="utf-8",
    )
    (functional_dir / "groups.html").write_text(
        """
<table>
<tr><td>Name</td><td>Score</td><td>Num Insts</td>
<td>Avg Instances Score</td><td>Weight</td><td>Goal</td></tr>
<tr>
<td><a href="grp0.html">async_fifo_uvm_pkg::async_fifo_monitor::async_fifo_cg</a></td>
<td>57.1429</td><td>1</td><td>57.1429</td><td>1</td><td>100</td>
</tr>
</table>
""",
        encoding="utf-8",
    )
    (functional_dir / "grp0.html").write_text(
        f"""
<a href="dashboard.html">Dashboard</a>
<a href="groups.html">Groups</a>
<span>Source File(s) :</span>
<a href="file:{project_path}/uvm/async_fifo_uvm_pkg.sv">
{project_path}/uvm/async_fifo_uvm_pkg.sv
</a>
<table id="sortable0">
<tr><td>Name</td><td>Score</td><td>Weight</td><td>Goal</td></tr>
<tr><td><span class="tooltiptext1">\this .async_fifo_cg</span></td>
<td>57.1429</td><td>1</td><td>100</td></tr>
</table>
<table id="sortable1">
<tr><td>Name</td><td>Expected</td><td>Uncovered</td>
<td>Covered</td><td>Percent</td><td>Goal</td></tr>
<tr><td>cp_write</td><td>1</td><td>0</td><td>1</td><td>100</td><td>100</td></tr>
<tr><td>cp_full</td><td>1</td><td>1</td><td>0</td><td>0</td><td>100</td></tr>
</table>
<table id="sortable2">
<tr><td>Name</td><td>Expected</td><td>Uncovered</td>
<td>Covered</td><td>Percent</td><td>Goal</td></tr>
<tr><td><span class="tooltiptext5">cross_write_full</span></td>
<td>1</td><td>1</td><td>0</td><td>0</td><td>100</td></tr>
<tr><td><span class="tooltiptext5">cross_read_empty</span></td>
<td>1</td><td>1</td><td>0</td><td>0</td><td>100</td></tr>
</table>
""",
        encoding="utf-8",
    )


def test_p4_1_extracts_project_low_coverage_items_from_xcrg(tmp_path):
    module = load_local_module("xcrg_coverage_items", XCRG_COVERAGE_PATH)
    project_dir = tmp_path / "async-fifo"
    _write_p4_1_xcrg_fixture(project_dir)

    result = module.extract_low_coverage_items(
        project_dir,
        report_base=tmp_path / "coverage-closure",
        target_threshold=80.0,
    )

    assert result["diagnostics"] == []
    assert len(result["items"]) == 14
    assert [item["score"] for item in result["items"]] == sorted(
        item["score"] for item in result["items"]
    )
    assert all(
        set(item) == {
            "source_file",
            "instance",
            "metric",
            "score",
            "details",
            "source_report",
        }
        for item in result["items"]
    )
    assert all(item["score"] < 80.0 for item in result["items"])
    assert not any(
        "xlnx_uvm_package.sv" in item["source_file"]
        for item in result["items"]
    )
    assert any(
        item["source_file"] == "uvm/async_fifo_uvm_pkg.sv"
        and item["instance"] == "async_fifo_uvm_pkg"
        and item["metric"] == "branch"
        and item["score"] == 18.2
        and item["details"]["scope"] == "module"
        for item in result["items"]
    )
    assert any(
        item["metric"] == "cover_point"
        and item["source_file"] == "uvm/async_fifo_uvm_pkg.sv"
        and item["instance"] == "this.async_fifo_cg"
        and item["score"] == 0.0
        and item["details"]["name"] == "cp_full"
        and item["details"]["uncovered"] == 1
        for item in result["items"]
    )
    assert any(
        item["metric"] == "cross"
        and item["details"]["name"] == "cross_write_full"
        and item["source_report"].endswith(
            "functionalCoverageReport/grp0.html"
        )
        for item in result["items"]
    )


def test_p4_1_reports_missing_and_invalid_xcrg_pages_without_zero_defaults(
    tmp_path,
):
    module = load_local_module("xcrg_coverage_diagnostics", XCRG_COVERAGE_PATH)
    project_dir = tmp_path / "broken-target"
    code_dir = (
        project_dir
        / "reports"
        / "uvm_coverage_xcrg"
        / "codeCoverageReport"
    )
    code_dir.mkdir(parents=True)
    (code_dir / "files.html").write_text(
        "<html><body>unsupported xcrg layout</body></html>",
        encoding="utf-8",
    )

    result = module.extract_low_coverage_items(
        project_dir,
        report_base=tmp_path / "coverage-closure",
        target_threshold=80.0,
    )

    assert result["items"] == []
    assert {diagnostic["status"] for diagnostic in result["diagnostics"]} == {
        "INVALID",
        "MISSING",
    }
    assert any(
        diagnostic["status"] == "INVALID"
        and diagnostic["source_report"].endswith(
            "codeCoverageReport/files.html"
        )
        for diagnostic in result["diagnostics"]
    )
    assert any(
        diagnostic["status"] == "MISSING"
        and diagnostic["source_report"].endswith(
            "functionalCoverageReport/groups.html"
        )
        for diagnostic in result["diagnostics"]
    )
    assert not any(
        item["score"] == 0.0
        for item in result["items"]
    )


def test_p4_1_dashboard_renders_concrete_items_and_writes_json(tmp_path):
    module = load_local_module(
        "coverage_closure_p4_1_dashboard",
        COVERAGE_CLOSURE_PATH,
    )

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "statement",
                            "label": "Statement coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "condition",
                            "label": "Condition coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "toggle",
                            "label": "Toggle coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "functional",
                            "label": "Functional coverage",
                            "source": "UVM covergroup",
                            "status": "PASS",
                        },
                    ],
                }
            ]

    async_dir = tmp_path / "async-fifo"
    reports_dir = async_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "\n".join(
            [
                "Line Coverage Score 60.2041",
                "Branch Coverage Score 23.5294",
                "Condition Coverage Score 22",
                "Toggle Coverage Score 4.84",
            ]
        ),
        encoding="utf-8",
    )
    (reports_dir / "uvm_coverage_summary.md").write_text(
        "- Total Coverage: 27.6%\n- Coverage threshold: 1.0%\n",
        encoding="utf-8",
    )
    _write_p4_1_xcrg_fixture(async_dir)

    result = module.write_coverage_closure_report(
        FakeAgent(),
        output_dir=tmp_path,
        target_threshold=80.0,
    )

    target = result["targets"][0]
    assert target["coverage_gaps"]
    assert len(target["low_coverage_items"]) == 14
    assert target["low_coverage_diagnostics"] == []
    assert target["recommended_scenarios"] == []
    assert result["low_coverage_items_path"] == (
        tmp_path / "coverage-closure" / "low_coverage_items.json"
    )
    payload = json.loads(
        result["low_coverage_items_path"].read_text(encoding="utf-8")
    )
    assert payload["targets"][0]["name"] == "async-fifo"
    assert len(payload["targets"][0]["low_coverage_items"]) == 14

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "### 低覆盖项" in markdown
    assert "uvm/async_fifo_uvm_pkg.sv" in markdown
    assert "this.async_fifo_cg" in markdown
    assert "cp_full" in markdown
    assert "functionalCoverageReport/grp0.html" in markdown
    assert "低覆盖项" in html_text
    assert "cross_write_full" in html_text


def test_p4_1_xcrg_coverage_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/xcrg_coverage.py"' in pyproject


def _p4_2_scenario_catalog():
    return [
        {
            "id": "full_boundary",
            "type": "boundary",
            "purpose": "写满边界与 full 标志",
            "status": "PASS",
            "coverage_match": {
                "tokens": ["full", "write_full"],
                "metrics": ["cover_point", "cross"],
                "priority": "HIGH",
            },
        },
        {
            "id": "empty_boundary",
            "type": "boundary",
            "purpose": "读空边界与 empty 标志",
            "status": "PASS",
            "coverage_match": {
                "tokens": ["empty", "read_empty"],
                "metrics": ["cover_point", "cross"],
                "priority": "HIGH",
            },
        },
        {
            "id": "reset_recovery",
            "type": "recovery",
            "purpose": "复位后重新收发",
            "status": "PASS",
            "coverage_match": {
                "tokens": ["reset", "rst"],
                "source_patterns": ["uvm/*sva*.sv"],
                "metrics": ["statement", "branch", "condition", "toggle"],
                "priority": "MEDIUM",
            },
        },
        {
            "id": "clock_ratio_sweep",
            "type": "timing",
            "purpose": "写快读慢、读快写慢和相位错开",
            "status": "PASS",
            "coverage_match": {
                "tokens": ["clock", "wr_clk", "rd_clk"],
                "source_patterns": ["rtl/async_fifo.v"],
                "metrics": ["toggle"],
                "priority": "MEDIUM",
            },
        },
        {
            "id": "mixed_stress",
            "type": "stress",
            "purpose": "读写混合压力与随机 burst",
            "status": "PASS",
            "coverage_match": {
                "metrics": [
                    "statement",
                    "branch",
                    "condition",
                    "toggle",
                    "functional_group",
                ],
                "fallback": True,
                "priority": "LOW",
            },
        },
        {
            "id": "disabled_full",
            "type": "boundary",
            "purpose": "不可执行的 full 场景",
            "status": "SKIP",
            "coverage_match": {
                "tokens": ["full"],
                "priority": "HIGH",
            },
        },
    ]


def test_p4_2_maps_low_coverage_items_to_scenario_ids_and_evidence():
    module = load_local_module(
        "coverage_recommendations_p4_2",
        COVERAGE_RECOMMENDATIONS_PATH,
    )
    low_coverage_items = [
        {
            "source_file": "uvm/async_fifo_uvm_pkg.sv",
            "instance": "this.async_fifo_cg",
            "metric": "cover_point",
            "score": 0.0,
            "details": {"name": "cp_full", "scope": "cover_point"},
            "source_report": "../reports/grp0.html",
        },
        {
            "source_file": "uvm/async_fifo_uvm_pkg.sv",
            "instance": "this.async_fifo_cg",
            "metric": "cross",
            "score": 0.0,
            "details": {"name": "cross_read_empty", "scope": "cross"},
            "source_report": "../reports/grp0.html",
        },
        {
            "source_file": "uvm/async_fifo_sva.sv",
            "instance": "tb.async_fifo_sva_i",
            "metric": "branch",
            "score": 0.0,
            "details": {"name": "async_fifo_sva", "scope": "module"},
            "source_report": "../reports/mod6.html",
        },
        {
            "source_file": "rtl/async_fifo.v",
            "instance": "tb.dut",
            "metric": "toggle",
            "score": 17.0,
            "details": {"name": "async_fifo_default", "scope": "module"},
            "source_report": "../reports/mod1.html",
        },
        {
            "source_file": "uvm/async_fifo_uvm_pkg.sv",
            "instance": "async_fifo_uvm_pkg",
            "metric": "condition",
            "score": 15.2,
            "details": {"name": "async_fifo_uvm_pkg", "scope": "module"},
            "source_report": "../reports/mod4.html",
        },
    ]

    result = module.recommend_scenarios(
        low_coverage_items,
        _p4_2_scenario_catalog(),
    )

    assert result["recommended_scenarios"] == [
        "full_boundary",
        "empty_boundary",
        "reset_recovery",
        "clock_ratio_sweep",
        "mixed_stress",
    ]
    assert not any(
        item["scenario_id"] == "disabled_full"
        for item in result["recommendations"]
    )
    full_recommendation = result["recommendations"][0]
    assert full_recommendation["scenario_id"] == "full_boundary"
    assert full_recommendation["priority"] == "HIGH"
    assert full_recommendation["matched_items"] == ["cp_full"]
    assert full_recommendation["matched_metrics"] == ["cover_point"]
    assert full_recommendation["evidence_count"] == 1
    assert "cp_full" in full_recommendation["reason"]
    assert module.recommend_scenarios([], _p4_2_scenario_catalog()) == {
        "recommended_scenarios": [],
        "recommendations": [],
    }


def test_p4_2_dashboard_renders_recommendations_and_json(tmp_path):
    module = load_local_module(
        "coverage_closure_p4_2_dashboard",
        COVERAGE_CLOSURE_PATH,
    )

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": _p4_2_scenario_catalog(),
                    "coverage_metrics": [
                        {
                            "id": "statement",
                            "label": "Statement coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "condition",
                            "label": "Condition coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "toggle",
                            "label": "Toggle coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "functional",
                            "label": "Functional coverage",
                            "source": "UVM covergroup",
                            "status": "PASS",
                        },
                    ],
                }
            ]

    async_dir = tmp_path / "async-fifo"
    reports_dir = async_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "\n".join(
            [
                "Line Coverage Score 60.2041",
                "Branch Coverage Score 23.5294",
                "Condition Coverage Score 22",
                "Toggle Coverage Score 4.84",
            ]
        ),
        encoding="utf-8",
    )
    (reports_dir / "uvm_coverage_summary.md").write_text(
        "- Total Coverage: 27.6%\n- Coverage threshold: 1.0%\n",
        encoding="utf-8",
    )
    _write_p4_1_xcrg_fixture(async_dir)

    result = module.write_coverage_closure_report(
        FakeAgent(),
        output_dir=tmp_path,
        target_threshold=80.0,
    )

    target = result["targets"][0]
    assert target["recommended_scenarios"] == [
        "full_boundary",
        "empty_boundary",
        "clock_ratio_sweep",
        "mixed_stress",
    ]
    assert [
        item["scenario_id"]
        for item in target["scenario_recommendations"]
    ] == target["recommended_scenarios"]
    assert target["scenario_recommendations"][0]["matched_items"] == [
        "cp_full",
        "cross_write_full",
    ]
    assert target["scenario_recommendations"][1]["matched_items"] == [
        "cross_read_empty"
    ]

    payload = json.loads(
        result["low_coverage_items_path"].read_text(encoding="utf-8")
    )
    payload_target = payload["targets"][0]
    assert payload_target["recommended_scenarios"] == (
        target["recommended_scenarios"]
    )
    assert payload_target["scenario_recommendations"]

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "### 推荐补测场景" in markdown
    assert "`full_boundary`" in markdown
    assert "cp_full" in markdown
    assert "clock_ratio_sweep" in markdown
    assert "推荐补测场景" in html_text
    assert "mixed_stress" in html_text


def test_p4_2_async_fifo_catalog_defines_coverage_matching_rules():
    target = json.loads(
        (
            ROOT
            / ".trae"
            / "agent"
            / "targets"
            / "async_fifo.json"
        ).read_text(encoding="utf-8")
    )
    scenarios = {
        item["id"]: item
        for item in target["scenario_catalog"]
    }

    assert "clock_ratio_sweep" in scenarios
    for scenario_id in [
        "full_boundary",
        "empty_boundary",
        "reset_recovery",
        "clock_ratio_sweep",
        "mixed_stress",
    ]:
        coverage_match = scenarios[scenario_id]["coverage_match"]
        assert coverage_match["priority"] in {"HIGH", "MEDIUM", "LOW"}
        assert coverage_match.get("tokens") or coverage_match.get(
            "source_patterns"
        ) or coverage_match.get("fallback")


def test_p4_2_recommendations_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/coverage_recommendations.py"' in pyproject


def test_p4_0_parses_xcrg_scores_and_existing_gate_threshold():
    module = load_local_module("coverage_closure_parser", COVERAGE_CLOSURE_PATH)
    score_text = """
Line Coverage Score 60.2041
Branch Coverage Score 23.5294
Condition Coverage Score 22
Toggle Coverage Score 4.84
"""
    summary_text = """
- 当前覆盖率：27.6%
- 覆盖率阈值：1.0%
"""

    scores = module.parse_coverage_scores(score_text, summary_text)

    assert scores == {
        "total": 27.6,
        "statement": 60.2,
        "branch": 23.5,
        "condition": 22.0,
        "toggle": 4.8,
    }
    assert module.parse_gate_threshold(summary_text) == 1.0


def test_p4_0_coverage_dashboard_aggregates_gaps_and_skipped_targets(tmp_path):
    module = load_local_module("coverage_closure_dashboard", COVERAGE_CLOSURE_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": [
                        {"id": "full_boundary", "status": "PASS"},
                        {"id": "reset_recovery", "status": "PASS"},
                    ],
                    "coverage_metrics": [
                        {
                            "id": "statement",
                            "label": "Statement coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "condition",
                            "label": "Condition coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "toggle",
                            "label": "Toggle coverage",
                            "source": "Vivado xcrg",
                            "status": "PASS",
                        },
                        {
                            "id": "functional",
                            "label": "Functional coverage",
                            "source": "UVM covergroup",
                            "status": "PASS",
                        },
                    ],
                },
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                    "flows": [],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "statement",
                            "label": "Statement coverage",
                            "source": "not-enabled",
                            "status": "SKIP",
                        },
                        {
                            "id": "functional",
                            "label": "Functional coverage",
                            "source": "no-uvm-flow",
                            "status": "N/A",
                        },
                    ],
                },
                {
                    "name": "round-robin-arbiter",
                    "display_name": "Round-Robin Arbiter",
                    "design_family": "arbiter",
                    "flows": [],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "not-enabled",
                            "status": "SKIP",
                        }
                    ],
                },
            ]

    async_dir = tmp_path / "async-fifo"
    reports_dir = async_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "\n".join(
            [
                "Line Coverage Score 60.2041",
                "Branch Coverage Score 23.5294",
                "Condition Coverage Score 22",
                "Toggle Coverage Score 4.84",
            ]
        ),
        encoding="utf-8",
    )
    (reports_dir / "uvm_coverage_summary.md").write_text(
        "\n".join(
            [
                "# async-fifo UVM 覆盖率摘要",
                "- 当前覆盖率：27.6%",
                "- 覆盖率阈值：1.0%",
            ]
        ),
        encoding="utf-8",
    )
    for report_path in [
        reports_dir / "uvm_coverage_summary.html",
        reports_dir
        / "uvm_coverage_xcrg"
        / "codeCoverageReport"
        / "dashboard.html",
        reports_dir
        / "uvm_coverage_xcrg"
        / "functionalCoverageReport"
        / "dashboard.html",
        reports_dir / "xcrg_coverage.log",
        async_dir / "sim" / "async_fifo_uvm_coverage.wdb",
    ]:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("fixture\n", encoding="utf-8")

    result = module.write_coverage_closure_report(
        FakeAgent(),
        output_dir=tmp_path,
        target_threshold=80.0,
    )

    assert result["status"] == "WARN"
    assert result["target_count"] == 3
    assert result["gap_target_count"] == 1
    assert result["skipped_target_count"] == 2
    assert [item["name"] for item in result["targets"]] == [
        "async-fifo",
        "round-robin-arbiter",
        "sync-fifo",
    ]

    async_target = result["targets"][0]
    assert async_target["status"] == "GAP"
    assert async_target["current_total"] == 27.6
    assert async_target["current_threshold"] == 1.0
    assert async_target["target_threshold"] == 80.0
    assert async_target["gap"] == 52.4
    assert [item["id"] for item in async_target["coverage_gaps"]] == [
        "total",
        "statement",
        "branch",
        "condition",
        "toggle",
        "functional",
    ]
    assert async_target["low_coverage_items"] == []
    assert async_target["low_coverage_diagnostics"]
    assert async_target["recommended_scenarios"] == []
    assert "P4.1" in async_target["next_action"]

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "# 多 Target Coverage Closure 看板" in markdown
    assert "| async-fifo | fifo | GAP | 27.6% | 80.0% | 52.4% |" in markdown
    assert "| round-robin-arbiter | arbiter | SKIP | - | 80.0% | - |" in markdown
    assert "Statement coverage | 60.2% | 80.0% | GAP" in markdown
    assert "Functional coverage | - | 80.0% | MISSING" in markdown
    assert "../async-fifo/reports/uvm_coverage_summary.html" in markdown
    assert "../async-fifo/sim/async_fifo_uvm_coverage.wdb" in markdown
    assert '<html lang="zh-CN">' in html_text
    assert 'class="target-card gap"' in html_text
    assert "乱码" not in html_text


def test_p4_0_coverage_dashboard_marks_enabled_target_without_data_not_run(tmp_path):
    module = load_local_module("coverage_closure_not_run", COVERAGE_CLOSURE_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "enabled-target",
                    "display_name": "Enabled Target",
                    "design_family": "custom",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "xcrg",
                            "status": "PASS",
                        }
                    ],
                }
            ]

    result = module.write_coverage_closure_report(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "WARN"
    assert result["targets"][0]["status"] == "NOT_RUN"
    assert result["targets"][0]["current_total"] is None
    assert result["targets"][0]["gap"] is None
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    assert "尚未找到 coverage 数值产物" in markdown
    assert "| enabled-target | custom | NOT_RUN | 0.0% |" not in markdown


def test_p4_0_coverage_dashboard_isolates_invalid_target_report(tmp_path):
    module = load_local_module("coverage_closure_invalid", COVERAGE_CLOSURE_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "broken-target",
                    "display_name": "Broken Target",
                    "design_family": "custom",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "xcrg",
                            "status": "PASS",
                        }
                    ],
                },
                {
                    "name": "skipped-target",
                    "display_name": "Skipped Target",
                    "design_family": "custom",
                    "flows": [],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "not-enabled",
                            "status": "SKIP",
                        }
                    ],
                },
            ]

    report_path = (
        tmp_path / "broken-target" / "reports" / "uvm_coverage_percent.txt"
    )
    report_path.parent.mkdir(parents=True)
    report_path.write_text("xcrg completed without score rows\n", encoding="utf-8")

    result = module.write_coverage_closure_report(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "FAIL"
    assert result["targets"][0]["status"] == "INVALID"
    assert result["targets"][1]["status"] == "SKIP"
    assert "未解析到 coverage score" in result["targets"][0]["error"]


def test_p4_0_cli_accepts_coverage_closure_target():
    cli_module = load_local_module("agent_cli_p4_0", AGENT_CLI_PATH)

    args = cli_module.parse_args(
        ["--coverage-closure", "--coverage-target", "85"]
    )

    assert args.coverage_closure is True
    assert args.coverage_target == 85.0


def test_p4_0_cli_generates_empty_coverage_dashboard(tmp_path):
    result = run_agent(
        "--coverage-closure",
        "--coverage-target",
        "80",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Coverage closure 状态: WARN" in result.stdout
    assert (tmp_path / "coverage-closure" / "index.md").exists()
    assert (tmp_path / "coverage-closure" / "index.html").exists()
    markdown = (
        tmp_path / "coverage-closure" / "index.md"
    ).read_text(encoding="utf-8")
    assert "| async-fifo | fifo | NOT_RUN | - | 80.0% | - |" in markdown
    assert "| sync-fifo | fifo | SKIP | - | 80.0% | - |" in markdown


def test_p4_0_coverage_closure_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/coverage_closure.py"' in pyproject


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


def test_p5_target_registry_lists_async_fifo_metadata():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    target_config = json.loads((AGENT_TARGETS_DIR / "async_fifo.json").read_text(encoding="utf-8"))
    targets = agent.list_targets()
    target_names = [target["name"] for target in targets]
    async_fifo = agent.get_target("async_fifo")

    assert target_config["name"] == "async-fifo"
    assert target_names == ["async-fifo", "round-robin-arbiter", "sync-fifo"]
    assert async_fifo["name"] == "async-fifo"
    assert async_fifo["display_name"] == "Asynchronous FIFO"
    assert async_fifo["design_family"] == "fifo"
    assert "async_fifo" in async_fifo["aliases"]
    assert "generate-rtl" in async_fifo["flows"]
    assert "sim-rtl" in async_fifo["flows"]
    assert "uvm-coverage" in async_fifo["flows"]
    assert agent.normalize_rtl_target("async_fifo") == "async-fifo"


def test_p5_2_target_registry_lists_sync_fifo_metadata():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    target_config = json.loads((AGENT_TARGETS_DIR / "sync_fifo.json").read_text(encoding="utf-8"))
    targets = agent.list_targets()
    target_names = [target["name"] for target in targets]
    sync_fifo = agent.get_target("sync_fifo")

    assert target_config["name"] == "sync-fifo"
    assert target_names == ["async-fifo", "round-robin-arbiter", "sync-fifo"]
    assert sync_fifo["name"] == "sync-fifo"
    assert sync_fifo["display_name"] == "Synchronous FIFO"
    assert sync_fifo["design_family"] == "fifo"
    assert "sync_fifo" in sync_fifo["aliases"]
    assert "generate-rtl" in sync_fifo["flows"]
    assert "sim-rtl" in sync_fifo["flows"]
    assert "analyze-rtl-vcd" in sync_fifo["flows"]
    assert agent.normalize_rtl_target("sync_fifo") == "sync-fifo"


def test_p5_3_target_registry_lists_round_robin_arbiter_metadata():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    target_config = json.loads((AGENT_TARGETS_DIR / "round_robin_arbiter.json").read_text(encoding="utf-8"))
    targets = agent.list_targets()
    target_names = [target["name"] for target in targets]
    arbiter = agent.get_target("round_robin_arbiter")

    assert target_config["name"] == "round-robin-arbiter"
    assert target_names == ["async-fifo", "round-robin-arbiter", "sync-fifo"]
    assert arbiter["name"] == "round-robin-arbiter"
    assert arbiter["display_name"] == "Round-Robin Arbiter"
    assert arbiter["design_family"] == "arbiter"
    assert "round_robin_arbiter" in arbiter["aliases"]
    assert "rr-arbiter" in arbiter["aliases"]
    assert "generate-rtl" in arbiter["flows"]
    assert "sim-rtl" in arbiter["flows"]
    assert "analyze-rtl-vcd" in arbiter["flows"]
    assert "open-wave" in arbiter["flows"]
    assert agent.normalize_rtl_target("round_robin_arbiter") == "round-robin-arbiter"


def test_p5_6_target_registry_exposes_common_capability_metadata():
    module = load_agent_module()
    agent = module.DigitalICAgent()
    allowed_statuses = {"PASS", "SKIP", "N/A"}

    for target in agent.list_targets():
        assert target["parameters"]
        assert target["interfaces"]
        assert target["checks"]
        assert target["scenario_catalog"]
        assert target["coverage_metrics"]
        assert target["artifact_manifest"]

        scenario_ids = [item["id"] for item in target["scenario_catalog"]]
        metric_ids = [item["id"] for item in target["coverage_metrics"]]
        artifact_ids = [item["id"] for item in target["artifact_manifest"]]
        assert len(scenario_ids) == len(set(scenario_ids))
        assert len(metric_ids) == len(set(metric_ids))
        assert len(artifact_ids) == len(set(artifact_ids))

        for item in (
            target["scenario_catalog"]
            + target["coverage_metrics"]
            + target["artifact_manifest"]
        ):
            assert item["status"] in allowed_statuses


def test_p5_6_target_registry_rejects_invalid_capability_status(tmp_path):
    module = load_agent_module()
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    config = {
        "name": "demo",
        "display_name": "Demo",
        "design_family": "demo",
        "aliases": [],
        "flows": [],
        "description": "Demo target",
        "parameters": [
            {"name": "WIDTH", "default": "8", "description": "Data width"},
        ],
        "interfaces": [
            {
                "name": "clk",
                "direction": "input",
                "width": "1",
                "description": "Clock",
            },
        ],
        "checks": ["Clock is present"],
        "scenario_catalog": [
            {
                "id": "smoke",
                "type": "functional",
                "purpose": "Smoke scenario",
                "status": "BROKEN",
            },
        ],
        "coverage_metrics": [
            {
                "id": "line",
                "label": "Line coverage",
                "source": "xcrg",
                "status": "SKIP",
            },
        ],
        "artifact_manifest": [
            {"id": "rtl", "path": "rtl/demo.v", "status": "PASS"},
        ],
        "notes": [],
    }
    (targets_dir / "demo.json").write_text(
        json.dumps(config, ensure_ascii=False),
        encoding="utf-8",
    )

    agent = module.DigitalICAgent()
    try:
        agent.load_target_registry(targets_dir)
    except ValueError as exc:
        assert "invalid status" in str(exc)
    else:
        raise AssertionError("Expected invalid capability status to raise ValueError")


def test_p5_6_spec_and_plan_surface_capability_statuses():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    spec_text = agent.render_target_design_spec("sync-fifo")
    plan_text = agent.render_target_verification_plan("sync-fifo")

    assert "## 覆盖率能力" in spec_text
    assert "## Artifact Manifest" in spec_text
    assert "| SKIP |" in spec_text
    assert "| 状态 |" in plan_text
    assert "coverage_metrics" in plan_text


def test_p5_7_target_scaffolder_generates_valid_candidate_project(tmp_path):
    assert TARGET_SCAFFOLDER_PATH.exists()

    module = load_agent_module()
    registry = load_local_module("target_registry", TARGET_REGISTRY_PATH)
    agent = module.DigitalICAgent()

    result = agent.create_target_scaffold(
        "packet_router",
        output_dir=tmp_path,
        description="Configurable packet router target",
    )

    project_dir = tmp_path / "packet-router"
    config_path = project_dir / "target" / "packet_router.json"
    assert result["project_dir"] == project_dir
    assert result["config_path"] == config_path

    target = registry.get_target(
        registry.load_target_registry(project_dir / "target"),
        "packet_router",
    )
    assert target["name"] == "packet-router"
    assert target["display_name"] == "Packet Router"
    assert target["design_family"] == "custom"
    assert target["aliases"] == ["packet_router"]
    assert target["flows"] == []
    assert target["description"] == "Configurable packet router target"
    assert target["parameters"][0]["name"] == "DATA_WIDTH"
    assert target["interfaces"][0]["name"] == "clk"
    assert target["scenario_catalog"][0]["status"] == "SKIP"
    assert target["coverage_metrics"][-1]["status"] == "N/A"
    assert target["artifact_manifest"][0]["status"] == "SKIP"

    rtl_path = project_dir / "rtl" / "packet_router.v"
    tb_path = project_dir / "tb" / "tb_packet_router.v"
    design_spec_path = project_dir / "reports" / "design_spec.md"
    verification_plan_path = project_dir / "reports" / "verification_plan.md"
    sim_report_path = project_dir / "reports" / "sim_report.md"
    todo_path = project_dir / "TODO.md"
    readme_path = project_dir / "README.md"
    for path in [
        rtl_path,
        tb_path,
        design_spec_path,
        verification_plan_path,
        sim_report_path,
        todo_path,
        readme_path,
    ]:
        assert path.exists()

    assert "module packet_router" in rtl_path.read_text(encoding="utf-8")
    assert "TODO" in rtl_path.read_text(encoding="utf-8")
    assert "module tb_packet_router" in tb_path.read_text(encoding="utf-8")
    assert "- [ ]" in todo_path.read_text(encoding="utf-8")
    assert ".trae/agent/targets/packet_router.json" in readme_path.read_text(
        encoding="utf-8"
    )


def test_p5_7_target_scaffolder_rejects_invalid_duplicate_and_overwrite(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    with pytest.raises(ValueError, match="invalid target name"):
        agent.create_target_scaffold("../escape", output_dir=tmp_path)

    with pytest.raises(ValueError, match="already registered"):
        agent.create_target_scaffold("async_fifo", output_dir=tmp_path)

    first = agent.create_target_scaffold("packet-router", output_dir=tmp_path)
    assert first["project_dir"].exists()
    with pytest.raises(FileExistsError, match="already exists"):
        agent.create_target_scaffold("packet-router", output_dir=tmp_path)


def test_p5_7_cli_create_target_generates_scaffold(tmp_path):
    result = run_agent(
        "--create-target",
        "packet_router",
        "--output-dir",
        str(tmp_path),
        "Configurable packet router target",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Created target scaffold" in result.stdout
    assert "packet_router.json" in result.stdout
    assert (tmp_path / "packet-router" / "target" / "packet_router.json").exists()
    assert (tmp_path / "packet-router" / "TODO.md").exists()


def test_p5_8_generate_rtl_writes_runtime_artifact_manifest(tmp_path):
    assert ARTIFACT_MANIFEST_PATH.exists()

    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("sync-fifo", tmp_path)

    manifest_path = project_dir / "artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["target"] == "sync-fifo"
    assert manifest["updated_at"].endswith("Z")
    assert len(manifest["runs"]) == 1

    run = manifest["runs"][0]
    assert run["flow"] == "generate-rtl"
    assert run["status"] == "PASS"
    assert run["recorded_at"].endswith("Z")
    assert "--generate-rtl" in run["command"]
    assert "sync-fifo" in run["command"]
    assert run["tools"]["python"]["version"]
    assert run["tools"]["python"]["executable"]

    artifacts = {item["id"]: item for item in run["artifacts"]}
    assert artifacts["rtl"]["path"] == "rtl/sync_fifo.v"
    assert artifacts["rtl"]["exists"] is True
    assert artifacts["rtl"]["status"] == "PASS"
    assert artifacts["rtl"]["size_bytes"] > 0
    assert artifacts["wave_vcd"]["exists"] is False
    assert artifacts["wave_vcd"]["status"] == "SKIP"
    assert artifacts["coverage_summary"]["status"] == "N/A"


def test_p5_8_report_generation_appends_manifest_history(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    agent.generate_rtl_project("sync-fifo", tmp_path)
    agent.write_target_design_spec("sync-fifo", output_dir=tmp_path)
    agent.write_target_verification_plan("sync-fifo", output_dir=tmp_path)

    manifest = json.loads(
        (tmp_path / "sync-fifo" / "artifacts.json").read_text(encoding="utf-8")
    )
    assert [run["flow"] for run in manifest["runs"]] == [
        "generate-rtl",
        "generate-spec",
        "generate-verification-plan",
    ]
    assert all(run["status"] == "PASS" for run in manifest["runs"])

    latest_artifacts = {
        item["id"]: item for item in manifest["runs"][-1]["artifacts"]
    }
    assert latest_artifacts["design_spec"]["status"] == "PASS"
    assert latest_artifacts["verification_plan"]["status"] == "PASS"


def test_history_rotation_archives_target_manifest_runs_and_can_be_disabled(
    tmp_path,
):
    module = load_local_module(
        "artifact_manifest_rotation",
        ARTIFACT_MANIFEST_PATH,
    )

    class FakeAgent:
        def get_target(self, target):
            return {
                "name": target,
                "artifact_manifest": [],
            }

    agent = FakeAgent()
    project_dir = tmp_path / "sync-fifo"
    for index in range(4):
        module.record_artifact_run(
            agent,
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            project_dir=project_dir,
            options={"sequence": index},
            max_active_runs=2,
        )

    manifest_path = project_dir / "artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [
        run["options"]["sequence"]
        for run in manifest["runs"]
    ] == [2, 3]
    assert manifest["history"] == {
        "active_limit": 2,
        "archive_path": "artifacts.archive.jsonl.gz",
        "archived_runs": 2,
    }

    archive_path = project_dir / "artifacts.archive.jsonl.gz"
    with gzip.open(archive_path, "rt", encoding="utf-8") as stream:
        archived = [
            json.loads(line)
            for line in stream.read().splitlines()
        ]
    assert [
        run["options"]["sequence"]
        for run in archived
    ] == [0, 1]

    unbounded_dir = tmp_path / "unbounded"
    for index in range(3):
        module.record_artifact_run(
            agent,
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            project_dir=unbounded_dir,
            options={"sequence": index},
            max_active_runs=None,
        )
    unbounded = json.loads(
        (unbounded_dir / "artifacts.json").read_text(encoding="utf-8")
    )
    assert len(unbounded["runs"]) == 3
    assert "history" not in unbounded
    assert not (unbounded_dir / "artifacts.archive.jsonl.gz").exists()

    with pytest.raises(ValueError, match="active record limit"):
        module.record_artifact_run(
            agent,
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            project_dir=tmp_path / "invalid-limit",
            max_active_runs=0,
        )


def test_p5_8_failed_target_flow_records_failure(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    class FailingHandler:
        def run(self, _flow, **_kwargs):
            raise RuntimeError("simulated manifest failure path")

    agent.target_handlers["sync-fifo"] = FailingHandler()

    with pytest.raises(RuntimeError, match="simulated manifest failure path"):
        agent.run_target_flow(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
        )

    manifest = json.loads(
        (tmp_path / "sync-fifo" / "artifacts.json").read_text(encoding="utf-8")
    )
    run = manifest["runs"][-1]
    assert run["flow"] == "generate-rtl"
    assert run["status"] == "FAIL"
    assert "simulated manifest failure path" in run["error"]
    assert "--generate-rtl" in run["command"]


def test_p5_8_create_target_scaffold_writes_runtime_manifest(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    scaffold = agent.create_target_scaffold("packet_router", output_dir=tmp_path)
    manifest = json.loads(
        (scaffold["project_dir"] / "artifacts.json").read_text(encoding="utf-8")
    )
    run = manifest["runs"][-1]

    assert manifest["target"] == "packet-router"
    assert run["flow"] == "create-target"
    assert run["status"] == "PASS"
    assert "--create-target" in run["command"]
    assert any(
        item["path"] == "target/packet_router.json"
        and item["exists"] is True
        and item["status"] == "PASS"
        for item in run["artifacts"]
    )


def test_p5_8_manifest_rejects_invalid_status_external_path_and_corrupt_json(
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    with pytest.raises(ValueError, match="invalid runtime flow status"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="BROKEN",
        )

    outside_path = tmp_path / "outside.log"
    outside_path.write_text("outside", encoding="utf-8")
    with pytest.raises(ValueError, match="inside project directory"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="PASS",
            extra_artifacts=[
                {"id": "outside", "path": outside_path, "status": "PASS"},
            ],
        )

    manifest_path = tmp_path / "sync-fifo" / "artifacts.json"
    manifest_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid runtime artifact manifest JSON"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="PASS",
        )


def test_artifact_manifest_rejects_relative_path_escape(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    outside_path = tmp_path / "outside.log"
    outside_path.write_text("outside", encoding="utf-8")
    relative_escape = Path("..") / outside_path.name

    with pytest.raises(ValueError, match="inside project directory"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="PASS",
            extra_artifacts=[
                {"id": "outside", "path": relative_escape, "status": "PASS"},
            ],
        )

    target_info = dict(agent.get_target("sync-fifo"))
    target_info["artifact_manifest"] = [
        {"id": "outside", "path": relative_escape, "status": "PASS"},
    ]
    with pytest.raises(ValueError, match="inside project directory"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="PASS",
            target_info=target_info,
        )


def test_p5_target_registry_rejects_invalid_target_config(tmp_path):
    module = load_agent_module()
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    (targets_dir / "broken.json").write_text('{"display_name": "Broken"}', encoding="utf-8")

    agent = module.DigitalICAgent()

    try:
        agent.load_target_registry(targets_dir)
    except ValueError as exc:
        assert "missing required field: name" in str(exc)
    else:
        raise AssertionError("Expected invalid target config to raise ValueError")


def test_target_registry_module_preserves_sorting_aliases_and_validation(tmp_path):
    assert TARGET_REGISTRY_PATH.exists()

    registry = load_local_module("target_registry", TARGET_REGISTRY_PATH)
    targets = registry.load_target_registry(AGENT_TARGETS_DIR)

    assert [target["name"] for target in registry.list_targets(targets)] == [
        "async-fifo",
        "round-robin-arbiter",
        "sync-fifo",
    ]
    assert registry.get_target(targets, "round_robin_arbiter")["name"] == (
        "round-robin-arbiter"
    )

    broken_dir = tmp_path / "targets"
    broken_dir.mkdir()
    (broken_dir / "broken.json").write_text(
        '{"display_name": "Broken"}',
        encoding="utf-8",
    )
    try:
        registry.load_target_registry(broken_dir)
    except ValueError as exc:
        assert "missing required field: name" in str(exc)
    else:
        raise AssertionError("Expected invalid target config to raise ValueError")


def test_target_handler_registry_matches_declared_flows():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert set(agent.target_handlers) == set(agent.targets)
    for target_name, target in agent.targets.items():
        assert set(agent.target_handlers[target_name].flows) == set(target["flows"])


def test_registered_check_rtl_flows_execute_for_all_targets(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    target_artifacts = {
        "sync-fifo": {
            "vcd": "sync_fifo_trace.vcd",
            "wdb": "sync_fifo_smoke.wdb",
            "xpr": "sync_fifo_project.xpr",
        },
        "round-robin-arbiter": {
            "vcd": "round_robin_arbiter_trace.vcd",
            "wdb": "round_robin_arbiter_smoke.wdb",
            "xpr": "round_robin_arbiter_project.xpr",
        },
    }

    for target, names in target_artifacts.items():
        project_dir = agent.generate_rtl_project(target, tmp_path)
        (project_dir / "sim" / names["vcd"]).write_text("$date\nfixture\n$end\n", encoding="utf-8")
        (project_dir / "sim" / names["wdb"]).write_text("wdb", encoding="utf-8")
        xpr_path = project_dir / "vivado_project" / names["xpr"]
        xpr_path.parent.mkdir(parents=True, exist_ok=True)
        xpr_path.write_text("<Project />\n", encoding="utf-8")
        report_path = project_dir / "reports" / "sim_report.md"
        report_path.write_text("# Simulation Report\n\n- Status: PASS\n", encoding="utf-8")

        assert module.main([
            "--check-rtl",
            target,
            "--output-dir",
            str(tmp_path),
        ]) == 0


def test_cli_list_targets_outputs_registered_targets(capsys):
    module = load_agent_module()

    assert module.main(["--list-targets"]) == 0

    output = capsys.readouterr().out
    assert "async-fifo" in output
    assert "fifo" in output
    assert "generate-rtl" in output
    assert "uvm-coverage" in output


def test_p5_4_generate_design_spec_from_round_robin_target_config(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    report = agent.write_target_design_spec(
        "round-robin-arbiter",
        output_dir=tmp_path,
        requirement="生成一个 4 requester round-robin arbiter，用于通用数字 IC Agent 规格文档验证。",
    )

    md_path = tmp_path / "round-robin-arbiter" / "reports" / "design_spec.md"
    html_path = tmp_path / "round-robin-arbiter" / "reports" / "design_spec.html"
    assert report["md_path"] == md_path
    assert report["html_path"] == html_path
    assert md_path.exists()
    assert html_path.exists()

    text = md_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")
    assert "# 设计规格" in text
    assert "round-robin-arbiter" in text
    assert "Round-Robin Arbiter" in text
    assert "arbiter" in text
    assert "req[3:0]" in text
    assert "grant[3:0]" in text
    assert "grant_valid" in text
    assert "single_request" in text
    assert "one-hot grant" in text
    assert "<html lang=\"zh-CN\">" in html_text
    assert "class=\"doc-card\"" in html_text


def test_p5_4_cli_generate_spec_creates_markdown_and_html(tmp_path):
    result = run_agent(
        "--generate-spec",
        "round-robin-arbiter",
        "--output-dir",
        str(tmp_path),
        "生成一个 4 requester round-robin arbiter",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "design_spec.md" in result.stdout
    assert (tmp_path / "round-robin-arbiter" / "reports" / "design_spec.md").exists()
    assert (tmp_path / "round-robin-arbiter" / "reports" / "design_spec.html").exists()


def test_p5_5_generate_verification_plan_from_scenario_catalog(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    report = agent.write_target_verification_plan("round-robin-arbiter", output_dir=tmp_path)

    md_path = tmp_path / "round-robin-arbiter" / "reports" / "verification_plan.md"
    html_path = tmp_path / "round-robin-arbiter" / "reports" / "verification_plan.html"
    assert report["md_path"] == md_path
    assert report["html_path"] == html_path
    assert md_path.exists()
    assert html_path.exists()

    text = md_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")
    assert "# 验证计划" in text
    assert "scenario catalog" in text
    assert "single_request" in text
    assert "multiple_requests" in text
    assert "rotating_grant" in text
    assert "reset_recovery" in text
    assert "fairness_window" in text
    assert "one-hot" in text
    assert "grant implies request" in text
    assert "<html lang=\"zh-CN\">" in html_text
    assert "class=\"scenario-card\"" in html_text


def test_p5_5_cli_generate_verification_plan_creates_markdown_and_html(tmp_path):
    result = run_agent(
        "--generate-verification-plan",
        "round-robin-arbiter",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "verification_plan.md" in result.stdout
    assert (tmp_path / "round-robin-arbiter" / "reports" / "verification_plan.md").exists()
    assert (tmp_path / "round-robin-arbiter" / "reports" / "verification_plan.html").exists()


def test_p5_4_p5_5_sync_fifo_spec_and_plan_are_target_generic(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    spec_report = agent.write_target_design_spec("sync_fifo", output_dir=tmp_path)
    plan_report = agent.write_target_verification_plan("sync_fifo", output_dir=tmp_path)

    spec_text = spec_report["md_path"].read_text(encoding="utf-8")
    plan_text = plan_report["md_path"].read_text(encoding="utf-8")
    assert "sync-fifo" in spec_text
    assert "Synchronous FIFO" in spec_text
    assert "clk" in spec_text
    assert "wr_en" in spec_text
    assert "rd_en" in spec_text
    assert "basic_ordered" in plan_text
    assert "full_boundary" in plan_text
    assert "empty_boundary" in plan_text


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
    readme_path = project_dir / "README.md"

    for path in [rtl_path, tb_path, sim_script_path, project_script_path, gui_script_path, project_dir / "reports", readme_path]:
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


def test_p5_3_generate_round_robin_arbiter_project_creates_rtl_tb_sim_reports(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    project_dir = agent.generate_rtl_project("round-robin-arbiter", tmp_path)

    assert project_dir == tmp_path / "round-robin-arbiter"
    rtl_path = project_dir / "rtl" / "round_robin_arbiter.v"
    tb_path = project_dir / "tb" / "tb_round_robin_arbiter.v"
    sim_script_path = project_dir / "sim" / "run_vivado_round_robin_arbiter.tcl"
    project_script_path = project_dir / "sim" / "create_round_robin_arbiter_project.tcl"
    gui_script_path = project_dir / "sim" / "open_round_robin_arbiter_project_gui.tcl"
    readme_path = project_dir / "README.md"

    for path in [rtl_path, tb_path, sim_script_path, project_script_path, gui_script_path, project_dir / "reports", readme_path]:
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
    assert (tmp_path / "round-robin-arbiter" / "rtl" / "round_robin_arbiter.v").exists()
    assert (tmp_path / "round-robin-arbiter" / "tb" / "tb_round_robin_arbiter.v").exists()


def test_run_async_fifo_vivado_sim_creates_project_and_can_skip_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
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


def test_p5_2_run_sync_fifo_vivado_sim_creates_project_and_can_skip_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
        calls.append(([str(part) for part in command], Path(cwd)))
        if "run_vivado_sync_fifo.tcl" in command:
            (Path(cwd) / "sync_fifo_trace.vcd").write_text("$date\nsync fifo\n$end\n", encoding="utf-8")
            (Path(cwd) / "sync_fifo_smoke.wdb").write_text("wdb placeholder", encoding="utf-8")
        if "create_sync_fifo_project.tcl" in command:
            xpr = Path(cwd).parent / "vivado_project" / "sync_fifo_project.xpr"
            xpr.parent.mkdir(parents=True, exist_ok=True)
            xpr.write_text("<Project />\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="SYNC_FIFO_SCOREBOARD_PASS", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "open_sync_fifo_project_gui", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GUI should be skipped")))
    monkeypatch.setattr(
        agent,
        "collect_sync_fifo_vcd_analysis",
        lambda output_dir="outputs", limit=20, waveform_backend="auto": {
            "info": {"signal_count": 3, "time_min_h": "0 ns", "time_max_h": "10 ns", "duration_h": "10 ns", "timescale": "1 ns"},
            "write_events": {"total": 1, "events": [{"time_h": "1 ns", "values": {"wr_data": "0x11"}}]},
            "read_events": {"total": 1, "events": [{"time_h": "2 ns", "values": {"rd_data": "0x11"}}]},
        },
    )

    assert agent.run_sync_fifo_vivado_sim(output_dir=tmp_path, open_wave_gui=False) is True

    sim_dir = tmp_path / "sync-fifo" / "sim"
    assert calls == [
        ([vivado_path, "-mode", "batch", "-source", "run_vivado_sync_fifo.tcl"], sim_dir),
        ([vivado_path, "-mode", "batch", "-nojournal", "-nolog", "-notrace", "-source", "create_sync_fifo_project.tcl"], sim_dir),
    ]
    assert (tmp_path / "sync-fifo" / "sim" / "sync_fifo_trace.vcd").exists()
    assert (tmp_path / "sync-fifo" / "sim" / "sync_fifo_smoke.wdb").exists()
    assert (tmp_path / "sync-fifo" / "vivado_project" / "sync_fifo_project.xpr").exists()
    assert (tmp_path / "sync-fifo" / "reports" / "sim_report.md").exists()
    assert (tmp_path / "sync-fifo" / "reports" / "sim_report.html").exists()


def test_p5_3_run_round_robin_arbiter_vivado_sim_creates_project_and_can_skip_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
        calls.append(([str(part) for part in command], Path(cwd)))
        if "run_vivado_round_robin_arbiter.tcl" in command:
            (Path(cwd) / "round_robin_arbiter_trace.vcd").write_text("$date\nround robin arbiter\n$end\n", encoding="utf-8")
            (Path(cwd) / "round_robin_arbiter_smoke.wdb").write_text("wdb placeholder", encoding="utf-8")
        if "create_round_robin_arbiter_project.tcl" in command:
            xpr = Path(cwd).parent / "vivado_project" / "round_robin_arbiter_project.xpr"
            xpr.parent.mkdir(parents=True, exist_ok=True)
            xpr.write_text("<Project />\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ROUND_ROBIN_ARBITER_SCOREBOARD_PASS", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "open_round_robin_arbiter_project_gui", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GUI should be skipped")))
    monkeypatch.setattr(
        agent,
        "collect_round_robin_arbiter_vcd_analysis",
        lambda output_dir="outputs", limit=20, waveform_backend="auto": {
            "info": {"signal_count": 4, "time_min_h": "0 ns", "time_max_h": "100 ns", "duration_h": "100 ns", "timescale": "1 ns"},
            "grant_events": {"total": 4, "events": [{"time_h": "20 ns", "values": {"grant": "0x1"}}]},
            "fairness_events": {"total": 4, "events": [{"time_h": "30 ns", "values": {"grant_count": "1"}}]},
        },
    )

    assert agent.run_round_robin_arbiter_vivado_sim(output_dir=tmp_path, open_wave_gui=False) is True

    sim_dir = tmp_path / "round-robin-arbiter" / "sim"
    assert calls == [
        ([vivado_path, "-mode", "batch", "-source", "run_vivado_round_robin_arbiter.tcl"], sim_dir),
        ([vivado_path, "-mode", "batch", "-nojournal", "-nolog", "-notrace", "-source", "create_round_robin_arbiter_project.tcl"], sim_dir),
    ]
    assert (tmp_path / "round-robin-arbiter" / "sim" / "round_robin_arbiter_trace.vcd").exists()
    assert (tmp_path / "round-robin-arbiter" / "sim" / "round_robin_arbiter_smoke.wdb").exists()
    assert (tmp_path / "round-robin-arbiter" / "vivado_project" / "round_robin_arbiter_project.xpr").exists()
    assert (tmp_path / "round-robin-arbiter" / "reports" / "sim_report.md").exists()
    assert (tmp_path / "round-robin-arbiter" / "reports" / "sim_report.html").exists()


def test_p5_2_analyze_sync_fifo_vcd_reports_write_and_read_handshakes(monkeypatch, tmp_path, capsys):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "sync-fifo" / "sim" / "sync_fifo_trace.vcd"
    vcd_path.parent.mkdir(parents=True)
    vcd_path.write_text("$date\nsync fifo\n$end\n", encoding="utf-8")
    calls = []

    def fake_run_waveform_analyzer_json(*args, backend="auto"):
        calls.append(args)
        if args[0] == "info":
            return {
                "signal_count": 9,
                "time_min_h": "0 ns",
                "time_max_h": "180 ns",
                "duration_h": "180 ns",
                "timescale": "1 ns",
                "_waveform_backend": "vcd_analyzer",
            }
        return {
            "total": 2,
            "events": [
                {"time_h": "50 ns", "values": {"data": "0x11"}},
                {"time_h": "60 ns", "values": {"data": "0x22"}},
            ],
        }

    monkeypatch.setattr(agent, "run_waveform_analyzer_json", fake_run_waveform_analyzer_json)

    assert agent.analyze_sync_fifo_vcd(output_dir=tmp_path, limit=4) is True

    captured = capsys.readouterr()
    assert "Sync FIFO VCD analysis" in captured.out
    assert "Write handshakes: 2" in captured.out
    assert "Read handshakes: 2" in captured.out
    assert calls[0] == ("info", vcd_path)
    assert "tb_sync_fifo.full=0" in calls[1]
    assert "tb_sync_fifo.write_count" in calls[1]
    assert "tb_sync_fifo.empty=0" in calls[2]
    assert "tb_sync_fifo.read_count" in calls[2]


def test_p5_2_cli_analyze_rtl_vcd_sync_fifo_invokes_analyzer(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_analyze_sync_fifo_vcd(self, output_dir="outputs", limit=20, waveform_backend="auto"):
        calls.append((output_dir, limit, waveform_backend))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "analyze_sync_fifo_vcd", fake_analyze_sync_fifo_vcd)

    assert module.main([
        "--analyze-rtl-vcd",
        "sync-fifo",
        "--output-dir",
        str(tmp_path),
        "--vcd-limit",
        "6",
        "--wave-backend",
        "rwave",
    ]) == 0
    assert calls == [(str(tmp_path), 6, "rwave")]


def test_p5_3_analyze_round_robin_arbiter_vcd_reports_grants_and_fairness(monkeypatch, tmp_path, capsys):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "round-robin-arbiter" / "sim" / "round_robin_arbiter_trace.vcd"
    vcd_path.parent.mkdir(parents=True)
    vcd_path.write_text("$date\nround robin arbiter\n$end\n", encoding="utf-8")
    calls = []

    def fake_run_waveform_analyzer_json(*args, backend="auto"):
        calls.append(args)
        if args[0] == "info":
            return {
                "signal_count": 12,
                "time_min_h": "0 ns",
                "time_max_h": "240 ns",
                "duration_h": "240 ns",
                "timescale": "1 ns",
                "_waveform_backend": "vcd_analyzer",
            }
        return {
            "total": 4,
            "events": [
                {"time_h": "50 ns", "values": {"grant": "0x1"}},
                {"time_h": "60 ns", "values": {"grant": "0x2"}},
            ],
        }

    monkeypatch.setattr(agent, "run_waveform_analyzer_json", fake_run_waveform_analyzer_json)

    assert agent.analyze_round_robin_arbiter_vcd(output_dir=tmp_path, limit=4) is True

    captured = capsys.readouterr()
    assert "Round-Robin Arbiter VCD analysis" in captured.out
    assert "Grant events: 4" in captured.out
    assert "Fairness checkpoints: 4" in captured.out
    assert calls[0] == ("info", vcd_path)
    assert "tb_round_robin_arbiter.grant_valid=1" in calls[1]
    assert "tb_round_robin_arbiter.grant_count" in calls[1]
    assert "tb_round_robin_arbiter.grant_valid=1" in calls[2]
    assert "tb_round_robin_arbiter.grant_count" in calls[2]
    assert any("tb_round_robin_arbiter.scenario_id" in str(arg) for arg in calls[2])


def test_round_robin_real_vcd_analysis_refreshes_clean_report(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "round-robin-arbiter"
    vcd_path = project_dir / "sim" / "round_robin_arbiter_trace.vcd"
    write_round_robin_vcd_fixture(vcd_path)
    wave_db_path = project_dir / "sim" / "round_robin_arbiter_smoke.wdb"
    wave_db_path.write_text("wdb", encoding="utf-8")

    assert agent.analyze_round_robin_arbiter_vcd(
        output_dir=tmp_path,
        limit=4,
        waveform_backend="vcd-analyzer",
    ) is True

    report_path = project_dir / "reports" / "sim_report.md"
    report_text = report_path.read_text(encoding="utf-8")
    assert "- 状态：PASS" in report_text
    assert "PASS_WITH_ANALYSIS_WARNING" not in report_text
    assert "- Backend: `vcd_analyzer`" in report_text


def test_p5_3_cli_analyze_rtl_vcd_round_robin_arbiter_invokes_analyzer(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_analyze_round_robin_arbiter_vcd(self, output_dir="outputs", limit=20, waveform_backend="auto"):
        calls.append((output_dir, limit, waveform_backend))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "analyze_round_robin_arbiter_vcd", fake_analyze_round_robin_arbiter_vcd)

    assert module.main([
        "--analyze-rtl-vcd",
        "round-robin-arbiter",
        "--output-dir",
        str(tmp_path),
        "--vcd-limit",
        "7",
        "--wave-backend",
        "rwave",
    ]) == 0
    assert calls == [(str(tmp_path), 7, "rwave")]


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

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
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
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
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
    (reports_dir / "wave_open_check.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_name": "async-fifo",
                "flow_name": "sim-rtl",
                "wave_database": str(sim_dir / "async_fifo_smoke_20260709_000000.wdb"),
                "wdb_opened": True,
                "scope_count": 3,
                "object_count": 48,
                "wave_count": 31,
                "wave_config_count": 1,
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    (reports_dir / "wave_screenshot_metrics.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado 2025.2",
                "width": 1600,
                "height": 900,
                "sampled_pixels": 4096,
                "unique_colors": 128,
                "non_uniform_pixels": 3011,
                "non_uniform_ratio": 0.7351,
            }
        ),
        encoding="utf-8",
    )

    report = agent.write_async_fifo_wave_visibility_report(project_dir)
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")

    assert report["visible"] is True
    assert report["runtime_status"] == "PASS"
    assert report["screenshot_status"] == "PASS"
    assert "\u6ce2\u5f62\u53ef\u89c1\u6027\u9a8c\u6536" in text
    assert "open_project" in text
    assert "open_wave_database" in text
    assert "- WCFG \u72b6\u6001\uff1aPASS" in text
    assert "Scope 数：3" in text
    assert "Object 数：48" in text
    assert "Wave 数：31" in text
    assert "非均匀像素比例：73.51%" in text
    assert "class=\"visibility-card pass\"" in html_text


def test_p4_6_wave_open_check_evaluates_runtime_and_screenshot_metrics(tmp_path):
    module = load_local_module("wave_visibility_p4_6", WAVE_VISIBILITY_PATH)
    probe_path = tmp_path / "wave_open_check.json"
    metrics_path = tmp_path / "wave_screenshot_metrics.json"
    probe_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_name": "sync-fifo",
                "flow_name": "formal-smoke",
                "wave_database": "sync_fifo.wdb",
                "wdb_opened": True,
                "scope_count": 2,
                "object_count": 18,
                "wave_count": 12,
                "wave_config_count": 1,
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado",
                "width": 1280,
                "height": 720,
                "sampled_pixels": 2048,
                "unique_colors": 64,
                "non_uniform_pixels": 1024,
                "non_uniform_ratio": 0.5,
            }
        ),
        encoding="utf-8",
    )

    result = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )

    assert result["status"] == "PASS"
    assert result["runtime_status"] == "PASS"
    assert result["screenshot_status"] == "PASS"
    assert result["visible"] is True
    assert result["probe"]["target_name"] == "sync-fifo"
    assert result["probe"]["flow_name"] == "formal-smoke"
    assert result["probe"]["scope_count"] == 2
    assert result["probe"]["object_count"] == 18
    assert result["probe"]["wave_count"] == 12
    assert result["screenshot_metrics"]["unique_colors"] == 64


def test_p4_6_wave_open_check_rejects_empty_runtime_and_blank_screenshot(tmp_path):
    module = load_local_module("wave_visibility_empty_p4_6", WAVE_VISIBILITY_PATH)
    probe_path = tmp_path / "wave_open_check.json"
    metrics_path = tmp_path / "wave_screenshot_metrics.json"
    probe_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_name": "round-robin-arbiter",
                "flow_name": "sim-rtl",
                "wave_database": "arbiter.wdb",
                "wdb_opened": True,
                "scope_count": 0,
                "object_count": 0,
                "wave_count": 0,
                "wave_config_count": 0,
                "diagnostics": ["get_scopes returned no scopes"],
            }
        ),
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado",
                "width": 1280,
                "height": 720,
                "sampled_pixels": 2048,
                "unique_colors": 1,
                "non_uniform_pixels": 0,
                "non_uniform_ratio": 0.0,
            }
        ),
        encoding="utf-8",
    )

    result = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )

    assert result["status"] == "FAIL"
    assert result["runtime_status"] == "FAIL"
    assert result["screenshot_status"] == "FAIL"
    assert result["visible"] is False
    assert {"scope_count", "object_count", "wave_count", "wave_config_count"} <= {
        item["id"] for item in result["checks"] if item["status"] == "FAIL"
    }
    assert "unique_colors" in {
        item["id"] for item in result["screenshot_checks"] if item["status"] == "FAIL"
    }


def test_p4_6_wave_open_check_handles_missing_corrupt_and_invalid_values(tmp_path):
    module = load_local_module("wave_visibility_edges_p4_6", WAVE_VISIBILITY_PATH)
    probe_path = tmp_path / "wave_open_check.json"
    metrics_path = tmp_path / "wave_screenshot_metrics.json"

    pending = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )
    assert pending["status"] == "PENDING"
    assert pending["runtime_status"] == "PENDING"
    assert pending["screenshot_status"] == "PENDING"
    assert pending["visible"] is False

    probe_path.write_text("{bad json", encoding="utf-8")
    corrupt_probe = module.evaluate_wave_open_check(probe_path)
    assert corrupt_probe["runtime_status"] == "FAIL"
    assert "invalid wave probe JSON" in corrupt_probe["diagnostics"][0]

    probe_path.write_text("[]", encoding="utf-8")
    non_object_probe = module.evaluate_wave_open_check(probe_path)
    assert "wave probe must be a JSON object" in non_object_probe["diagnostics"][0]

    probe_path.write_text('{"schema_version": 2}', encoding="utf-8")
    unsupported_probe = module.evaluate_wave_open_check(probe_path)
    assert "unsupported wave probe schema" in unsupported_probe["diagnostics"][0]

    probe_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "wdb_opened": False,
                "scope_count": "invalid",
                "object_count": None,
                "wave_count": "invalid",
                "wave_config_count": False,
                "diagnostics": "not-a-list",
            }
        ),
        encoding="utf-8",
    )
    metrics_path.write_text("{bad metrics", encoding="utf-8")
    invalid_values = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )
    assert invalid_values["runtime_status"] == "FAIL"
    assert invalid_values["screenshot_status"] == "FAIL"
    assert invalid_values["visible"] is False
    assert any(
        "invalid wave screenshot metrics JSON" in item
        for item in invalid_values["diagnostics"]
    )

    metrics_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "width": "invalid",
                "height": None,
                "sampled_pixels": False,
                "unique_colors": "invalid",
                "non_uniform_ratio": "invalid",
            }
        ),
        encoding="utf-8",
    )
    invalid_metrics = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )
    assert invalid_metrics["screenshot_status"] == "FAIL"
    assert {
        "width",
        "height",
        "sampled_pixels",
        "unique_colors",
        "non_uniform_ratio",
    } == {
        item["id"]
        for item in invalid_metrics["screenshot_checks"]
        if item["status"] == "FAIL"
    }


def test_p4_6_wave_probe_and_capture_scripts_are_flow_agnostic():
    module = load_local_module("wave_visibility_scripts_p4_6", WAVE_VISIBILITY_PATH)

    probe_tcl = module.render_wave_open_probe_tcl(
        "../reports/wave_open_check.json",
        target_name="sync-fifo",
        flow_name="formal-smoke",
    )
    capture_script = module.render_window_capture_script(
        screenshot_name="formal_wave.png",
        metrics_name="formal_wave_metrics.json",
    )

    assert "get_scopes" in probe_tcl
    assert "get_objects" in probe_tcl
    assert "get_waves" in probe_tcl
    assert "wave_config_count" in probe_tcl
    assert "formal-smoke" in probe_tcl
    assert "GetForegroundWindow" in capture_script
    assert "GetWindowRect" in capture_script
    assert "unique_colors" in capture_script
    assert "non_uniform_ratio" in capture_script
    source = WAVE_VISIBILITY_PATH.read_text(encoding="utf-8")
    assert "tb_async_fifo" not in source
    assert "async_fifo" not in source


def test_p4_6_async_fifo_gui_script_ignores_stale_latest_wdb_pointer():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    script = agent.render_async_fifo_open_project_gui_script()

    assert "set latest_candidate [file normalize [file join $script_dir $latest_wdb]]" in script
    assert (
        'if {$latest_wdb ne "" && [file exists $latest_candidate]}'
        in script
    )
    assert "set wave_db $latest_candidate" in script


def test_async_fifo_wave_screenshot_report_embeds_png_and_capture_script(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = reports_dir / "wave_visibility.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-png")
    (reports_dir / "wave_screenshot_metrics.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado 2025.2",
                "width": 1600,
                "height": 900,
                "sampled_pixels": 4096,
                "unique_colors": 128,
                "non_uniform_pixels": 3011,
                "non_uniform_ratio": 0.7351,
            }
        ),
        encoding="utf-8",
    )

    report = agent.write_async_fifo_wave_screenshot_report(project_dir)
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    script_text = report["capture_script_path"].read_text(encoding="utf-8")

    assert report["captured"] is True
    assert report["screenshot_status"] == "PASS"
    assert "GUI 波形截图验收" in text
    assert "- 状态：PASS" in text
    assert "wave_visibility.png" in text
    assert "非均匀像素比例：73.51%" in text
    assert "CopyFromScreen" in script_text
    assert "GetForegroundWindow" in script_text
    assert "wave_screenshot_metrics.json" in script_text
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
    assert 'class="target-selector"' in html_text
    assert 'href="../../index.html"' in html_text
    assert 'data-stage="Simulation"' in html_text
    assert 'data-stage="Coverage"' in html_text
    assert "最近运行" in html_text


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

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: "rwave")

    def fake_run_rwave_batch_json(path, command_lines):
        calls.append((path, command_lines))
        return {
            "info": {
                "signal_count": 12,
                "time_min_h": "0 ns",
                "time_max_h": "240 ns",
                "duration_h": "240 ns",
                "timescale": "1 ns",
                "_waveform_backend": "rwave",
            },
            "write_events": {
                "total": 2,
                "events": [
                    {"time_h": "50 ns", "values": {"data": "0x11"}},
                    {"time_h": "60 ns", "values": {"data": "0x22"}},
                ],
            },
            "read_events": {
                "total": 2,
                "events": [
                    {"time_h": "70 ns", "values": {"data": "0x11"}},
                    {"time_h": "80 ns", "values": {"data": "0x22"}},
                ],
            },
        }

    monkeypatch.setattr(agent, "run_rwave_batch_json", fake_run_rwave_batch_json)

    assert agent.analyze_async_fifo_vcd(output_dir=tmp_path, limit=4) is True

    captured = capsys.readouterr()
    assert "Async FIFO VCD analysis" in captured.out
    assert "Write handshakes: 2" in captured.out
    assert "Read handshakes: 2" in captured.out
    assert calls[0][0] == vcd_path
    assert len(calls[0][1]) == 3
    assert calls[0][1][0] == "info #info"
    assert "tb_async_fifo.full=0" in calls[0][1][1]
    assert "tb_async_fifo.write_count" in calls[0][1][1]
    assert "tb_async_fifo.error_count=0" in calls[0][1][2]
    assert "tb_async_fifo.read_count" in calls[0][1][2]


def test_cli_analyze_rtl_vcd_async_fifo_invokes_analyzer(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_analyze_async_fifo_vcd(self, output_dir="outputs", limit=20, waveform_backend="auto"):
        calls.append((output_dir, limit, waveform_backend))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "analyze_async_fifo_vcd", fake_analyze_async_fifo_vcd)

    assert module.main([
        "--analyze-rtl-vcd",
        "async-fifo",
        "--output-dir",
        str(tmp_path),
        "--vcd-limit",
        "6",
        "--wave-backend",
        "vcd-analyzer",
    ]) == 0
    assert calls == [(str(tmp_path), 6, "vcd-analyzer")]


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

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
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

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
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


def test_write_async_fifo_uvm_coverage_summary_report_gates_component_thresholds(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    reports_dir = project_dir / "reports"
    cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
    cov_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
        "ASYNC_FIFO_UVM_TEST_DONE\n",
        encoding="utf-8",
    )
    (cov_dir / "xsim.CCInfo").write_bytes(
        b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00"
        b"../rtl/async_fifo.v\x00tb_async_fifo_uvm.dut\x00"
    )
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "Line Coverage Score 85\n"
        "Branch Coverage Score 55\n"
        "Condition Coverage Score 90\n"
        "Toggle Coverage Score 45\n"
        "Functional Coverage Score 92\n"
        "Total Coverage : 73.4%\n",
        encoding="utf-8",
    )

    report = agent.write_async_fifo_uvm_coverage_summary_report(
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
    assert "## P4.3 分项 Coverage Gate" in markdown
    assert "| Branch | 55.0% | 60.0% | 5.0% | FAIL |" in markdown
    assert "| Functional | 92.0% | 90.0% | -2.0% | PASS |" in markdown
    assert "P4.3 Component Coverage Gates" in html_text
    assert 'data-metric="branch"' in html_text
    assert 'class="component-gate fail"' in html_text


def test_write_async_fifo_uvm_coverage_summary_report_marks_missing_component_data(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    reports_dir = project_dir / "reports"
    cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
    cov_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
        "ASYNC_FIFO_UVM_TEST_DONE\n",
        encoding="utf-8",
    )
    (cov_dir / "xsim.CCInfo").write_bytes(
        b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00"
    )
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "Line Coverage Score 85\n",
        encoding="utf-8",
    )

    report = agent.write_async_fifo_uvm_coverage_summary_report(
        project_dir,
        coverage_thresholds={"functional": 90.0},
    )

    functional_gate = report["coverage_gates"]["functional"]
    assert report["passed"] is False
    assert report["coverage_gate_passed"] is False
    assert functional_gate["current"] is None
    assert functional_gate["gap"] is None
    assert functional_gate["result"] == "MISSING"
    assert functional_gate["diagnostic"] == "数据源缺失"
    markdown = report["markdown_path"].read_text(encoding="utf-8")
    assert "| Functional | N/A | 90.0% | N/A | MISSING | 数据源缺失 |" in markdown
    assert "| Functional | 0.0%" not in markdown


def test_p4_3_coverage_gates_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/coverage_gates.py"' in pyproject


def test_p4_4_appends_coverage_history_and_renders_trend_deltas(tmp_path):
    module = load_local_module("coverage_history_p4_4", COVERAGE_HISTORY_PATH)
    reports_dir = tmp_path / "reports"
    common = {
        "target_name": "async-fifo",
        "flow_name": "uvm-coverage",
        "toolchain": {
            "vivado": {
                "version": "2025.2",
                "command": r"D:\vivado\2025.2\Vivado\bin\vivado.bat",
            }
        },
        "coverage_gates": {
            "total": {"result": "PASS", "threshold": 75.0},
            "branch": {"result": "PASS", "threshold": 70.0},
        },
        "status": "PASS",
    }

    first = module.append_coverage_history(
        reports_dir,
        recorded_at="2026-07-10T01:00:00.000Z",
        seed_set=[11],
        coverage_metrics={
            "total": 80.0,
            "statement": 90.0,
            "branch": 75.0,
            "condition": 78.0,
            "toggle": 66.0,
            "functional": None,
        },
        **common,
    )
    second = module.append_coverage_history(
        reports_dir,
        recorded_at="2026-07-10T02:00:00.000Z",
        seed_set=[22],
        coverage_metrics={
            "total": 82.0,
            "statement": 91.0,
            "branch": 74.0,
            "condition": 80.0,
            "toggle": 70.0,
            "functional": 95.0,
        },
        **common,
    )

    history_lines = first["history_path"].read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in history_lines]
    assert len(records) == 2
    assert records[0]["schema_version"] == 1
    assert records[0]["target_name"] == "async-fifo"
    assert records[0]["flow_name"] == "uvm-coverage"
    assert records[0]["toolchain"]["vivado"]["version"] == "2025.2"
    assert records[0]["seed_set"] == [11]
    assert records[1]["coverage_metrics"]["functional"] == 95.0
    assert second["metric_deltas"]["total"] == 2.0
    assert second["metric_deltas"]["branch"] == -1.0

    markdown = second["markdown_path"].read_text(encoding="utf-8")
    html_text = second["html_path"].read_text(encoding="utf-8")
    assert "# Coverage 趋势" in markdown
    assert "| Total | 82.0% | +2.0% |" in markdown
    assert "| Branch | 74.0% | -1.0% |" in markdown
    assert "2026-07-10T01:00:00.000Z" in markdown
    assert "2026-07-10T02:00:00.000Z" in markdown
    assert 'data-target="async-fifo"' in html_text
    assert 'class="delta trend-up"' in html_text
    assert 'class="delta trend-down"' in html_text


def test_history_rotation_archives_coverage_records_and_keeps_latest_deltas(
    tmp_path,
):
    module = load_local_module(
        "coverage_history_rotation",
        COVERAGE_HISTORY_PATH,
    )
    reports_dir = tmp_path / "reports"
    result = None
    for index in range(4):
        result = module.append_coverage_history(
            reports_dir,
            target_name="async-fifo",
            flow_name="uvm-coverage",
            toolchain={"vivado": {"version": "2025.2"}},
            seed_set=[index],
            coverage_metrics={
                "total": 80.0 + index,
                "statement": 90.0,
                "branch": 75.0,
                "condition": 78.0,
                "toggle": 66.0,
                "functional": 95.0,
            },
            coverage_gates={},
            status="PASS",
            recorded_at="2026-07-11T01:0{}:00.000Z".format(index),
            max_active_records=2,
        )

    assert result is not None
    active_records = module.load_coverage_history(
        reports_dir / "coverage_history.jsonl"
    )
    assert [
        record["seed_set"]
        for record in active_records
    ] == [[2], [3]]
    assert result["metric_deltas"]["total"] == 1.0

    archive_path = reports_dir / "coverage_history.archive.jsonl.gz"
    with gzip.open(archive_path, "rt", encoding="utf-8") as stream:
        archived = [
            json.loads(line)
            for line in stream.read().splitlines()
        ]
    assert [
        record["seed_set"]
        for record in archived
    ] == [[0], [1]]
    assert result["archive_path"] == archive_path
    assert result["archived_records"] == 2

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "活动记录数量：2" in markdown
    assert "coverage_history.archive.jsonl.gz" in markdown
    assert "coverage_history.archive.jsonl.gz" in html_text


def test_p4_4_history_reports_invalid_jsonl_line(tmp_path):
    module = load_local_module("coverage_history_invalid_p4_4", COVERAGE_HISTORY_PATH)
    history_path = tmp_path / "coverage_history.jsonl"
    history_path.write_text(
        '{"schema_version": 1, "target_name": "async-fifo"}\n'
        "not-json\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="line 2"):
        module.load_coverage_history(history_path)


def test_p4_4_runner_appends_pass_and_fail_history_and_refreshes_index(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    run_count = 0

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
        env=None,
    ):
        nonlocal run_count
        run_count += 1
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
        )
        branch_score = 84.0 if run_count == 1 else 48.0
        total_score = 80.25 if run_count == 1 else 75.0
        (reports_dir / "uvm_coverage_percent.txt").write_text(
            "Statement Coverage : 91.5%\n"
            "Branch Coverage : {:.1f}%\n"
            "Condition Coverage : 79.5%\n"
            "Toggle Coverage : 66.0%\n"
            "Total Coverage : {:.2f}%\n".format(branch_score, total_score),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert agent.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_thresholds={"branch": 50.0},
        seed=11,
    ) is True
    assert agent.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_thresholds={"branch": 50.0},
        seed=22,
    ) is False

    reports_dir = tmp_path / "async-fifo" / "reports"
    history_path = reports_dir / "coverage_history.jsonl"
    records = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["PASS", "FAIL"]
    assert [record["seed_set"] for record in records] == [[11], [22]]
    assert records[0]["toolchain"]["vivado"]["version"] == "2025.2"
    assert records[1]["coverage_gates"]["branch"]["result"] == "FAIL"
    trend = (reports_dir / "coverage_trend.md").read_text(encoding="utf-8")
    index = (reports_dir / "index.md").read_text(encoding="utf-8")
    assert "| Total | 75.0% | -5.2% |" in trend
    assert "| Branch | 48.0% | -36.0% |" in trend
    assert "coverage_trend.html" in index
    assert "coverage_history.jsonl" in index


def test_p4_4_coverage_history_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/coverage_history.py"' in pyproject


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

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
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

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
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


def test_run_async_fifo_uvm_coverage_fails_when_component_gate_not_met(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(command, cwd=None, capture_output=False, text=False, encoding=None, errors=None, timeout=None, check=False):
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
        )
        (reports_dir / "uvm_coverage_percent.txt").write_text(
            "Line Coverage Score 91.5\n"
            "Branch Coverage Score 48\n"
            "Condition Coverage Score 79.5\n"
            "Toggle Coverage Score 66\n"
            "Functional Coverage Score 95\n"
            "Total Coverage : 80.0%\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert agent.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_thresholds={"branch": 50.0},
    ) is False

    project_dir = tmp_path / "async-fifo"
    summary = project_dir / "reports" / "uvm_coverage_summary.md"
    reports_index = project_dir / "reports" / "index.md"
    assert "| Branch | 48.0% | 50.0% | 2.0% | FAIL |" in summary.read_text(encoding="utf-8")
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

    monkeypatch.setattr(module.DigitalICAgent, "run_uvm_coverage", fake_run_uvm_coverage)

    assert module.main(["--uvm-coverage", "async-fifo", "--output-dir", str(tmp_path)]) == 0
    assert calls == [("async-fifo", str(tmp_path), None, None, {})]


def test_cli_uvm_coverage_async_fifo_forwards_component_thresholds(monkeypatch, tmp_path):
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

    monkeypatch.setattr(module.DigitalICAgent, "run_uvm_coverage", fake_run_uvm_coverage)

    assert module.main([
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
    ]) == 0
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
        "Functional Coverage Score 88\n"
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
    assert summary["metrics"]["functional"] == 88.0


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


def test_p4_5_archives_failed_run_materials_with_generic_manifest(tmp_path):
    module = load_local_module("failure_archive_p4_5", FAILURE_ARCHIVE_PATH)
    source_dir = tmp_path / "run"
    log_path = source_dir / "sim" / "failed.log"
    wdb_path = source_dir / "sim" / "failed.wdb"
    coverage_db = source_dir / "sim" / "coverage" / "xsim.codeCov"
    tcl_path = source_dir / "sim" / "run_failed.tcl"
    config_path = source_dir / "config" / "target.json"
    log_path.parent.mkdir(parents=True)
    coverage_db.mkdir(parents=True)
    config_path.parent.mkdir(parents=True)
    log_path.write_text("simulation failed\n", encoding="utf-8")
    wdb_path.write_text("wdb", encoding="utf-8")
    (coverage_db / "xsim.CCInfo").write_text("coverage", encoding="utf-8")
    tcl_path.write_text("puts failed\n", encoding="utf-8")
    config_path.write_text('{"name": "sync-fifo"}\n', encoding="utf-8")

    result = module.archive_failed_run(
        tmp_path / "failure_archives",
        target_name="sync-fifo",
        flow_name="formal-smoke",
        run_id="seed_22",
        status="FAIL",
        seed=22,
        artifacts=[
            {"role": "log", "path": log_path},
            {"role": "waveform", "path": wdb_path},
            {"role": "coverage_db", "path": coverage_db},
            {"role": "tcl", "path": tcl_path},
            {"role": "target_config", "path": config_path},
        ],
        reproduce_command=[
            "python",
            ".trae/agent/agent.py",
            "--uvm-random-regress",
            "sync-fifo",
            "--uvm-seeds",
            "22",
        ],
        wave_open_command=["vivado", "-mode", "gui", str(wdb_path)],
    )

    archive_dir = tmp_path / "failure_archives" / "formal-smoke" / "seed_22"
    assert result["archive_dir"] == archive_dir
    assert result["manifest_path"] == archive_dir / "failure_archive.json"
    assert result["reproduce_script_path"] == archive_dir / "reproduce.ps1"
    manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["target_name"] == "sync-fifo"
    assert manifest["flow_name"] == "formal-smoke"
    assert manifest["run_id"] == "seed_22"
    assert manifest["status"] == "FAIL"
    assert manifest["seed"] == 22
    assert manifest["reproduce_command"][-2:] == ["--uvm-seeds", "22"]
    assert manifest["wave_open_command"][:3] == ["vivado", "-mode", "gui"]
    assert {item["role"] for item in manifest["artifacts"]} == {
        "log",
        "waveform",
        "coverage_db",
        "tcl",
        "target_config",
    }
    for item in manifest["artifacts"]:
        assert item["available"] is True
        assert (archive_dir / item["archive_path"]).exists()
    assert "--uvm-seeds 22" in result["reproduce_script_path"].read_text(encoding="utf-8")
    assert "formal-smoke" in result["readme_path"].read_text(encoding="utf-8")
    source = FAILURE_ARCHIVE_PATH.read_text(encoding="utf-8")
    assert "async_fifo" not in source
    assert "uvm_coverage" not in source


def test_p4_5_random_regression_archives_only_failed_seed_and_links_report(
    monkeypatch, tmp_path
):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    def fake_run(
        output_dir="outputs",
        data_width=8,
        addr_width=4,
        coverage_threshold=None,
        coverage_percent=None,
        coverage_thresholds=None,
        seed=None,
    ):
        project_dir = Path(output_dir) / "async-fifo"
        sim_dir = project_dir / "sim"
        coverage_db = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
        coverage_db.mkdir(parents=True, exist_ok=True)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "PASS\n" if seed == 11 else "FAIL\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb", encoding="utf-8")
        (coverage_db / "xsim.CCInfo").write_text("coverage", encoding="utf-8")
        (sim_dir / "run_vivado_async_fifo_uvm_coverage.tcl").write_text(
            "puts run\n",
            encoding="utf-8",
        )
        return seed == 11

    monkeypatch.setattr(agent, "run_async_fifo_uvm_coverage", fake_run)

    assert agent.run_async_fifo_uvm_random_regression(
        output_dir=tmp_path,
        seeds=[11, 22],
    ) is False

    archive_root = tmp_path / "async-fifo" / "failure_archives" / "uvm-coverage"
    assert not (archive_root / "seed_11").exists()
    failed_archive = archive_root / "seed_22"
    assert (failed_archive / "failure_archive.json").exists()
    assert (failed_archive / "reproduce.ps1").exists()
    archived_roles = {
        item["role"]
        for item in json.loads(
            (failed_archive / "failure_archive.json").read_text(encoding="utf-8")
        )["artifacts"]
    }
    assert archived_roles == {
        "log",
        "waveform",
        "coverage_db",
        "tcl",
        "target_config",
    }
    report = (
        tmp_path / "async-fifo" / "reports" / "uvm_random_regression.md"
    ).read_text(encoding="utf-8")
    html_report = (
        tmp_path / "async-fifo" / "reports" / "uvm_random_regression.html"
    ).read_text(encoding="utf-8")
    assert "Failure Archive" in report
    assert "reproduce.ps1" in report
    assert "failure_archives" in report
    assert "Open WDB" in report
    assert "failure_archives" in html_report
    assert "reproduce.ps1" in html_report


def test_p4_5_failure_archive_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/failure_archive.py"' in pyproject


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
    assert "uvm_coverage_wave_open_check.json" in script_text
    assert "get_scopes" in script_text
    assert "get_objects" in script_text
    assert "get_waves" in script_text
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
    (reports_dir / "uvm_coverage_wave_open_check.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_name": "async-fifo",
                "flow_name": "uvm-coverage",
                "wave_database": str(sim_dir / "async_fifo_uvm_coverage.wdb"),
                "wdb_opened": True,
                "scope_count": 2,
                "object_count": 40,
                "wave_count": 40,
                "wave_config_count": 1,
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    (reports_dir / "uvm_wave_screenshot_metrics.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado 2025.2",
                "width": 1600,
                "height": 900,
                "sampled_pixels": 4096,
                "unique_colors": 96,
                "non_uniform_pixels": 2440,
                "non_uniform_ratio": 0.5957,
            }
        ),
        encoding="utf-8",
    )

    report = agent.write_async_fifo_uvm_wave_screenshot_report(project_dir, wave_kind="coverage")

    assert report["captured"] is True
    assert report["runtime_status"] == "PASS"
    assert report["screenshot_status"] == "PASS"
    assert report["markdown_path"].name == "uvm_wave_screenshot.md"
    assert report["html_path"].name == "uvm_wave_screenshot.html"
    assert report["capture_script_path"].name == "capture_uvm_wave_screenshot.ps1"
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    script_text = report["capture_script_path"].read_text(encoding="utf-8")
    assert "async-fifo UVM GUI 波形截图验收" in text
    assert "--open-uvm-wave async-fifo --uvm-wave-kind coverage" in text
    assert "uvm_wave_visibility.png" in text
    assert "Scope 数：2" in text
    assert "非均匀像素比例：59.57%" in text
    assert "uvm_wave_visibility.png" in html_text
    assert "capture_uvm_wave_screenshot.ps1" in script_text
    assert "GetForegroundWindow" in script_text
    assert "uvm_wave_screenshot_metrics.json" in script_text


def test_p4_6_wave_visibility_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/wave_visibility.py"' in pyproject


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
