import json
import os
from pathlib import Path
from typing import Any

from digital_ic_agent._runtime.artifact_manifest import (
    build_run_input_digest,
    collect_tools,
    file_digest,
    snapshot_project_inputs,
)


SCHEMA_VERSION = 1
FAILURE_STATUSES = {"FAIL", "INVALID"}
WARNING_STATUSES = {"WARN", "MISSING", "NOT_RUN", "STALE"}
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


def _clean_text(value: Any) -> Any:
    return " ".join(str(value or "").split())


def _markdown_text(value: Any) -> Any:
    return _clean_text(value).replace("|", "\\|")


def _relative_href(output_dir: Any, path: Any) -> Any:
    return Path(path).resolve().relative_to(Path(output_dir).resolve()).as_posix()


def _relative_from(base_dir: Any, path: Any) -> Any:
    return Path(
        os.path.relpath(
            Path(path).resolve(),
            Path(base_dir).resolve(),
        )
    ).as_posix()


def _load_json_object(path: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("manifest JSON 无效: {}".format(path)) from exc
    if not isinstance(value, dict):
        raise ValueError("manifest 必须是 JSON object: {}".format(path))
    return value


def _validate_target_manifest(manifest: Any, target_name: Any) -> Any:
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


def _target_surface_path(project_dir: Any, surface_id: Any, candidates: Any) -> Any:
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


def _latest_artifact_map(runs: Any) -> Any:
    if not runs:
        return {}
    return {
        str(item.get("path", "")).replace("\\", "/"): item
        for item in runs[-1].get("artifacts", [])
        if item.get("path")
    }


def _artifact_file_status(project_dir: Any, path: Any, artifact_map: Any) -> Any:
    if path is None:
        return "MISSING"
    if not artifact_map:
        return "READY"
    relative_path = path.resolve().relative_to(project_dir.resolve()).as_posix()
    artifact = artifact_map.get(relative_path)
    if artifact is None:
        return "INVALID"
    recorded_status = str(artifact.get("status", "INVALID"))
    if recorded_status == "CURRENT":
        recorded_digest = artifact.get("sha256")
        if not recorded_digest:
            return "INVALID"
        try:
            return (
                "CURRENT"
                if file_digest(path) == recorded_digest
                else "INVALID"
            )
        except OSError:
            return "INVALID"
    if recorded_status in {"STALE", "MISSING", "INVALID", "N/A"}:
        return recorded_status
    return "INVALID"


def _apply_input_state(status: Any, input_state: Any) -> Any:
    if input_state == "STALE" and status in {"CURRENT", "READY"}:
        return "STALE"
    return status


def _collect_surfaces(
    output_dir: Any,
    project_dir: Any,
    artifact_map: Any=None,
    input_state: Any=None,
) -> Any:
    artifact_map = dict(artifact_map or {})
    surfaces = []
    for surface_id, label, candidates in REPORT_SURFACES:
        path = _target_surface_path(project_dir, surface_id, candidates)
        surfaces.append(
            {
                "id": surface_id,
                "label": label,
                "status": _apply_input_state(
                    _artifact_file_status(
                        project_dir,
                        path,
                        artifact_map,
                    ),
                    input_state,
                ),
                "href": _relative_href(output_dir, path) if path else None,
            }
        )
    return surfaces


def _latest_flow_statuses(runs: Any) -> Any:
    statuses = {}
    for run in runs:
        statuses[str(run["flow"])] = str(run["status"])
    return statuses


def _run_input_state(agent: Any, project_dir: Any, run: Any) -> Any:
    if agent is None:
        return None
    recorded_digest = run.get("input_digest")
    recorded_files = run.get("input_files")
    if not recorded_digest or not isinstance(recorded_files, dict):
        return None
    try:
        options = dict(run.get("options") or {})
        command = list(run.get("command") or [])
        tools = collect_tools(agent, str(run["flow"]), options=options)
        current_digest = build_run_input_digest(
            options,
            command,
            tools,
            snapshot_project_inputs(project_dir),
        )
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return "INVALID"
    return "CURRENT" if current_digest == recorded_digest else "STALE"


def _collect_target(output_dir: Any, target_info: Any, agent: Any=None) -> Any:
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
    input_state = _run_input_state(agent, project_dir, latest_run)
    result["surfaces"] = _collect_surfaces(
        output_dir,
        project_dir,
        _latest_artifact_map(runs),
        input_state=input_state,
    )
    flow_statuses = _latest_flow_statuses(runs)
    target_status = (
        "FAIL"
        if any(status == "FAIL" for status in flow_statuses.values())
        else "PASS"
    )
    if target_status == "PASS" and input_state in {"STALE", "INVALID"}:
        target_status = input_state
    result.update(
        {
            "status": target_status,
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
            "input_state": input_state,
        }
    )
    return result


def _format_command(command: Any) -> Any:
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    if command:
        return str(command)
    return "-"


def _registered_target_map(agent: Any) -> Any:
    return {
        str(item["name"]): dict(item)
        for item in agent.list_targets()
    }


def _discover_target_names(output_dir: Any) -> Any:
    names: set[str] = set()
    if not output_dir.is_dir():
        return names
    for manifest_path in output_dir.glob("*/artifacts.json"):
        if manifest_path.parent.name != "environment-report":
            names.add(manifest_path.parent.name)
    return names


def collect_targets(agent: Any, output_dir: Any) -> Any:
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
        targets.append(_collect_target(output_dir, target_info, agent=agent))
    return targets


def collect_environment(output_dir: Any) -> Any:
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


def project_status(targets: Any, environment: Any) -> Any:
    statuses = [target["status"] for target in targets]
    statuses.append(environment["status"])
    if any(status in FAILURE_STATUSES for status in statuses):
        return "FAIL"
    if any(status in WARNING_STATUSES for status in statuses):
        return "WARN"
    return "PASS"
