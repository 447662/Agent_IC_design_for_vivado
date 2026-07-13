import html
from pathlib import Path
from typing import Any

from digital_ic_agent._runtime.project_overview_core import (
    REPORT_SURFACES,
    RESOURCE_SUFFIXES,
    _apply_input_state,
    _artifact_file_status,
    _clean_text,
    _collect_target,
    _discover_target_names,
    _format_command,
    _latest_artifact_map,
    _load_json_object,
    _registered_target_map,
    _relative_from,
    _target_surface_path,
    _validate_target_manifest,
)


def _surface_status(statuses: Any) -> Any:
    if not statuses:
        return "MISSING"
    for status in ("INVALID", "STALE", "CURRENT", "READY", "N/A"):
        if status in statuses:
            return status
    return "MISSING"


def _dashboard_surfaces(
    project_dir: Any,
    reports_dir: Any,
    runs: Any=None,
    input_state: Any=None,
) -> Any:
    artifact_map = _latest_artifact_map(runs or [])
    surfaces = []
    for surface_id, label, candidates in REPORT_SURFACES:
        paths = []
        for relative_path in candidates:
            candidate = project_dir / relative_path
            if candidate.is_file():
                paths.append(candidate)
        fallback = _target_surface_path(
            project_dir,
            surface_id,
            candidates,
        )
        if fallback is not None and fallback not in paths:
            paths.append(fallback)
        links = [
            {
                "label": path.name,
                "href": _relative_from(reports_dir, path),
                "status": _apply_input_state(
                    _artifact_file_status(
                        project_dir,
                        path,
                        artifact_map,
                    ),
                    input_state,
                ),
            }
            for path in paths
        ]
        surfaces.append(
            {
                "id": surface_id,
                "label": label,
                "status": _surface_status(
                    {link["status"] for link in links}
                ),
                "links": links,
            }
        )
    return surfaces


def _dashboard_target_selector(agent: Any, output_dir: Any, current_target: Any) -> Any:
    registered = _registered_target_map(agent)
    target_names = (
        set(registered)
        | _discover_target_names(output_dir)
        | {current_target}
    )
    selectors = []
    for target_name in sorted(target_names):
        target_info = registered.get(target_name, {})
        current = target_name == current_target
        target_dashboard = (
            output_dir
            / target_name
            / "reports"
            / "index.html"
        )
        if current:
            href = "index.html"
        elif target_dashboard.is_file():
            href = "../../{}/reports/index.html".format(target_name)
        else:
            href = "../../index.html#target-{}".format(target_name)
        selectors.append(
            {
                "name": target_name,
                "display_name": target_info.get(
                    "display_name",
                    target_name,
                ),
                "current": current,
                "href": href,
            }
        )
    return selectors


def _dashboard_runs(project_dir: Any, target_name: Any) -> Any:
    manifest_path = project_dir / "artifacts.json"
    if not manifest_path.is_file():
        return []
    manifest = _load_json_object(manifest_path)
    return _validate_target_manifest(manifest, target_name)


