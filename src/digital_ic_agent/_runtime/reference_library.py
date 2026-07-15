from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import uuid
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from digital_ic_agent._runtime.design_workspace import (
    consume_reference_reminder,
)


REFERENCE_REMINDER = (
    "即将检索本地数字 IC 参考库。后续可将 RTL 或项目压缩包放入 "
    "references/inbox/rtl，将 UVM/SVA/验证代码放入 references/inbox/uvm，"
    "将论文放入 references/inbox/papers，将协议和芯片资料放入 "
    "references/inbox/specs，并将对应 LICENSE/NOTICE 放入 "
    "references/inbox/licenses。"
)
LAYOUT = {
    "rtl": Path("references/inbox/rtl"),
    "uvm": Path("references/inbox/uvm"),
    "papers": Path("references/inbox/papers"),
    "specs": Path("references/inbox/specs"),
    "licenses": Path("references/inbox/licenses"),
    "cache": Path("references/cache"),
    "index": Path("references/index"),
    "catalog": Path("references/catalog"),
}
LEGACY_INPUTS = ("OpenRTLSet-main.zip", "2606.10285v1.pdf")
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".tcl",
    ".py",
    ".v",
    ".sv",
    ".svh",
    ".vhd",
    ".vhdl",
}
RTL_SUFFIXES = {".v", ".sv", ".svh", ".vhd", ".vhdl"}
MAX_ARCHIVE_ENTRIES = 20_000
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 4 * 1024 * 1024
MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_SHOW_CHARS = 20_000
OPENHW_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
GITHUB_PROXY = "http://127.0.0.1:7897"
GitRunner = Callable[..., subprocess.CompletedProcess[str]]


class ReferenceLibraryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.replace(temporary, path)
    except OSError:
        if temporary.exists():
            temporary.unlink()
        raise


def ensure_reference_layout(workspace: Path) -> dict[str, str]:
    workspace = Path(workspace).resolve()
    directories = {name: workspace / relative for name, relative in LAYOUT.items()}
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return {name: str(path) for name, path in directories.items()}


def _reference_files(workspace: Path) -> list[Path]:
    workspace = Path(workspace).resolve()
    files: list[Path] = []
    for category in ("rtl", "uvm", "papers", "specs", "licenses"):
        root = workspace / LAYOUT[category]
        if root.is_dir():
            resolved_root = root.resolve()
            files.extend(
                path
                for path in root.rglob("*")
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and path.resolve().is_relative_to(resolved_root)
                )
            )
    files.extend(
        path
        for name in LEGACY_INPUTS
        if (path := workspace / name).is_file() and not path.is_symlink()
    )
    openhw_root = workspace / LAYOUT["cache"] / "openhwgroup"
    if openhw_root.is_dir():
        resolved_root = openhw_root.resolve()
        files.extend(
            path
            for path in openhw_root.rglob("*")
            if (
                path.is_file()
                and not path.is_symlink()
                and ".git" not in path.relative_to(openhw_root).parts
                and path.resolve().is_relative_to(resolved_root)
            )
        )
    return sorted(set(files), key=lambda path: str(path).casefold())


def _source_snapshot(workspace: Path) -> str:
    workspace = Path(workspace).resolve()
    payload = []
    for path in _reference_files(workspace):
        stat = path.stat()
        try:
            relative = path.relative_to(workspace).as_posix()
        except ValueError:
            relative = str(path)
        payload.append((relative, stat.st_size, stat.st_mtime_ns))
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _metadata_path(workspace: Path) -> Path:
    return Path(workspace).resolve() / LAYOUT["index"] / "index_metadata.json"


def _database_path(workspace: Path) -> Path:
    return Path(workspace).resolve() / LAYOUT["index"] / "references.sqlite3"


def _catalog_path(workspace: Path) -> Path:
    return Path(workspace).resolve() / LAYOUT["catalog"] / "catalog.json"


def _index_status(workspace: Path, snapshot: str) -> str:
    metadata_path = _metadata_path(workspace)
    database_path = _database_path(workspace)
    if not metadata_path.is_file() or not database_path.is_file():
        return "MISSING"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "STALE"
    return "CURRENT" if metadata.get("source_snapshot") == snapshot else "STALE"


