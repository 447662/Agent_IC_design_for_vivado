from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


IntentStatus = Literal["PASS", "FAIL", "AMBIGUOUS"]
IssueKind = Literal["INVALID", "AMBIGUOUS"]
MAX_INTENT_BYTES = 1024 * 1024
DESIGN_SCHEMA_VERSION = "digital-ic-agent.design-intent.v1"
VERIFICATION_SCHEMA_VERSION = "digital-ic-agent.verification-intent.v1"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class IntentIssue:
    code: str
    path: str
    message: str
    kind: IssueKind

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class IntentValidationResult:
    status: IntentStatus
    issues: tuple[IntentIssue, ...]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class IntentFileError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _issue(
    issues: list[IntentIssue],
    code: str,
    path: str,
    message: str,
    kind: IssueKind = "INVALID",
) -> None:
    candidate = IntentIssue(code=code, path=path, message=message, kind=kind)
    if candidate not in issues:
        issues.append(candidate)


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _sequence(value: object) -> Sequence[object] | None:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    return None


def _named_items(
    value: object,
    *,
    path: str,
    duplicate_code: str,
    issues: list[IntentIssue],
) -> tuple[list[Mapping[str, object]], set[str]]:
    raw_items = _sequence(value)
    if raw_items is None:
        _issue(issues, "FIELD_TYPE_INVALID", path, f"{path} must be an array")
        return [], set()
    items: list[Mapping[str, object]] = []
    names: set[str] = set()
    for index, raw_item in enumerate(raw_items):
        item = _mapping(raw_item)
        item_path = f"{path}.{index}"
        if item is None:
            _issue(issues, "FIELD_TYPE_INVALID", item_path, "Entry must be an object")
            continue
        name = item.get("name")
        if not isinstance(name, str) or _IDENTIFIER.fullmatch(name) is None:
            _issue(issues, "IDENTIFIER_INVALID", f"{item_path}.name", "Name is invalid")
        elif name in names:
            _issue(issues, duplicate_code, f"{item_path}.name", f"Duplicate name: {name}")
        else:
            names.add(name)
        items.append(item)
    return items, names


