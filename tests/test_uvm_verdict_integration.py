from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

def _plugin() -> object:
    agent_module = importlib.import_module("digital_ic_agent._runtime.agent")
    return agent_module.DigitalICAgent().target_plugins["async-fifo"]


def _verdict(project_dir: Path) -> dict[str, object]:
    return json.loads(
        (project_dir / "reports" / "verification_verdict.json").read_text(
            encoding="utf-8"
        )
    )


def _reason_codes(payload: dict[str, object]) -> set[str]:
    reasons = payload["reasons"]
    assert isinstance(reasons, list)
    return {str(reason["code"]) for reason in reasons}


@pytest.mark.parametrize(
    ("failure_text", "reason_code"),
    [
        ("UVM_ERROR : 1\n", "UVM_ERROR_FOUND"),
        ("UVM_FATAL : 1\n", "UVM_FATAL_FOUND"),
        ("ASYNC_FIFO_SVA_FAIL p_no_write_when_full\n", "ASSERTION_FAIL_FOUND"),
    ],
)
def test_uvm_smoke_rejects_failure_after_pass_markers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_text: str,
    reason_code: str,
) -> None:
    plugin = _plugin()
    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: "vivado")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        sim_dir = tmp_path / "async-fifo" / "sim"
        (sim_dir / "async_fifo_uvm_smoke.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n"
            + failure_text,
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_smoke.wdb").write_text(
            "wave\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(["vivado"], 0, stdout="", stderr="")

    monkeypatch.setattr(plugin, "run_vivado_batch", fake_run)

    assert plugin.run_async_fifo_uvm_smoke(tmp_path, open_wave_gui=False) is False
    payload = _verdict(tmp_path / "async-fifo")
    assert payload["status"] == "FAIL"
    assert reason_code in _reason_codes(payload)


@pytest.mark.parametrize(
    ("artifact", "reason_code"),
    [
        ("missing-log", "ARTIFACT_MISSING"),
        ("missing-wdb", "ARTIFACT_MISSING"),
        ("stale-log", "ARTIFACT_STALE"),
    ],
)
def test_uvm_smoke_rejects_missing_or_stale_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    artifact: str,
    reason_code: str,
) -> None:
    plugin = _plugin()
    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: "vivado")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        sim_dir = tmp_path / "async-fifo" / "sim"
        if artifact != "missing-log":
            log_path = sim_dir / "async_fifo_uvm_smoke.log"
            log_path.write_text(
                "ASYNC_FIFO_UVM_SCOREBOARD_PASS\nASYNC_FIFO_UVM_TEST_DONE\n",
                encoding="utf-8",
            )
            if artifact == "stale-log":
                old = datetime.now(UTC) - timedelta(hours=1)
                os.utime(log_path, (old.timestamp(), old.timestamp()))
        if artifact != "missing-wdb":
            (sim_dir / "async_fifo_uvm_smoke.wdb").write_text(
                "wave\n", encoding="utf-8"
            )
        return subprocess.CompletedProcess(
            ["vivado"],
            0,
            stdout="ASYNC_FIFO_UVM_SCOREBOARD_PASS\nASYNC_FIFO_UVM_TEST_DONE\n",
            stderr="",
        )

    monkeypatch.setattr(plugin, "run_vivado_batch", fake_run)

    assert plugin.run_async_fifo_uvm_smoke(tmp_path, open_wave_gui=False) is False
    assert reason_code in _reason_codes(_verdict(tmp_path / "async-fifo"))


@pytest.mark.parametrize(
    ("coverage_threshold", "coverage_percent", "reason_code"),
    [
        (80.0, 75.0, "COVERAGE_GATE_FAILED"),
        (80.0, None, "COVERAGE_GATE_MISSING"),
        (None, None, "COVERAGE_GATE_SKIPPED"),
    ],
)
def test_uvm_coverage_rejects_nonpassing_gate_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    coverage_threshold: float | None,
    coverage_percent: float | None,
    reason_code: str,
) -> None:
    plugin = _plugin()
    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: "vivado")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        sim_dir = tmp_path / "async-fifo" / "sim"
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n"
            "ASYNC_FIFO_UVM_FCOV_PASS full=1 empty=1 reset=1 mixed=1\n"
            "ASYNC_FIFO_UVM_ASSERT_PASS\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text(
            "wave\n", encoding="utf-8"
        )
        ccinfo = (
            sim_dir
            / "coverage"
            / "xsim.codeCov"
            / "async_fifo_uvm_cov"
            / "xsim.CCInfo"
        )
        ccinfo.parent.mkdir(parents=True, exist_ok=True)
        ccinfo.write_text("xsim.codeCov\n", encoding="utf-8")
        return subprocess.CompletedProcess(["vivado"], 0, stdout="", stderr="")

    monkeypatch.setattr(plugin, "run_vivado_batch", fake_run)

    assert (
        plugin.run_async_fifo_uvm_coverage(
            tmp_path,
            coverage_threshold=coverage_threshold,
            coverage_percent=coverage_percent,
        )
        is False
    )
    assert reason_code in _reason_codes(_verdict(tmp_path / "async-fifo"))


@pytest.mark.parametrize(
    ("artifact", "reason_code"),
    [
        ("missing-log", "ARTIFACT_MISSING"),
        ("missing-wdb", "ARTIFACT_MISSING"),
        ("missing-ccinfo", "ARTIFACT_MISSING"),
        ("stale-ccinfo", "ARTIFACT_STALE"),
    ],
)
def test_uvm_coverage_rejects_missing_or_stale_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    artifact: str,
    reason_code: str,
) -> None:
    plugin = _plugin()
    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: "vivado")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        sim_dir = tmp_path / "async-fifo" / "sim"
        if artifact != "missing-log":
            (sim_dir / "async_fifo_uvm_coverage.log").write_text(
                "ASYNC_FIFO_UVM_SCOREBOARD_PASS\n"
                "ASYNC_FIFO_UVM_TEST_DONE\n"
                "ASYNC_FIFO_UVM_FCOV_PASS full=1 empty=1 reset=1 mixed=1\n"
                "ASYNC_FIFO_UVM_ASSERT_PASS\n",
                encoding="utf-8",
            )
        if artifact != "missing-wdb":
            (sim_dir / "async_fifo_uvm_coverage.wdb").write_text(
                "wave\n", encoding="utf-8"
            )
        if artifact != "missing-ccinfo":
            ccinfo = (
                sim_dir
                / "coverage"
                / "xsim.codeCov"
                / "async_fifo_uvm_cov"
                / "xsim.CCInfo"
            )
            ccinfo.parent.mkdir(parents=True, exist_ok=True)
            ccinfo.write_text("xsim.codeCov\n", encoding="utf-8")
            if artifact == "stale-ccinfo":
                old = datetime.now(UTC) - timedelta(hours=1)
                os.utime(ccinfo, (old.timestamp(), old.timestamp()))
        return subprocess.CompletedProcess(
            ["vivado"],
            0,
            stdout="ASYNC_FIFO_UVM_SCOREBOARD_PASS\nASYNC_FIFO_UVM_TEST_DONE\n",
            stderr="",
        )

    monkeypatch.setattr(plugin, "run_vivado_batch", fake_run)

    assert (
        plugin.run_async_fifo_uvm_coverage(
            tmp_path,
            coverage_threshold=0.0,
            coverage_percent=100.0,
        )
        is False
    )
    assert reason_code in _reason_codes(_verdict(tmp_path / "async-fifo"))
