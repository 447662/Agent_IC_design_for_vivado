from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


STATE_SCHEMA_VERSION = "digital-ic-agent.state.v1"
WORKSPACE_DIRECTORIES = (
    "contracts",
    "rtl",
    "uvm",
    "sim",
    "reports",
    "iterations",
)


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


def initialize_workspace(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    for relative in WORKSPACE_DIRECTORIES:
        (workspace / relative).mkdir(parents=True, exist_ok=True)
    state_path = workspace / ".digital_ic_agent" / "state.json"
    already_initialized = state_path.is_file()
    if already_initialized:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        now = _timestamp()
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "workspace_id": uuid.uuid4().hex,
            "created_at": now,
            "updated_at": now,
            "stage": "INITIALIZED",
            "status": "READY",
            "iteration": 0,
            "last_successful_stage": "INITIALIZED",
            "reference_reminder_shown": False,
        }
        _atomic_write_json(state_path, state)
    return {
        "workspace": str(workspace),
        "state_path": str(state_path),
        "stage": state.get("stage"),
        "status": state.get("status"),
        "already_initialized": already_initialized,
        "directories": {
            relative: str(workspace / relative)
            for relative in WORKSPACE_DIRECTORIES
        },
    }
