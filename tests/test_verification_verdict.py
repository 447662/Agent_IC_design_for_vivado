from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from digital_ic_agent._runtime.verification_verdict import (
    ArtifactRequirement,
    VerificationVerdict,
    VerificationRequest,
    aggregate_verification_verdicts,
    evaluate_verification,
    failed_verdict,
    write_verification_verdict,
)


PASS_MARKER = "DIGITAL_IC_SCOREBOARD_PASS"


def _request(tmp_path: Path, **overrides: object) -> VerificationRequest:
    wave = tmp_path / "sim" / "wave.wdb"
    wave.parent.mkdir(parents=True, exist_ok=True)
    wave.write_text("wave\n", encoding="utf-8")
    values: dict[str, object] = {
        "return_codes": {"vivado": 0, "xsim": 0},
        "evidence": {"xsim.log": f"{PASS_MARKER}\nUVM_ERROR : 0\nUVM_FATAL : 0\n"},
        "required_pass_markers": (PASS_MARKER,),
        "coverage_gates": {"functional": "PASS", "statement": "PASS"},
        "coverage_required": True,
        "required_artifacts": (ArtifactRequirement(path=wave),),
    }
    values.update(overrides)
    return VerificationRequest(**values)


def test_verification_verdict_accepts_only_complete_positive_evidence(tmp_path: Path):
    verdict = evaluate_verification(_request(tmp_path))

    assert verdict.status == "PASS"
    assert verdict.passed is True
    assert verdict.reasons == ()
    assert verdict.to_dict()["schema_version"] == 1
    json.dumps(verdict.to_dict())


def test_verification_verdict_rejects_missing_verification_policy():
    verdict = evaluate_verification(
        VerificationRequest(
            return_codes={},
            evidence={"xsim.log": "clean\n"},
            required_pass_markers=(),
            coverage_gates={},
            coverage_required=True,
            required_artifacts=(),
        )
    )

    assert verdict.status == "FAIL"
    assert {reason.code for reason in verdict.reasons} >= {
        "RETURN_CODE_POLICY_MISSING",
        "PASS_MARKER_POLICY_MISSING",
        "COVERAGE_POLICY_MISSING",
        "ARTIFACT_POLICY_MISSING",
    }


@pytest.mark.parametrize(
    ("case_id", "overrides", "reason_code"),
    [
        ("nonzero-vivado", {"return_codes": {"vivado": 1}}, "NONZERO_EXIT"),
        ("missing-pass", {"evidence": {"xsim.log": "clean\n"}}, "PASS_MARKER_MISSING"),
        (
            "async-dw8-aw3-false-pass",
            {
                "evidence": {
                    "xsim.log": (
                        "ASYNC_FIFO_SCOREBOARD_PASS writes=24 reads=24\n"
                        "Fatal: ASYNC_FIFO_SCOREBOARD_FAIL errors=4\n"
                    )
                },
                "required_pass_markers": ("ASYNC_FIFO_SCOREBOARD_PASS",),
            },
            "FAIL_MARKER_FOUND",
        ),
        (
            "round-robin-false-pass",
            {
                "evidence": {
                    "xsim.log": (
                        "ROUND_ROBIN_ARBITER_SCOREBOARD_PASS\n"
                        "Fatal: ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL errors=5\n"
                    )
                },
                "required_pass_markers": ("ROUND_ROBIN_ARBITER_SCOREBOARD_PASS",),
            },
            "FAIL_MARKER_FOUND",
        ),
        ("fatal", {"evidence": {"xsim.log": f"{PASS_MARKER}\nFatal: boom\n"}}, "FATAL_FOUND"),
        ("uvm-error", {"evidence": {"xsim.log": f"{PASS_MARKER}\nUVM_ERROR : 1\n"}}, "UVM_ERROR_FOUND"),
        ("uvm-fatal", {"evidence": {"xsim.log": f"{PASS_MARKER}\nUVM_FATAL : 2\n"}}, "UVM_FATAL_FOUND"),
        ("sva-fail", {"evidence": {"xsim.log": f"{PASS_MARKER}\nASYNC_FIFO_SVA_FAIL\n"}}, "ASSERTION_FAIL_FOUND"),
        ("assert-fail", {"evidence": {"xsim.log": f"{PASS_MARKER}\nASSERT_FAIL id=4\n"}}, "ASSERTION_FAIL_FOUND"),
        ("assertion-failed", {"evidence": {"xsim.log": f"{PASS_MARKER}\nAssertion failed at 20ns\n"}}, "ASSERTION_FAIL_FOUND"),
        ("test-failed", {"evidence": {"xsim.log": f"{PASS_MARKER}\nTEST_FAILED\n"}}, "FAIL_MARKER_FOUND"),
        ("vrfc-error", {"evidence": {"vivado.log": f"{PASS_MARKER}\nERROR: [VRFC 10-1] parse\n"}}, "TOOL_ERROR_FOUND"),
        ("xelab-error", {"evidence": {"vivado.log": f"{PASS_MARKER}\nERROR: [XSIM 43-1] elaborate\n"}}, "TOOL_ERROR_FOUND"),
        ("simtcl-error", {"evidence": {"xsim.log": f"{PASS_MARKER}\nERROR: [Simtcl 6-50] engine failed\n"}}, "TOOL_ERROR_FOUND"),
        ("coverage-fail", {"coverage_gates": {"functional": "FAIL"}}, "COVERAGE_GATE_FAILED"),
        ("coverage-missing", {"coverage_gates": {"functional": "MISSING"}}, "COVERAGE_GATE_MISSING"),
        ("coverage-skip", {"coverage_gates": {"functional": "SKIP"}}, "COVERAGE_GATE_SKIPPED"),
        ("artifact-not-current", {"required_artifacts": (ArtifactRequirement(path=Path("wave.wdb"), declared_status="STALE"),)}, "ARTIFACT_NOT_CURRENT"),
        ("artifact-missing", {"required_artifacts": (ArtifactRequirement(path=Path("missing.wdb")),)}, "ARTIFACT_MISSING"),
        ("artifact-empty", {"required_artifacts": (ArtifactRequirement(path=Path("empty.wdb")),)}, "ARTIFACT_EMPTY"),
        ("evidence-empty", {"evidence": {}}, "EVIDENCE_MISSING"),
    ],
)
def test_verification_verdict_fails_closed_for_twenty_failure_classes(
    tmp_path: Path,
    case_id: str,
    overrides: dict[str, object],
    reason_code: str,
):
    artifacts = overrides.get("required_artifacts")
    if artifacts:
        normalized = []
        for artifact in artifacts:
            assert isinstance(artifact, ArtifactRequirement)
            path = artifact.path if artifact.path.is_absolute() else tmp_path / artifact.path
            if case_id == "artifact-empty":
                path.write_bytes(b"")
            normalized.append(
                ArtifactRequirement(
                    path=path,
                    declared_status=artifact.declared_status,
                    started_at=artifact.started_at,
                )
            )
        overrides["required_artifacts"] = tuple(normalized)

    verdict = evaluate_verification(_request(tmp_path, **overrides))

    assert verdict.status == "FAIL", case_id
    assert verdict.passed is False
    assert reason_code in {reason.code for reason in verdict.reasons}, case_id


