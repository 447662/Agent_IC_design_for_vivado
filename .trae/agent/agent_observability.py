from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypedDict, cast

from agent_errors import ErrorCategory, sanitize_details


MAX_DETAIL_TEXT_LENGTH = 1024
TRUNCATION_SUFFIX = "...[truncated]"

ObservabilityStatus = Literal["PASS", "FAIL", "WARN", "INFO"]
ObservabilityEventName = Literal[
    "flow_started",
    "flow_finished",
    "stage_started",
    "stage_finished",
    "tool_started",
    "tool_finished",
]


JsonValue = (
    None
    | bool
    | int
    | float
    | str
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)


class ObservabilityEvent(TypedDict):
    schema_version: str
    run_id: str
    flow: str
    stage: str
    event: ObservabilityEventName
    status: ObservabilityStatus
    duration_ms: int | None
    exit_code: int | None
    error_category: ErrorCategory | None
    tool_versions: dict[str, str]
    details: dict[str, JsonValue]


class ObservabilityEventInput(TypedDict, total=False):
    run_id: str
    flow: str
    stage: str
    event: ObservabilityEventName
    status: ObservabilityStatus
    duration_ms: int | None
    exit_code: int | None
    error_category: ErrorCategory | None
    tool_versions: dict[str, str]
    details: dict[str, object]


def _truncate_text(value: str) -> str:
    if len(value) <= MAX_DETAIL_TEXT_LENGTH:
        return value
    limit = max(0, MAX_DETAIL_TEXT_LENGTH - len(TRUNCATION_SUFFIX))
    return value[:limit] + TRUNCATION_SUFFIX


def _normalize_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _truncate_text(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _normalize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple | set):
        return [_normalize_json_value(item) for item in value]
    return _truncate_text(str(value))


def normalize_observability_details(details: dict[str, object]) -> dict[str, JsonValue]:
    redacted = sanitize_details(details)
    return {
        str(key): _normalize_json_value(value)
        for key, value in redacted.items()
    }


def build_observability_event(
    *,
    run_id: str,
    flow: str,
    stage: str,
    event: ObservabilityEventName,
    status: ObservabilityStatus,
    duration_ms: int | None = None,
    exit_code: int | None = None,
    error_category: ErrorCategory | None = None,
    tool_versions: dict[str, str] | None = None,
    details: dict[str, object] | None = None,
) -> ObservabilityEvent:
    return {
        "schema_version": "digital-ic-agent.observability.v1",
        "run_id": run_id,
        "flow": flow,
        "stage": stage,
        "event": event,
        "status": status,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "error_category": error_category,
        "tool_versions": dict(tool_versions or {}),
        "details": normalize_observability_details(dict(details or {})),
    }


def dumps_observability_event(event: ObservabilityEvent) -> str:
    return json.dumps(
        event,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def append_observability_event(
    path: str | Path,
    event: ObservabilityEvent,
) -> Path:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(dumps_observability_event(event))
        handle.write("\n")
    return log_path


def load_observability_timeline(
    path: str | Path,
    *,
    run_id: str | None = None,
) -> list[ObservabilityEvent]:
    log_path = Path(path)
    if not log_path.exists():
        return []

    events: list[ObservabilityEvent] = []
    for line_number, raw_line in enumerate(
        log_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        if not isinstance(payload, dict):
            raise ValueError(
                "observability timeline event must be an object at line {}".format(
                    line_number
                )
            )
        event = cast(ObservabilityEvent, payload)
        if run_id is None or event["run_id"] == run_id:
            events.append(event)
    return events
