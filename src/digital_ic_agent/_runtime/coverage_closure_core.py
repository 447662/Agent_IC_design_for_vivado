import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from digital_ic_agent._runtime.coverage_recommendations import (
    ScenarioRecommendation,
    recommend_scenarios,
)
from digital_ic_agent._runtime.xcrg_coverage import (
    CoverageDiagnostic,
    CoverageItem,
    extract_low_coverage_items,
)


SCORE_PATTERNS = {
    "statement": r"(?:Statement|Line)\s+Coverage\s+Score\s+([0-9]+(?:\.[0-9]+)?)",
    "branch": r"Branch\s+Coverage\s+Score\s+([0-9]+(?:\.[0-9]+)?)",
    "condition": r"Condition\s+Coverage\s+Score\s+([0-9]+(?:\.[0-9]+)?)",
    "toggle": r"Toggle\s+Coverage\s+Score\s+([0-9]+(?:\.[0-9]+)?)",
    "functional": r"Functional\s+Coverage\s+Score\s+([0-9]+(?:\.[0-9]+)?)",
}
TOTAL_PATTERNS = (
    r"当前覆盖率[：:]\s*([0-9]+(?:\.[0-9]+)?)%",
    r"Total\s+Coverage(?:\s+Score)?[：:\s]+([0-9]+(?:\.[0-9]+)?)%?",
)
GATE_THRESHOLD_PATTERNS = (
    r"覆盖率阈值[：:]\s*([0-9]+(?:\.[0-9]+)?)%",
    r"Coverage\s+threshold[：:\s]+([0-9]+(?:\.[0-9]+)?)%?",
)
FAILURE_TARGET_STATUSES = {"INVALID"}
WARNING_TARGET_STATUSES = {"GAP", "MISSING", "NOT_RUN"}


class CoverageClosureAgent(Protocol):
    def list_targets(self) -> list[dict[str, Any]]: ...


def _round_percent(value: str | float) -> float:
    return round(float(value), 1)


def _last_match(pattern: str, text: str) -> float | None:
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    return _round_percent(matches[-1]) if matches else None


def parse_gate_threshold(summary_text: str) -> float | None:
    for pattern in GATE_THRESHOLD_PATTERNS:
        value = _last_match(pattern, summary_text)
        if value is not None:
            return value
    return None