def _is_license_file(path: Path) -> bool:
    name = path.name.casefold()
    return "license" in name or name.startswith("notice") or "copying" in name


def _associated_license(path: Path, license_files: list[Path]) -> str:
    source_stem = path.stem.casefold()
    for license_path in license_files:
        license_stem = license_path.stem.casefold()
        if (
            source_stem not in license_stem
            and license_path.parent != path.parent
            and license_path.parent not in path.parents
        ):
            continue
        if license_path.stat().st_size > MAX_TEXT_BYTES:
            continue
        detected = _detect_license(_decode_text(license_path.read_bytes()))
        if detected != "LICENSE_UNKNOWN":
            return detected
    return "LICENSE_UNKNOWN"


def reference_status(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    directories = ensure_reference_layout(workspace)
    files = _reference_files(workspace)
    content_files = [path for path in files if not _is_license_file(path)]
    license_files = [path for path in files if _is_license_file(path)]
    missing_licenses = 0
    for path in content_files:
        if path.suffix.casefold() == ".zip":
            try:
                has_license = bool(inspect_zip_archive(path)["has_repository_license"])
            except ReferenceLibraryError:
                has_license = False
            missing_licenses += int(not has_license)
        else:
            missing_licenses += int(
                _associated_license(path, license_files) == "LICENSE_UNKNOWN"
            )
    snapshot = _source_snapshot(workspace)
    legacy_inputs = [str(workspace / name) for name in LEGACY_INPUTS if (workspace / name).is_file()]
    reminder_required = consume_reference_reminder(workspace)
    return {
        "status": "REFERENCE_LIBRARY_EMPTY" if not content_files else "READY",
        "reference_reminder": REFERENCE_REMINDER,
        "reminder_required": reminder_required,
        "directories": directories,
        "file_count": len(content_files),
        "category_counts": {
            category: sum(
                1
                for path in content_files
                if (workspace / LAYOUT[category]) in path.parents
            )
            for category in ("rtl", "uvm", "papers", "specs")
        },
        "license_file_count": len(license_files),
        "license_missing_count": missing_licenses,
        "index_status": _index_status(workspace, snapshot),
        "source_snapshot": snapshot,
        "legacy_inputs": legacy_inputs,
    }


def _safe_member_name(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        path.is_absolute()
        or ".." in path.parts
        or (path.parts and ":" in path.parts[0])
    ):
        raise ReferenceLibraryError(
            "ARCHIVE_UNSAFE",
            f"Unsafe archive member path: {name}",
        )
    return path


def inspect_zip_archive(path: Path) -> dict[str, Any]:
    path = Path(path).resolve()
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise ReferenceLibraryError(
                    "ARCHIVE_LIMIT_EXCEEDED",
                    f"Archive contains too many entries: {path}",
                )
            total_bytes = 0
            rtl_entries = 0
            has_license = False
            oversized_entries = 0
            for entry in entries:
                member = _safe_member_name(entry.filename)
                if entry.flag_bits & 0x1:
                    raise ReferenceLibraryError(
                        "ARCHIVE_UNSAFE",
                        f"Encrypted archive member is not supported: {entry.filename}",
                    )
                oversized_entries += int(entry.file_size > MAX_MEMBER_BYTES)
                total_bytes += entry.file_size
                if total_bytes > MAX_ARCHIVE_BYTES:
                    raise ReferenceLibraryError(
                        "ARCHIVE_LIMIT_EXCEEDED",
                        f"Archive expands beyond the safety limit: {path}",
                    )
                rtl_entries += int(member.suffix.casefold() in RTL_SUFFIXES)
                has_license = has_license or _is_license_file(Path(member.name))
    except zipfile.BadZipFile as exc:
        raise ReferenceLibraryError("ARCHIVE_INVALID", f"Invalid ZIP archive: {path}") from exc
    except OSError as exc:
        raise ReferenceLibraryError("ARCHIVE_UNREADABLE", str(exc)) from exc
    return {
        "path": str(path),
        "entry_count": len(entries),
        "uncompressed_bytes": total_bytes,
        "rtl_entry_count": rtl_entries,
        "has_repository_license": has_license,
        "oversized_entry_count": oversized_entries,
        "executed": False,
        "extracted": False,
    }


def _decode_text(content: bytes) -> str:
    if b"\x00" in content:
        return ""
    return content.decode("utf-8", errors="replace")


def _detect_license(text: str) -> str:
    folded = text.casefold()
    if "apache license" in folded and "version 2.0" in folded:
        return "Apache-2.0"
    if "mit license" in folded:
        return "MIT"
    if "redistribution and use in source and binary forms" in folded:
        return "BSD"
    return "LICENSE_UNKNOWN"


def _language(path: str) -> str:
    suffix = Path(path).suffix.casefold()
    return {
        ".v": "verilog",
        ".sv": "systemverilog",
        ".svh": "systemverilog",
        ".vhd": "vhdl",
        ".vhdl": "vhdl",
        ".py": "python",
        ".md": "markdown",
        ".pdf": "pdf",
    }.get(suffix, "text")


def _rtl_metadata(text: str, language: str) -> tuple[str | None, str]:
    if language not in {"verilog", "systemverilog", "vhdl"}:
        return None, ""
    if language == "vhdl":
        match = re.search(r"(?im)^\s*entity\s+([A-Za-z_][A-Za-z0-9_]*)\s+is\b", text)
    else:
        match = re.search(r"(?m)\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)
    module = match.group(1) if match else None
    signals = re.findall(
        r"(?m)\b(?:input|output|inout)\b[^;\n]*?([A-Za-z_][A-Za-z0-9_]*)\s*(?:[,;\)])",
        text,
    )
    return module, ", ".join(dict.fromkeys(signals[:32]))


def _record(
    *,
    source: str,
    path: str,
    content: str,
    archive: str | None,
    license_id: str,
    imported_at: str,
    repository: str | None = None,
    commit: str | None = None,
) -> dict[str, Any]:
    encoded = content.encode("utf-8", errors="replace")
    sha256 = hashlib.sha256(encoded).hexdigest()
    language = _language(path)
    module, interface_summary = _rtl_metadata(content, language)
    record_key = json.dumps(
        (source, archive, repository, commit, path, sha256),
        separators=(",", ":"),
    )
    record_id = hashlib.sha256(record_key.encode()).hexdigest()[:24]
    return {
        "record_id": record_id,
        "source": source,
        "archive": archive,
        "repository": repository,
        "commit": commit,
        "path": path,
        "sha256": sha256,
        "license": license_id,
        "reuse_policy": "REUSE_ALLOWED" if license_id != "LICENSE_UNKNOWN" else "CONCEPT_ONLY",
        "language": language,
        "module": module,
        "interface_summary": interface_summary,
        "protocol": "",
        "imported_at": imported_at,
        "title": Path(path).name,
        "content": content[:MAX_SHOW_CHARS],
    }


def _read_file_record(
    path: Path,
    workspace: Path,
    license_id: str,
    imported_at: str,
    openhw_repositories: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    suffix = path.suffix.casefold()
    relative = path.relative_to(workspace).as_posix()
    if suffix == ".pdf":
        content = f"PDF reference: {path.name}"
    elif suffix in TEXT_SUFFIXES:
        if path.stat().st_size > MAX_TEXT_BYTES:
            raise ReferenceLibraryError("REFERENCE_FILE_TOO_LARGE", f"Reference file is too large: {path}")
        content = _decode_text(path.read_bytes())
    else:
        return None
    relative_parts = Path(relative).parts
    repository_record = None
    if relative_parts[:3] == ("references", "cache", "openhwgroup") and len(relative_parts) > 3:
        repository_record = openhw_repositories.get(relative_parts[3])
    return _record(
        source="openhwgroup" if repository_record is not None else "local-file",
        path=relative,
        content=content,
        archive=None,
        license_id=license_id,
        imported_at=imported_at,
        repository=(
            None if repository_record is None else str(repository_record["url"])
        ),
        commit=(
            None if repository_record is None else str(repository_record["commit"])
        ),
    )


def _read_zip_records(path: Path, workspace: Path, imported_at: str) -> list[dict[str, Any]]:
    inventory = inspect_zip_archive(path)
    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        repository_license = "LICENSE_UNKNOWN"
        for entry in archive.infolist():
            if entry.is_dir() or not _is_license_file(Path(entry.filename)):
                continue
            repository_license = _detect_license(_decode_text(archive.read(entry)))
            if repository_license != "LICENSE_UNKNOWN":
                break
        for entry in archive.infolist():
            member = _safe_member_name(entry.filename)
            if (
                entry.is_dir()
                or entry.file_size > MAX_MEMBER_BYTES
                or member.suffix.casefold() not in TEXT_SUFFIXES
            ):
                continue
            content = _decode_text(archive.read(entry))
            language = _language(member.as_posix())
            license_id = (
                "LICENSE_UNKNOWN"
                if language in {"verilog", "systemverilog", "vhdl"}
                else repository_license
            )
            records.append(
                _record(
                    source="legacy-archive" if path.name in LEGACY_INPUTS else "local-archive",
                    path=member.as_posix(),
                    content=content,
                    archive=str(path.relative_to(workspace)),
                    license_id=license_id,
                    imported_at=imported_at,
                )
            )
    if inventory["rtl_entry_count"] == 0 and path.name == "OpenRTLSet-main.zip":
        records.append(
            _record(
                source="archive-inventory",
                path="OpenRTLSet-main.zip#inventory",
                content="OpenRTLSet repository archive contains no RTL sample files.",
                archive=str(path.relative_to(workspace)),
                license_id="LICENSE_UNKNOWN",
                imported_at=imported_at,
            )
        )
    return records


def _collect_records(workspace: Path) -> list[dict[str, Any]]:
    workspace = Path(workspace).resolve()
    imported_at = _timestamp()
    files = _reference_files(workspace)
    license_files = [path for path in files if _is_license_file(path)]
    openhw_repositories: dict[str, dict[str, Any]] = {}
    openhw_catalog = _openhw_catalog_path(workspace)
    if openhw_catalog.is_file():
        try:
            catalog_payload = json.loads(openhw_catalog.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReferenceLibraryError(
                "OPENHW_CATALOG_INVALID",
                f"Invalid OpenHWGroup catalog: {openhw_catalog}",
            ) from exc
        for item in catalog_payload.get("repositories", []):
            if isinstance(item, dict) and isinstance(item.get("repository"), str):
                openhw_repositories[item["repository"]] = item
    records: list[dict[str, Any]] = []
    for path in files:
        if _is_license_file(path):
            continue
        if path.suffix.casefold() == ".zip":
            records.extend(_read_zip_records(path, workspace, imported_at))
            continue
        record = _read_file_record(
            path,
            workspace,
            _associated_license(path, license_files),
            imported_at,
            openhw_repositories,
        )
        if record is not None:
            records.append(record)
    return records


def _create_database(path: Path, records: list[dict[str, Any]]) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE records (
                record_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                archive TEXT,
                repository TEXT,
                commit_sha TEXT,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                license TEXT NOT NULL,
                reuse_policy TEXT NOT NULL,
                language TEXT NOT NULL,
                module TEXT,
                interface_summary TEXT NOT NULL,
                protocol TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        try:
            connection.execute(
                "CREATE VIRTUAL TABLE records_fts USING fts5("
                "record_id UNINDEXED, title, content, module, interface_summary, protocol)"
            )
        except sqlite3.OperationalError as exc:
            raise ReferenceLibraryError(
                "FTS5_UNAVAILABLE",
                "Python SQLite does not provide FTS5",
            ) from exc
        for record in records:
            connection.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["record_id"], record["source"], record["archive"],
                    record["repository"], record["commit"], record["path"],
                    record["sha256"], record["license"], record["reuse_policy"],
                    record["language"], record["module"], record["interface_summary"],
                    record["protocol"], record["imported_at"], record["title"],
                    record["content"],
                ),
            )
            connection.execute(
                "INSERT INTO records_fts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record["record_id"], record["title"], record["content"],
                    record["module"] or "", record["interface_summary"],
                    record["protocol"],
                ),
            )
        connection.commit()
    finally:
        connection.close()


def index_reference_library(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    status_before = reference_status(workspace)
    if status_before["status"] == "REFERENCE_LIBRARY_EMPTY":
        raise ReferenceLibraryError(
            "REFERENCE_LIBRARY_EMPTY",
            "Reference library is empty",
        )
    records = _collect_records(workspace)
    if not records:
        raise ReferenceLibraryError(
            "REFERENCE_LIBRARY_EMPTY",
            "Reference library contains no indexable records",
        )
    database_path = _database_path(workspace)
    temporary = database_path.with_name(
        f".{database_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        _create_database(temporary, records)
        os.replace(temporary, database_path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    snapshot = _source_snapshot(workspace)
    metadata = {
        "schema_version": "digital-ic-agent.reference-index.v1",
        "indexed_at": _timestamp(),
        "source_snapshot": snapshot,
        "record_count": len(records),
        "engine": "sqlite-fts5-bm25",
    }
    _atomic_write_json(_metadata_path(workspace), metadata)
    _atomic_write_json(
        _catalog_path(workspace),
        {
            "schema_version": "digital-ic-agent.reference-catalog.v1",
            "records": [
                {key: value for key, value in record.items() if key != "content"}
                for record in records
            ],
        },
    )
    return {
        "status": "CURRENT",
        "record_count": len(records),
        "engine": "sqlite-fts5-bm25",
        "database_path": str(database_path),
        "catalog_path": str(_catalog_path(workspace)),
        "source_snapshot": snapshot,
        "reference_status": status_before,
    }


def _require_current_index(workspace: Path) -> dict[str, Any]:
    status = reference_status(workspace)
    if status["index_status"] == "MISSING":
        raise ReferenceLibraryError("REFERENCE_INDEX_MISSING", "Reference index is missing")
    if status["index_status"] != "CURRENT":
        raise ReferenceLibraryError("REFERENCE_INDEX_STALE", "Reference index is stale")
    return status


def _row_payload(row: sqlite3.Row, *, include_content: bool) -> dict[str, Any]:
    payload = dict(row)
    if not include_content:
        payload.pop("content", None)
    return payload


def _openhw_catalog_path(workspace: Path) -> Path:
    return (
        Path(workspace).resolve()
        / LAYOUT["catalog"]
        / "openhwgroup-repositories.json"
    )


def search_references(workspace: Path, query: str, limit: int = 10) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    status = _require_current_index(workspace)
    terms = re.findall(r"[A-Za-z0-9_]+", query)
    if not terms:
        raise ReferenceLibraryError("REFERENCE_QUERY_INVALID", "Search query has no indexable terms")
    expression = " OR ".join(f'"{term}"' for term in terms)
    connection = sqlite3.connect(_database_path(workspace))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT records.*, bm25(records_fts) AS score
            FROM records_fts
            JOIN records ON records.record_id = records_fts.record_id
            WHERE records_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (expression, max(1, min(int(limit), 100))),
        ).fetchall()
    finally:
        connection.close()
    return {
        "query": query,
        "index_status": status["index_status"],
        "results": [_row_payload(row, include_content=False) for row in rows],
        "reference_status": status,
    }


def show_reference(workspace: Path, record_id: str) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    status = _require_current_index(workspace)
    connection = sqlite3.connect(_database_path(workspace))
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM records WHERE record_id = ?",
            (record_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ReferenceLibraryError(
            "REFERENCE_RECORD_NOT_FOUND",
            f"Reference record was not found: {record_id}",
        )
    return {
        "record": _row_payload(row, include_content=True),
        "index_status": status["index_status"],
        "reference_status": status,
    }


def fetch_openhw_repository(
    workspace: Path,
    repository: str,
    *,
    runner: GitRunner = subprocess.run,
) -> dict[str, Any]:
    from digital_ic_agent._runtime.openhw_reference import (
        fetch_openhw_repository as _fetch_openhw_repository,
    )

    return _fetch_openhw_repository(workspace, repository, runner=runner)
