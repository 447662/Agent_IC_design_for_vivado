import html
import json
import os
from pathlib import Path

from artifact_manifest import utc_timestamp


SCHEMA_VERSION = 1
FAILURE_STATUSES = {"FAIL", "INVALID"}
WARNING_STATUSES = {"WARN", "MISSING", "NOT_RUN"}
REPORT_SURFACES = (
    (
        "Spec",
        "规格",
        (
            "reports/design_spec.html",
            "reports/design_spec.md",
        ),
    ),
    (
        "RTL",
        "RTL",
        (),
    ),
    (
        "Simulation",
        "仿真",
        (
            "reports/sim_report.html",
            "reports/sim_summary.html",
            "reports/regression_summary.html",
        ),
    ),
    (
        "UVM",
        "UVM",
        (
            "reports/uvm_smoke_report.html",
            "reports/uvm_coverage_report.html",
        ),
    ),
    (
        "Coverage",
        "覆盖率",
        (
            "reports/uvm_coverage_summary.html",
            "reports/uvm_coverage_xcrg/codeCoverageReport/dashboard.html",
            "reports/uvm_coverage_xcrg/functionalCoverageReport/dashboard.html",
        ),
    ),
    (
        "Wave",
        "波形",
        (
            "reports/wave_visibility.html",
            "reports/wave_screenshot.html",
            "reports/uvm_wave_screenshot.html",
        ),
    ),
    (
        "Lessons",
        "复盘",
        (
            "reports/lessons_learned.html",
            "reports/lessons_learned.md",
            "README.md",
        ),
    ),
)
RESOURCE_SUFFIXES = {
    ".html",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".png",
    ".txt",
}


def _clean_text(value):
    return " ".join(str(value or "").split())


def _markdown_text(value):
    return _clean_text(value).replace("|", "\\|")


def _relative_href(output_dir, path):
    return Path(path).resolve().relative_to(Path(output_dir).resolve()).as_posix()


def _relative_from(base_dir, path):
    return Path(
        os.path.relpath(
            Path(path).resolve(),
            Path(base_dir).resolve(),
        )
    ).as_posix()


