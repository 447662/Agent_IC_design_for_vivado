from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from digital_ic_agent._runtime.reference_library import (
    GITHUB_PROXY,
    LAYOUT,
    MAX_TEXT_BYTES,
    OPENHW_REPOSITORY_PATTERN,
    GitRunner,
    ReferenceLibraryError,
    _atomic_write_json,
    _decode_text,
    _detect_license,
    _openhw_catalog_path,
    _timestamp,
    ensure_reference_layout,
)


def _run_git(
    runner: GitRunner,
    command: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except OSError as exc:
        raise ReferenceLibraryError("GIT_UNAVAILABLE", str(exc)) from exc


def _is_connection_failure(result: subprocess.CompletedProcess[str]) -> bool:
    text = "\n".join((result.stdout or "", result.stderr or "")).casefold()
    return any(
        marker in text
        for marker in (
            "could not resolve host",
            "failed to connect",
            "connection timed out",
            "connection was reset",
            "network is unreachable",
        )
    )


def _record_openhw_repository(workspace: Path, record: dict[str, Any]) -> None:
    catalog_path = _openhw_catalog_path(workspace)
    if catalog_path.is_file():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReferenceLibraryError(
                "OPENHW_CATALOG_INVALID",
                f"Invalid OpenHWGroup catalog: {catalog_path}",
            ) from exc
    else:
        catalog = {
            "schema_version": "digital-ic-agent.openhw-catalog.v1",
            "repositories": [],
        }
    repositories = catalog.get("repositories")
    if not isinstance(repositories, list):
        raise ReferenceLibraryError(
            "OPENHW_CATALOG_INVALID",
            f"Invalid OpenHWGroup catalog: {catalog_path}",
        )
    repositories[:] = [
        item
        for item in repositories
        if not isinstance(item, dict) or item.get("repository") != record["repository"]
    ]
    repositories.append(record)
    _atomic_write_json(catalog_path, catalog)


def _openhw_provenance(
    workspace: Path,
    repository: str,
    cache_path: Path,
    runner: GitRunner,
    *,
    proxy_retry: bool,
    cached: bool,
) -> dict[str, Any]:
    commit_result = _run_git(
        runner,
        ["git", "-C", str(cache_path), "rev-parse", "HEAD"],
    )
    remote_result = _run_git(
        runner,
        ["git", "-C", str(cache_path), "remote", "get-url", "origin"],
    )
    if commit_result.returncode != 0 or remote_result.returncode != 0:
        raise ReferenceLibraryError(
            "OPENHW_PROVENANCE_FAILED",
            "Unable to read OpenHWGroup repository provenance",
        )
    commit = (commit_result.stdout or "").strip()
    expected_url = f"https://github.com/openhwgroup/{repository}.git"
    remote_url = (remote_result.stdout or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{40}", commit) is None or remote_url != expected_url:
        raise ReferenceLibraryError(
            "OPENHW_PROVENANCE_INVALID",
            "OpenHWGroup repository provenance did not match the requested source",
        )
    license_id = "LICENSE_UNKNOWN"
    for license_path in sorted(cache_path.glob("LICENSE*")):
        if license_path.is_file() and license_path.stat().st_size <= MAX_TEXT_BYTES:
            license_id = _detect_license(_decode_text(license_path.read_bytes()))
            if license_id != "LICENSE_UNKNOWN":
                break
    notice_present = any(path.is_file() for path in cache_path.glob("NOTICE*"))
    record = {
        "repository": repository,
        "url": expected_url,
        "commit": commit.lower(),
        "cache_path": str(cache_path),
        "license": license_id,
        "notice_present": notice_present,
        "fetched_at": _timestamp(),
        "cached": cached,
        "proxy_retry": proxy_retry,
        "executed_repository_code": False,
    }
    _record_openhw_repository(workspace, record)
    return record


def fetch_openhw_repository(
    workspace: Path,
    repository: str,
    *,
    runner: GitRunner = subprocess.run,
) -> dict[str, Any]:
    if OPENHW_REPOSITORY_PATTERN.fullmatch(repository or "") is None:
        raise ReferenceLibraryError(
            "OPENHW_REPOSITORY_INVALID",
            "OpenHWGroup repository must be a simple repository name",
        )
    workspace = Path(workspace).resolve()
    ensure_reference_layout(workspace)
    cache_path = workspace / LAYOUT["cache"] / "openhwgroup" / repository
    expected_url = f"https://github.com/openhwgroup/{repository}.git"
    if cache_path.exists():
        if not cache_path.is_dir():
            raise ReferenceLibraryError(
                "OPENHW_CACHE_CONFLICT",
                f"OpenHWGroup cache path is not a directory: {cache_path}",
            )
        return _openhw_provenance(
            workspace,
            repository,
            cache_path,
            runner,
            proxy_retry=False,
            cached=True,
        )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    clone_arguments = [
        "clone",
        "--depth",
        "1",
        "--single-branch",
        "--filter=blob:none",
        expected_url,
        str(cache_path),
    ]
    result = _run_git(runner, ["git", *clone_arguments])
    proxy_retry = False
    if result.returncode != 0 and _is_connection_failure(result):
        if cache_path.exists():
            raise ReferenceLibraryError(
                "OPENHW_CLONE_PARTIAL",
                "Git left a partial cache directory; it was preserved for inspection",
            )
        proxy_retry = True
        result = _run_git(
            runner,
            [
                "git",
                "-c",
                f"http.proxy={GITHUB_PROXY}",
                "-c",
                f"https.proxy={GITHUB_PROXY}",
                *clone_arguments,
            ],
        )
    if result.returncode != 0:
        raise ReferenceLibraryError(
            "OPENHW_CLONE_FAILED",
            (result.stderr or result.stdout or "git clone failed").strip(),
        )
    return _openhw_provenance(
        workspace,
        repository,
        cache_path,
        runner,
        proxy_retry=proxy_retry,
        cached=False,
    )
