import importlib.util
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
        "digital_ic_agent_waveform_runtime_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_waveform_analyzer_prefers_rwave_when_available(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "wave.vcd"
    vcd_path.write_text("$date\nwave\n$end\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: "rwave")

    def fake_run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"signal_count":3,"duration_h":"20 ns"}',
            stderr="",
        )

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

    def fake_run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"signal_count":2,"duration_h":"10 ns"}',
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = agent.run_waveform_analyzer_json("info", vcd_path)

    assert result["signal_count"] == 2
    assert result["_waveform_backend"] == "vcd_analyzer"
    assert calls == [
        [
            sys.executable,
            str(agent.resolve_vcd_analyzer_path()),
            "--json",
            "info",
            str(vcd_path),
        ]
    ]


def test_waveform_analyzer_can_force_vcd_analyzer(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = tmp_path / "wave.vcd"
    vcd_path.write_text("$date\nwave\n$end\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(agent, "resolve_rwave_command", lambda: "rwave")

    def fake_run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"signal_count":4,"duration_h":"30 ns"}',
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = agent.run_waveform_analyzer_json("info", vcd_path, backend="vcd-analyzer")

    assert result["signal_count"] == 4
    assert result["_waveform_backend"] == "vcd_analyzer"
    assert calls == [
        [
            sys.executable,
            str(agent.resolve_vcd_analyzer_path()),
            "--json",
            "info",
            str(vcd_path),
        ]
    ]


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
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="\n".join(
                [
                    '{"id":"info","ok":true,"result":{"signal_count":12}}',
                    '{"id":"write_events","ok":true,"result":{"total":2,"events":[]}}',
                    '{"id":"read_events","ok":true,"result":{"total":3,"events":[]}}',
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = agent.run_rwave_batch_json(
        vcd_path,
        [
            "info #info",
            "search --condition tb_async_fifo.full=0 "
            "--changed tb_async_fifo.write_count #write_events",
            "search --condition tb_async_fifo.error_count=0 "
            "--changed tb_async_fifo.read_count #read_events",
        ],
    )

    assert result["info"]["signal_count"] == 12
    assert result["write_events"]["total"] == 2
    assert result["read_events"]["total"] == 3
    assert calls[0][0] == ["rwave", "--batch", "--json", str(vcd_path)]
    assert "info #info" in calls[0][1]["input"]
    assert "tb_async_fifo.write_count" in calls[0][1]["input"]
    assert "tb_async_fifo.read_count" in calls[0][1]["input"]
