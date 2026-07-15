from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


EVAL_REPORT_SCHEMA_VERSION = "digital-ic-agent.eval-report.v1"
EVAL_SUMMARY_SCHEMA_VERSION = "digital-ic-agent.eval-summary.v1"
EXPECTED_CASES = 10


def _integer_count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _issue(
    issues: list[dict[str, str]],
    code: str,
    path: str,
    message: str,
) -> None:
    candidate = {"code": code, "path": path, "message": message}
    if candidate not in issues:
        issues.append(candidate)


def _cases(
    report: Mapping[str, object],
    name: str,
    issues: list[dict[str, str]],
) -> list[Mapping[str, object]]:
    raw_cases = report.get("cases")
    if not isinstance(raw_cases, Sequence) or isinstance(raw_cases, str | bytes):
        _issue(issues, "EVAL_CASES_INVALID", f"{name}.cases", "Cases must be an array")
        return []
    cases: list[Mapping[str, object]] = []
    for index, case in enumerate(raw_cases):
        if not isinstance(case, Mapping):
            _issue(
                issues,
                "EVAL_CASE_INVALID",
                f"{name}.cases.{index}",
                "Case must be an object",
            )
            continue
        cases.append(case)
    return cases


def _validate_report(
    report: Mapping[str, object],
    *,
    name: str,
    suite: str,
    evidence_kind: str,
    issues: list[dict[str, str]],
) -> list[Mapping[str, object]]:
    if report.get("schema_version") != EVAL_REPORT_SCHEMA_VERSION:
        _issue(
            issues,
            "EVAL_REPORT_SCHEMA_INVALID",
            f"{name}.schema_version",
            f"Expected {EVAL_REPORT_SCHEMA_VERSION}",
        )
    if report.get("suite") != suite:
        _issue(issues, "EVAL_SUITE_INVALID", f"{name}.suite", f"Expected {suite}")
    if report.get("evidence_kind") != evidence_kind:
        _issue(
            issues,
            "EVAL_EVIDENCE_KIND_INVALID",
            f"{name}.evidence_kind",
            f"Expected {evidence_kind}",
        )
    if report.get("status") != "PASS":
        _issue(issues, "EVAL_REPORT_FAILED", f"{name}.status", "Report must pass")
    if report.get("executed") != EXPECTED_CASES:
        _issue(
            issues,
            "EVAL_CASE_COUNT_INVALID",
            f"{name}.executed",
            f"Expected {EXPECTED_CASES} executed cases",
        )
    cases = _cases(report, name, issues)
    if len(cases) != EXPECTED_CASES:
        _issue(
            issues,
            "EVAL_CASE_COUNT_INVALID",
            f"{name}.cases",
            f"Expected {EXPECTED_CASES} case records",
        )
    ids = [case.get("id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        _issue(issues, "EVAL_CASE_ID_INVALID", f"{name}.cases", "Case IDs are required")
    elif len(set(ids)) != len(ids):
        _issue(issues, "EVAL_CASE_ID_DUPLICATE", f"{name}.cases", "Case IDs must be unique")
    for index, case in enumerate(cases):
        if case.get("status") != "PASS":
            _issue(
                issues,
                "EVAL_CASE_FAILED",
                f"{name}.cases.{index}.status",
                "Every case must pass",
            )
    return cases


def _validate_coverage(
    cases: Sequence[Mapping[str, object]],
    name: str,
    issues: list[dict[str, str]],
) -> None:
    for index, case in enumerate(cases):
        coverage = case.get("coverage")
        gates = coverage.get("gates") if isinstance(coverage, Mapping) else None
        if not isinstance(gates, Mapping) or not gates:
            _issue(
                issues,
                "EVAL_COVERAGE_MISSING",
                f"{name}.cases.{index}.coverage.gates",
                "Coverage gates are required",
            )
            continue
        for metric, status in gates.items():
            if status != "PASS":
                _issue(
                    issues,
                    "EVAL_COVERAGE_NOT_PASS",
                    f"{name}.cases.{index}.coverage.gates.{metric}",
                    f"Coverage gate must PASS, observed {status}",
                )


def _sanitized_cases(
    cases: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for case in cases:
        record = {field: case[field] for field in fields if field in case}
        coverage = case.get("coverage")
        if isinstance(coverage, Mapping):
            record["coverage"] = {
                field: dict(value)
                for field in ("gates", "scores")
                if isinstance((value := coverage.get(field)), Mapping)
            }
        sanitized.append(record)
    return sanitized


def aggregate_eval_reports(
    *,
    generation: Mapping[str, object],
    repair_prepare: Mapping[str, object],
    repair: Mapping[str, object],
    negative: Mapping[str, object],
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    generation_cases = _validate_report(
        generation,
        name="generation",
        suite="generation",
        evidence_kind="real-vivado",
        issues=issues,
    )
    prepare_cases = _validate_report(
        repair_prepare,
        name="repair_prepare",
        suite="repair-prepare",
        evidence_kind="real-vivado-repair",
        issues=issues,
    )
    repair_cases = _validate_report(
        repair,
        name="repair",
        suite="repair-verify",
        evidence_kind="real-vivado-repair",
        issues=issues,
    )
    negative_cases = _validate_report(
        negative,
        name="negative",
        suite="negative",
        evidence_kind="contract-negative",
        issues=issues,
    )

    _validate_coverage(generation_cases, "generation", issues)
    _validate_coverage(repair_cases, "repair", issues)

    if repair_prepare.get("detected") != EXPECTED_CASES:
        _issue(
            issues,
            "EVAL_DEFECT_DETECTION_INCOMPLETE",
            "repair_prepare.detected",
            "All ten injected defects must be detected",
        )
    repaired = repair.get("repaired")
    if not isinstance(repaired, int) or isinstance(repaired, bool) or repaired < 7:
        _issue(
            issues,
            "EVAL_REPAIR_THRESHOLD_MISSED",
            "repair.repaired",
            "At least seven defects must be repaired",
        )
    prepare_ids = {case.get("id") for case in prepare_cases}
    repair_ids = {case.get("id") for case in repair_cases}
    if prepare_ids != repair_ids:
        _issue(
            issues,
            "EVAL_REPAIR_CASE_MISMATCH",
            "repair.cases",
            "Repair prepare and verify case IDs must match",
        )
    for index, case in enumerate(repair_cases):
        iterations = case.get("repair_iterations")
        maximum = case.get("max_repair_iterations")
        if (
            not isinstance(iterations, int)
            or isinstance(iterations, bool)
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or not 1 <= iterations <= maximum <= 3
        ):
            _issue(
                issues,
                "EVAL_REPAIR_ITERATION_LIMIT",
                f"repair.cases.{index}.repair_iterations",
                "Repair must complete in one to three iterations",
            )

    if negative.get("vivado_invoked") is not False or any(
        case.get("vivado_invoked") is not False for case in negative_cases
    ):
        _issue(
            issues,
            "EVAL_NEGATIVE_VIVADO_INVOKED",
            "negative.vivado_invoked",
            "Negative cases must stop before Vivado invocation",
        )

    generation_count = generation.get("executed")
    repair_count = repair.get("executed")
    negative_count = negative.get("executed")
    numeric_counts = (
        _integer_count(generation_count),
        _integer_count(repair_count),
        _integer_count(negative_count),
    )
    totals = {
        "generation": numeric_counts[0],
        "repair": numeric_counts[1],
        "negative": numeric_counts[2],
        "overall": sum(numeric_counts),
        "defects_detected": _integer_count(repair_prepare.get("detected")),
        "repaired": _integer_count(repaired),
    }
    return {
        "schema_version": EVAL_SUMMARY_SCHEMA_VERSION,
        "status": "PASS" if not issues else "FAIL",
        "totals": totals,
        "issues": issues,
        "cases": {
            "generation": _sanitized_cases(
                generation_cases,
                ("id", "design_template", "status", "iteration", "evidence_kind"),
            ),
            "repair_prepare": _sanitized_cases(
                prepare_cases,
                (
                    "id",
                    "design_template",
                    "status",
                    "expected_reason_codes",
                    "observed_reason_codes",
                    "diagnosis_reason_codes",
                ),
            ),
            "repair": _sanitized_cases(
                repair_cases,
                (
                    "id",
                    "design_template",
                    "status",
                    "repair_iterations",
                    "max_repair_iterations",
                    "injected_sha256",
                    "repaired_sha256",
                ),
            ),
            "negative": _sanitized_cases(
                negative_cases,
                (
                    "id",
                    "status",
                    "expected_status",
                    "observed_status",
                    "expected_code",
                    "observed_codes",
                    "vivado_invoked",
                ),
            ),
        },
    }