def _validate_design(
    design: Mapping[str, object],
    issues: list[IntentIssue],
) -> tuple[str | None, set[str]]:
    if design.get("schema_version") != DESIGN_SCHEMA_VERSION:
        _issue(
            issues,
            "DESIGN_SCHEMA_VERSION_INVALID",
            "design.schema_version",
            f"Expected {DESIGN_SCHEMA_VERSION}",
        )
    module = _mapping(design.get("module"))
    module_name: str | None = None
    module_kind: str | None = None
    if module is None:
        _issue(issues, "MODULE_MISSING", "design.module", "Module object is required")
    else:
        name = module.get("name")
        if isinstance(name, str) and _IDENTIFIER.fullmatch(name):
            module_name = name
        else:
            _issue(issues, "MODULE_NAME_INVALID", "design.module.name", "Module name is invalid")
        kind = module.get("kind")
        if kind in {"sequential", "combinational"}:
            module_kind = str(kind)
        else:
            _issue(
                issues,
                "MODULE_KIND_INVALID",
                "design.module.kind",
                "Module kind must be sequential or combinational",
            )

    parameters, parameter_names = _named_items(
        design.get("parameters", []),
        path="design.parameters",
        duplicate_code="PARAMETER_DUPLICATE",
        issues=issues,
    )
    for index, parameter in enumerate(parameters):
        default = parameter.get("default")
        if parameter.get("type") == "integer" and (
            not isinstance(default, int) or isinstance(default, bool)
        ):
            _issue(
                issues,
                "PARAMETER_DEFAULT_INVALID",
                f"design.parameters.{index}.default",
                "Integer parameter default must be an integer",
            )

    if "ports" not in design or not _sequence(design.get("ports")):
        _issue(
            issues,
            "INTERFACE_SEMANTICS_MISSING",
            "design.ports",
            "Ports must be explicitly defined",
            "AMBIGUOUS",
        )
    ports, port_names = _named_items(
        design.get("ports", []),
        path="design.ports",
        duplicate_code="PORT_DUPLICATE",
        issues=issues,
    )
    for index, port in enumerate(ports):
        port_path = f"design.ports.{index}"
        if port.get("direction") not in {"input", "output", "inout"}:
            _issue(
                issues,
                "PORT_DIRECTION_INVALID",
                f"{port_path}.direction",
                "Port direction is invalid",
            )
        width = port.get("width")
        if isinstance(width, bool) or (
            isinstance(width, int) and width <= 0
        ):
            _issue(
                issues,
                "PORT_WIDTH_INVALID",
                f"{port_path}.width",
                "Port width must be positive",
            )
        elif isinstance(width, str) and width not in parameter_names:
            _issue(
                issues,
                "WIDTH_PARAMETER_UNDEFINED",
                f"{port_path}.width",
                f"Width parameter is undefined: {width}",
            )
        elif not isinstance(width, int | str):
            _issue(
                issues,
                "PORT_WIDTH_INVALID",
                f"{port_path}.width",
                "Port width must be an integer or parameter name",
            )
        semantics = port.get("semantics")
        if not isinstance(semantics, str) or not semantics.strip():
            _issue(
                issues,
                "PORT_SEMANTICS_MISSING",
                f"{port_path}.semantics",
                "Port semantics require user clarification",
                "AMBIGUOUS",
            )

    if "clocks" not in design:
        _issue(
            issues,
            "CLOCK_SEMANTICS_MISSING",
            "design.clocks",
            "Clock semantics must be explicit, including an empty array",
            "AMBIGUOUS",
        )
    clocks, clock_names = _named_items(
        design.get("clocks", []),
        path="design.clocks",
        duplicate_code="CLOCK_DUPLICATE",
        issues=issues,
    )
    if module_kind == "sequential" and "clocks" in design and not clocks:
        _issue(
            issues,
            "CLOCK_SEMANTICS_MISSING",
            "design.clocks",
            "Sequential modules require at least one clock",
            "AMBIGUOUS",
        )
    for index, clock in enumerate(clocks):
        if clock.get("signal") not in port_names:
            _issue(
                issues,
                "CLOCK_SIGNAL_UNDEFINED",
                f"design.clocks.{index}.signal",
                "Clock signal is not a declared port",
            )
        if clock.get("edge") not in {"rising", "falling"}:
            _issue(
                issues,
                "CLOCK_EDGE_INVALID",
                f"design.clocks.{index}.edge",
                "Clock edge is invalid",
            )

    if "resets" not in design:
        _issue(
            issues,
            "RESET_SEMANTICS_MISSING",
            "design.resets",
            "Reset semantics must be explicit, including an empty array",
            "AMBIGUOUS",
        )
    resets, _reset_names = _named_items(
        design.get("resets", []),
        path="design.resets",
        duplicate_code="RESET_DUPLICATE",
        issues=issues,
    )
    if module_kind == "sequential" and "resets" in design and not resets:
        _issue(
            issues,
            "RESET_SEMANTICS_MISSING",
            "design.resets",
            "Sequential modules require explicit reset behavior",
            "AMBIGUOUS",
        )
    for index, reset in enumerate(resets):
        if reset.get("signal") not in port_names:
            _issue(
                issues,
                "RESET_SIGNAL_UNDEFINED",
                f"design.resets.{index}.signal",
                "Reset signal is not a declared port",
            )
        if "clocks" in design and reset.get("clock") not in clock_names:
            _issue(
                issues,
                "RESET_CLOCK_UNDEFINED",
                f"design.resets.{index}.clock",
                "Reset clock domain is undefined",
            )

    if "protocols" not in design:
        _issue(
            issues,
            "INTERFACE_SEMANTICS_MISSING",
            "design.protocols",
            "Protocol semantics must be explicit, including an empty array",
            "AMBIGUOUS",
        )
    protocols = _sequence(design.get("protocols", [])) or []
    for index, raw_protocol in enumerate(protocols):
        protocol = _mapping(raw_protocol)
        if protocol is None:
            _issue(
                issues,
                "FIELD_TYPE_INVALID",
                f"design.protocols.{index}",
                "Protocol must be an object",
            )
            continue
        signals = _sequence(protocol.get("signals")) or []
        for signal in signals:
            if signal not in port_names:
                _issue(
                    issues,
                    "PROTOCOL_SIGNAL_UNDEFINED",
                    f"design.protocols.{index}.signals",
                    f"Protocol signal is undefined: {signal}",
                )

    acceptance = _sequence(design.get("acceptance_criteria"))
    if not acceptance or not all(
        isinstance(item, str) and item.strip() for item in acceptance
    ):
        _issue(
            issues,
            "ACCEPTANCE_CRITERIA_MISSING",
            "design.acceptance_criteria",
            "At least one explicit acceptance criterion is required",
            "AMBIGUOUS",
        )
    return module_name, port_names


def _verification_signals(
    container: object,
    field: str,
) -> list[tuple[str, str]]:
    items = _sequence(container) or []
    found: list[tuple[str, str]] = []
    for index, raw_item in enumerate(items):
        item = _mapping(raw_item)
        if item is None:
            continue
        signals = _sequence(item.get("signals")) or []
        found.extend((str(signal), f"verification.{field}.{index}.signals") for signal in signals)
    return found


