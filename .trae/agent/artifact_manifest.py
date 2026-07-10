import json
import platform
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from history_rotation import (
    DEFAULT_ACTIVE_RECORD_LIMIT,
    build_rotation_metadata,
    rotate_json_records,
)


SCHEMA_VERSION = 1
RUN_STATUSES = {"PASS", "FAIL"}
VIVADO_FLOWS = {
    "sim-rtl",
    "regress-rtl",
    "uvm-smoke",
    "uvm-coverage",
    "uvm-random-regress",
    "open-wave",
    "open-uvm-wave",
}
WAVEFORM_FLOWS = {"analyze-rtl-vcd"}


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


def normalize_json_value(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): normalize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [normalize_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def build_replay_command(flow, target_name, output_dir, options=None):
    options = dict(options or {})
    command = [
        sys.executable,
        ".trae/agent/agent.py",
        "--{}".format(flow),
        target_name,
        "--output-dir",
        str(output_dir),
    ]

    if options.get("open_wave_gui") is False:
        command.append("--no-wave-gui")
    option_flags = (
        ("limit", "--vcd-limit"),
        ("waveform_backend", "--wave-backend"),
        ("coverage_threshold", "--coverage-threshold"),
        ("coverage_percent", "--coverage-percent"),
        ("wave_kind", "--uvm-wave-kind"),
    )
    for option_name, flag in option_flags:
        value = options.get(option_name)
        if value is not None:
            command.extend([flag, str(value)])

    seeds = options.get("seeds")
    if seeds:
        command.extend(["--uvm-seeds", ",".join(str(seed) for seed in seeds)])

    description = options.get("description")
    requirement = options.get("requirement")
    if flow == "create-target" and description:
        command.append(str(description))
    if flow == "generate-spec" and requirement:
        command.append(str(requirement))
    return command


def extract_tool_version(command):
    if not command:
        return None
    match = re.search(r"(?<!\d)(20\d{2}\.\d+)(?!\d)", str(command))
    return match.group(1) if match else None


def collect_tools(agent, flow, options=None):
    tools = {
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        }
    }
    if flow in VIVADO_FLOWS:
        try:
            command = agent.resolve_vivado_command()
        except (OSError, ValueError):
            command = None
        tools["vivado"] = {
            "version": extract_tool_version(command),
            "command": command,
        }
    if flow in WAVEFORM_FLOWS:
        options = dict(options or {})
        tools["waveform"] = {
            "backend": options.get("waveform_backend", "auto"),
        }
    return tools


def artifact_status(declared_status, exists):
    if exists:
        return "PASS"
    if declared_status == "N/A":
        return "N/A"
    return "SKIP"


def build_artifact_entry(project_dir, artifact_id, relative_path, declared_status):
    artifact_path = project_dir / relative_path
    exists = artifact_path.exists()
    entry = {
        "id": str(artifact_id),
        "path": str(relative_path).replace("\\", "/"),
        "declared_status": str(declared_status),
        "status": artifact_status(str(declared_status), exists),
        "exists": exists,
    }
    if exists and artifact_path.is_file():
        entry["size_bytes"] = artifact_path.stat().st_size
    return entry


def normalize_extra_artifact(project_dir, item):
    artifact_path = Path(item["path"])
    if artifact_path.is_absolute():
        try:
            relative_path = artifact_path.resolve().relative_to(project_dir.resolve())
        except ValueError as exc:
            raise ValueError(
                "runtime artifact must be inside project directory: {}".format(
                    artifact_path
                )
            ) from exc
    else:
        relative_path = artifact_path
    return {
        "id": str(item.get("id") or relative_path.as_posix()),
        "path": relative_path,
        "status": str(item.get("status", "PASS")).upper(),
    }


def collect_artifacts(target_info, project_dir, extra_artifacts=None):
    artifacts = []
    seen_paths = set()
    for item in target_info.get("artifact_manifest", []):
        relative_path = Path(item["path"])
        entry = build_artifact_entry(
            project_dir,
            item["id"],
            relative_path,
            item["status"],
        )
        artifacts.append(entry)
        seen_paths.add(entry["path"])

    for raw_item in extra_artifacts or []:
        item = normalize_extra_artifact(project_dir, raw_item)
        relative_text = item["path"].as_posix()
        if relative_text in seen_paths:
            continue
        artifacts.append(
            build_artifact_entry(
                project_dir,
                item["id"],
                item["path"],
                item["status"],
            )
        )
        seen_paths.add(relative_text)
    return artifacts


def load_runtime_manifest(manifest_path, target_name):
    if not manifest_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "target": target_name,
            "updated_at": None,
            "runs": [],
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "invalid runtime artifact manifest JSON: {}".format(manifest_path)
        ) from exc
    if not isinstance(manifest, dict):
        raise ValueError("runtime artifact manifest must be an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported runtime artifact manifest schema")
    if manifest.get("target") != target_name:
        raise ValueError("runtime artifact manifest target mismatch")
    if not isinstance(manifest.get("runs"), list):
        raise ValueError("runtime artifact manifest runs must be a list")
    return manifest


def record_artifact_run(
    self,
    target,
    flow,
    output_dir="outputs",
    status="PASS",
    error=None,
    options=None,
    target_info=None,
    project_dir=None,
    extra_artifacts=None,
    command=None,
    max_active_runs=DEFAULT_ACTIVE_RECORD_LIMIT,
):
    status = str(status).upper()
    if status not in RUN_STATUSES:
        raise ValueError("invalid runtime flow status: {}".format(status))

    target_info = dict(target_info or self.get_target(target))
    target_name = target_info["name"]
    output_dir = Path(output_dir)
    project_dir = Path(project_dir or (output_dir / target_name))
    project_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project_dir / "artifacts.json"
    manifest = load_runtime_manifest(manifest_path, target_name)
    recorded_at = utc_timestamp()
    normalized_options = normalize_json_value(dict(options or {}))

    run = {
        "run_id": uuid.uuid4().hex,
        "flow": str(flow),
        "status": status,
        "recorded_at": recorded_at,
        "command": list(
            command
            or build_replay_command(
                str(flow),
                target_name,
                output_dir,
                options=normalized_options,
            )
        ),
        "options": normalized_options,
        "tools": collect_tools(self, str(flow), options=normalized_options),
        "artifacts": collect_artifacts(
            target_info,
            project_dir,
            extra_artifacts=extra_artifacts,
        ),
        "error": str(error) if error else None,
    }
    manifest["runs"].append(run)
    active_runs, archive_path, archived_runs = rotate_json_records(
        manifest["runs"],
        manifest_path,
        active_limit=max_active_runs,
    )
    manifest["runs"] = active_runs
    history = build_rotation_metadata(
        manifest.get("history"),
        active_limit=max_active_runs,
        archive_path=archive_path,
        newly_archived=archived_runs,
        count_key="archived_runs",
    )
    if history is None:
        manifest.pop("history", None)
    else:
        manifest["history"] = history
    manifest["updated_at"] = recorded_at
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path
