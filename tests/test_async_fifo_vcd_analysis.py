import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    return importlib.import_module("digital_ic_agent._runtime.agent")

def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


def test_analyze_async_fifo_vcd_reports_write_and_read_handshakes(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    vcd_path = tmp_path / "async-fifo" / "sim" / "async_fifo_trace.vcd"
    vcd_path.parent.mkdir(parents=True)
    vcd_path.write_text("$date\nasync fifo\n$end\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(plugin, "resolve_rwave_command", lambda: "rwave")

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

    monkeypatch.setattr(plugin, "run_rwave_batch_json", fake_run_rwave_batch_json)

    assert plugin.analyze_async_fifo_vcd(output_dir=tmp_path, limit=4) is True

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


def test_collect_async_fifo_vcd_analysis_falls_back_from_rwave(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    vcd_path = tmp_path / "async-fifo" / "sim" / "async_fifo_trace.vcd"
    vcd_path.parent.mkdir(parents=True)
    vcd_path.write_text("$date\nasync fifo\n$end\n", encoding="utf-8")
    analyzer_calls = []

    monkeypatch.setattr(plugin, "resolve_rwave_command", lambda: "rwave")
    monkeypatch.setattr(
        plugin,
        "collect_async_fifo_vcd_analysis_with_rwave_batch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("rwave unavailable")
        ),
    )

    def fake_run_waveform_analyzer_json(command, path, *args, backend="auto"):
        analyzer_calls.append((command, path, args, backend))
        if command == "info":
            return {"signal_count": 3, "_waveform_backend": "fallback"}
        return {"total": 1, "events": [{"time_h": "1 ns", "values": {"data": "0x1"}}]}

    monkeypatch.setattr(
        plugin,
        "run_waveform_analyzer_json",
        fake_run_waveform_analyzer_json,
    )

    analysis = plugin.collect_async_fifo_vcd_analysis(
        output_dir=tmp_path,
        limit=1,
        waveform_backend="auto",
    )

    assert analysis["vcd_path"] == vcd_path
    assert analysis["info"]["_waveform_backend"] == "fallback"
    assert [call[0] for call in analyzer_calls] == ["info", "search", "search"]


def test_collect_async_fifo_vcd_analysis_rwave_backend_reraises(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    vcd_path = tmp_path / "async-fifo" / "sim" / "async_fifo_trace.vcd"
    vcd_path.parent.mkdir(parents=True)
    vcd_path.write_text("$date\nasync fifo\n$end\n", encoding="utf-8")

    monkeypatch.setattr(plugin, "resolve_rwave_command", lambda: "rwave")
    monkeypatch.setattr(
        plugin,
        "collect_async_fifo_vcd_analysis_with_rwave_batch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FileNotFoundError("missing rwave")
        ),
    )

    with pytest.raises(FileNotFoundError):
        plugin.collect_async_fifo_vcd_analysis(
            output_dir=tmp_path,
            waveform_backend="rwave",
        )


def test_analyze_async_fifo_vcd_reports_missing_and_runtime_errors(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)

    assert plugin.analyze_async_fifo_vcd(output_dir=tmp_path) is False
    missing = capsys.readouterr()
    assert "Async FIFO VCD file not found" in missing.err

    monkeypatch.setattr(
        plugin,
        "collect_async_fifo_vcd_analysis",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("analyzer failed")),
    )

    assert plugin.analyze_async_fifo_vcd(output_dir=tmp_path) is False
    runtime = capsys.readouterr()
    assert "analyzer failed" in runtime.err


def test_analyze_async_fifo_vcd_prints_segment_end(monkeypatch, tmp_path, capsys):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)

    monkeypatch.setattr(
        plugin,
        "collect_async_fifo_vcd_analysis",
        lambda **_kwargs: {
            "vcd_path": tmp_path / "async-fifo" / "sim" / "async_fifo_trace.vcd",
            "info": {"signal_count": 1},
            "write_events": {
                "total": 1,
                "segments": [
                    {
                        "begin_h": "10 ns",
                        "end_h": "20 ns",
                        "values": {"wr_data": "0xAA"},
                    },
                ],
            },
            "read_events": {"total": 0, "events": []},
        },
    )

    assert plugin.analyze_async_fifo_vcd(output_dir=tmp_path, limit=4) is True
    captured = capsys.readouterr()
    assert "10 ns -> 20 ns" in captured.out


def test_cli_analyze_rtl_vcd_async_fifo_invokes_analyzer(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []
    agent = module.DigitalICAgent()

    monkeypatch.setattr(module, "create_agent", lambda: agent)

    def fake_analyze_async_fifo_vcd(
        output_dir="outputs",
        limit=20,
        waveform_backend="auto",
    ):
        calls.append((output_dir, limit, waveform_backend))
        return True

    monkeypatch.setattr(
        async_fifo_plugin(agent),
        "analyze_async_fifo_vcd",
        fake_analyze_async_fifo_vcd,
    )

    assert module.main(
        [
            "--analyze-rtl-vcd",
            "async-fifo",
            "--output-dir",
            str(tmp_path),
            "--vcd-limit",
            "6",
            "--wave-backend",
            "vcd-analyzer",
        ]
    ) == 0
    assert calls == [(str(tmp_path), 6, "vcd-analyzer")]
