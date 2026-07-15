import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent_cli import parse_args  # noqa: E402
from digital_ic_agent._runtime.agent_cli_dispatch import dispatch_cli_command  # noqa: E402


@pytest.mark.parametrize("option", ["--analyze-vcd", "--analyze-waveform"])
def test_cli_waveform_runtime_errors_are_user_visible(option, capsys):
    class FailingWaveformAgent:
        @staticmethod
        def analyze_vcd(*_args: object, **_kwargs: object) -> bool:
            raise RuntimeError("waveform backend protocol failure")

        @staticmethod
        def analyze_waveform(*_args: object, **_kwargs: object) -> bool:
            raise RuntimeError("waveform backend protocol failure")

    exit_code = dispatch_cli_command(
        parse_args([option, "broken.vcd"]),
        FailingWaveformAgent(),
    )

    assert exit_code == 1
    assert (
        "Waveform analysis failed: waveform backend protocol failure"
        in capsys.readouterr().err
    )


def test_cli_sim_smoke_os_errors_are_user_visible(capsys):
    class FailingSimulationAgent:
        @staticmethod
        def run_sim_smoke(**_kwargs: object) -> bool:
            raise OSError("simulator launch denied")

    exit_code = dispatch_cli_command(
        parse_args(["--sim-smoke"]),
        FailingSimulationAgent(),
    )

    assert exit_code == 1
    assert "Simulation smoke failed: simulator launch denied" in capsys.readouterr().err
