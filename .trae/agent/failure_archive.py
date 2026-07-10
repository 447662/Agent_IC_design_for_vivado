import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


SCHEMA_VERSION = 1


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


def safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    if not segment:
        raise ValueError("archive path segment must not be empty")
    return segment


def powershell_argument(value: str) -> str:
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9._:/\\-]+", text):
        return text
    return "'{}'".format(text.replace("'", "''"))


def command_text(command: Sequence[str]) -> str:
    return " ".join(powershell_argument(part) for part in command)


def copy_artifact(
    archive_dir: Path,
    artifact: Mapping[str, object],
) -> dict[str, object]:
    role = safe_segment(str(artifact.get("role", "")))
    raw_path = artifact.get("path")
    if raw_path is None:
        raise ValueError("archive artifact path is required")
    source_path = Path(str(raw_path))
    target_path = archive_dir / "artifacts" / role / source_path.name
    available = source_path.exists()
    archive_path = None
    size_bytes = None

    if available:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_dir():
            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, target_path)
            size_bytes = target_path.stat().st_size
        archive_path = target_path.relative_to(archive_dir).as_posix()

    entry: dict[str, object] = {
        "role": role,
        "source_path": str(source_path),
        "archive_path": archive_path,
        "available": available,
    }
    if size_bytes is not None:
        entry["size_bytes"] = size_bytes
    return entry


def write_command_script(path: Path, command: Sequence[str], description: str) -> Path:
    path.write_text(
        "\n".join(
            [
                "# {}".format(description),
                "$ErrorActionPreference = \"Stop\"",
                command_text(command),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def archive_failed_run(
    archive_root: Path | str,
    *,
    target_name: str,
    flow_name: str,
    run_id: str,
    status: str,
    seed: int | None,
    artifacts: Iterable[Mapping[str, object]],
    reproduce_command: Sequence[str],
    wave_open_command: Sequence[str] | None = None,
) -> dict[str, Path]:
    archive_dir = (
        Path(archive_root)
        / safe_segment(flow_name)
        / safe_segment(run_id)
    )
    archive_dir.mkdir(parents=True, exist_ok=True)

    artifact_entries = [
        copy_artifact(archive_dir, artifact)
        for artifact in artifacts
    ]
    reproduce_parts = [str(part) for part in reproduce_command]
    wave_open_parts = (
        [str(part) for part in wave_open_command]
        if wave_open_command is not None
        else None
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": utc_timestamp(),
        "target_name": str(target_name),
        "flow_name": str(flow_name),
        "run_id": str(run_id),
        "status": str(status).upper(),
        "seed": None if seed is None else int(seed),
        "artifacts": artifact_entries,
        "reproduce_command": reproduce_parts,
        "wave_open_command": wave_open_parts,
    }
    manifest_path = archive_dir / "failure_archive.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    reproduce_script_path = write_command_script(
        archive_dir / "reproduce.ps1",
        reproduce_parts,
        "Reproduce archived failed run",
    )
    wave_open_script_path = archive_dir / "open_wave.ps1"
    if wave_open_parts is not None:
        write_command_script(
            wave_open_script_path,
            wave_open_parts,
            "Open waveform for archived failed run",
        )

    available_count = sum(
        1 for item in artifact_entries if item["available"]
    )
    readme_lines = [
        "# 失败运行归档",
        "",
        "- Target：`{}`".format(target_name),
        "- Flow：`{}`".format(flow_name),
        "- Run ID：`{}`".format(run_id),
        "- Status：`{}`".format(str(status).upper()),
        "- Seed：{}".format("-" if seed is None else seed),
        "- 可用材料：{}/{}".format(available_count, len(artifact_entries)),
        "",
        "## 重跑命令",
        "",
        "```powershell",
        command_text(reproduce_parts),
        "```",
    ]
    if wave_open_parts is not None:
        readme_lines.extend(
            [
                "",
                "## 打开波形",
                "",
                "```powershell",
                command_text(wave_open_parts),
                "```",
            ]
        )
    readme_lines.extend(
        [
            "",
            "## 材料",
            "",
            "| Role | Available | Archive Path |",
            "|---|---|---|",
        ]
    )
    for item in artifact_entries:
        readme_lines.append(
            "| {role} | {available} | `{archive_path}` |".format(
                role=item["role"],
                available="YES" if item["available"] else "NO",
                archive_path=item["archive_path"] or "-",
            )
        )
    readme_path = archive_dir / "README.md"
    readme_path.write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    result = {
        "archive_dir": archive_dir,
        "manifest_path": manifest_path,
        "reproduce_script_path": reproduce_script_path,
        "readme_path": readme_path,
    }
    if wave_open_parts is not None:
        result["wave_open_script_path"] = wave_open_script_path
    return result
