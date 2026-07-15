from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _main() -> object:
    return importlib.import_module("digital_ic_agent._runtime.agent").main


def _json_call(
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> tuple[int, dict[str, object]]:
    exit_code = _main()([*argv, "--json"])
    captured = capsys.readouterr()
    assert captured.err == ""
    return exit_code, json.loads(captured.out)


def _write_failed_verdict(workspace: Path) -> None:
    verdict_module = importlib.import_module(
        "digital_ic_agent._runtime.verification_verdict"
    )
    verdict_module.write_verification_verdict(
        workspace,
        verdict_module.failed_verdict(
            "UVM_ERROR_FOUND",
            "UVM reported one error",
            "xsim.log",
        ),
    )


def test_status_diagnose_resume_and_report_share_atomic_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    exit_code, initialized = _json_call(
        capsys,
        ["workspace", "init", "--workspace", str(workspace)],
    )
    assert exit_code == 0
    assert initialized["data"]["stage"] == "INITIALIZED"

    exit_code, status = _json_call(
        capsys,
        ["status", "--workspace", str(workspace)],
    )
    assert exit_code == 0
    assert status["data"]["state"]["last_successful_stage"] == "INITIALIZED"

    _write_failed_verdict(workspace)
    exit_code, diagnosis = _json_call(
        capsys,
        ["diagnose", "--workspace", str(workspace)],
    )
    assert exit_code == 1
    assert diagnosis["error_code"] == "VERIFICATION_FAILED"
    assert diagnosis["data"]["diagnosis"]["reasons"][0]["code"] == (
        "UVM_ERROR_FOUND"
    )
    diagnose_path = workspace / "reports" / "diagnose.json"
    assert diagnose_path.is_file()
    assert json.loads(diagnose_path.read_text(encoding="utf-8")) == (
        diagnosis["data"]["diagnosis"]
    )

    exit_code, resume = _json_call(
        capsys,
        ["resume", "--workspace", str(workspace)],
    )
    assert exit_code == 0
    assert resume["data"]["resume_from"] == "INITIALIZED"
    assert resume["data"]["current_stage"] == "DIAGNOSED"

    exit_code, report = _json_call(
        capsys,
        ["report", "--workspace", str(workspace)],
    )
    assert exit_code == 1
    assert report["error_code"] == "VERIFICATION_FAILED"
    assert (workspace / "reports" / "final_report.json").is_file()
    assert (workspace / "reports" / "final_report.md").is_file()
    assert report["data"]["report"]["verdict"]["status"] == "FAIL"


def test_lifecycle_commands_fail_closed_for_corrupt_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    state_path = workspace / ".digital_ic_agent" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{broken", encoding="utf-8")

    for command in ("status", "resume", "report"):
        exit_code, payload = _json_call(
            capsys,
            [command, "--workspace", str(workspace)],
        )
        assert exit_code == 1
        assert payload["error_code"] == "STATE_INVALID"
    assert state_path.read_text(encoding="utf-8") == "{broken"


def test_diagnose_identifies_windows_app_control_simulation_block(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    exit_code, _ = _json_call(
        capsys,
        ["workspace", "init", "--workspace", str(workspace)],
    )
    assert exit_code == 0
    verdict_module = importlib.import_module(
        "digital_ic_agent._runtime.verification_verdict"
    )
    verdict_module.write_verification_verdict(
        workspace,
        verdict_module.failed_verdict(
            "SIMULATION_ENGINE_LAUNCH_BLOCKED",
            "The simulation engine child process could not be launched",
            "xsim.log",
        ),
    )

    exit_code, payload = _json_call(
        capsys,
        ["diagnose", "--workspace", str(workspace)],
    )

    assert exit_code == 1
    recommendation = payload["data"]["diagnosis"]["recommendations"][0]["action"]
    assert "Windows Code Integrity" in recommendation
    assert "Smart App Control" in recommendation
    assert "RTL" in recommendation
