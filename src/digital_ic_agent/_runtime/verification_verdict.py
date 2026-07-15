from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, Sequence, TypedDict
from uuid import uuid4


VerdictStatus = Literal["PASS", "FAIL"]
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


class ProcessResult(Protocol):
    returncode: int
    stdout: str | None
    stderr: str | None


class VerificationReasonPayload(TypedDict):
    code: str
    message: str
    source: str | None


class EvidencePayload(TypedDict):
    sha256: str
    size_bytes: int


class VerificationVerdictPayload(TypedDict):
    schema_version: int
    generated_at: str
    status: VerdictStatus
    passed: bool
    reasons: list[VerificationReasonPayload]
    evidence: dict[str, EvidencePayload]


@dataclass(frozen=True)
class VerificationReason:
    code: str
    message: str
    source: str | None = None

    def to_dict(self) -> VerificationReasonPayload:
        return {
            "code": self.code,
            "message": self.message,
            "source": self.source,
        }


@dataclass(frozen=True)
class ArtifactRequirement:
    path: Path
    declared_status: str = "CURRENT"
    started_at: datetime | None = None
    allow_empty: bool = False


@dataclass(frozen=True)
class VerificationRequest:
    return_codes: Mapping[str, int] = field(default_factory=dict)
    evidence: Mapping[str, str] = field(default_factory=dict)
    required_pass_markers: Sequence[str] = ()
    coverage_gates: Mapping[str, str] = field(default_factory=dict)
    coverage_required: bool | None = None
    required_artifacts: Sequence[ArtifactRequirement] = ()


@dataclass(frozen=True)
class VerificationVerdict:
    status: VerdictStatus
    reasons: tuple[VerificationReason, ...]
    evidence: Mapping[str, EvidencePayload]
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
    )

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> VerificationVerdictPayload:
        return {
            "schema_version": 1,
            "generated_at": self.generated_at,
            "status": self.status,
            "passed": self.passed,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "evidence": dict(self.evidence),
        }


_FAIL_MARKER_PATTERN = re.compile(
    r"(?im)^\s*(?:#\s*)?(?:fatal:\s*)?"
    r"(?:[A-Z][A-Z0-9_]*_)?(?:SCOREBOARD_(?:FAIL|ERROR)|TEST_FAILED)\b"
)
_FATAL_PATTERN = re.compile(r"(?im)^\s*(?:#\s*)?fatal\s*:")
_ASSERTION_FAIL_PATTERN = re.compile(
    r"(?im)^\s*(?:#\s*)?(?:[A-Z][A-Z0-9_]*_)?"
    r"(?:SVA_FAIL|ASSERT(?:ION)?_FAIL)\b|^\s*Assertion failed\b"
)
_TOOL_ERROR_PATTERN = re.compile(
    r"(?im)^\s*(?:#\s*)?ERROR:\s*\[(?:VRFC|XSIM|Simtcl|Synth|Common)\b"
)
_SIMULATION_ENGINE_LAUNCH_BLOCKED_PATTERN = re.compile(
    r"(?is)ERROR:\s*\[Simtcl\s+6-50\].*?"
    r"Simulation engine failed to start:.*?"
    r"Failed to launch child process\s*\(child exe not found\)"
)
_UVM_COUNT_PATTERN = re.compile(
    r"(?im)^\s*(?:#\s*)?UVM_(ERROR|FATAL)\s*:\s*(\d+)\b"
)


def _add_reason(
    reasons: list[VerificationReason],
    code: str,
    message: str,
    source: str | None = None,
) -> None:
    candidate = VerificationReason(code=code, message=message, source=source)
    if candidate not in reasons:
        reasons.append(candidate)


def _evaluate_return_codes(
    request: VerificationRequest,
    reasons: list[VerificationReason],
) -> None:
    if not request.return_codes:
        _add_reason(
            reasons,
            "RETURN_CODE_POLICY_MISSING",
            "At least one tool return code is required",
        )
    for tool, return_code in sorted(request.return_codes.items()):
        if return_code != 0:
            _add_reason(
                reasons,
                "NONZERO_EXIT",
                f"{tool} exited with status {return_code}",
                tool,
            )