def _load_json_object(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("manifest JSON 无效: {}".format(path)) from exc
    if not isinstance(value, dict):
        raise ValueError("manifest 必须是 JSON object: {}".format(path))
    return value


def _validate_target_manifest(manifest, target_name):
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("manifest schema_version 不受支持")
    if manifest.get("target") != target_name:
        raise ValueError("manifest target 与目录不匹配")
    runs = manifest.get("runs")
    if not isinstance(runs, list):
        raise ValueError("manifest runs 必须是列表")
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("manifest run 必须是 object")
        if not run.get("flow"):
            raise ValueError("manifest run 缺少 flow")
        if run.get("status") not in {"PASS", "FAIL"}:
            raise ValueError("manifest run status 非法")
    return runs


def _target_surface_path(project_dir, surface_id, candidates):
    for relative_path in candidates:
        candidate = project_dir / relative_path
        if candidate.is_file():
            return candidate

    if surface_id == "RTL":
        rtl_dir = project_dir / "rtl"
        rtl_files = []
        if rtl_dir.is_dir():
            rtl_files.extend(rtl_dir.glob("*.v"))
            rtl_files.extend(rtl_dir.glob("*.sv"))
        if rtl_files:
            return sorted(rtl_files)[0]

    if surface_id == "UVM":
        uvm_dir = project_dir / "uvm"
        if uvm_dir.is_dir():
            uvm_files = sorted(uvm_dir.glob("*.sv"))
            if uvm_files:
                return uvm_files[0]

    if surface_id == "Wave":
        sim_dir = project_dir / "sim"
        if sim_dir.is_dir():
            wave_files = sorted(sim_dir.glob("*.wdb")) + sorted(
                sim_dir.glob("*.vcd")
            )
            if wave_files:
                return wave_files[-1]
    return None


def _collect_surfaces(output_dir, project_dir):
    surfaces = []
    for surface_id, label, candidates in REPORT_SURFACES:
        path = _target_surface_path(project_dir, surface_id, candidates)
        surfaces.append(
            {
                "id": surface_id,
                "label": label,
                "status": "READY" if path else "MISSING",
                "href": _relative_href(output_dir, path) if path else None,
            }
        )
    return surfaces


def _latest_flow_statuses(runs):
    statuses = {}
    for run in runs:
        statuses[str(run["flow"])] = str(run["status"])
    return statuses


def _collect_target(output_dir, target_info):
    target_name = target_info["name"]
    project_dir = output_dir / target_name
    manifest_path = project_dir / "artifacts.json"
    result = {
        "name": target_name,
        "display_name": target_info.get("display_name", target_name),
        "design_family": target_info.get("design_family", "unknown"),
        "status": "NOT_RUN",
        "manifest_state": "MISSING",
        "manifest_href": None,
        "latest_flow": "-",
        "latest_status": "NOT_RUN",
        "recorded_at": "-",
        "error": "尚无运行记录",
        "replay_command": "-",
        "surfaces": _collect_surfaces(output_dir, project_dir),
    }
    if not manifest_path.is_file():
        return result

    result["manifest_href"] = _relative_href(output_dir, manifest_path)
    try:
        manifest = _load_json_object(manifest_path)
        runs = _validate_target_manifest(manifest, target_name)
    except (OSError, ValueError) as exc:
        result.update(
            {
                "status": "INVALID",
                "manifest_state": "INVALID",
                "latest_status": "INVALID",
                "error": "{}: {}".format(manifest_path.name, _clean_text(exc)),
            }
        )
        return result

    result["manifest_state"] = "READY"
    if not runs:
        return result

    latest_run = runs[-1]
    flow_statuses = _latest_flow_statuses(runs)
    result.update(
        {
            "status": (
                "FAIL"
                if any(status == "FAIL" for status in flow_statuses.values())
                else "PASS"
            ),
            "latest_flow": str(latest_run["flow"]),
            "latest_status": str(latest_run["status"]),
            "recorded_at": str(
                latest_run.get("recorded_at")
                or manifest.get("updated_at")
                or "-"
            ),
            "error": _clean_text(latest_run.get("error")) or "-",
            "replay_command": _format_command(latest_run.get("command")),
            "flow_statuses": flow_statuses,
        }
    )
    return result


def _format_command(command):
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    if command:
        return str(command)
    return "-"


def _registered_target_map(agent):
    return {
        str(item["name"]): dict(item)
        for item in agent.list_targets()
    }


def _discover_target_names(output_dir):
    names: set[str] = set()
    if not output_dir.is_dir():
        return names
    for manifest_path in output_dir.glob("*/artifacts.json"):
        if manifest_path.parent.name != "environment-report":
            names.add(manifest_path.parent.name)
    return names


def collect_targets(agent, output_dir):
    registered = _registered_target_map(agent)
    target_names = set(registered) | _discover_target_names(output_dir)
    targets = []
    for target_name in sorted(target_names):
        target_info = registered.get(
            target_name,
            {
                "name": target_name,
                "display_name": target_name,
                "design_family": "unregistered",
            },
        )
        targets.append(_collect_target(output_dir, target_info))
    return targets


def collect_environment(output_dir):
    report_dir = output_dir / "environment-report"
    manifest_path = report_dir / "artifacts.json"
    report_path = report_dir / "environment_report.html"
    result = {
        "status": "MISSING",
        "recorded_at": "-",
        "error": "尚未生成环境预检报告",
        "manifest_href": None,
        "report_href": (
            _relative_href(output_dir, report_path)
            if report_path.is_file()
            else None
        ),
    }
    if not manifest_path.is_file():
        return result

    result["manifest_href"] = _relative_href(output_dir, manifest_path)
    try:
        manifest = _load_json_object(manifest_path)
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("environment manifest schema_version 不受支持")
        if manifest.get("scope") != "environment":
            raise ValueError("environment manifest scope 不匹配")
        runs = manifest.get("runs")
        if not isinstance(runs, list):
            raise ValueError("environment manifest runs 必须是列表")
        if not runs:
            return result
        latest_run = runs[-1]
        status = latest_run.get("status")
        if status not in {"PASS", "WARN", "FAIL"}:
            raise ValueError("environment run status 非法")
    except (OSError, ValueError) as exc:
        result.update(
            {
                "status": "INVALID",
                "error": _clean_text(exc),
            }
        )
        return result

    result.update(
        {
            "status": str(status),
            "recorded_at": str(
                latest_run.get("recorded_at")
                or manifest.get("updated_at")
                or "-"
            ),
            "error": _clean_text(latest_run.get("error")) or "-",
        }
    )
    return result


def project_status(targets, environment):
    statuses = [target["status"] for target in targets]
    statuses.append(environment["status"])
    if any(status in FAILURE_STATUSES for status in statuses):
        return "FAIL"
    if any(status in WARNING_STATUSES for status in statuses):
        return "WARN"
    return "PASS"


def render_project_overview_markdown(
    output_dir,
    targets,
    environment,
    status,
    generated_at,
):
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


def _status_class(status):
    if status in FAILURE_STATUSES:
        return "fail"
    if status == "PASS":
        return "pass"
    return "warn"


def _surface_html(surface):
    if surface["href"]:
        content = '<a href="{href}">{label}</a>'.format(
            href=html.escape(surface["href"], quote=True),
            label=html.escape(surface["label"]),
        )
    else:
        content = "<span>{}</span>".format(html.escape(surface["label"]))
    return (
        '<li class="{klass}">{content}<strong>{status}</strong></li>'.format(
            klass="ready" if surface["status"] == "READY" else "missing",
            content=content,
            status=surface["status"],
        )
    )


def render_project_overview_html(targets, environment, status, generated_at):
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


def _dashboard_surfaces(project_dir, reports_dir):
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
            }
            for path in paths
        ]
        surfaces.append(
            {
                "id": surface_id,
                "label": label,
                "status": "READY" if links else "MISSING",
                "links": links,
            }
        )
    return surfaces


