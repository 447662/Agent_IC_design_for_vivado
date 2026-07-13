import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
AGENT_CONFIG_PATH = AGENT_DIR / "agent.json"
TRAE_CONFIG_PATH = ROOT / ".trae" / "config.json"
HANDSHAKE_VCD_PATH = (
    ROOT
    / "VCD_ANALYZER-main"
    / "VCD_ANALYZER-main"
    / "verify"
    / "fixtures"
    / "handshake_trace.vcd"
)

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


def test_config_uses_portable_synthpilot_command():
    agent_config = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
    trae_config = json.loads(TRAE_CONFIG_PATH.read_text(encoding="utf-8"))

    assert agent_config["mcpServers"]["synthpilot"]["command"] == "uvx"
    assert trae_config["mcpServers"]["synthpilot"]["command"] == "uvx"
    assert agent_config["mcpServers"]["synthpilot"]["args"] == ["synthpilot==0.1.0"]
    assert trae_config["mcpServers"]["synthpilot"]["args"] == ["synthpilot==0.1.0"]


def test_cli_check_commands_are_arrays():
    agent_config = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))

    for tool in agent_config["cliTools"]:
        assert isinstance(tool["checkCommand"], list)
        assert all(isinstance(part, str) for part in tool["checkCommand"])
        assert tool["checkCommand"]


def test_analyze_requirement_matches_design_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("请生成这个模块的设计文档") == [
        "digital-ic-designer"
    ]


def test_analyze_requirement_matches_rtl_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("implement UART Verilog RTL code") == [
        "digital-ic-rtl-designer"
    ]


def test_analyze_requirement_matches_uvm_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert "digital-ic-verifier" in agent.analyze_requirement(
        "use UVM to run verification and coverage"
    )


def test_analyze_requirement_defaults_to_rtl_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("build a counter") == ["digital-ic-rtl-designer"]


@pytest.mark.parametrize(
    ("requirement", "expected_skills"),
    [
        ("do not use UVM, only write RTL", ["digital-ic-rtl-designer"]),
        ("no design document, only implement RTL", ["digital-ic-rtl-designer"]),
        ("only generate design document, do not write RTL or simulation", ["digital-ic-designer"]),
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
    assert "CLI" in result.stdout
    assert "MCP" in result.stdout


def test_cli_rejects_conflicting_modes():
    result = run_agent("--diagnostic", "--list-skills")

    assert result.returncode != 0
    assert (
        "not allowed with argument" in result.stderr
        or "conflict" in result.stderr.lower()
        or "cannot" in result.stderr.lower()
    )


def test_cli_no_tool_check_generates_design_spec_but_requires_configured_target(
    tmp_path,
):
    result = run_agent(
        "--no-tool-check",
        "--output-dir",
        str(tmp_path),
        "design a UART controller",
    )

    assert result.returncode != 0
    assert "must name one configured RTL target" in result.stderr
    assert "sync-fifo" in result.stderr
    spec_files = list(tmp_path.glob("*/design_spec.md"))
    assert len(spec_files) == 1

    content = spec_files[0].read_text(encoding="utf-8")
    assert "design a UART controller" in content
    assert "digital-ic-rtl-designer" in content


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
    assert "handshake_trace.vcd" in result.stdout
    assert "valid=1,ready=1" in result.stdout
    assert "0xaa" in result.stdout
    assert "0x55" in result.stdout


def test_cli_analyze_vcd_rejects_missing_file(tmp_path):
    missing_vcd = tmp_path / "missing.vcd"

    result = run_agent("--analyze-vcd", str(missing_vcd))

    assert result.returncode != 0
    assert "VCD file not found" in result.stderr