def test_verification_verdict_rejects_stale_artifact(tmp_path: Path):
    wave = tmp_path / "wave.wdb"
    wave.write_text("wave\n", encoding="utf-8")
    old = datetime.now(UTC) - timedelta(hours=1)
    os.utime(wave, (old.timestamp(), old.timestamp()))

    verdict = evaluate_verification(
        _request(
            tmp_path,
            required_artifacts=(
                ArtifactRequirement(
                    path=wave,
                    started_at=datetime.now(UTC) - timedelta(minutes=1),
                ),
            ),
        )
    )

    assert verdict.status == "FAIL"
    assert "ARTIFACT_STALE" in {reason.code for reason in verdict.reasons}


def test_verification_verdict_ignores_zero_uvm_counts_and_failure_words_in_marker_names(
    tmp_path: Path,
):
    verdict = evaluate_verification(
        _request(
            tmp_path,
            evidence={
                "xsim.log": (
                    f"{PASS_MARKER}\n"
                    "Testbench checks SCOREBOARD_FAIL paths but did not emit them.\n"
                    "UVM_ERROR : 0\nUVM_FATAL : 0\n"
                )
            },
        )
    )

    assert verdict.status == "PASS"


def test_aggregate_verdict_requires_every_child_to_pass(tmp_path: Path):
    pass_dir = tmp_path / "pass"
    fail_dir = tmp_path / "fail"
    pass_verdict = VerificationVerdict(status="PASS", reasons=(), evidence={})
    write_verification_verdict(pass_dir, pass_verdict)
    write_verification_verdict(
        fail_dir,
        failed_verdict("CHILD_SIM_FAILED", "child simulation failed"),
    )

    verdict = aggregate_verification_verdicts(
        (
            pass_dir / "reports" / "verification_verdict.json",
            fail_dir / "reports" / "verification_verdict.json",
        )
    )

    assert verdict.status == "FAIL"
    assert "CHILD_VERDICT_FAILED" in {reason.code for reason in verdict.reasons}
    assert len(verdict.evidence) == 2


def test_aggregate_verdict_fails_closed_for_missing_child(tmp_path: Path):
    verdict = aggregate_verification_verdicts(
        (tmp_path / "missing" / "verification_verdict.json",)
    )

    assert verdict.status == "FAIL"
    assert verdict.reasons[0].code == "CHILD_VERDICT_MISSING"


def test_aggregate_verdict_passes_when_all_children_pass(tmp_path: Path):
    paths = []
    for name in ("one", "two", "three"):
        project_dir = tmp_path / name
        write_verification_verdict(
            project_dir,
            VerificationVerdict(status="PASS", reasons=(), evidence={}),
        )
        paths.append(project_dir / "reports" / "verification_verdict.json")

    verdict = aggregate_verification_verdicts(tuple(paths))

    assert verdict.status == "PASS"
    assert verdict.reasons == ()
    assert len(verdict.evidence) == 3