def _dashboard_failure_href(project_dir: Any, reports_dir: Any) -> Any:
    failure_manifests = sorted(
        project_dir.glob(
            "failure_archives/*/*/failure_archive.json"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if failure_manifests:
        return _relative_from(reports_dir, failure_manifests[0])
    return "../artifacts.json"


def _dashboard_resources(reports_dir: Any, extra_resources: Any=None) -> Any:
    resources = []
    seen_hrefs = set()
    if reports_dir.is_dir():
        resource_paths = {
            path
            for path in reports_dir.iterdir()
            if path.is_file()
        }
        resource_paths.update(reports_dir.rglob("dashboard.html"))
        for path in sorted(
            resource_paths,
            key=lambda item: item.as_posix(),
        ):
            if (
                path.name in {"index.html", "index.md"}
                or path.suffix.lower() not in RESOURCE_SUFFIXES
            ):
                continue
            href = _relative_from(reports_dir, path)
            seen_hrefs.add(href)
            resources.append(
                {
                    "title": path.relative_to(reports_dir).as_posix(),
                    "href": href,
                    "kind": path.suffix.lower().lstrip(".") or "file",
                }
            )

    for resource in extra_resources or []:
        path = Path(resource["path"])
        if not path.is_file():
            continue
        href = resource.get("href") or _relative_from(reports_dir, path)
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        resources.append(
            {
                "title": resource.get("title") or path.name,
                "href": href,
                "kind": path.suffix.lower().lstrip(".") or "file",
            }
        )
    return resources


def _dashboard_markdown(
    target: Any,
    selectors: Any,
    surfaces: Any,
    latest_run: Any,
    last_failure: Any,
    failure_href: Any,
    resources: Any,
) -> Any:
    ready_stage_count = sum(
        surface["status"] in {"CURRENT", "READY"}
        for surface in surfaces
    )
    lines = [
        "# {} 报告总览".format(target["name"]),
        "",
        "- 当前状态：{}".format(target["status"]),
        "- 设计族：{}".format(target["design_family"]),
        "- 阶段就绪：{}/{}".format(
            ready_stage_count,
            len(surfaces),
        ),
        "- 项目总览：[../../index.html](../../index.html)",
        "",
        "## 目标选择",
        "",
    ]
    for selector in selectors:
        suffix = "（当前）" if selector["current"] else ""
        lines.append(
            "- [{name}]({href}) {display_name}{suffix}".format(
                name=selector["name"],
                href=selector["href"],
                display_name=selector["display_name"],
                suffix=suffix,
            )
        )

    lines.extend(
        [
            "",
            "## 阶段状态",
            "",
            "| Stage | 名称 | 状态 | 入口 |",
            "|---|---|---|---|",
        ]
    )
    for surface in surfaces:
        links = " / ".join(
            "[{label}]({href})".format(**link)
            for link in surface["links"]
        ) or "-"
        lines.append(
            "| {id} | {label} | {status} | {links} |".format(
                id=surface["id"],
                label=surface["label"],
                status=surface["status"],
                links=links,
            )
        )

    lines.extend(["", "## 最近运行", ""])
    if latest_run is None:
        lines.append("- 尚无运行记录。")
    else:
        lines.extend(
            [
                "- Flow：{}".format(latest_run["flow"]),
                "- 状态：{}".format(latest_run["status"]),
                "- 时间：{}".format(
                    latest_run.get("recorded_at") or "-"
                ),
                "- 重跑命令：`{}`".format(
                    _format_command(latest_run.get("command"))
                ),
            ]
        )

    lines.extend(["", "## 最近失败", ""])
    if last_failure is None:
        lines.append("- 尚无失败运行。")
    else:
        lines.extend(
            [
                "- Flow：{}".format(last_failure["flow"]),
                "- 时间：{}".format(
                    last_failure.get("recorded_at") or "-"
                ),
                "- 原因：{}".format(
                    _clean_text(last_failure.get("error")) or "-"
                ),
                "- 调试入口：[{}]({})".format(
                    failure_href,
                    failure_href,
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 工程资源",
            "",
            "| 资源 | 类型 | 入口 |",
            "|---|---|---|",
        ]
    )
    for resource in resources:
        lines.append(
            "| {title} | {kind} | [{href}]({href}) |".format(
                **resource
            )
        )
    lines.append("")
    return "\n".join(lines)


def _dashboard_stage_html(surface: Any) -> Any:
    links = "".join(
        '<a href="{href}">{label}</a>'.format(
            href=html.escape(link["href"], quote=True),
            label=html.escape(link["label"]),
        )
        for link in surface["links"]
    )
    if not links:
        links = '<span class="muted">尚无入口</span>'
    return """
<article class="report-card {klass}" data-stage="{stage}">
  <div class="stage-head">
    <div><p class="eyebrow">{stage}</p><h2>{label}</h2></div>
    <strong>{status}</strong>
  </div>
  <div class="stage-links">{links}</div>
</article>""".format(
        klass=(
            "ready"
            if surface["status"] in {"CURRENT", "READY"}
            else "missing"
        ),
        stage=html.escape(surface["id"], quote=True),
        label=html.escape(surface["label"]),
        status=surface["status"],
        links=links,
    )


def _dashboard_html(
    target: Any,
    selectors: Any,
    surfaces: Any,
    latest_run: Any,
    last_failure: Any,
    failure_href: Any,
    resources: Any,
) -> Any:
    ready_stage_count = sum(
        surface["status"] in {"CURRENT", "READY"}
        for surface in surfaces
    )
    selector_links = [
        '<a href="../../index.html">项目总览</a>'
    ]
    for selector in selectors:
        current_attr = (
            ' aria-current="page"'
            if selector["current"]
            else ""
        )
        selector_links.append(
            '<a href="{href}"{current}>{name}</a>'.format(
                href=html.escape(selector["href"], quote=True),
                current=current_attr,
                name=html.escape(selector["name"]),
            )
        )

    latest_flow = "-"
    latest_status = "NOT_RUN"
    latest_time = "-"
    latest_command = "-"
    if latest_run is not None:
        latest_flow = str(latest_run["flow"])
        latest_status = str(latest_run["status"])
        latest_time = str(latest_run.get("recorded_at") or "-")
        latest_command = _format_command(latest_run.get("command"))

    if last_failure is None:
        failure_class = "clear"
        failure_title = "最近失败：无"
        failure_message = "尚无失败运行"
        failure_link = ""
    else:
        failure_class = "fail"
        failure_title = "最近失败：{}".format(last_failure["flow"])
        failure_message = (
            _clean_text(last_failure.get("error"))
            or "运行失败"
        )
        failure_link = (
            '<a href="{href}">打开失败调试入口</a>'.format(
                href=html.escape(failure_href, quote=True)
            )
        )

    resource_rows = "\n".join(
        """
<tr>
  <td>{title}</td>
  <td>{kind}</td>
  <td><a href="{href}">打开</a></td>
</tr>""".format(
            title=html.escape(resource["title"]),
            kind=html.escape(resource["kind"].upper()),
            href=html.escape(resource["href"], quote=True),
        )
        for resource in resources
    )
    if not resource_rows:
        resource_rows = (
            '<tr><td colspan="3" class="muted">'
            "尚无工程资源</td></tr>"
        )

    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{target_name} 报告总览</title>
<style>
:root {{ --bg:#f4f7fb; --panel:#fff; --ink:#172033; --muted:#5b6878; --line:#d9e2ec; --pass:#087a55; --warn:#a35b00; --fail:#b42318; --accent:#175cd3; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; line-height:1.55; }}
a {{ color:var(--accent); }}
.page {{ max-width:1240px; margin:0 auto; padding:28px 20px 56px; }}
.target-selector {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }}
.target-selector a {{ padding:7px 10px; border:1px solid var(--line); border-radius:6px; background:#fff; text-decoration:none; }}
.target-selector a[aria-current="page"] {{ color:#fff; background:#17324d; border-color:#17324d; }}
.hero {{ padding:26px; border-radius:8px; color:#fff; background:#17324d; }}
.hero h1 {{ margin:0 0 6px; font-size:30px; }}
.hero p {{ margin:0; color:#dbe9f6; }}
.summary {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:16px 0; }}
.summary div {{ padding:15px; background:var(--panel); border:1px solid var(--line); border-radius:8px; }}
.summary strong {{ display:block; font-size:22px; }}
.summary span,.muted,.eyebrow {{ color:var(--muted); }}
.stage-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
.report-card {{ padding:18px; background:var(--panel); border:1px solid var(--line); border-left:6px solid var(--warn); border-radius:8px; }}
.report-card.ready {{ border-left-color:var(--pass); }}
.stage-head {{ display:flex; justify-content:space-between; gap:16px; }}
.stage-head h2 {{ margin:0; font-size:19px; }}
.eyebrow {{ margin:0 0 3px; font-size:12px; font-weight:800; }}
.stage-links {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }}
.detail-grid {{ display:grid; grid-template-columns:1.3fr 1fr; gap:14px; margin-top:16px; }}
.run-panel,.failure-entry,.resources {{ padding:18px; background:var(--panel); border:1px solid var(--line); border-radius:8px; }}
.run-panel h2,.failure-entry h2,.resources h2 {{ margin:0 0 10px; font-size:20px; }}
.run-panel dl {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:0; }}
.run-panel dl div {{ padding:10px; background:#f7f9fc; border-radius:6px; }}
.run-panel dt {{ color:var(--muted); font-size:12px; }}
.run-panel dd {{ margin:2px 0 0; font-weight:700; word-break:break-word; }}
.command {{ margin:12px 0 0; padding:10px; overflow:auto; background:#f7f9fc; border-radius:6px; }}
.failure-entry {{ border-left:6px solid var(--pass); }}
.failure-entry.fail {{ border-left-color:var(--fail); }}
.resources {{ margin-top:16px; overflow:auto; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ padding:10px; border-bottom:1px solid var(--line); text-align:left; }}
th {{ color:var(--muted); font-size:12px; }}
@media(max-width:820px) {{ .summary,.stage-grid,.detail-grid,.run-panel dl {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<main class="page">
<nav class="target-selector" aria-label="目标选择">{selectors}</nav>
<section class="hero">
  <h1>{target_name} 报告总览</h1>
  <p>{display_name} · {family} · 当前状态 {status}</p>
</section>
<section class="summary">
  <div><strong>{status}</strong><span>目标状态</span></div>
  <div><strong>{ready_stage_count}/{stage_count}</strong><span>阶段就绪</span></div>
  <div><strong>{latest_flow}</strong><span>最近 flow</span></div>
  <div><strong>{latest_status}</strong><span>最近状态</span></div>
</section>
<section class="stage-grid">{stage_cards}</section>
<section class="detail-grid">
  <article class="run-panel">
    <h2>最近运行</h2>
    <dl>
      <div><dt>Flow</dt><dd>{latest_flow}</dd></div>
      <div><dt>状态</dt><dd>{latest_status}</dd></div>
      <div><dt>时间</dt><dd>{latest_time}</dd></div>
    </dl>
    <pre class="command">{latest_command}</pre>
  </article>
  <article class="failure-entry {failure_class}">
    <h2>{failure_title}</h2>
    <p>{failure_message}</p>
    {failure_link}
  </article>
</section>
<section class="resources">
  <h2>工程资源</h2>
  <table>
    <thead><tr><th>资源</th><th>类型</th><th>入口</th></tr></thead>
    <tbody>{resource_rows}</tbody>
  </table>
</section>
</main>
</body>
</html>
""".format(
        target_name=html.escape(target["name"]),
        display_name=html.escape(target["display_name"]),
        family=html.escape(target["design_family"]),
        status=target["status"],
        ready_stage_count=ready_stage_count,
        stage_count=len(surfaces),
        latest_flow=html.escape(latest_flow),
        latest_status=latest_status,
        latest_time=html.escape(latest_time),
        latest_command=html.escape(latest_command),
        selectors="\n".join(selector_links),
        stage_cards="\n".join(
            _dashboard_stage_html(surface)
            for surface in surfaces
        ),
        failure_class=failure_class,
        failure_title=html.escape(failure_title),
        failure_message=html.escape(failure_message),
        failure_link=failure_link,
        resource_rows=resource_rows,
    )


def write_target_dashboard(
    self: Any,
    project_dir: Any,
    extra_resources: Any=None,
) -> Any:
    project_dir = Path(project_dir)
    output_dir = project_dir.parent
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    target_name = project_dir.name
    registered = _registered_target_map(self)
    target_info = registered.get(
        target_name,
        {
            "name": target_name,
            "display_name": target_name,
            "design_family": "unregistered",
        },
    )
    target = _collect_target(output_dir, target_info, agent=self)
    try:
        runs = _dashboard_runs(project_dir, target_name)
    except (OSError, ValueError):
        runs = []
    latest_run = runs[-1] if runs else None
    last_failure = next(
        (
            run
            for run in reversed(runs)
            if run["status"] == "FAIL"
        ),
        None,
    )
    surfaces = _dashboard_surfaces(
        project_dir,
        reports_dir,
        runs=runs,
        input_state=target.get("input_state"),
    )
    selectors = _dashboard_target_selector(
        self,
        output_dir,
        target_name,
    )
    failure_href = _dashboard_failure_href(
        project_dir,
        reports_dir,
    )
    resources = _dashboard_resources(
        reports_dir,
        extra_resources=extra_resources,
    )
    markdown_path = reports_dir / "index.md"
    html_path = reports_dir / "index.html"
    markdown_path.write_text(
        _dashboard_markdown(
            target,
            selectors,
            surfaces,
            latest_run,
            last_failure,
            failure_href,
            resources,
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        _dashboard_html(
            target,
            selectors,
            surfaces,
            latest_run,
            last_failure,
            failure_href,
            resources,
        ),
        encoding="utf-8",
    )
    ready_stage_count = sum(
        surface["status"] in {"CURRENT", "READY"}
        for surface in surfaces
    )
    return {
        "status": target["status"],
        "target_count": len(selectors),
        "stage_count": len(surfaces),
        "ready_stage_count": ready_stage_count,
        "latest_run": latest_run,
        "last_failure": last_failure,
        "failure_href": failure_href,
        "ready_count": len(resources),
        "reports": resources,
        "surfaces": surfaces,
        "markdown_path": markdown_path,
        "html_path": html_path,
    }
