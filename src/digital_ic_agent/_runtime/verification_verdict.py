from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Sequence, TypedDict


VerdictStatus = Literal["PASS", "FAIL"]


class VerificationReasonPayload(TypedDict):
    code: str
    message: str
    source: str | None


class EvidencePayload(TypedDict):
    sha256: str
    size_bytes: int


class VerificationVerdictPayload(TypedDict):
    schema_version: int
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
    required_artifacts: Sequence[ArtifactRequirement] = ()


@dataclass(frozen=True)
class VerificationVerdict:
    status: VerdictStatus
    reasons: tuple[VerificationReason, ...]
    evidence: Mapping[str, EvidencePayload]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> VerificationVerdictPayload:
        return {
            "schema_version": 1,
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
    r"(?im)^\s*(?:#\s*)?ERROR:\s*\[(?:VRFC|XSIM|Synth|Common)\b"
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