def _dashboard_target_selector(agent, output_dir, current_target):
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


def _dashboard_runs(project_dir, target_name):
    manifest_path = project_dir / "artifacts.json"
    if not manifest_path.is_file():
        return []
    manifest = _load_json_object(manifest_path)
    return _validate_target_manifest(manifest, target_name)


def _dashboard_failure_href(project_dir, reports_dir):
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


def _dashboard_resources(reports_dir, extra_resources=None):
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
    target,
    selectors,
    surfaces,
    latest_run,
    last_failure,
    failure_href,
    resources,
):
    ready_stage_count = sum(
        surface["status"] == "READY"
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


def _dashboard_stage_html(surface):
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
            if surface["status"] == "READY"
            else "missing"
        ),
        stage=html.escape(surface["id"], quote=True),
        label=html.escape(surface["label"]),
        status=surface["status"],
        links=links,
    )


def _dashboard_html(
    target,
    selectors,
    surfaces,
    latest_run,
    last_failure,
    failure_href,
    resources,
):
    ready_stage_count = sum(
        surface["status"] == "READY"
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
    self,
    project_dir,
    extra_resources=None,
):
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
    target = _collect_target(output_dir, target_info)
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
    surfaces = _dashboard_surfaces(project_dir, reports_dir)
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
        surface["status"] == "READY"
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


def write_project_overview(self, output_dir="outputs"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = collect_targets(self, output_dir)
    environment = collect_environment(output_dir)
    status = project_status(targets, environment)
    generated_at = utc_timestamp()
    markdown_path = output_dir / "index.md"
    html_path = output_dir / "index.html"
    markdown_path.write_text(
        render_project_overview_markdown(
            output_dir,
            targets,
            environment,
            status,
            generated_at,
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        render_project_overview_html(
            targets,
            environment,
            status,
            generated_at,
        ),
        encoding="utf-8",
    )
    return {
        "status": status,
        "target_count": len(targets),
        "ready_target_count": sum(
            target["status"] == "PASS"
            for target in targets
        ),
        "failed_target_count": sum(
            target["status"] in FAILURE_STATUSES
            for target in targets
        ),
        "environment_status": environment["status"],
        "targets": targets,
        "environment": environment,
        "markdown_path": markdown_path,
        "html_path": html_path,
    }
