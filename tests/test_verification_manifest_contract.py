from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _agent() -> object:
    module = importlib.import_module("digital_ic_agent._runtime.agent")
    return module.DigitalICAgent()


def _payload(status: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "passed": status == "PASS",
        "reasons": (
            []
            if status == "PASS"
            else [
                {
                    "code": "TEST_FAILURE",
                    "message": "test verdict failure",
                    "source": "test",
                }
            ]
        ),
        "evidence": {
            "xsim.log": {
                "sha256": "0" * 64,
                "size_bytes": 1,
            }
        },
    }


def _write_payload(project_dir: Path, payload: dict[str, object]) -> None:
    path = project_dir / "reports" / "verification_verdict.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _prepare_flow(monkeypatch: pytest.MonkeyPatch, agent: object, flow: object) -> None:
    monkeypatch.setattr(
        agent,
        "run_preflight",
        lambda _flow: SimpleNamespace(ok=True, missing_required=()),
    )
    agent.target_handlers["sync-fifo"].flows["sim-rtl"] = flow


def test_verification_flow_embeds_current_verdict_in_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = _agent()

    def flow(**kwargs: object) -> bool:
        _write_payload(tmp_path / "sync-fifo", _payload("PASS"))
        return True

    _prepare_flow(monkeypatch, agent, flow)

    assert agent.run_target_flow("sync-fifo", "sim-rtl", output_dir=tmp_path) is True
    manifest = json.loads(
        (tmp_path / "sync-fifo" / "artifacts.json").read_text(encoding="utf-8")
    )
    run = manifest["runs"][-1]
    assert run["status"] == "PASS"
    assert run["verification_verdict"]["status"] == "PASS"
    assert run["verification_verdict"]["passed"] is True


@pytest.mark.parametrize(
    ("scenario", "reason_code"),
    [
        ("missing", "CANONICAL_VERDICT_MISSING"),
        ("stale", "CANONICAL_VERDICT_STALE"),
        ("invalid", "CANONICAL_VERDICT_INVALID"),
    ],
)
def test_verification_flow_fails_closed_without_current_valid_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario: str,
    reason_code: str,
) -> None:
    agent = _agent()
    project_dir = tmp_path / "sync-fifo"
    if scenario == "stale":
        _write_payload(project_dir, _payload("PASS"))
    elif scenario == "invalid":
        _write_payload(project_dir, {"status": "PASS"})

    _prepare_flow(monkeypatch, agent, lambda **kwargs: True)

    assert agent.run_target_flow("sync-fifo", "sim-rtl", output_dir=tmp_path) is False
    verdict = json.loads(
        (project_dir / "reports" / "verification_verdict.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads((project_dir / "artifacts.json").read_text(encoding="utf-8"))
    run = manifest["runs"][-1]
    assert verdict["status"] == "FAIL"
    assert verdict["reasons"][0]["code"] == reason_code
    assert run["status"] == "FAIL"
    assert run["verification_verdict"] == verdict


def test_verification_flow_rejects_handler_and_verdict_disagreement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = _agent()

    def flow(**kwargs: object) -> bool:
        _write_payload(tmp_path / "sync-fifo", _payload("PASS"))
        return False

    _prepare_flow(monkeypatch, agent, flow)

    assert agent.run_target_flow("sync-fifo", "sim-rtl", output_dir=tmp_path) is False
    verdict = json.loads(
        (
            tmp_path
            / "sync-fifo"
            / "reports"
            / "verification_verdict.json"
        ).read_text(encoding="utf-8")
    )
    assert verdict["reasons"][0]["code"] == "VERDICT_RESULT_MISMATCH"


def test_manifest_rejects_status_that_disagrees_with_embedded_verdict(
    tmp_path: Path,
) -> None:
    agent = _agent()

    with pytest.raises(ValueError, match="verification verdict status mismatch"):
        agent.record_artifact_run(
            "sync-fifo",
            "sim-rtl",
            output_dir=tmp_path,
            status="PASS",
            verification_verdict=_payload("FAIL"),
        )


def test_verification_preflight_failure_writes_canonical_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = _agent()
    monkeypatch.setattr(
        agent,
        "run_preflight",
        lambda _flow: SimpleNamespace(
            ok=False,
            missing_required=("vivado",),
        ),
    )

    assert agent.run_target_flow("sync-fifo", "sim-rtl", output_dir=tmp_path) is False
    project_dir = tmp_path / "sync-fifo"
    verdict = json.loads(
        (project_dir / "reports" / "verification_verdict.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads((project_dir / "artifacts.json").read_text(encoding="utf-8"))
    assert verdict["reasons"][0]["code"] == "PREFLIGHT_FAILED"
    assert manifest["runs"][-1]["verification_verdict"] == verdict


def test_verification_handler_exception_writes_canonical_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = _agent()

    def flow(**kwargs: object) -> bool:
        raise RuntimeError("simulator crashed")

    _prepare_flow(monkeypatch, agent, flow)

    with pytest.raises(RuntimeError, match="simulator crashed"):
        agent.run_target_flow("sync-fifo", "sim-rtl", output_dir=tmp_path)
    project_dir = tmp_path / "sync-fifo"
    verdict = json.loads(
        (project_dir / "reports" / "verification_verdict.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads((project_dir / "artifacts.json").read_text(encoding="utf-8"))
    assert verdict["reasons"][0]["code"] == "TARGET_FLOW_EXCEPTION"
    assert manifest["runs"][-1]["verification_verdict"] == verdict
