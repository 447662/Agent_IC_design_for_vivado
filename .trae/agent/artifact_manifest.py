from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict, cast
import hashlib
import json
import os
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


RunStatus = Literal["PASS", "FAIL"]
ArtifactStatus = Literal["CURRENT", "MISSING", "N/A", "STALE"]


class ArtifactFingerprint(TypedDict):
    sha256: str
    size_bytes: int
    created_at: str
    modified_at: str


class ArtifactEntry(ArtifactFingerprint, total=False):
    id: str
    path: str
    declared_status: str
    status: ArtifactStatus
    exists: bool
    observed_at: str
    produced_by_run_id: str | None


class RuntimeRun(TypedDict):
    run_id: str
    flow: str
    status: RunStatus
    recorded_at: str
    command: list[str]
    command_digest: str
    options: dict[str, Any]
    tools: dict[str, dict[str, Any]]
    input_files: dict[str, ArtifactFingerprint]
    input_digest: str
    artifacts: list[ArtifactEntry]
    error: str | None


class RotationHistory(TypedDict):
    active_limit: int
    archive_path: str
    archived_runs: int


class RuntimeManifest(TypedDict):
    schema_version: int
    target: str
    updated_at: str | None
    runs: list[RuntimeRun]
    history: NotRequired[RotationHistory]


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
INPUT_FILE_SUFFIXES = {
    ".json",
    ".sv",
    ".tcl",
    ".v",
    ".vhd",
    ".vhdl",
    ".xdc",
}
INPUT_EXCLUDED_DIRECTORIES = {
    ".git",
    ".xil",
    "__pycache__",
    "reports",
    "xsim.dir",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


def normalize_json_value(value: Any) -> Any:
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


def build_replay_command(flow: Any, target_name: Any, output_dir: Any, options: Any=None) -> Any:
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


def extract_tool_version(command: Any) -> Any:
    if not command:
        return None
    match = re.search(r"(?<!\d)(20\d{2}\.\d+)(?!\d)", str(command))
    return match.group(1) if match else None


def collect_tools(agent: Any, flow: Any, options: Any=None) -> Any:
    tools = {
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        }
    }
    if flow in VIVADO_FLOWS:
        try:
            command = agent.resolve_vivado_command()
        except (AttributeError, OSError, ValueError):
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


