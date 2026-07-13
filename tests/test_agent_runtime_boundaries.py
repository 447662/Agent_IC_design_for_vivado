import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
AGENT_RUNTIME_PATH = AGENT_DIR / "agent_runtime.py"
AGENT_CLI_PATH = AGENT_DIR / "agent_cli.py"
AGENT_ENTRYPOINT_PATH = AGENT_DIR / "agent_entrypoint.py"
AGENT_COMPOSITION_PATH = AGENT_DIR / "agent_composition.py"
AGENT_CONFIG_HELPERS_PATH = AGENT_DIR / "agent_config.py"
AGENT_REPORTS_PATH = AGENT_DIR / "agent_reports.py"
AGENT_WAVEFORM_PATH = AGENT_DIR / "agent_waveform.py"
TARGET_CHECKS_PATH = AGENT_DIR / "target_checks.py"
TARGET_FLOWS_PATH = AGENT_DIR / "target_flows.py"
AGENT_CONFIG_PATH = AGENT_DIR / "agent.json"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_runtime_boundaries_split",
        AGENT_PATH,
    )
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


def test_configure_text_stream_uses_utf8_replacement_mode():
    module = load_agent_module()
    calls = []

    class FakeStream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    module._configure_text_stream(FakeStream())

    assert calls == [
        {
            "encoding": "utf-8",
            "errors": "replace",
            "write_through": True,
        }
    ]


def test_command_runner_applies_timeout_and_utf8_defaults(monkeypatch):
    module = load_agent_module()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="done", stderr="")

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
    assert cli.parse_args(["--list-targets"]).list_targets is True
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
    assert len(calls) == 1
    argv, agent_factory = calls[0]
    assert argv == ["--list-targets"]
    assert callable(agent_factory)
    assert agent_factory() is not None


def test_config_helpers_live_in_dedicated_module():
    assert AGENT_CONFIG_HELPERS_PATH.exists()

    config_helpers = load_local_module("agent_config", AGENT_CONFIG_HELPERS_PATH)
    module = load_agent_module()

    assert module.load_agent_config is config_helpers.load_agent_config
    assert module.normalize_configured_command is config_helpers.normalize_configured_command
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

    assert module.render_markdown_html_document is reports.render_markdown_document_html
    html_text = reports.render_markdown_document_html(
        "verification report",
        "# Title\n\n| Item | Status |\n| --- | --- |\n| smoke | PASS |\n",
    )
    assert "<title>verification report</title>" in html_text
    assert "<th>Item</th>" in html_text
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
    assert waveform.resolve_rwave_command(tmp_path, env={}, which=lambda _: None) == str(
        binary
    )


def test_target_flow_builder_lives_in_dedicated_module():
    assert TARGET_FLOWS_PATH.exists()

    flows = load_local_module("target_flows", TARGET_FLOWS_PATH)
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert module.build_registered_target_handlers is flows.build_target_handlers
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
