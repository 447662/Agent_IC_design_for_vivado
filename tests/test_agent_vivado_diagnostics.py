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

def test_resolve_vivado_command_uses_configured_command(monkeypatch):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    agent.vivado_command = r"D:\vivado\2025.2\Vivado\bin\unwrapped\win64.o\vivado.exe"

    monkeypatch.setattr(module.shutil, "which", lambda _name: None)

    assert agent.resolve_vivado_command() == r"D:\vivado\2025.2\Vivado\bin\vivado.bat"


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


def test_capability_preflight_accepts_vivado_banner_on_nonzero_exit(monkeypatch):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"

    monkeypatch.setattr(agent, "resolve_vivado_command", lambda: vivado_path)
    monkeypatch.setattr(
        agent.command_runner,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            1,
            stdout="vivado v2025.2 (64-bit) SW Build 6299465",
            stderr="",
        ),
    )

    report = agent.run_preflight("sim-rtl")

    assert report.ok is True
    assert report.status_for("vivado").value == "available"
