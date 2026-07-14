from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict

from digital_ic_agent._runtime.design_workspace import (
    WorkspaceError,
    build_workspace_report,
    diagnose_workspace,
    initialize_workspace,
    resume_workspace,
    workspace_status,
)
from digital_ic_agent._runtime.intent_contract import (
    IntentFileError,
    validate_intent_files,
)
from digital_ic_agent._runtime.reference_library import (
    ReferenceLibraryError,
    index_reference_library,
    reference_status,
    search_references,
    show_reference,
)
from digital_ic_agent._runtime.verification_verdict import (
    load_verification_verdict,
    verification_verdict_from_payload,
)


CLI_SCHEMA_VERSION = "digital-ic-agent.cli.v1"
MACHINE_COMMANDS = {
    "workspace",
    "spec",
    "reference",
    "verify",
    "diagnose",
    "status",
    "resume",
    "report",
}
CliStatus = Literal["PASS", "FAIL", "AMBIGUOUS"]


class CliResponse(TypedDict):
    schema_version: str
    command: str
    status: CliStatus
    ok: bool
    error_code: str | None
    message: str
    data: dict[str, Any]


def _argv(argv: Sequence[str] | None) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)


def is_machine_invocation(argv: Sequence[str] | None) -> bool:
    for token in _argv(argv):
        if token == "--json":
            continue
        return token in MACHINE_COMMANDS
    return False