def parse_coverage_scores(
    score_text: str,
    summary_text: str = "",
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for metric_id, pattern in SCORE_PATTERNS.items():
        value = _last_match(pattern, score_text)
        if value is not None:
            scores[metric_id] = value

    for pattern in TOTAL_PATTERNS:
        total = _last_match(pattern, summary_text or score_text)
        if total is not None:
            scores["total"] = total
            break

    code_values = [
        scores[metric_id]
        for metric_id in ("statement", "branch", "condition", "toggle")
        if metric_id in scores
    ]
    if "total" not in scores and code_values:
        scores["total"] = round(sum(code_values) / len(code_values), 1)

    ordered_scores: dict[str, float] = {}
    for metric_id in (
        "total",
        "statement",
        "branch",
        "condition",
        "toggle",
        "functional",
    ):
        if metric_id in scores:
            ordered_scores[metric_id] = scores[metric_id]
    return ordered_scores


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _markdown_text(value: object) -> str:
    return _clean_text(value).replace("|", "\\|")


def _percent(value: float | None) -> str:
    return "-" if value is None else "{:.1f}%".format(value)


def _item_detail(item: dict[str, Any]) -> str:
    details = item.get("details", {})
    if not isinstance(details, dict):
        return _clean_text(details)
    parts = [
        _clean_text(details.get("scope", "")),
        _clean_text(details.get("name", "")),
    ]
    for field in ("expected", "uncovered", "covered", "goal"):
        if field in details:
            parts.append("{}={}".format(field, details[field]))
    return "; ".join(part for part in parts if part)


def _relative_href(report_dir: Path, path: Path) -> str:
    return Path(os.path.relpath(path, report_dir)).as_posix()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _report_links(project_dir: Path, report_dir: Path) -> list[dict[str, str]]:
    candidates = (
        (
            "Coverage Summary",
            project_dir / "reports" / "uvm_coverage_summary.html",
        ),
        (
            "Vivado Code Coverage",
            project_dir
            / "reports"
            / "uvm_coverage_xcrg"
            / "codeCoverageReport"
            / "dashboard.html",
        ),
        (
            "Vivado Functional Coverage",
            project_dir
            / "reports"
            / "uvm_coverage_xcrg"
            / "functionalCoverageReport"
            / "dashboard.html",
        ),
        (
            "XCRG Log",
            project_dir / "reports" / "xcrg_coverage.log",
        ),
        (
            "Coverage Percent Text",
            project_dir / "reports" / "uvm_coverage_percent.txt",
        ),
        (
            "Coverage WDB",
            project_dir / "sim" / "async_fifo_uvm_coverage.wdb",
        ),
    )
    return [
        {
            "label": label,
            "href": _relative_href(report_dir, path),
        }
        for label, path in candidates
        if path.is_file()
    ]


def _metric_row(
    metric_id: str,
    label: str,
    source: str,
    declared_status: str,
    current: float | None,
    target_threshold: float,
    has_data: bool,
) -> dict[str, Any]:
    if declared_status in {"SKIP", "N/A"}:
        status = declared_status
        gap = None
    elif current is None:
        status = "MISSING" if has_data else "NOT_RUN"
        gap = None
    else:
        gap = round(max(target_threshold - current, 0.0), 1)
        status = "PASS" if current >= target_threshold else "GAP"
    return {
        "id": metric_id,
        "label": label,
        "source": source,
        "declared_status": declared_status,
        "current": current,
        "target": target_threshold,
        "gap": gap,
        "status": status,
    }


def _target_next_action(target: dict[str, Any]) -> str:
    status = target["status"]
    if status == "INVALID":
        return "修复 coverage 报告格式后重新生成看板。"
    if status == "GAP":
        scenarios = ", ".join(target.get("recommended_scenarios", []))
        if scenarios:
            return (
                "基于 P4.1 低覆盖明细执行 P4.2 补测场景：{}。"
            ).format(scenarios)
        return "基于 P4.1 低覆盖明细继续补充 P4.2 场景映射规则。"
    if status == "MISSING":
        return "补齐缺失的 coverage metric 数据源，再重新评估 closure gap。"
    if status == "NOT_RUN":
        if "uvm-coverage" in target["flows"]:
            return (
                "运行 `python .trae/agent/agent.py --uvm-coverage {} "
                "--output-dir <dir>` 生成 coverage 数值。"
            ).format(target["name"])
        return "该 target 尚未提供 coverage flow，需要先接入 UVM/coverage。"
    if status == "SKIP":
        return "Coverage 当前为 SKIP/N/A；需要时先为该 target 接入 coverage flow。"
    return "当前 coverage 已达到目标阈值，继续通过回归防止指标回退。"


def _collect_target(
    target_info: dict[str, Any],
    output_dir: Path,
    report_dir: Path,
    target_threshold: float,
) -> dict[str, Any]:
    target_name = str(target_info["name"])
    project_dir = output_dir / target_name
    reports_dir = project_dir / "reports"
    percent_path = reports_dir / "uvm_coverage_percent.txt"
    summary_path = reports_dir / "uvm_coverage_summary.md"
    configured_metrics = list(target_info.get("coverage_metrics", []))
    declared_statuses = {
        str(metric.get("status", "N/A")).upper()
        for metric in configured_metrics
    }
    expects_data = "PASS" in declared_statuses
    has_score_file = percent_path.is_file()
    has_summary_file = summary_path.is_file()
    has_data = has_score_file or has_summary_file
    error = None
    scores: dict[str, float] = {}
    current_threshold = None

    try:
        score_text = _read_text(percent_path) if has_score_file else ""
        summary_text = _read_text(summary_path) if has_summary_file else ""
        if has_data:
            scores = parse_coverage_scores(score_text, summary_text)
            current_threshold = parse_gate_threshold(summary_text)
            if has_score_file and not scores:
                raise ValueError(
                    "未解析到 coverage score: {}".format(percent_path)
                )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        error = _clean_text(exc)

    metric_rows = []
    if expects_data:
        metric_rows.append(
            _metric_row(
                "total",
                "Total Coverage",
                "coverage summary",
                "PASS",
                scores.get("total"),
                target_threshold,
                has_data,
            )
        )
    else:
        metric_rows.append(
            _metric_row(
                "total",
                "Total Coverage",
                "not-enabled",
                "SKIP",
                None,
                target_threshold,
                has_data,
            )
        )
    for metric in configured_metrics:
        metric_id = str(metric["id"])
        metric_rows.append(
            _metric_row(
                metric_id,
                str(metric.get("label", metric_id)),
                str(metric.get("source", "unknown")),
                str(metric.get("status", "N/A")).upper(),
                scores.get(metric_id),
                target_threshold,
                has_data,
            )
        )

    if error:
        status = "INVALID"
    elif not has_data:
        status = "NOT_RUN" if expects_data else "SKIP"
    elif any(metric["status"] == "GAP" for metric in metric_rows):
        status = "GAP"
    elif any(metric["status"] == "MISSING" for metric in metric_rows):
        status = "MISSING"
    else:
        status = "PASS"

    current_total = scores.get("total")
    gap = (
        round(max(target_threshold - current_total, 0.0), 1)
        if current_total is not None
        else None
    )
    coverage_gaps = [
        metric
        for metric in metric_rows
        if metric["status"] in {"GAP", "MISSING"}
    ]
    low_coverage_items: list[CoverageItem] = []
    low_coverage_diagnostics: list[CoverageDiagnostic] = []
    xcrg_dir = reports_dir / "uvm_coverage_xcrg"
    if expects_data and (has_data or xcrg_dir.is_dir()):
        extraction = extract_low_coverage_items(
            project_dir,
            report_base=report_dir,
            target_threshold=target_threshold,
        )
        low_coverage_items = extraction["items"]
        low_coverage_diagnostics = extraction["diagnostics"]
    scenario_result = recommend_scenarios(
        low_coverage_items,
        list(target_info.get("scenario_catalog", [])),
    )
    scenario_recommendations: list[ScenarioRecommendation] = (
        scenario_result["recommendations"]
    )

    result = {
        "name": target_name,
        "display_name": str(
            target_info.get("display_name", target_name)
        ),
        "design_family": str(
            target_info.get("design_family", "unknown")
        ),
        "flows": list(target_info.get("flows", [])),
        "status": status,
        "current_total": current_total,
        "current_threshold": current_threshold,
        "target_threshold": target_threshold,
        "gap": gap,
        "metrics": metric_rows,
        "coverage_gaps": coverage_gaps,
        "low_coverage_items": low_coverage_items,
        "low_coverage_diagnostics": low_coverage_diagnostics,
        "recommended_scenarios": scenario_result[
            "recommended_scenarios"
        ],
        "scenario_recommendations": scenario_recommendations,
        "links": _report_links(project_dir, report_dir),
        "error": error,
    }
    if status == "NOT_RUN":
        result["error"] = "尚未找到 coverage 数值产物"
    elif status == "SKIP":
        result["error"] = "coverage_metrics 均为 SKIP/N/A"
    elif not result["error"]:
        result["error"] = "-"
    result["next_action"] = _target_next_action(result)
    return result


def collect_coverage_targets(
    agent: CoverageClosureAgent,
    output_dir: str | Path,
    target_threshold: float = 80.0,
) -> list[dict[str, Any]]:
    if not 0.0 <= float(target_threshold) <= 100.0:
        raise ValueError("coverage target must be between 0 and 100")
    output_path = Path(output_dir)
    report_dir = output_path / "coverage-closure"
    return [
        _collect_target(
            dict(target_info),
            output_path,
            report_dir,
            float(target_threshold),
        )
        for target_info in sorted(
            agent.list_targets(),
            key=lambda item: str(item["name"]),
        )
    ]


def coverage_closure_status(targets: list[dict[str, Any]]) -> str:
    statuses = {str(target["status"]) for target in targets}
    if statuses & FAILURE_TARGET_STATUSES:
        return "FAIL"
    if statuses & WARNING_TARGET_STATUSES:
        return "WARN"
    if statuses and statuses <= {"SKIP"}:
        return "WARN"
    return "PASS"
