from __future__ import annotations

import difflib
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict


class SourceRecord(TypedDict):
    path: str
    sha256: str
    size_bytes: int


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(content)
    try:
        os.replace(temporary, path)
    except OSError:
        if temporary.exists():
            temporary.unlink()
        raise


def atomic_write_text(path: Path, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def file_summary(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {
        "path": str(path),
        "sha256": sha256(content),
        "size_bytes": len(content),
    }


def collect_intent_hashes(workspace: Path) -> tuple[dict[str, str], str]:
    paths = {
        "design_intent": workspace / "contracts" / "design_intent.json",
        "verification_intent": workspace / "contracts" / "verification_intent.json",
    }
    hashes = {name: sha256(path.read_bytes()) for name, path in paths.items()}
    combined = hashlib.sha256()
    for name in sorted(hashes):
        combined.update(name.encode("utf-8"))
        combined.update(hashes[name].encode("ascii"))
    return hashes, combined.hexdigest()


def progress_signature(intent_sha256: str, records: list[SourceRecord]) -> str:
    digest = hashlib.sha256(intent_sha256.encode("ascii"))
    for record in records:
        digest.update(record["path"].encode("utf-8"))
        digest.update(record["sha256"].encode("ascii"))
    return digest.hexdigest()


def existing_iteration(workspace: Path, state_iteration: object) -> int:
    value = state_iteration if isinstance(state_iteration, int) else 0
    for path in (workspace / "iterations").glob("[0-9][0-9][0-9][0-9]"):
        if path.is_dir() and path.name.isdigit():
            value = max(value, int(path.name))
    return value


def _previous_iteration_dir(workspace: Path, iteration: int) -> Path | None:
    for candidate in range(iteration - 1, 0, -1):
        path = workspace / "iterations" / f"{candidate:04d}"
        if path.is_dir():
            return path
    return None


def write_source_snapshot_and_diff(
    workspace: Path,
    iteration_dir: Path,
    iteration: int,
    records: list[SourceRecord],
    contents: dict[str, bytes],
) -> Path:
    snapshot_dir = iteration_dir / "sources"
    for relative, content in contents.items():
        atomic_write_bytes(snapshot_dir / relative, content)

    previous_dir = _previous_iteration_dir(workspace, iteration)
    previous_records: dict[str, bytes] = {}
    if previous_dir is not None:
        previous_metadata_path = previous_dir / "iteration.json"
        if previous_metadata_path.is_file():
            try:
                previous_metadata = json.loads(
                    previous_metadata_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                previous_metadata = {}
            for raw_record in previous_metadata.get("sources", []):
                if not isinstance(raw_record, dict) or not isinstance(
                    raw_record.get("path"), str
                ):
                    continue
                relative = raw_record["path"]
                snapshot = previous_dir / "sources" / relative
                if snapshot.is_file():
                    previous_records[relative] = snapshot.read_bytes()

    diff_lines: list[str] = []
    current_paths = {record["path"] for record in records}
    for relative in sorted(current_paths | set(previous_records)):
        before = previous_records.get(relative, b"").decode(
            "utf-8", errors="replace"
        ).splitlines()
        after = contents.get(relative, b"").decode(
            "utf-8", errors="replace"
        ).splitlines()
        if before == after:
            continue
        diff_lines.extend(
            difflib.unified_diff(
                before,
                after,
                fromfile=(f"a/{relative}" if relative in previous_records else "/dev/null"),
                tofile=(f"b/{relative}" if relative in contents else "/dev/null"),
                lineterm="",
            )
        )
    diff_path = iteration_dir / "source.diff"
    atomic_write_text(diff_path, "\n".join(diff_lines) + ("\n" if diff_lines else ""))
    return diff_path


def same_failed_progress_count(workspace: Path, signature: str) -> int:
    count = 0
    paths = sorted(
        (
            path
            for path in (workspace / "iterations").glob("[0-9][0-9][0-9][0-9]")
            if path.is_dir()
        ),
        reverse=True,
    )
    for path in paths:
        metadata_path = path / "iteration.json"
        if not metadata_path.is_file():
            break
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            break
        verdict = metadata.get("verdict")
        if (
            metadata.get("progress_signature") != signature
            or not isinstance(verdict, dict)
            or verdict.get("status") != "FAIL"
        ):
            break
        count += 1
    return count