def build_machine_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="digital-ic-agent",
        description="Deterministic machine interface for Codex",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    workspace = subparsers.add_parser("workspace", help="Manage a design workspace")
    workspace_commands = workspace.add_subparsers(
        dest="workspace_command",
        required=True,
    )
    workspace_init = workspace_commands.add_parser(
        "init",
        help="Initialize a non-destructive design workspace",
    )
    workspace_init.add_argument("--workspace", required=True, type=Path)

    spec = subparsers.add_parser("spec", help="Manage intent contracts")
    spec_commands = spec.add_subparsers(dest="spec_command", required=True)
    spec_validate = spec_commands.add_parser(
        "validate",
        help="Validate DesignIntent and VerificationIntent",
    )
    spec_validate.add_argument("--design-intent", required=True, type=Path)
    spec_validate.add_argument("--verification-intent", required=True, type=Path)

    reference = subparsers.add_parser("reference", help="Manage local references")
    reference.add_argument("reference_command", choices=("status", "index", "search", "show"))
    reference.add_argument("--workspace", type=Path, default=Path.cwd())
    reference.add_argument("--query", default=None)
    reference.add_argument("--record-id", default=None)

    for command in ("diagnose", "status", "resume", "report"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--workspace", required=True, type=Path)

    verify = subparsers.add_parser(
        "verify",
        help="Validate a canonical project verification verdict",
    )
    verify.add_argument("--project-dir", required=True, type=Path)
    verify.add_argument("--expected-flow", default=None)
    return parser


def _parse_machine_args(argv: Sequence[str] | None) -> argparse.Namespace:
    raw = _argv(argv)
    json_output = "--json" in raw
    args = build_machine_parser().parse_args(
        [token for token in raw if token != "--json"]
    )
    args.json_output = json_output
    return args


def _response(
    *,
    command: str,
    status: CliStatus,
    error_code: str | None,
    message: str,
    data: dict[str, Any] | None = None,
) -> CliResponse:
    return {
        "schema_version": CLI_SCHEMA_VERSION,
        "command": command,
        "status": status,
        "ok": status == "PASS",
        "error_code": error_code,
        "message": message,
        "data": dict(data or {}),
    }


def _failure(
    code: str,
    message: str,
    *,
    command: str = "verify",
    data: dict[str, Any] | None = None,
) -> CliResponse:
    return _response(
        command=command,
        status="FAIL",
        error_code=code,
        message=message,
        data=data,
    )


def verify_project(
    project_dir: Path,
    *,
    expected_flow: str | None = None,
) -> CliResponse:
    project_dir = Path(project_dir).resolve()
    verdict_path = project_dir / "reports" / "verification_verdict.json"
    manifest_path = project_dir / "artifacts.json"
    base_data: dict[str, Any] = {
        "project_dir": str(project_dir),
        "verdict_path": str(verdict_path),
        "manifest_path": str(manifest_path),
    }
    if not verdict_path.is_file():
        return _failure(
            "VERDICT_NOT_FOUND",
            "Canonical verification verdict was not found",
            data=base_data,
        )
    try:
        verdict = load_verification_verdict(verdict_path)
    except ValueError as exc:
        return _failure(
            "VERDICT_INVALID",
            str(exc),
            data=base_data,
        )
    verdict_payload = verdict.to_dict()
    base_data["verdict"] = verdict_payload

    if not manifest_path.is_file():
        return _failure(
            "MANIFEST_NOT_FOUND",
            "Runtime artifact manifest was not found",
            data=base_data,
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _failure(
            "MANIFEST_INVALID",
            f"Invalid runtime artifact manifest: {type(exc).__name__}",
            data=base_data,
        )
    if not isinstance(manifest, dict) or not isinstance(manifest.get("runs"), list):
        return _failure(
            "MANIFEST_INVALID",
            "Runtime artifact manifest must contain a runs list",
            data=base_data,
        )
    runs = manifest["runs"]
    if not runs or not isinstance(runs[-1], dict):
        return _failure(
            "MANIFEST_RUN_MISSING",
            "Runtime artifact manifest contains no latest run",
            data=base_data,
        )
    latest_run = runs[-1]
    flow = latest_run.get("flow")
    manifest_status = latest_run.get("status")
    base_data.update(
        {
            "flow": flow,
            "manifest_status": manifest_status,
            "run_id": latest_run.get("run_id"),
        }
    )
    if expected_flow is not None and flow != expected_flow:
        return _failure(
            "FLOW_MISMATCH",
            f"Latest manifest flow is {flow!r}, expected {expected_flow!r}",
            data=base_data,
        )
    try:
        embedded = verification_verdict_from_payload(
            latest_run.get("verification_verdict")
        )
    except ValueError as exc:
        return _failure(
            "VERDICT_MANIFEST_MISMATCH",
            str(exc),
            data=base_data,
        )
    if (
        embedded.to_dict() != verdict_payload
        or manifest_status != verdict.status
    ):
        return _failure(
            "VERDICT_MANIFEST_MISMATCH",
            "Manifest status or embedded verdict disagrees with canonical verdict",
            data=base_data,
        )
    if not verdict.passed:
        return _failure(
            "VERIFICATION_FAILED",
            "Canonical verification verdict reported FAIL",
            data=base_data,
        )
    return _response(
        command="verify",
        status="PASS",
        error_code=None,
        message="Canonical verification verdict passed",
        data=base_data,
    )


def _emit(response: CliResponse, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(response, ensure_ascii=False, sort_keys=True))
        return
    stream = sys.stdout if response["ok"] else sys.stderr
    print(
        "{}: {}".format(response["status"], response["message"]),
        file=stream,
    )


def run_machine_cli(argv: Sequence[str] | None = None) -> int:
    args = _parse_machine_args(argv)
    if args.command == "workspace" and args.workspace_command == "init":
        response = _response(
            command="workspace init",
            status="PASS",
            error_code=None,
            message="Workspace initialized",
            data=initialize_workspace(args.workspace),
        )
    elif args.command == "spec" and args.spec_command == "validate":
        try:
            result = validate_intent_files(
                args.design_intent,
                args.verification_intent,
            )
        except IntentFileError as exc:
            response = _failure(
                exc.code,
                str(exc),
                command="spec validate",
            )
        else:
            response = _response(
                command="spec validate",
                status=result.status,
                error_code=(
                    None
                    if result.status == "PASS"
                    else (
                        "INTENT_AMBIGUOUS"
                        if result.status == "AMBIGUOUS"
                        else "INTENT_INVALID"
                    )
                ),
                message=(
                    "Intent contracts passed"
                    if result.status == "PASS"
                    else "Intent contracts require clarification or correction"
                ),
                data={"issues": [issue.to_dict() for issue in result.issues]},
            )
    elif args.command == "reference":
        reference_command = str(args.reference_command)
        command_name = f"reference {reference_command}"
        try:
            if reference_command == "status":
                data = reference_status(args.workspace)
                if data["status"] == "REFERENCE_LIBRARY_EMPTY":
                    raise ReferenceLibraryError(
                        "REFERENCE_LIBRARY_EMPTY",
                        "Reference library is empty",
                    )
            elif reference_command == "index":
                data = index_reference_library(args.workspace)
            elif reference_command == "search":
                if not args.query:
                    raise ReferenceLibraryError(
                        "REFERENCE_QUERY_REQUIRED",
                        "--query is required for reference search",
                    )
                data = search_references(args.workspace, args.query)
            else:
                if not args.record_id:
                    raise ReferenceLibraryError(
                        "REFERENCE_RECORD_ID_REQUIRED",
                        "--record-id is required for reference show",
                    )
                data = show_reference(args.workspace, args.record_id)
        except ReferenceLibraryError as exc:
            if reference_command != "status":
                data = {"reference_status": reference_status(args.workspace)}
            response = _failure(
                exc.code,
                str(exc),
                command=command_name,
                data=data,
            )
        else:
            response = _response(
                command=command_name,
                status="PASS",
                error_code=None,
                message=f"Reference {reference_command} completed",
                data=data,
            )
    elif args.command in {"status", "resume", "diagnose", "report"}:
        try:
            if args.command == "status":
                data = workspace_status(args.workspace)
            elif args.command == "resume":
                data = resume_workspace(args.workspace)
            elif args.command == "diagnose":
                data = diagnose_workspace(args.workspace)
            else:
                data = build_workspace_report(args.workspace)
        except WorkspaceError as exc:
            response = _failure(
                exc.code,
                str(exc),
                command=str(args.command),
            )
        else:
            verdict_status = None
            if args.command == "diagnose":
                verdict_status = data["diagnosis"]["status"]
            elif args.command == "report":
                verdict = data["report"]["verdict"]
                verdict_status = (
                    None if verdict is None else verdict["status"]
                )
            failed = verdict_status in {"FAIL", None} and args.command in {
                "diagnose",
                "report",
            }
            response = _response(
                command=str(args.command),
                status="FAIL" if failed else "PASS",
                error_code="VERIFICATION_FAILED" if failed else None,
                message=(
                    "Workspace verification has not passed"
                    if failed
                    else f"Workspace {args.command} completed"
                ),
                data=data,
            )
    elif args.command == "verify":
        response = verify_project(
            args.project_dir,
            expected_flow=args.expected_flow,
        )
    else:
        response = _failure(
            "COMMAND_NOT_IMPLEMENTED",
            f"Command is not implemented yet: {args.command}",
            command=str(args.command),
        )
    _emit(response, json_output=bool(args.json_output))
    if response["ok"]:
        return 0
    return 2 if response["status"] == "AMBIGUOUS" else 1
