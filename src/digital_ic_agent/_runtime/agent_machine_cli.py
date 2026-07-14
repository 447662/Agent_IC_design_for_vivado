from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict

from digital_ic_agent._runtime.verification_verdict import (
    load_verification_verdict,
    verification_verdict_from_payload,
)


CLI_SCHEMA_VERSION = "digital-ic-agent.cli.v1"
MACHINE_COMMANDS = {"verify"}


class CliResponse(TypedDict):
    schema_version: str
    command: str
    status: Literal["PASS", "FAIL"]
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
    status: Literal["PASS", "FAIL"],
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
    data: dict[str, Any] | None = None,
) -> CliResponse:
    return _response(
        command="verify",
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
    if args.command == "verify":
        response = verify_project(
            args.project_dir,
            expected_flow=args.expected_flow,
        )
    else:  # pragma: no cover - argparse constrains command values
        raise AssertionError(f"unsupported machine command: {args.command}")
    _emit(response, json_output=bool(args.json_output))
    return 0 if response["ok"] else 1
