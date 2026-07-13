import html
from typing import Any

from digital_ic_agent._runtime.coverage_closure_core import (
    _item_detail,
    _markdown_text,
    _percent,
)


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
                    ", ".join(target["recommended_scenarios"])
                    or "无匹配场景"
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
        if target["low_coverage_items"]:
            lines.extend(
                [
                    "",
                    "### 低覆盖项",
                    "",
                    "| Source File | Instance | Metric | Score | Details | Source Report |",
                    "|---|---|---|---:|---|---|",
                ]
            )
            for item in target["low_coverage_items"]:
                lines.append(
                    "| {source_file} | {instance} | {metric} | {score} | "
                    "{details} | [原始报告]({source_report}) |".format(
                        source_file=_markdown_text(item["source_file"]) or "-",
                        instance=_markdown_text(item["instance"]) or "-",
                        metric=_markdown_text(item["metric"]),
                        score=_percent(item["score"]),
                        details=_markdown_text(_item_detail(item)),
                        source_report=item["source_report"],
                    )
                )
        if target["scenario_recommendations"]:
            lines.extend(
                [
                    "",
                    "### 推荐补测场景",
                    "",
                    "| Priority | Scenario ID | Type | Purpose | Evidence | Reason |",
                    "|---|---|---|---|---|---|",
                ]
            )
            for recommendation in target["scenario_recommendations"]:
                lines.append(
                    "| {priority} | `{scenario_id}` | {scenario_type} | "
                    "{purpose} | {evidence} | {reason} |".format(
                        priority=_markdown_text(
                            recommendation["priority"]
                        ),
                        scenario_id=_markdown_text(
                            recommendation["scenario_id"]
                        ),
                        scenario_type=_markdown_text(
                            recommendation["scenario_type"]
                        ),
                        purpose=_markdown_text(
                            recommendation["purpose"]
                        ),
                        evidence=_markdown_text(
                            ", ".join(
                                recommendation["matched_items"]
                            )
                        ),
                        reason=_markdown_text(
                            recommendation["reason"]
                        ),
                    )
                )
        if target["low_coverage_diagnostics"]:
            lines.extend(
                [
                    "",
                    "### 低覆盖项解析诊断",
                    "",
                    "| Status | Message | Source Report |",
                    "|---|---|---|",
                ]
            )
            for diagnostic in target["low_coverage_diagnostics"]:
                lines.append(
                    "| {status} | {message} | [原始报告]({source_report}) |".format(
                        status=_markdown_text(diagnostic["status"]),
                        message=_markdown_text(diagnostic["message"]),
                        source_report=diagnostic["source_report"],
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
        low_item_rows = []
        for item in target["low_coverage_items"]:
            low_item_rows.append(
                "<tr><td>{source_file}</td><td>{instance}</td>"
                "<td>{metric}</td><td>{score}</td><td>{details}</td>"
                '<td><a href="{source_report}">原始报告</a></td></tr>'.format(
                    source_file=html.escape(str(item["source_file"] or "-")),
                    instance=html.escape(str(item["instance"] or "-")),
                    metric=html.escape(str(item["metric"])),
                    score=html.escape(_percent(item["score"])),
                    details=html.escape(_item_detail(item)),
                    source_report=html.escape(
                        str(item["source_report"]),
                        quote=True,
                    ),
                )
            )
        diagnostic_rows = []
        for diagnostic in target["low_coverage_diagnostics"]:
            diagnostic_rows.append(
                "<tr><td>{status}</td><td>{message}</td>"
                '<td><a href="{source_report}">原始报告</a></td></tr>'.format(
                    status=html.escape(str(diagnostic["status"])),
                    message=html.escape(str(diagnostic["message"])),
                    source_report=html.escape(
                        str(diagnostic["source_report"]),
                        quote=True,
                    ),
                )
            )
        scenario_rows = []
        for recommendation in target["scenario_recommendations"]:
            scenario_rows.append(
                "<tr><td>{priority}</td><td><code>{scenario_id}</code></td>"
                "<td>{scenario_type}</td><td>{purpose}</td>"
                "<td>{evidence}</td><td>{reason}</td></tr>".format(
                    priority=html.escape(
                        str(recommendation["priority"])
                    ),
                    scenario_id=html.escape(
                        str(recommendation["scenario_id"])
                    ),
                    scenario_type=html.escape(
                        str(recommendation["scenario_type"])
                    ),
                    purpose=html.escape(
                        str(recommendation["purpose"])
                    ),
                    evidence=html.escape(
                        ", ".join(recommendation["matched_items"])
                    ),
                    reason=html.escape(
                        str(recommendation["reason"])
                    ),
                )
            )
        scenario_section = ""
        if scenario_rows:
            scenario_section = (
                "<h3>推荐补测场景</h3><table><thead><tr>"
                "<th>Priority</th><th>Scenario ID</th><th>Type</th>"
                "<th>Purpose</th><th>Evidence</th><th>Reason</th>"
                "</tr></thead><tbody>{}</tbody></table>"
            ).format("".join(scenario_rows))
        low_coverage_section = ""
        if low_item_rows:
            low_coverage_section += (
                "<h3>低覆盖项</h3><table><thead><tr>"
                "<th>Source File</th><th>Instance</th><th>Metric</th>"
                "<th>Score</th><th>Details</th><th>Source Report</th>"
                "</tr></thead><tbody>{}</tbody></table>"
            ).format("".join(low_item_rows))
        if diagnostic_rows:
            low_coverage_section += (
                "<h3>低覆盖项解析诊断</h3><table><thead><tr>"
                "<th>Status</th><th>Message</th><th>Source Report</th>"
                "</tr></thead><tbody>{}</tbody></table>"
            ).format("".join(diagnostic_rows))
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
  {scenario_section}
  {low_coverage_section}
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
                scenario_section=scenario_section,
                low_coverage_section=low_coverage_section,
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