def _evaluate_evidence(
    request: VerificationRequest,
    reasons: list[VerificationReason],
) -> dict[str, EvidencePayload]:
    summaries: dict[str, EvidencePayload] = {}
    nonempty_evidence = {
        str(source): str(content)
        for source, content in request.evidence.items()
        if str(content).strip()
    }
    if not nonempty_evidence:
        _add_reason(reasons, "EVIDENCE_MISSING", "No non-empty verification evidence was provided")
        return summaries

    combined = "\n".join(nonempty_evidence.values())
    if not request.required_pass_markers:
        _add_reason(
            reasons,
            "PASS_MARKER_POLICY_MISSING",
            "At least one required pass marker must be declared",
        )
    for marker in request.required_pass_markers:
        if marker not in combined:
            _add_reason(
                reasons,
                "PASS_MARKER_MISSING",
                f"Required pass marker was not found: {marker}",
            )

    for source, content in sorted(nonempty_evidence.items()):
        encoded = content.encode("utf-8", errors="replace")
        summaries[source] = {
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "size_bytes": len(encoded),
        }
        if _FAIL_MARKER_PATTERN.search(content):
            _add_reason(reasons, "FAIL_MARKER_FOUND", "A failure marker was found", source)
        if _FATAL_PATTERN.search(content):
            _add_reason(reasons, "FATAL_FOUND", "A fatal simulator event was found", source)
        if _ASSERTION_FAIL_PATTERN.search(content):
            _add_reason(
                reasons,
                "ASSERTION_FAIL_FOUND",
                "An assertion or SVA failure marker was found",
                source,
            )
        if _TOOL_ERROR_PATTERN.search(content):
            _add_reason(reasons, "TOOL_ERROR_FOUND", "A Vivado tool error was found", source)
        if _SIMULATION_ENGINE_LAUNCH_BLOCKED_PATTERN.search(content):
            _add_reason(
                reasons,
                "SIMULATION_ENGINE_LAUNCH_BLOCKED",
                "The xsim simulation engine could not launch its generated child executable",
                source,
            )
        for match in _UVM_COUNT_PATTERN.finditer(content):
            category = match.group(1)
            count = int(match.group(2))
            if count > 0:
                _add_reason(
                    reasons,
                    f"UVM_{category}_FOUND",
                    f"UVM reported {count} {category.lower()} event(s)",
                    source,
                )
    return summaries


def _evaluate_coverage(
    request: VerificationRequest,
    reasons: list[VerificationReason],
) -> None:
    if request.coverage_required is None:
        _add_reason(
            reasons,
            "COVERAGE_POLICY_UNDECLARED",
            "The caller must explicitly declare whether coverage is required",
        )
    elif request.coverage_required and not request.coverage_gates:
        _add_reason(
            reasons,
            "COVERAGE_POLICY_MISSING",
            "Coverage is required but no coverage gates were provided",
        )
    for metric, raw_status in sorted(request.coverage_gates.items()):
        status = str(raw_status).strip().upper()
        if status == "PASS":
            continue
        if status == "FAIL":
            code = "COVERAGE_GATE_FAILED"
        elif status == "MISSING":
            code = "COVERAGE_GATE_MISSING"
        elif status in {"SKIP", "N/A"}:
            code = "COVERAGE_GATE_SKIPPED"
        else:
            code = "COVERAGE_GATE_INVALID"
        _add_reason(
            reasons,
            code,
            f"Coverage gate {metric} reported {status or 'EMPTY'}",
            metric,
        )