def json_digest(value: Any) -> Any:
    encoded = json.dumps(
        normalize_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp_from_epoch(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def file_fingerprint(path: str | Path) -> ArtifactFingerprint:
    path = Path(path)
    stat = path.stat()
    return {
        "sha256": file_digest(path),
        "size_bytes": stat.st_size,
        "created_at": _timestamp_from_epoch(stat.st_ctime),
        "modified_at": _timestamp_from_epoch(stat.st_mtime),
    }


def snapshot_project_artifacts(project_dir: str | Path) -> dict[str, ArtifactFingerprint]:
    project_root = Path(project_dir).resolve()
    if not project_root.is_dir():
        return {}
    snapshot = {}
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(project_root).as_posix()
        if (
            relative_path == "artifacts.json"
            or relative_path == "artifacts.archive.jsonl.gz"
            or relative_path.startswith(".artifacts.json.")
        ):
            continue
        snapshot[relative_path] = file_fingerprint(path)
    return snapshot


def snapshot_project_inputs(project_dir: Any) -> Any:
    project_root = Path(project_dir).resolve()
    if not project_root.is_dir():
        return {}
    snapshot = {}
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(project_root)
        relative_text = relative_path.as_posix()
        if any(
            part.lower() in INPUT_EXCLUDED_DIRECTORIES
            for part in relative_path.parts[:-1]
        ):
            continue
        if relative_text == "artifacts.json":
            continue
        if path.suffix.lower() not in INPUT_FILE_SUFFIXES:
            continue
        snapshot[relative_text] = file_fingerprint(path)
    return snapshot


def input_file_digest_payload(input_files: Any) -> Any:
    return {
        str(path).replace("\\", "/"): {
            "sha256": fingerprint.get("sha256"),
            "size_bytes": fingerprint.get("size_bytes"),
        }
        for path, fingerprint in sorted(dict(input_files or {}).items())
    }


def build_run_input_digest(options: Any, command: Any, tools: Any, input_files: Any) -> Any:
    return json_digest(
        {
            "options": normalize_json_value(dict(options or {})),
            "command": normalize_json_value(list(command or [])),
            "tools": normalize_json_value(dict(tools or {})),
            "input_files": input_file_digest_payload(input_files),
        }
    )


def artifact_status(declared_status: str, exists: bool, is_current: bool = False) -> ArtifactStatus:
    if declared_status == "N/A":
        return "N/A"
    if not exists:
        return "MISSING"
    return "CURRENT" if is_current else "STALE"


def normalize_artifact_path(project_dir: Any, artifact_path: Any) -> Any:
    project_root = Path(project_dir).resolve()
    artifact_path = Path(artifact_path)
    resolved_path = (
        artifact_path.resolve()
        if artifact_path.is_absolute()
        else (project_root / artifact_path).resolve()
    )
    try:
        return resolved_path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(
            "runtime artifact must be inside project directory: {}".format(
                artifact_path
            )
        ) from exc


def build_artifact_entry(
    project_dir: Any,
    artifact_id: Any,
    relative_path: Any,
    declared_status: Any,
    run_id: Any,
    observed_at: Any,
    baseline: Any=None,
    run_status: Any="PASS",
) -> Any:
    project_dir = Path(project_dir).resolve()
    relative_path = normalize_artifact_path(project_dir, relative_path)
    artifact_path = project_dir / relative_path
    exists = artifact_path.is_file()
    fingerprint = file_fingerprint(artifact_path) if exists else None
    baseline = dict(baseline or {})
    baseline_digest = baseline.get("sha256")
    if fingerprint is None:
        is_current = False
    else:
        is_current = bool(
            (baseline_digest is None and not baseline)
            or (
                baseline_digest is not None
                and fingerprint["sha256"] != baseline_digest
            )
        )
    if run_status != "PASS" and not baseline:
        is_current = False
    entry = {
        "id": str(artifact_id),
        "path": str(relative_path).replace("\\", "/"),
        "declared_status": str(declared_status),
        "status": artifact_status(
            str(declared_status),
            exists,
            is_current=is_current,
        ),
        "exists": exists,
        "observed_at": observed_at,
        "produced_by_run_id": run_id if is_current else None,
    }
    if fingerprint is not None:
        entry.update(fingerprint)
    return entry


def normalize_extra_artifact(project_dir: Any, item: Any) -> Any:
    artifact_path = Path(item["path"])
    relative_path = normalize_artifact_path(project_dir, artifact_path)
    return {
        "id": str(item.get("id") or relative_path.as_posix()),
        "path": relative_path,
        "status": str(item.get("status", "PASS")).upper(),
    }


def collect_artifacts(
    target_info: Any,
    project_dir: Any,
    run_id: Any,
    observed_at: Any,
    run_status: Any,
    baseline: Any=None,
    extra_artifacts: Any=None,
) -> Any:
    artifacts = []
    seen_paths = set()
    baseline = dict(baseline or {})
    for item in target_info.get("artifact_manifest", []):
        relative_path = Path(item["path"])
        relative_text = relative_path.as_posix()
        entry = build_artifact_entry(
            project_dir,
            item["id"],
            relative_path,
            item["status"],
            run_id,
            observed_at,
            baseline=baseline.get(relative_text),
            run_status=run_status,
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
                run_id,
                observed_at,
                baseline=baseline.get(relative_text),
                run_status=run_status,
            )
        )
        seen_paths.add(relative_text)
    return artifacts


def _latest_artifact_snapshot(manifest: Any) -> Any:
    runs = manifest.get("runs", [])
    if not runs:
        return {}
    snapshot = {}
    for item in runs[-1].get("artifacts", []):
        if not item.get("exists"):
            continue
        path = str(item.get("path", "")).replace("\\", "/")
        if not path:
            continue
        snapshot[path] = {
            "sha256": item.get("sha256"),
            "size_bytes": item.get("size_bytes"),
            "created_at": item.get("created_at"),
            "modified_at": item.get("modified_at"),
            "produced_by_run_id": item.get("produced_by_run_id"),
        }
    return snapshot


def atomic_write_json(path: Any, value: Any) -> Any:
    path = Path(path)
    temporary_path = path.with_name(
        ".{}.{}.tmp".format(path.name, uuid.uuid4().hex)
    )
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def load_runtime_manifest(manifest_path: Path, target_name: str) -> RuntimeManifest:
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
    return cast(RuntimeManifest, manifest)


def record_artifact_run(
    self: Any,
    target: Any,
    flow: Any,
    output_dir: Any="outputs",
    status: Any="PASS",
    error: Any=None,
    options: Any=None,
    target_info: Any=None,
    project_dir: Any=None,
    extra_artifacts: Any=None,
    command: Any=None,
    artifact_snapshot: Any=None,
    max_active_runs: Any=DEFAULT_ACTIVE_RECORD_LIMIT,
) -> Any:
    status = str(status).upper()
    if status not in RUN_STATUSES:
        raise ValueError("invalid runtime flow status: {}".format(status))

    target_info = dict(target_info or self.get_target(target))
    target_name = str(target_info["name"])
    output_dir = Path(output_dir)
    project_dir = Path(project_dir or (output_dir / target_name))
    project_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project_dir / "artifacts.json"
    manifest = load_runtime_manifest(manifest_path, target_name)
    recorded_at = utc_timestamp()
    normalized_options = normalize_json_value(dict(options or {}))
    run_id = uuid.uuid4().hex
    replay_command = list(
        command
        or build_replay_command(
            str(flow),
            target_name,
            output_dir,
            options=normalized_options,
        )
    )
    tools = collect_tools(self, str(flow), options=normalized_options)
    input_files = snapshot_project_inputs(project_dir)
    baseline = (
        dict(artifact_snapshot)
        if artifact_snapshot is not None
        else _latest_artifact_snapshot(manifest)
    )

    run = cast(RuntimeRun, {
        "run_id": run_id,
        "flow": str(flow),
        "status": cast(RunStatus, status),
        "recorded_at": recorded_at,
        "command": replay_command,
        "command_digest": json_digest(replay_command),
        "options": normalized_options,
        "tools": tools,
        "input_files": input_files,
        "input_digest": build_run_input_digest(
            normalized_options,
            replay_command,
            tools,
            input_files,
        ),
        "artifacts": collect_artifacts(
            target_info,
            project_dir,
            run_id,
            recorded_at,
            status,
            baseline=baseline,
            extra_artifacts=extra_artifacts,
        ),
        "error": str(error) if error else None,
    })
    manifest["runs"].append(run)
    active_runs, archive_path, archived_runs = rotate_json_records(
        manifest["runs"],
        manifest_path,
        active_limit=max_active_runs,
    )
    manifest["runs"] = cast(list[RuntimeRun], active_runs)
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
        manifest["history"] = cast(RotationHistory, history)
    manifest["updated_at"] = recorded_at
    atomic_write_json(manifest_path, manifest)
    return manifest_path
