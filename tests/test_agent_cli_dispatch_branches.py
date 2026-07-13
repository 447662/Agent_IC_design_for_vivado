import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent_cli import parse_args  # noqa: E402
from digital_ic_agent._runtime.agent_cli_dispatch import (  # noqa: E402
    _required_mode_value,
    _run_boolean_flow,
    _status_exit,
    dispatch_cli_command,
)
from digital_ic_agent._runtime.agent_errors import CapabilityError  # noqa: E402


def test_cli_dispatch_helpers_preserve_status_and_structured_exit_codes(capsys):
    assert _required_mode_value("target") == "target"
    with pytest.raises(ValueError, match="requires a target"):
        _required_mode_value(None)
    assert _status_exit({"status": "PASS"}) == 0
    assert _status_exit({"status": "FAIL"}) == 1
    assert _run_boolean_flow("Flow", lambda: True, (RuntimeError,)) == 0
    assert _run_boolean_flow("Flow", lambda: False, (RuntimeError,)) == 1

    def fail():
        raise CapabilityError("missing tool")

    assert _run_boolean_flow("Flow", fail, (CapabilityError,)) == 3
    assert "Flow failed" in capsys.readouterr().err


class ReportAgent:
    def __init__(self, status: str = "PASS"):
        self.status = status

    def write_environment_report(self, **_kwargs):
        return {
            "status": self.status,
            "markdown_path": "environment.md",
            "html_path": "environment.html",
            "manifest_path": "artifacts.json",
        }

    def write_project_overview(self, **_kwargs):
        return {
            "status": self.status,
            "markdown_path": "overview.md",
            "html_path": "overview.html",
        }

    def write_coverage_closure_report(self, **_kwargs):
        return {
            "status": self.status,
            "markdown_path": "coverage.md",
            "html_path": "coverage.html",
        }

    def write_waveform_sample_report(self, **_kwargs):
        return {
            "status": self.status,
            "markdown_path": "waveform.md",
            "html_path": "waveform.html",
        }


@pytest.mark.parametrize(
    "option",
    [
        "--environment-report",
        "--generate-overview",
        "--coverage-closure",
        "--verify-waveform-samples",
    ],
)
def test_cli_dispatch_report_commands_map_status_to_exit_code(option):
    assert dispatch_cli_command(parse_args([option]), ReportAgent("PASS")) == 0
    assert dispatch_cli_command(parse_args([option]), ReportAgent("FAIL")) == 1


def test_cli_dispatch_report_errors_are_user_visible(capsys):
    class FailingAgent:
        @staticmethod
        def write_environment_report(**_kwargs):
            raise OSError("report path denied")

    assert dispatch_cli_command(parse_args(["--environment-report"]), FailingAgent()) == 1
    assert "report path denied" in capsys.readouterr().err


def test_cli_dispatch_rejects_empty_default_requirement(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    assert dispatch_cli_command(parse_args([]), object()) == 1
    assert "用户需求不能为空" in capsys.readouterr().err
