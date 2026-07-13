import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime import agent_sim_smoke as smoke  # noqa: E402


class Detector:
    def __init__(self, vivado: str | None = None):
        self.vivado = vivado

    def resolve_vivado_command(self) -> str | None:
        return self.vivado


@pytest.mark.parametrize(
    ("vivado", "available", "expected"),
    [
        ("vivado", set(), "vivado"),
        (None, {"iverilog", "vvp"}, "icarus"),
        (None, {"verilator"}, "verilator"),
        (None, set(), None),
    ],
)
def test_detect_simulator_covers_supported_and_missing_tools(
    monkeypatch,
    vivado,
    available,
    expected,
):
    monkeypatch.setattr(smoke.shutil, "which", lambda name: name if name in available else None)

    assert smoke.detect_simulator(Detector(vivado)) == expected


class QueueRunner:
    def __init__(self, results, vcd_path: Path | None = None):
        self.results = list(results)
        self.vcd_path = vcd_path

    def run(self, command, **_kwargs):
        result = self.results.pop(0)
        if command[0] == "vvp" and result.returncode == 0 and self.vcd_path is not None:
            self.vcd_path.write_text("$date\nfixture\n$end\n", encoding="utf-8")
        return result


class IcarusAgent:
    def __init__(self, tmp_path: Path, results, *, analyze: bool = True, create_vcd: bool = False):
        self.tmp_path = tmp_path
        self.vcd_path = tmp_path / "sim-smoke" / "handshake_trace.vcd"
        self.command_runner = QueueRunner(results, self.vcd_path if create_vcd else None)
        self.analyze = analyze

    def write_sim_smoke_sources(self, output_dir):
        return smoke.write_sim_smoke_sources(output_dir)

    def analyze_vcd(self, *_args, **_kwargs):
        return self.analyze


@pytest.mark.parametrize(
    ("results", "expected_error"),
    [
        ([subprocess.CompletedProcess([], 1, "", "compile denied")], "compile denied"),
        (
            [
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 1, "", "run denied"),
            ],
            "run denied",
        ),
        (
            [
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "", ""),
            ],
            "did not generate VCD",
        ),
    ],
)
def test_icarus_smoke_reports_compile_run_and_artifact_failures(
    tmp_path,
    capsys,
    results,
    expected_error,
):
    agent = IcarusAgent(tmp_path, results)

    assert smoke.run_icarus_sim_smoke(agent, tmp_path) is False
    assert expected_error in capsys.readouterr().err


def test_icarus_smoke_returns_waveform_analysis_result(tmp_path):
    results = [
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, "", ""),
    ]
    agent = IcarusAgent(tmp_path, results, analyze=False, create_vcd=True)

    assert smoke.run_icarus_sim_smoke(agent, tmp_path) is False


class GuiAgent(Detector):
    def __init__(self, vivado: str | None):
        super().__init__(vivado)
        self.launches = []

    def launch_vivado_gui(self, *args):
        self.launches.append(args)


def test_open_vivado_wave_gui_reports_missing_database_and_command(tmp_path, capsys):
    agent = GuiAgent("vivado")
    assert smoke.open_vivado_wave_gui(agent, tmp_path, tmp_path / "trace.vcd") is False
    assert "database not found" in capsys.readouterr().err

    (tmp_path / "handshake_smoke.wdb").write_text("fixture", encoding="utf-8")
    agent.vivado = None
    assert smoke.open_vivado_wave_gui(agent, tmp_path, tmp_path / "trace.vcd") is False
    assert "Vivado command not found" in capsys.readouterr().err


class DispatchAgent:
    def __init__(self, simulator: str | None):
        self.simulator = simulator
        self.calls: list[str] = []

    def detect_simulator(self):
        return self.simulator

    def run_vivado_sim_smoke(self, **_kwargs):
        self.calls.append("vivado")
        return True

    def run_icarus_sim_smoke(self, **_kwargs):
        self.calls.append("icarus")
        return True


@pytest.mark.parametrize(
    ("simulator", "expected", "result"),
    [
        ("vivado", ["vivado"], True),
        ("icarus", ["icarus"], True),
        ("verilator", [], False),
        (None, [], False),
    ],
)
def test_sim_smoke_dispatches_or_reports_unsupported_simulator(
    simulator,
    expected,
    result,
):
    agent = DispatchAgent(simulator)

    assert smoke.run_sim_smoke(agent) is result
    assert agent.calls == expected
