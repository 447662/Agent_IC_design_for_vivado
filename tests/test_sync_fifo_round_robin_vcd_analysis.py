import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_sync_fifo_round_robin_vcd_analysis_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def test_p5_2_analyze_sync_fifo_vcd_reports_write_and_read_handshakes(
    monkeypatch,
    tmp_path,
    capsys,
):
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

    monkeypatch.setattr(
        agent,
        "run_waveform_analyzer_json",
        fake_run_waveform_analyzer_json,
    )

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

    def fake_analyze_sync_fifo_vcd(
        self,
        output_dir="outputs",
        limit=20,
        waveform_backend="auto",
    ):
        calls.append((output_dir, limit, waveform_backend))
        return True

    monkeypatch.setattr(
        module.DigitalICAgent,
        "analyze_sync_fifo_vcd",
        fake_analyze_sync_fifo_vcd,
    )

    assert (
        module.main(
            [
                "--analyze-rtl-vcd",
                "sync-fifo",
                "--output-dir",
                str(tmp_path),
                "--vcd-limit",
                "6",
                "--wave-backend",
                "rwave",
            ]
        )
        == 0
    )
    assert calls == [(str(tmp_path), 6, "rwave")]


def test_p5_3_analyze_round_robin_arbiter_vcd_reports_grants_and_fairness(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    vcd_path = (
        tmp_path
        / "round-robin-arbiter"
        / "sim"
        / "round_robin_arbiter_trace.vcd"
    )
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

    monkeypatch.setattr(
        agent,
        "run_waveform_analyzer_json",
        fake_run_waveform_analyzer_json,
    )

    assert (
        agent.analyze_round_robin_arbiter_vcd(output_dir=tmp_path, limit=4)
        is True
    )

    captured = capsys.readouterr()
    assert "Round-Robin Arbiter VCD analysis" in captured.out
    assert "Grant events: 4" in captured.out
    assert "Fairness checkpoints: 4" in captured.out
    assert calls[0] == ("info", vcd_path)
    assert "tb_round_robin_arbiter.grant_valid=1" in calls[1]
    assert "tb_round_robin_arbiter.grant_count" in calls[1]
    assert "tb_round_robin_arbiter.grant_valid=1" in calls[2]
    assert "tb_round_robin_arbiter.grant_count" in calls[2]
    assert any(
        "tb_round_robin_arbiter.scenario_id" in str(arg) for arg in calls[2]
    )


def test_round_robin_real_vcd_analysis_refreshes_clean_report(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "round-robin-arbiter"
    vcd_path = project_dir / "sim" / "round_robin_arbiter_trace.vcd"
    write_round_robin_vcd_fixture(vcd_path)
    wave_db_path = project_dir / "sim" / "round_robin_arbiter_smoke.wdb"
    wave_db_path.write_text("wdb", encoding="utf-8")

    assert (
        agent.analyze_round_robin_arbiter_vcd(
            output_dir=tmp_path,
            limit=4,
            waveform_backend="vcd-analyzer",
        )
        is True
    )

    report_path = project_dir / "reports" / "sim_report.md"
    report_text = report_path.read_text(encoding="utf-8")
    assert "- 状态：PASS" in report_text
    assert "PASS_WITH_ANALYSIS_WARNING" not in report_text
    assert "- Backend: `vcd_analyzer`" in report_text


def test_p5_3_cli_analyze_rtl_vcd_round_robin_arbiter_invokes_analyzer(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_analyze_round_robin_arbiter_vcd(
        self,
        output_dir="outputs",
        limit=20,
        waveform_backend="auto",
    ):
        calls.append((output_dir, limit, waveform_backend))
        return True

    monkeypatch.setattr(
        module.DigitalICAgent,
        "analyze_round_robin_arbiter_vcd",
        fake_analyze_round_robin_arbiter_vcd,
    )

    assert (
        module.main(
            [
                "--analyze-rtl-vcd",
                "round-robin-arbiter",
                "--output-dir",
                str(tmp_path),
                "--vcd-limit",
                "7",
                "--wave-backend",
                "rwave",
            ]
        )
        == 0
    )
    assert calls == [(str(tmp_path), 7, "rwave")]
