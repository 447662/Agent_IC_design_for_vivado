import html
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


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
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _markdown_text(value: object) -> str:
    return _clean_text(value).replace("|", "\\|")


def _percent(value: float | None) -> str:
    return "-" if value is None else "{:.1f}%".format(value)


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
        return "进入 P4.1 提取低覆盖明细，再由 P4.2 映射 scenario_catalog 补测。"
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
        "low_coverage_items": [
            metric
            for metric in metric_rows
            if metric["status"] in {"GAP", "MISSING"}
        ],
        "recommended_scenarios": [],
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


def render_coverage_closure_markdown(
    targets: list[dict[str, Any]],
    status: str,
    target_threshold: float,
    generated_at: str,
) -> str:
    lines = [
        "# 多 Target Coverage Closure 看板",
        "",
        "- 总体状态：{}".format(status),
        "- 目标阈值：{:.1f}%".format(target_threshold),
        "- Target 数量：{}".format(len(targets)),
        "- 生成时间（UTC）：{}".format(generated_at),
        "",
        "## Target 汇总",
        "",
        "| Target | Design Family | Status | Current Total | Target | Gap |",
        "|---|---|---|---:|---:|---:|",
    ]
    for target in targets:
        lines.append(
            "| {name} | {family} | {status} | {current} | {target_value} | "
            "{gap} |".format(
                name=_markdown_text(target["name"]),
                family=_markdown_text(target["design_family"]),
                status=target["status"],
                current=_percent(target["current_total"]),
                target_value=_percent(target["target_threshold"]),
                gap=_percent(target["gap"]),
            )
        )

    for target in targets:
        lines.extend(
            [
                "",
                "## {}".format(target["name"]),
                "",
                "- 显示名：{}".format(target["display_name"]),
                "- 设计族：{}".format(target["design_family"]),
                "- Coverage 状态：{}".format(target["status"]),
                "- 当前 gate 阈值：{}".format(
                    _percent(target["current_threshold"])
                ),
                "- 诊断：{}".format(_markdown_text(target["error"])),
                "- 下一步：{}".format(target["next_action"]),
                "- `recommended_scenarios`：{}".format(
                    ", ".join(target["recommended_scenarios"]) or "待 P4.2 生成"
                ),
                "",
                "| Metric | Current | Target | Status | Gap | Source |",
                "|---|---:|---:|---|---:|---|",
            ]
        )
        for metric in target["metrics"]:
            lines.append(
                "| {label} | {current} | {target_value} | {status} | "
                "{gap} | {source} |".format(
                    label=_markdown_text(metric["label"]),
                    current=_percent(metric["current"]),
                    target_value=_percent(metric["target"]),
                    status=metric["status"],
                    gap=_percent(metric["gap"]),
                    source=_markdown_text(metric["source"]),
                )
            )
        if target["links"]:
            lines.extend(["", "### 产物入口", ""])
            for link in target["links"]:
                lines.append(
                    "- [{label}]({href})".format(
                        label=link["label"],
                        href=link["href"],
                    )
                )
    lines.append("")
    return "\n".join(lines)


def _status_class(status: str) -> str:
    if status == "INVALID":
        return "fail"
    if status == "PASS":
        return "pass"
    if status == "GAP":
        return "gap"
    return "warn"


