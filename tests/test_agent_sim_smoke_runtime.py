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

def run_agent(*args):
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class FakeRunningGuiProcess:
    pid = 4321
    returncode = None

    @staticmethod
    def poll():
        return None


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


def test_run_sim_smoke_reports_missing_simulator(monkeypatch, capsys, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    monkeypatch.setattr(agent, "detect_simulator", lambda: None)

    assert agent.run_sim_smoke(output_dir=tmp_path, limit=5) is False

    captured = capsys.readouterr()
    assert "No supported Verilog simulator found" in captured.err
    assert "iverilog" in captured.err


def test_icarus_compile_failure_is_reported(monkeypatch, capsys, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    monkeypatch.setattr(
        agent.command_runner,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            2,
            stdout="",
            stderr="iverilog rejected the source",
        ),
    )

    assert agent.run_icarus_sim_smoke(output_dir=tmp_path) is False
    assert "iverilog rejected the source" in capsys.readouterr().err


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

    def fake_run(
        command,
        cwd=None,
        capture_output=False,
        text=False,
        encoding=None,
        errors=None,
        timeout=None,
        check=False,
    ):
        calls.append([str(part) for part in command])
        if command[0] == "iverilog":
            assert "-o" in command
        elif command[0] == "vvp":
            vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
            vcd_path.write_text("$date\nsim smoke test\n$end\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    analyzed = {}

    def fake_analyze_vcd(
        vcd_path,
        condition=None,
        show=None,
        limit=20,
        waveform_backend="auto",
    ):
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
    monkeypatch.setattr(
        agent,
        "resolve_vivado_command",
        lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat",
    )
    monkeypatch.setattr(
        agent,
        "open_vivado_wave_gui",
        lambda sim_dir, vcd_path: gui_calls.append((Path(sim_dir), Path(vcd_path))) or True,
    )

    def fake_run(
        command,
        cwd=None,
        capture_output=False,
        text=False,
        encoding=None,
        errors=None,
        timeout=None,
        check=False,
    ):
        calls.append([str(part) for part in command])
        assert command[0] == r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
        assert "-mode" in command
        assert "-source" in command
        assert command[command.index("-source") + 1] == "run_vivado_sim.tcl"
        vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
        vcd_path.write_text("$date\nvivado sim smoke test\n$end\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="Vivado simulation done", stderr="")

    analyzed = {}

    def fake_analyze_vcd(
        vcd_path,
        condition=None,
        show=None,
        limit=20,
        waveform_backend="auto",
    ):
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

    monkeypatch.setattr(
        agent,
        "resolve_vivado_command",
        lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat",
    )

    def fake_run(
        command,
        cwd=None,
        capture_output=False,
        text=False,
        encoding=None,
        errors=None,
        timeout=None,
        check=False,
    ):
        vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
        vcd_path.write_text("$date\nvivado sim smoke test\n$end\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="Vivado simulation done", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "analyze_vcd", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        agent,
        "open_vivado_wave_gui",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GUI should be skipped")),
    )

    assert agent.run_vivado_sim_smoke(output_dir=tmp_path, limit=9, open_wave_gui=False) is True


def test_open_vivado_wave_gui_uses_wdb_database(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    calls = []

    (tmp_path / "handshake_smoke.wdb").write_text("wdb placeholder", encoding="utf-8")
    monkeypatch.setattr(
        agent,
        "resolve_vivado_command",
        lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat",
    )
    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda command, cwd=None: (
            calls.append((command, Path(cwd))),
            FakeRunningGuiProcess(),
        )[1],
    )

    assert agent.open_vivado_wave_gui(tmp_path, tmp_path / "handshake_trace.vcd") is True

    script = (tmp_path / "open_vivado_wave.tcl").read_text(encoding="utf-8")
    assert "set wave_db handshake_smoke.wdb" in script
    assert "open_wave_database $wave_db" in script
    assert "open_wave_database handshake_trace.vcd" not in script
    assert calls == [
        (
            [r"D:\vivado\2025.2\Vivado\bin\vivado.bat", "-mode", "gui", "-source", "open_vivado_wave.tcl"],
            tmp_path,
        )
    ]


def test_sim_smoke_rtl_and_testbench_use_same_timescale(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    _sim_dir, rtl_path, tb_path, _vcd_path = agent.write_sim_smoke_sources(tmp_path)

    assert rtl_path.read_text(encoding="utf-8").startswith("`timescale 1ns/1ps")
    assert tb_path.read_text(encoding="utf-8").startswith("`timescale 1ns/1ps")
