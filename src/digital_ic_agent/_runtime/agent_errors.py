from __future__ import annotations

import json
import re
from collections.abc import Mapping
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
SENSITIVE_NORMALIZED_KEYS = {
    "accesstoken",
    "apikey",
    "authorization",
    "clientsecret",
    "license",
    "licensekey",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
    "token",
}
SENSITIVE_KEY_SUFFIXES = (
    "apikey",
    "authorization",
    "licensekey",
    "password",
    "privatekey",
    "secret",
    "token",
)
AUTHORIZATION_BEARER_PATTERN = re.compile(
    r"(?i)(\bauthorization\s*:\s*bearer\s+)([^\s,;]+)"
)
BEARER_PATTERN = re.compile(r"(?i)(\bbearer\s+)([^\s,;]+)")
CREDENTIAL_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"license[_-]?key|password|private[_-]?key|secret|token)\b[\"']?\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


def _normalized_sensitive_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


def is_sensitive_key(key: str) -> bool:
    normalized = _normalized_sensitive_key(key)
    return normalized in SENSITIVE_NORMALIZED_KEYS or normalized.endswith(
        SENSITIVE_KEY_SUFFIXES
    )


def sanitize_text(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            pass
        else:
            sanitized = _redact_detail("", decoded)
            return json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
    value = AUTHORIZATION_BEARER_PATTERN.sub(r"\1***", value)
    value = BEARER_PATTERN.sub(r"\1***", value)
    return CREDENTIAL_ASSIGNMENT_PATTERN.sub(r"\1***", value)


def _redact_detail(key: str, value: object) -> object:
    if key.lower() in SENSITIVE_DETAIL_KEYS or is_sensitive_key(key):
        return "***"
    if isinstance(value, Mapping):
        return {
            str(item_key): _redact_detail(str(item_key), item)
            for item_key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact_detail(key, item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
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
            "message": sanitize_text(self.message),
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
        return "[{}:{}] {}".format(
            self.category,
            self.stage,
            sanitize_text(self.message),
        )


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
