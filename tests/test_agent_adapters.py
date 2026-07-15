import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
ADAPTERS_DIR = AGENT_DIR / "adapters"
REPORT_ADAPTER_PATH = ADAPTERS_DIR / "report.py"
WAVEFORM_ADAPTER_PATH = ADAPTERS_DIR / "waveform.py"
VIVADO_ADAPTER_PATH = ADAPTERS_DIR / "vivado.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    return importlib.import_module("digital_ic_agent._runtime.agent")

def test_p5_9_adapter_modules_own_extracted_agent_methods():
    assert REPORT_ADAPTER_PATH.exists()
    assert WAVEFORM_ADAPTER_PATH.exists()
    assert VIVADO_ADAPTER_PATH.exists()

    module = load_agent_module()
    report_adapter = importlib.import_module("digital_ic_agent._runtime.adapters.report")
    waveform_adapter = importlib.import_module("digital_ic_agent._runtime.adapters.waveform")
    vivado_adapter = importlib.import_module("digital_ic_agent._runtime.adapters.vivado")

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
    assert module.DigitalICAgent.resolve_vivado_command is (
        vivado_adapter.resolve_vivado_command
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
