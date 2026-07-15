import html
from typing import Any

from digital_ic_agent._runtime.project_overview_core import (
    FAILURE_STATUSES,
    _markdown_text,
)


def render_project_overview_markdown(
    output_dir: Any,
    targets: Any,
    environment: Any,
    status: Any,
    generated_at: Any,
) -> Any:
    ready_count = sum(target["status"] == "PASS" for target in targets)
    failed_count = sum(
        target["status"] in FAILURE_STATUSES
        for target in targets
    )
    environment_report = (
        "[报告]({})".format(environment["report_href"])
        if environment["report_href"]
        else "报告尚未生成"
    )
    environment_manifest = (
        "[manifest]({})".format(environment["manifest_href"])
        if environment["manifest_href"]
        else "manifest 尚未生成"
    )
    lines = [
        "# 数字 IC Agent 多目标项目总览",
        "",
        "- 总体状态：{}".format(status),
        "- 目标数量：{}".format(len(targets)),
        "- 已通过目标：{}".format(ready_count),
        "- 失败目标：{}".format(failed_count),
        "- 输出目录：`{}`".format(output_dir),
        "- 生成时间（UTC）：{}".format(generated_at),
        "- 环境预检：{}（{} / {}）".format(
            environment["status"],
            environment_report,
            environment_manifest,
        ),
        "",
        "## 目标状态",
        "",
        "| Target | 显示名 | 状态 | 最近 flow | 最近状态 | 最近时间 | Manifest | 失败/提示 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for target in targets:
        manifest_entry = (
            "[artifacts.json]({})".format(target["manifest_href"])
            if target["manifest_href"]
            else "manifest 尚未生成"
        )
        lines.append(
            "| {name} | {display_name} | {status} | {latest_flow} | "
            "{latest_status} | {recorded_at} | {manifest} | "
            "{error} |".format(
                name=_markdown_text(target["name"]),
                display_name=_markdown_text(target["display_name"]),
                status=target["status"],
                latest_flow=_markdown_text(target["latest_flow"]),
                latest_status=target["latest_status"],
                recorded_at=_markdown_text(target["recorded_at"]),
                manifest=manifest_entry,
                error=_markdown_text(target["error"]),
            )
        )

    for target in targets:
        lines.extend(
            [
                "",
                "## {}".format(target["name"]),
                "",
                "- 设计族：{}".format(target["design_family"]),
                "- 当前状态：{}".format(target["status"]),
                "- 最近运行：{} / {}".format(
                    target["latest_flow"],
                    target["latest_status"],
                ),
                "- 重跑命令：`{}`".format(target["replay_command"]),
                "",
                "| Surface | 状态 | 入口 |",
                "|---|---|---|",
            ]
        )
        for surface in target["surfaces"]:
            link = (
                "[{}]({})".format(surface["href"], surface["href"])
                if surface["href"]
                else "-"
            )
            lines.append(
                "| {} | {} | {} |".format(
                    surface["label"],
                    surface["status"],
                    link,
                )
            )
    lines.append("")
    return "\n".join(lines)


def _status_class(status: Any) -> Any:
    if status in FAILURE_STATUSES:
        return "fail"
    if status == "PASS":
        return "pass"
    return "warn"


def _surface_html(surface: Any) -> Any:
    if surface["href"]:
        content = '<a href="{href}">{label}</a>'.format(
            href=html.escape(surface["href"], quote=True),
            label=html.escape(surface["label"]),
        )
    else:
        content = "<span>{}</span>".format(html.escape(surface["label"]))
    return (
        '<li class="{klass}">{content}<strong>{status}</strong></li>'.format(
            klass=(
                "ready"
                if surface["status"] in {"CURRENT", "READY"}
                else "missing"
            ),
            content=content,
            status=surface["status"],
        )
    )
def render_project_overview_html(targets: Any, environment: Any, status: Any, generated_at: Any) -> Any:
    nav_links = []
    target_cards = []
    for target in targets:
        anchor = "target-{}".format(target["name"])
        nav_links.append(
            '<a href="#{anchor}">{name}</a>'.format(
                anchor=html.escape(anchor, quote=True),
                name=html.escape(target["name"]),
            )
        )
        surfaces = "\n".join(
            _surface_html(surface)
            for surface in target["surfaces"]
        )
        manifest_entry = (
            '<p class="manifest"><a href="{href}">'
            "打开 artifacts.json</a></p>".format(
                href=html.escape(
                    target["manifest_href"],
                    quote=True,
                )
            )
            if target["manifest_href"]
            else '<p class="manifest missing">manifest 尚未生成</p>'
        )
        target_cards.append(
            """
<article id="{anchor}" class="target-card {klass}">
  <div class="target-head">
    <div><p class="eyebrow">{family}</p><h2>{name}</h2><p>{display_name}</p></div>
    <span class="status">{status}</span>
  </div>
  <dl>
    <div><dt>最近 flow</dt><dd>{latest_flow}</dd></div>
    <div><dt>最近状态</dt><dd>{latest_status}</dd></div>
    <div><dt>运行时间</dt><dd>{recorded_at}</dd></div>
  </dl>
  <p class="message">{message}</p>
  {manifest_entry}
  <ul class="surface-list">{surfaces}</ul>
</article>""".format(
                anchor=html.escape(anchor, quote=True),
                klass=_status_class(target["status"]),
                family=html.escape(target["design_family"]),
                name=html.escape(target["name"]),
                display_name=html.escape(target["display_name"]),
                status=target["status"],
                latest_flow=html.escape(target["latest_flow"]),
                latest_status=target["latest_status"],
                recorded_at=html.escape(target["recorded_at"]),
                message=html.escape(target["error"]),
                manifest_entry=manifest_entry,
                surfaces=surfaces,
            )
        )

    environment_report = (
        '<a href="{href}">打开环境报告</a>'.format(
            href=html.escape(environment["report_href"], quote=True)
        )
        if environment["report_href"]
        else "报告尚未生成"
    )
    environment_manifest = (
        '<a href="{href}">打开环境 manifest</a>'.format(
            href=html.escape(environment["manifest_href"], quote=True)
        )
        if environment["manifest_href"]
        else "manifest 尚未生成"
    )
    environment_entry = "{} / {}".format(
        environment_report,
        environment_manifest,
    )
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>数字 IC Agent 多目标项目总览</title>
<style>
:root {{ --bg:#f4f7fb; --panel:#fff; --ink:#172033; --muted:#5b6878; --line:#d9e2ec; --pass:#087a55; --warn:#a35b00; --fail:#b42318; --accent:#175cd3; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; line-height:1.55; }}
.page {{ max-width:1240px; margin:0 auto; padding:32px 20px 56px; }}
.hero {{ padding:28px; border-radius:8px; color:#fff; background:#17324d; }}
.hero h1 {{ margin:0 0 8px; font-size:32px; }}
.hero p {{ margin:0; color:#dbe9f6; }}
.summary {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:16px; }}
.summary div,.environment-card,.target-card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 8px 24px rgba(31,45,61,.06); }}
.summary div {{ padding:16px; }}
.summary strong {{ display:block; font-size:24px; }}
.summary span,.eyebrow,.target-head p,.message {{ color:var(--muted); }}
.environment-card {{ margin-top:16px; padding:18px; border-left:6px solid var(--warn); }}
.environment-card.pass {{ border-left-color:var(--pass); }}
.environment-card.fail {{ border-left-color:var(--fail); }}
.environment-card h2 {{ margin:0 0 6px; font-size:20px; }}
.target-nav {{ display:flex; flex-wrap:wrap; gap:8px; margin:18px 0; }}
.target-nav a {{ padding:7px 10px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--accent); text-decoration:none; }}
.target-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }}
.target-card {{ padding:20px; border-left:6px solid var(--warn); }}
.target-card.pass {{ border-left-color:var(--pass); }}
.target-card.fail {{ border-left-color:var(--fail); }}
.target-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }}
.target-head h2 {{ margin:0; font-size:22px; }}
.target-head p {{ margin:2px 0 0; }}
.eyebrow {{ text-transform:uppercase; font-size:12px; font-weight:700; }}
.status {{ font-weight:800; }}
dl {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:16px 0; }}
dl div {{ padding:10px; background:#f7f9fc; border-radius:6px; }}
dt {{ color:var(--muted); font-size:12px; }}
dd {{ margin:2px 0 0; font-weight:700; word-break:break-word; }}
.manifest a,.surface-list a,.environment-card a {{ color:var(--accent); }}
.surface-list {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; padding:0; list-style:none; }}
.surface-list li {{ display:flex; justify-content:space-between; gap:8px; padding:9px 10px; border:1px solid var(--line); border-radius:6px; }}
.surface-list li.missing {{ color:var(--muted); background:#f8fafc; }}
.surface-list strong {{ font-size:12px; }}
@media(max-width:820px) {{ .summary,.target-grid,dl {{ grid-template-columns:1fr; }} .surface-list {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<main class="page">
<section class="hero">
  <h1>数字 IC Agent 多目标项目总览</h1>
  <p>状态：{status} · 生成时间（UTC）：{generated_at}</p>
</section>
<section class="summary">
  <div><strong>{target_count}</strong><span>目标数量</span></div>
  <div><strong>{ready_count}</strong><span>PASS 目标</span></div>
  <div><strong>{failed_count}</strong><span>失败目标</span></div>
</section>
<section class="environment-card {environment_class}">
  <h2>环境预检：{environment_status}</h2>
  <p>{environment_message}</p>
  <p class="manifest">{environment_entry}</p>
</section>
<nav class="target-nav">{nav_links}</nav>
<section class="target-grid">{target_cards}</section>
</main>
</body>
</html>
""".format(
        status=status,
        generated_at=html.escape(generated_at),
        target_count=len(targets),
        ready_count=sum(target["status"] == "PASS" for target in targets),
        failed_count=sum(
            target["status"] in FAILURE_STATUSES
            for target in targets
        ),
        environment_class=_status_class(environment["status"]),
        environment_status=environment["status"],
        environment_message=html.escape(environment["error"]),
        environment_entry=environment_entry,
        nav_links="\n".join(nav_links),
        target_cards="\n".join(target_cards),
    )
