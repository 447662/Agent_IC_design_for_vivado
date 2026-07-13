from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, TypeAlias


ErrorCategory: TypeAlias = Literal[
    "artifact_validation",
    "capability",
    "configuration",
    "tool_execution",
]

SENSITIVE_DETAIL_KEYS = {
    "api_key",
    "authorization",
    "license",
    "license_key",
    "password",
    "secret",
    "token",
}


def _redact_detail(key: str, value: object) -> object:
    if key.lower() in SENSITIVE_DETAIL_KEYS:
        return "***"
    if isinstance(value, dict):
        return sanitize_details(value)
    if isinstance(value, list | tuple):
        return [_redact_detail(key, item) for item in value]
    return value


def sanitize_details(details: dict[str, object]) -> dict[str, object]:
    return {
        str(key): _redact_detail(str(key), value)
        for key, value in details.items()
    }


@dataclass(frozen=True)
class AgentError(Exception):
    message: str
    category: ErrorCategory
    exit_code: int
    stage: str
    details: dict[str, object] = field(default_factory=dict)

    def as_payload(self) -> dict[str, object]:
        return {
            "category": self.category,
            "exit_code": self.exit_code,
            "stage": self.stage,
            "message": self.message,
            "details": sanitize_details(self.details),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.as_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def __str__(self) -> str:
        return "[{}:{}] {}".format(self.category, self.stage, self.message)


class ConfigurationError(AgentError):
    def __init__(
        self,
        message: str,
        *,
        stage: str = "configuration",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            category="configuration",
            exit_code=2,
            stage=stage,
            details=dict(details or {}),
        )


class CapabilityError(AgentError):
    def __init__(
        self,
        message: str,
        *,
        stage: str = "preflight",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            category="capability",
            exit_code=3,
            stage=stage,
            details=dict(details or {}),
        )


class ToolExecutionError(AgentError):
    def __init__(
        self,
        message: str,
        *,
        stage: str = "tool_execution",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            category="tool_execution",
            exit_code=4,
            stage=stage,
            details=dict(details or {}),
        )


class ArtifactValidationError(AgentError):
    def __init__(
        self,
        message: str,
        *,
        stage: str = "artifact_validation",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            category="artifact_validation",
            exit_code=5,
            stage=stage,
            details=dict(details or {}),
        )
