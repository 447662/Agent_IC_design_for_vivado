from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable, Mapping


class PreflightStatus(str, Enum):
    AVAILABLE = "available"
    MISSING_REQUIRED = "missing-required"
    MISSING_OPTIONAL = "missing-optional"
    NOT_APPLICABLE = "not-applicable"


@dataclass(frozen=True)
class CapabilityCheck:
    capability: str
    status: PreflightStatus


@dataclass(frozen=True)
class PreflightReport:
    flow: str
    checks: tuple[CapabilityCheck, ...]
    known_capabilities: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not any(
            check.status is PreflightStatus.MISSING_REQUIRED
            for check in self.checks
        )

    def status_for(self, capability: str) -> PreflightStatus:
        for check in self.checks:
            if check.capability == capability:
                return check.status
        return PreflightStatus.NOT_APPLICABLE

    @property
    def missing_required(self) -> tuple[str, ...]:
        return tuple(
            check.capability
            for check in self.checks
            if check.status is PreflightStatus.MISSING_REQUIRED
        )

    @property
    def missing_optional(self) -> tuple[str, ...]:
        return tuple(
            check.capability
            for check in self.checks
            if check.status is PreflightStatus.MISSING_OPTIONAL
        )


class FlowPreflight:
    def __init__(
        self,
        policies: Mapping[str, Mapping[str, Iterable[str]]],
    ):
        normalized: dict[str, dict[str, tuple[str, ...]]] = {}
        known_capabilities: set[str] = set()
        for flow, policy in policies.items():
            required = tuple(
                str(name).strip()
                for name in policy.get("required", ())
                if str(name).strip()
            )
            optional = tuple(
                str(name).strip()
                for name in policy.get("optional", ())
                if str(name).strip()
            )
            overlap = set(required) & set(optional)
            if overlap:
                raise ValueError(
                    "Flow {} declares capabilities as required and optional: {}".format(
                        flow,
                        ", ".join(sorted(overlap)),
                    )
                )
            normalized[str(flow)] = {
                "required": required,
                "optional": optional,
            }
            known_capabilities.update(required)
            known_capabilities.update(optional)
        self.policies = normalized
        self.known_capabilities = tuple(sorted(known_capabilities))

    def evaluate(
        self,
        flow: str,
        checker: Callable[[str], bool],
    ) -> PreflightReport:
        policy = self.policies.get(flow)
        if policy is None:
            raise ValueError("Unknown flow for preflight: {}".format(flow))
        checks: list[CapabilityCheck] = []
        for capability in policy["required"]:
            available = bool(checker(capability))
            checks.append(
                CapabilityCheck(
                    capability,
                    (
                        PreflightStatus.AVAILABLE
                        if available
                        else PreflightStatus.MISSING_REQUIRED
                    ),
                )
            )
        for capability in policy["optional"]:
            available = bool(checker(capability))
            checks.append(
                CapabilityCheck(
                    capability,
                    (
                        PreflightStatus.AVAILABLE
                        if available
                        else PreflightStatus.MISSING_OPTIONAL
                    ),
                )
            )
        return PreflightReport(
            flow=flow,
            checks=tuple(checks),
            known_capabilities=self.known_capabilities,
            required_capabilities=policy["required"],
            optional_capabilities=policy["optional"],
        )

    def required_flows(self, capability: str) -> tuple[str, ...]:
        return tuple(
            flow
            for flow, policy in self.policies.items()
            if capability in policy["required"]
        )

    def optional_flows(self, capability: str) -> tuple[str, ...]:
        return tuple(
            flow
            for flow, policy in self.policies.items()
            if capability in policy["optional"]
        )


def build_default_preflight() -> FlowPreflight:
    no_external_tools = {"required": (), "optional": ()}
    vivado_required = {
        "required": ("vivado",),
        "optional": ("synthpilot",),
    }
    return FlowPreflight(
        {
            "design-document": no_external_tools,
            "rtl-implementation": no_external_tools,
            "verification-plan": no_external_tools,
            "generate-rtl": no_external_tools,
            "check-rtl": no_external_tools,
            "analyze-rtl-vcd": no_external_tools,
            "sim-rtl": vivado_required,
            "regress-rtl": vivado_required,
            "uvm-smoke": vivado_required,
            "uvm-coverage": vivado_required,
            "uvm-random-regress": vivado_required,
            "open-wave": vivado_required,
            "open-uvm-wave": vivado_required,
        }
    )
