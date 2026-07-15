from __future__ import annotations

import json
import hashlib
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from digital_ic_agent._runtime.verification_verdict import (
    load_verification_verdict,
)


STATE_SCHEMA_VERSION = "digital-ic-agent.state.v1"
WORKSPACE_DIRECTORIES = (
    "contracts",
    "rtl",
    "uvm",
    "sim",
    "reports",
    "iterations",
)


class WorkspaceError(ValueError):
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


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(content, encoding="utf-8")
    try:
        os.replace(temporary, path)
    except OSError:
        if temporary.exists():
            temporary.unlink()
        raise


def _state_path(workspace: Path) -> Path:
    return Path(workspace).resolve() / ".digital_ic_agent" / "state.json"


def load_workspace_state(workspace: Path) -> dict[str, Any]:
    state_path = _state_path(workspace)
    if not state_path.is_file():
        raise WorkspaceError(
            "STATE_NOT_FOUND",
            f"Workspace state was not found: {state_path}",
        )
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceError("STATE_INVALID", f"Invalid workspace state: {state_path}") from exc
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != STATE_SCHEMA_VERSION
        or not isinstance(state.get("stage"), str)
        or not isinstance(state.get("last_successful_stage"), str)
    ):
        raise WorkspaceError("STATE_INVALID", f"Invalid workspace state: {state_path}")
    return state


def _write_workspace_state(workspace: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _timestamp()
    _atomic_write_json(_state_path(workspace), state)


def consume_reference_reminder(workspace: Path) -> bool:
    try:
        state = load_workspace_state(workspace)
    except WorkspaceError:
        return True
    if state.get("reference_reminder_shown") is True:
        return False
    state["reference_reminder_shown"] = True
    _write_workspace_state(workspace, state)
    return True


def workspace_status(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    return {
        "workspace": str(workspace),
        "state_path": str(_state_path(workspace)),
        "state": load_workspace_state(workspace),
    }


def resume_workspace(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    state = load_workspace_state(workspace)
    return {
        "workspace": str(workspace),
        "current_stage": state["stage"],
        "resume_from": state["last_successful_stage"],
        "iteration": state.get("iteration", 0),
        "state_path": str(_state_path(workspace)),
    }


def record_workspace_verification(
    workspace: Path,
    *,
    iteration: int,
    iteration_dir: Path | None,
    verdict_status: str,
    stopped_reason: str | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    state = load_workspace_state(workspace)
    if iteration < 0:
        raise WorkspaceError("ITERATION_INVALID", "Iteration cannot be negative")
    if verdict_status not in {"PASS", "FAIL"}:
        raise WorkspaceError("VERDICT_INVALID", "Verdict status must be PASS or FAIL")
    state["iteration"] = iteration
    state["last_verdict_status"] = verdict_status
    if iteration_dir is not None:
        state["last_iteration_dir"] = str(Path(iteration_dir).resolve())
    if stopped_reason is not None:
        state["stage"] = "STOPPED"
        state["status"] = "FAILED"
        state["stop_reason"] = stopped_reason
    elif verdict_status == "PASS":
        state["stage"] = "VERIFIED"
        state["status"] = "COMPLETE"
        state["last_successful_stage"] = "VERIFIED"
        state.pop("stop_reason", None)
    else:
        state["stage"] = "VERIFICATION_FAILED"
        state["status"] = "FAILED"
        state.pop("stop_reason", None)
    _write_workspace_state(workspace, state)
    return state


def _diagnosis_recommendation(code: str) -> str:
    if code == "SIMULATION_ENGINE_LAUNCH_BLOCKED":
        return (
            "Check Windows Code Integrity and Smart App Control for blocked xsimk.exe "
            "events before retrying Vivado; this is a host policy or toolchain failure, "
            "so do not modify RTL to address it."
        )
    if code.startswith("UVM_"):
        return "Inspect the UVM report and fix the first emitted error or fatal condition."
    if "COVERAGE" in code:
        return "Inspect coverage gaps and add a targeted sequence, assertion, or coverpoint."
    if "ARTIFACT" in code:
        return "Regenerate the missing, empty, or stale required artifact."
    if "ASSERT" in code or "SVA" in code:
        return "Inspect the failing property and the RTL behavior at its first failure."
    if "EXIT" in code or "TOOL" in code:
        return "Inspect the tool stage and correct the earliest compile or simulation failure."
    return "Inspect the canonical reason and patch the smallest responsible design area."


def diagnose_workspace(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    state = load_workspace_state(workspace)
    verdict_path = workspace / "reports" / "verification_verdict.json"
    if not verdict_path.is_file():
        raise WorkspaceError(
            "VERDICT_NOT_FOUND",
            f"Canonical verification verdict was not found: {verdict_path}",
        )
    try:
        verdict = load_verification_verdict(verdict_path)
    except ValueError as exc:
        raise WorkspaceError("VERDICT_INVALID", str(exc)) from exc
    reasons = [reason.to_dict() for reason in verdict.reasons]
    diagnosis = {
        "schema_version": "digital-ic-agent.diagnosis.v1",
        "generated_at": _timestamp(),
        "status": verdict.status,
        "verdict_generated_at": verdict.generated_at,
        "reasons": reasons,
        "recommendations": [
            {
                "reason_code": reason["code"],
                "action": _diagnosis_recommendation(reason["code"]),
            }
            for reason in reasons
        ],
    }
    diagnose_path = workspace / "reports" / "diagnose.json"
    _atomic_write_json(diagnose_path, diagnosis)
    state["stage"] = "DIAGNOSED"
    state["status"] = "READY" if verdict.passed else "FAILED"
    state["last_verdict_status"] = verdict.status
    _write_workspace_state(workspace, state)
    return {
        "workspace": str(workspace),
        "diagnose_path": str(diagnose_path),
        "diagnosis": diagnosis,
    }


def _file_summary(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    content = path.read_bytes()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }


def build_workspace_report(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    state = load_workspace_state(workspace)
    verdict_path = workspace / "reports" / "verification_verdict.json"
    verdict = None
    if verdict_path.is_file():
        try:
            verdict = load_verification_verdict(verdict_path)
        except ValueError as exc:
            raise WorkspaceError("VERDICT_INVALID", str(exc)) from exc
    report = {
        "schema_version": "digital-ic-agent.report.v1",
        "generated_at": _timestamp(),
        "workspace": str(workspace),
        "state": state,
        "contracts": {
            "design_intent": _file_summary(
                workspace / "contracts" / "design_intent.json"
            ),
            "verification_intent": _file_summary(
                workspace / "contracts" / "verification_intent.json"
            ),
        },
        "verdict": None if verdict is None else verdict.to_dict(),
    }
    reports_dir = workspace / "reports"
    json_path = reports_dir / "final_report.json"
    markdown_path = reports_dir / "final_report.md"
    _atomic_write_json(json_path, report)
    verdict_status = "MISSING" if verdict is None else verdict.status
    _atomic_write_text(
        markdown_path,
        "\n".join(
            (
                "# Digital IC Design Report",
                "",
                f"- Workspace: `{workspace}`",
                f"- Stage: `{state['stage']}`",
                f"- Verdict: **{verdict_status}**",
                f"- Iteration: `{state.get('iteration', 0)}`",
                "",
            )
        ),
    )
    return {
        "workspace": str(workspace),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "report": report,
    }


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
