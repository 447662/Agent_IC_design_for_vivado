from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonObject: TypeAlias = Mapping[str, "JsonValue"]
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | JsonObject
PayloadMapping: TypeAlias = Mapping[str, JsonValue]


@dataclass(frozen=True)
class AgentRequest:
    request_id: str
    user_input: str
    output_dir: Path
    context: PayloadMapping = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    tool_call_id: str
    tool_name: str
    arguments: PayloadMapping = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    skill_name: str
    tool_calls: tuple[ToolCall, ...] = ()


class ToolResultStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    tool_name: str
    status: ToolResultStatus
    returncode: int | None
    artifacts: tuple[Path, ...] = ()
    output: str = ""
    error: str | None = None
    metadata: PayloadMapping = field(default_factory=dict)


class AgentRunStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AgentRun:
    request: AgentRequest
    plan: ExecutionPlan | None
    status: AgentRunStatus
    tool_results: tuple[ToolResult, ...] = ()
    artifacts: tuple[Path, ...] = ()
    failure_reason: str | None = None