def render_coverage_closure_html(
    targets: list[dict[str, Any]],
    status: str,
    target_threshold: float,
    generated_at: str,
) -> str:
    cards = []
    for target in targets:
        metric_rows = []
        for metric in target["metrics"]:
            metric_rows.append(
                "<tr><td>{label}</td><td>{current}</td><td>{target_value}</td>"
                "<td>{status}</td><td>{gap}</td><td>{source}</td></tr>".format(
                    label=html.escape(str(metric["label"])),
                    current=html.escape(_percent(metric["current"])),
                    target_value=html.escape(_percent(metric["target"])),
                    status=html.escape(str(metric["status"])),
                    gap=html.escape(_percent(metric["gap"])),
                    source=html.escape(str(metric["source"])),
                )
            )
        link_items = "".join(
            '<li><a href="{href}">{label}</a></li>'.format(
                href=html.escape(link["href"], quote=True),
                label=html.escape(link["label"]),
            )
            for link in target["links"]
        )
        cards.append(
            """
<article class="target-card {klass}">
  <header>
    <div><p>{family}</p><h2>{name}</h2><span>{display_name}</span></div>
    <strong>{status}</strong>
  </header>
  <div class="numbers">
    <div><span>Current</span><b>{current}</b></div>
    <div><span>Target</span><b>{target_value}</b></div>
    <div><span>Gap</span><b>{gap}</b></div>
  </div>
  <p class="diagnostic">{diagnostic}</p>
  <p class="next-action">{next_action}</p>
  <table>
    <thead><tr><th>Metric</th><th>Current</th><th>Target</th><th>Status</th><th>Gap</th><th>Source</th></tr></thead>
    <tbody>{metric_rows}</tbody>
  </table>
  <ul class="links">{links}</ul>
</article>""".format(
                klass=_status_class(str(target["status"])),
                family=html.escape(str(target["design_family"])),
                name=html.escape(str(target["name"])),
                display_name=html.escape(str(target["display_name"])),
                status=html.escape(str(target["status"])),
                current=html.escape(_percent(target["current_total"])),
                target_value=html.escape(
                    _percent(target["target_threshold"])
                ),
                gap=html.escape(_percent(target["gap"])),
                diagnostic=html.escape(str(target["error"])),
                next_action=html.escape(str(target["next_action"])),
                metric_rows="".join(metric_rows),
                links=link_items,
            )
        )
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>多 Target Coverage Closure 看板</title>
<style>
:root {{ --bg:#f5f7fa; --panel:#fff; --ink:#172033; --muted:#607080; --line:#d8e0e8; --pass:#087a55; --gap:#b54708; --warn:#9a6700; --fail:#b42318; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; line-height:1.5; }}
main {{ max-width:1240px; margin:0 auto; padding:28px 20px 52px; }}
.page-head {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-end; padding-bottom:18px; border-bottom:2px solid var(--ink); }}
.page-head h1 {{ margin:0; font-size:28px; }}
.page-head p {{ margin:4px 0 0; color:var(--muted); }}
.page-head strong {{ font-size:22px; }}
.target-grid {{ display:grid; gap:16px; margin-top:20px; }}
.target-card {{ background:var(--panel); border:1px solid var(--line); border-left:6px solid var(--warn); border-radius:8px; padding:20px; }}
.target-card.pass {{ border-left-color:var(--pass); }}
.target-card.gap {{ border-left-color:var(--gap); }}
.target-card.fail {{ border-left-color:var(--fail); }}
.target-card header {{ display:flex; justify-content:space-between; gap:16px; }}
.target-card h2 {{ margin:0; font-size:21px; }}
.target-card header p,.target-card header span,.diagnostic {{ margin:0; color:var(--muted); }}
.numbers {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:16px 0; }}
.numbers div {{ padding:12px; background:#f7f9fb; border:1px solid var(--line); border-radius:6px; }}
.numbers span {{ display:block; color:var(--muted); font-size:12px; }}
.numbers b {{ font-size:20px; }}
.next-action {{ font-weight:700; }}
table {{ width:100%; border-collapse:collapse; margin-top:14px; }}
th,td {{ padding:9px 10px; border:1px solid var(--line); text-align:left; }}
th {{ background:#243447; color:#fff; }}
.links {{ display:flex; flex-wrap:wrap; gap:10px 16px; padding:0; list-style:none; }}
.links a {{ color:#175cd3; }}
@media(max-width:760px) {{ .page-head {{ align-items:flex-start; flex-direction:column; }} .numbers {{ grid-template-columns:1fr; }} table {{ display:block; overflow-x:auto; }} }}
</style>
</head>
<body>
<main>
  <header class="page-head">
    <div><h1>多 Target Coverage Closure 看板</h1><p>目标阈值 {target_threshold:.1f}% · 生成时间 {generated_at}</p></div>
    <strong>{status}</strong>
  </header>
  <section class="target-grid">{cards}</section>
</main>
</body>
</html>
""".format(
        target_threshold=target_threshold,
        generated_at=html.escape(generated_at),
        status=html.escape(status),
        cards="".join(cards),
    )


def write_coverage_closure_report(
    agent: CoverageClosureAgent,
    output_dir: str | Path = "outputs",
    target_threshold: float = 80.0,
) -> dict[str, Any]:
    targets = collect_coverage_targets(
        agent,
        output_dir=output_dir,
        target_threshold=target_threshold,
    )
    status = coverage_closure_status(targets)
    generated_at = _utc_timestamp()
    report_dir = Path(output_dir) / "coverage-closure"
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / "index.md"
    html_path = report_dir / "index.html"
    markdown_path.write_text(
        render_coverage_closure_markdown(
            targets,
            status,
            float(target_threshold),
            generated_at,
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        render_coverage_closure_html(
            targets,
            status,
            float(target_threshold),
            generated_at,
        ),
        encoding="utf-8",
    )
    return {
        "status": status,
        "target_count": len(targets),
        "gap_target_count": sum(
            target["status"] in {"GAP", "MISSING"}
            for target in targets
        ),
        "skipped_target_count": sum(
            target["status"] == "SKIP"
            for target in targets
        ),
        "not_run_target_count": sum(
            target["status"] == "NOT_RUN"
            for target in targets
        ),
        "targets": targets,
        "markdown_path": markdown_path,
        "html_path": html_path,
    }
