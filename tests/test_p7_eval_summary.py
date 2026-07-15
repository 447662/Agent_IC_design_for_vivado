from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.eval_summary import aggregate_eval_reports  # noqa: E402


def _generation() -> dict[str, Any]:
    return {
        "schema_version": "digital-ic-agent.eval-report.v1",
        "suite": "generation",
        "evidence_kind": "real-vivado",
        "status": "PASS",
        "executed": 10,
        "passed": 10,
        "failed": 0,
        "cases": [
            {
                "id": f"gen-{index}",
                "status": "PASS",
                "coverage": {"gates": {"statement": "PASS", "branch": "PASS"}},
            }
            for index in range(10)
        ],
    }


def _repair_prepare() -> dict[str, Any]:
    return {
        "schema_version": "digital-ic-agent.eval-report.v1",
        "suite": "repair-prepare",
        "evidence_kind": "real-vivado-repair",
        "status": "PASS",
        "executed": 10,
        "detected": 10,
        "failed_detection": 0,
        "cases": [{"id": f"repair-{index}", "status": "PASS"} for index in range(10)],
    }


def _repair() -> dict[str, Any]:
    return {
        "schema_version": "digital-ic-agent.eval-report.v1",
        "suite": "repair-verify",
        "evidence_kind": "real-vivado-repair",
        "status": "PASS",
        "executed": 10,
        "repaired": 10,
        "failed_repair": 0,
        "required_repaired": 7,
        "cases": [
            {
                "id": f"repair-{index}",
                "status": "PASS",
                "repair_iterations": 1,
                "max_repair_iterations": 3,
                "coverage": {"gates": {"statement": "PASS", "branch": "PASS"}},
            }
            for index in range(10)
        ],
    }


def _negative() -> dict[str, Any]:
    return {
        "schema_version": "digital-ic-agent.eval-report.v1",
        "suite": "negative",
        "evidence_kind": "contract-negative",
        "status": "PASS",
        "executed": 10,
        "passed": 10,
        "failed": 0,
        "vivado_invoked": False,
        "cases": [
            {"id": f"negative-{index}", "status": "PASS", "vivado_invoked": False}
            for index in range(10)
        ],
    }


def test_p7_eval_summary_accepts_only_complete_thirty_case_evidence() -> None:
    summary = aggregate_eval_reports(
        generation=_generation(),
        repair_prepare=_repair_prepare(),
        repair=_repair(),
        negative=_negative(),
    )

    assert summary["schema_version"] == "digital-ic-agent.eval-summary.v1"
    assert summary["status"] == "PASS"
    assert summary["issues"] == []
    assert summary["totals"] == {
        "generation": 10,
        "repair": 10,
        "negative": 10,
        "overall": 30,
        "defects_detected": 10,
        "repaired": 10,
    }
    assert set(summary["cases"]) == {
        "generation",
        "repair_prepare",
        "repair",
        "negative",
    }
    assert [case["id"] for case in summary["cases"]["generation"]] == [
        f"gen-{index}" for index in range(10)
    ]
    assert all(
        "workspace" not in case
        for suite_cases in summary["cases"].values()
        for case in suite_cases
    )


def test_p7_eval_summary_fails_closed_for_case_coverage_and_iteration_gaps() -> None:
    generation = _generation()
    repair = _repair()
    negative = _negative()
    generation["cases"][0]["status"] = "FAIL"
    generation["cases"][1]["coverage"]["gates"]["branch"] = "SKIP"
    repair["cases"][0]["repair_iterations"] = 4
    negative["cases"][0]["vivado_invoked"] = True

    summary = aggregate_eval_reports(
        generation=generation,
        repair_prepare=_repair_prepare(),
        repair=repair,
        negative=negative,
    )

    assert summary["status"] == "FAIL"
    codes = {issue["code"] for issue in summary["issues"]}
    assert {
        "EVAL_CASE_FAILED",
        "EVAL_COVERAGE_NOT_PASS",
        "EVAL_REPAIR_ITERATION_LIMIT",
        "EVAL_NEGATIVE_VIVADO_INVOKED",
    } <= codes


def test_p7_eval_summary_reports_malformed_and_inconsistent_evidence() -> None:
    generation = _generation()
    generation.update(
        {
            "schema_version": "invalid",
            "suite": "wrong-suite",
            "evidence_kind": "synthetic",
            "status": "FAIL",
            "executed": 9,
        }
    )
    generation["cases"][0] = None
    generation["cases"][1]["id"] = ""
    generation["cases"][2].pop("coverage")
    generation["cases"][3]["coverage"] = {"gates": {}}

    repair_prepare = _repair_prepare()
    repair_prepare["detected"] = 9
    repair_prepare["cases"][1]["id"] = repair_prepare["cases"][0]["id"]

    repair = _repair()
    repair["repaired"] = True
    repair["cases"][0]["id"] = "different-repair-case"
    repair["cases"][0]["repair_iterations"] = True
    repair["cases"][0]["max_repair_iterations"] = True
    repair["cases"][1]["coverage"]["gates"]["statement"] = "MISSING"

    negative = _negative()
    negative["vivado_invoked"] = True

    summary = aggregate_eval_reports(
        generation=generation,
        repair_prepare=repair_prepare,
        repair=repair,
        negative=negative,
    )

    assert summary["status"] == "FAIL"
    codes = {issue["code"] for issue in summary["issues"]}
    assert {
        "EVAL_REPORT_SCHEMA_INVALID",
        "EVAL_SUITE_INVALID",
        "EVAL_EVIDENCE_KIND_INVALID",
        "EVAL_REPORT_FAILED",
        "EVAL_CASE_COUNT_INVALID",
        "EVAL_CASE_INVALID",
        "EVAL_CASE_ID_INVALID",
        "EVAL_CASE_ID_DUPLICATE",
        "EVAL_COVERAGE_MISSING",
        "EVAL_COVERAGE_NOT_PASS",
        "EVAL_DEFECT_DETECTION_INCOMPLETE",
        "EVAL_REPAIR_THRESHOLD_MISSED",
        "EVAL_REPAIR_CASE_MISMATCH",
        "EVAL_REPAIR_ITERATION_LIMIT",
        "EVAL_NEGATIVE_VIVADO_INVOKED",
    } <= codes


def test_p7_eval_summary_rejects_non_array_cases_and_non_numeric_totals() -> None:
    generation = _generation()
    generation["cases"] = "not-an-array"
    generation["executed"] = "ten"
    repair_prepare = _repair_prepare()
    repair_prepare["detected"] = "ten"
    repair = _repair()
    repair["executed"] = None
    repair["repaired"] = None
    negative = _negative()
    negative["executed"] = False

    summary = aggregate_eval_reports(
        generation=generation,
        repair_prepare=repair_prepare,
        repair=repair,
        negative=negative,
    )

    assert summary["status"] == "FAIL"
    assert summary["totals"] == {
        "generation": 0,
        "repair": 0,
        "negative": 0,
        "overall": 0,
        "defects_detected": 0,
        "repaired": 0,
    }
    assert all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in summary["totals"].values()
    )
    assert "EVAL_CASES_INVALID" in {
        issue["code"] for issue in summary["issues"]
    }