def _normalize_started_at(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _evaluate_artifacts(
    request: VerificationRequest,
    reasons: list[VerificationReason],
) -> None:
    if not request.required_artifacts:
        _add_reason(
            reasons,
            "ARTIFACT_POLICY_MISSING",
            "At least one required artifact must be declared",
        )
    for requirement in request.required_artifacts:
        path = Path(requirement.path)
        source = str(path)
        if requirement.declared_status != "CURRENT":
            _add_reason(
                reasons,
                "ARTIFACT_NOT_CURRENT",
                f"Required artifact status is {requirement.declared_status}",
                source,
            )
            continue
        if not path.is_file():
            _add_reason(reasons, "ARTIFACT_MISSING", "Required artifact is missing", source)
            continue
        stat = path.stat()
        if stat.st_size == 0 and not requirement.allow_empty:
            _add_reason(reasons, "ARTIFACT_EMPTY", "Required artifact is empty", source)
        if requirement.started_at is not None:
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            if modified_at < _normalize_started_at(requirement.started_at):
                _add_reason(
                    reasons,
                    "ARTIFACT_STALE",
                    "Required artifact predates the verification run",
                    source,
                )


def evaluate_verification(request: VerificationRequest) -> VerificationVerdict:
    reasons: list[VerificationReason] = []
    _evaluate_return_codes(request, reasons)
    evidence = _evaluate_evidence(request, reasons)
    _evaluate_coverage(request, reasons)
    _evaluate_artifacts(request, reasons)
    status: VerdictStatus = "FAIL" if reasons else "PASS"
    return VerificationVerdict(
        status=status,
        reasons=tuple(reasons),
        evidence=MappingProxyType(evidence),
    )


def failed_verdict(
    code: str,
    message: str,
    source: str | None = None,
) -> VerificationVerdict:
    return VerificationVerdict(
        status="FAIL",
        reasons=(VerificationReason(code=code, message=message, source=source),),
        evidence=MappingProxyType({}),
    )


def verification_verdict_from_payload(
    payload: object,
) -> VerificationVerdict:
    if not isinstance(payload, dict):
        raise ValueError("verification verdict must be an object")
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported verification verdict schema")
    status = payload.get("status")
    if status not in {"PASS", "FAIL"}:
        raise ValueError("invalid verification verdict status")
    passed = payload.get("passed")
    if not isinstance(passed, bool) or passed != (status == "PASS"):
        raise ValueError("verification verdict passed/status mismatch")
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("verification verdict generated_at is required")
    try:
        parsed_generated_at = datetime.fromisoformat(
            generated_at.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError("invalid verification verdict generated_at") from exc
    if parsed_generated_at.tzinfo is None:
        raise ValueError("verification verdict generated_at must include timezone")

    raw_reasons = payload.get("reasons")
    if not isinstance(raw_reasons, list):
        raise ValueError("verification verdict reasons must be a list")
    reasons: list[VerificationReason] = []
    for raw_reason in raw_reasons:
        if not isinstance(raw_reason, dict):
            raise ValueError("verification verdict reason must be an object")
        code = raw_reason.get("code")
        message = raw_reason.get("message")
        source = raw_reason.get("source")
        if not isinstance(code, str) or not code:
            raise ValueError("verification verdict reason code is required")
        if not isinstance(message, str) or not message:
            raise ValueError("verification verdict reason message is required")
        if source is not None and not isinstance(source, str):
            raise ValueError("verification verdict reason source must be a string")
        reasons.append(
            VerificationReason(code=code, message=message, source=source)
        )
    if status == "PASS" and reasons:
        raise ValueError("passing verification verdict cannot contain reasons")
    if status == "FAIL" and not reasons:
        raise ValueError("failing verification verdict requires a reason")

    raw_evidence = payload.get("evidence")
    if not isinstance(raw_evidence, dict):
        raise ValueError("verification verdict evidence must be an object")
    evidence: dict[str, EvidencePayload] = {}
    for source, raw_summary in raw_evidence.items():
        if not isinstance(source, str) or not isinstance(raw_summary, dict):
            raise ValueError("invalid verification verdict evidence entry")
        sha256 = raw_summary.get("sha256")
        size_bytes = raw_summary.get("size_bytes")
        if (
            not isinstance(sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 0
        ):
            raise ValueError("invalid verification verdict evidence summary")
        evidence[source] = {"sha256": sha256, "size_bytes": size_bytes}
    return VerificationVerdict(
        status=status,
        reasons=tuple(reasons),
        evidence=MappingProxyType(evidence),
        generated_at=generated_at,
    )


def load_verification_verdict(path: Path) -> VerificationVerdict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid verification verdict file: {path}") from exc
    return verification_verdict_from_payload(payload)


def _read_evidence_file(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return f"ERROR: [Common EVIDENCE_READ_ERROR] {type(exc).__name__}"
    if size > MAX_EVIDENCE_BYTES:
        return f"ERROR: [Common EVIDENCE_TOO_LARGE] {size} bytes"
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"ERROR: [Common EVIDENCE_READ_ERROR] {type(exc).__name__}"


def aggregate_verification_verdicts(
    verdict_paths: Sequence[Path],
) -> VerificationVerdict:
    reasons: list[VerificationReason] = []
    evidence: dict[str, EvidencePayload] = {}
    if not verdict_paths:
        _add_reason(
            reasons,
            "CHILD_VERDICT_POLICY_MISSING",
            "At least one child verification verdict is required",
        )
    for raw_path in verdict_paths:
        path = Path(raw_path)
        source = str(path)
        if not path.is_file():
            _add_reason(
                reasons,
                "CHILD_VERDICT_MISSING",
                "Child verification verdict is missing",
                source,
            )
            continue
        content = _read_evidence_file(path)
        encoded = content.encode("utf-8", errors="replace")
        evidence[source] = {
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "size_bytes": len(encoded),
        }
        try:
            child = load_verification_verdict(path)
        except ValueError as exc:
            _add_reason(
                reasons,
                "CHILD_VERDICT_INVALID",
                str(exc),
                source,
            )
            continue
        if not child.passed:
            _add_reason(
                reasons,
                "CHILD_VERDICT_FAILED",
                "Child verification verdict reported FAIL",
                source,
            )
    return VerificationVerdict(
        status="FAIL" if reasons else "PASS",
        reasons=tuple(reasons),
        evidence=MappingProxyType(evidence),
    )


def evaluate_process_results(
    *,
    process_results: Mapping[str, ProcessResult],
    evidence_paths: Mapping[str, Path],
    required_pass_markers: Sequence[str],
    required_artifact_paths: Sequence[Path],
    started_at: datetime,
    coverage_required: bool,
    coverage_gates: Mapping[str, str] | None = None,
) -> VerificationVerdict:
    evidence: dict[str, str] = {}
    for name, result in process_results.items():
        if result.stdout:
            evidence[f"{name}.stdout"] = result.stdout
        if result.stderr:
            evidence[f"{name}.stderr"] = result.stderr
    for name, path in evidence_paths.items():
        evidence[name] = _read_evidence_file(path)

    return evaluate_verification(
        VerificationRequest(
            return_codes={
                name: result.returncode
                for name, result in process_results.items()
            },
            evidence=evidence,
            required_pass_markers=tuple(required_pass_markers),
            coverage_gates=dict(coverage_gates or {}),
            coverage_required=coverage_required,
            required_artifacts=tuple(
                ArtifactRequirement(path=path, started_at=started_at)
                for path in required_artifact_paths
            ),
        )
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_verification_verdict(
    project_dir: Path,
    verdict: VerificationVerdict,
) -> tuple[Path, Path]:
    reports_dir = Path(project_dir) / "reports"
    json_path = reports_dir / "verification_verdict.json"
    markdown_path = reports_dir / "verification_verdict.md"
    payload = verdict.to_dict()
    _atomic_write_text(
        json_path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    lines = [
        "# Verification Verdict",
        "",
        f"- Schema version: `{payload['schema_version']}`",
        f"- Status: **{verdict.status}**",
        f"- Evidence sources: `{len(verdict.evidence)}`",
        "",
        "## Reasons",
        "",
    ]
    if verdict.reasons:
        for reason in verdict.reasons:
            source = f" (`{reason.source}`)" if reason.source else ""
            lines.append(f"- `{reason.code}`{source}: {reason.message}")
    else:
        lines.append("- All required verification conditions passed.")
    _atomic_write_text(markdown_path, "\n".join(lines) + "\n")
    return json_path, markdown_path


def format_verification_failure(verdict: VerificationVerdict) -> str:
    return "; ".join(
        f"{reason.code}: {reason.message}"
        for reason in verdict.reasons
    ) or "verification failed without a reason"
