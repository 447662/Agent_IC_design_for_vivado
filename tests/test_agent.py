import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / ".trae" / "agent" / "agent.py"
AGENT_CONFIG_PATH = ROOT / ".trae" / "agent" / "agent.json"
TRAE_CONFIG_PATH = ROOT / ".trae" / "config.json"


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
    assert "not allowed with argument" in result.stderr or "tool" in result.stderr.lower() or "冲突" in result.stderr