def _validate_verification(
    verification: Mapping[str, object],
    module_name: str | None,
    port_names: set[str],
    issues: list[IntentIssue],
) -> None:
    if verification.get("schema_version") != VERIFICATION_SCHEMA_VERSION:
        _issue(
            issues,
            "VERIFICATION_SCHEMA_VERSION_INVALID",
            "verification.schema_version",
            f"Expected {VERIFICATION_SCHEMA_VERSION}",
        )
    if module_name is not None and verification.get("module") != module_name:
        _issue(
            issues,
            "MODULE_MISMATCH",
            "verification.module",
            "VerificationIntent module does not match DesignIntent",
        )
    directed = _sequence(verification.get("directed_scenarios"))
    if not directed:
        _issue(
            issues,
            "DIRECTED_SCENARIOS_MISSING",
            "verification.directed_scenarios",
            "At least one directed scenario is required",
            "AMBIGUOUS",
        )
    scoreboard = _mapping(verification.get("scoreboard"))
    if scoreboard is None:
        _issue(
            issues,
            "SCOREBOARD_MISSING",
            "verification.scoreboard",
            "Scoreboard behavior must be explicit",
            "AMBIGUOUS",
        )
    else:
        for signal in _sequence(scoreboard.get("compare_signals")) or []:
            if signal not in port_names:
                _issue(
                    issues,
                    "VERIFICATION_SIGNAL_UNDEFINED",
                    "verification.scoreboard.compare_signals",
                    f"Verification signal is undefined: {signal}",
                )
    for signal, path in (
        _verification_signals(
            verification.get("random_constraints"), "random_constraints"
        )
        + _verification_signals(verification.get("assertions"), "assertions")
        + _verification_signals(
            verification.get("functional_coverage"), "functional_coverage"
        )
    ):
        if signal not in port_names:
            _issue(
                issues,
                "VERIFICATION_SIGNAL_UNDEFINED",
                path,
                f"Verification signal is undefined: {signal}",
            )

    coverage = _mapping(verification.get("code_coverage"))
    if coverage is None:
        _issue(
            issues,
            "CODE_COVERAGE_MISSING",
            "verification.code_coverage",
            "Code coverage thresholds must be explicit",
            "AMBIGUOUS",
        )
    else:
        for metric in ("statement", "branch", "condition", "toggle"):
            threshold = coverage.get(metric)
            if (
                not isinstance(threshold, int | float)
                or isinstance(threshold, bool)
                or not 0 <= float(threshold) <= 100
            ):
                _issue(
                    issues,
                    "COVERAGE_THRESHOLD_INVALID",
                    f"verification.code_coverage.{metric}",
                    "Coverage threshold must be between 0 and 100",
                )
    if _mapping(verification.get("exit_criteria")) is None:
        _issue(
            issues,
            "EXIT_CRITERIA_MISSING",
            "verification.exit_criteria",
            "Verification exit criteria require clarification",
            "AMBIGUOUS",
        )


def validate_intents(
    design: object,
    verification: object,
) -> IntentValidationResult:
    issues: list[IntentIssue] = []
    design_document = _mapping(design)
    verification_document = _mapping(verification)
    if design_document is None:
        _issue(issues, "DESIGN_DOCUMENT_INVALID", "design", "DesignIntent must be an object")
    if verification_document is None:
        _issue(
            issues,
            "VERIFICATION_DOCUMENT_INVALID",
            "verification",
            "VerificationIntent must be an object",
        )
    if design_document is not None:
        module_name, port_names = _validate_design(design_document, issues)
    else:
        module_name, port_names = None, set()
    if verification_document is not None:
        _validate_verification(
            verification_document,
            module_name,
            port_names,
            issues,
        )
    if any(issue.kind == "INVALID" for issue in issues):
        status: IntentStatus = "FAIL"
    elif issues:
        status = "AMBIGUOUS"
    else:
        status = "PASS"
    return IntentValidationResult(status=status, issues=tuple(issues))


def load_intent_json(path: Path) -> object:
    path = Path(path)
    if not path.is_file():
        raise IntentFileError("INTENT_FILE_NOT_FOUND", f"Intent file not found: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise IntentFileError("INTENT_FILE_UNREADABLE", str(exc)) from exc
    if size > MAX_INTENT_BYTES:
        raise IntentFileError(
            "INTENT_FILE_TOO_LARGE",
            f"Intent file exceeds {MAX_INTENT_BYTES} bytes: {path}",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntentFileError("INTENT_JSON_INVALID", f"Invalid intent JSON: {path}") from exc


def validate_intent_files(
    design_path: Path,
    verification_path: Path,
) -> IntentValidationResult:
    return validate_intents(
        load_intent_json(design_path),
        load_intent_json(verification_path),
    )
