import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, TextIO, TypedDict

from capability_preflight import FlowPreflight, PreflightReport, PreflightStatus


class CliToolInfo(TypedDict):
    name: str


class SkillInfo(TypedDict):
    name: str


class DiagnosticAgent(Protocol):
    OK: str
    WARN: str
    NO: str
    cli_tools: Sequence[CliToolInfo]
    mcp_servers: Mapping[str, Mapping[str, str]]
    agent_config: Mapping[str, Sequence[SkillInfo]]
    preflight: FlowPreflight

    def run_preflight(self, flow: str) -> PreflightReport:
        ...

    def check_capability(self, capability: str) -> bool:
        ...

    def get_install_guide(self, kind: str, name: str) -> str:
        ...

    def resolve_skill_path(self, skill: SkillInfo) -> Path:
        ...


CapabilityStatus = tuple[str, PreflightStatus]


def diagnostic_status_text(status: PreflightStatus, requirement: str) -> str:
    if status is PreflightStatus.NOT_APPLICABLE:
        return "[N/A] \u5f53\u524d\u52a8\u4f5c\u4e0d\u9002\u7528"
    if status is PreflightStatus.MISSING_REQUIRED:
        return "[NO] \u7f3a\u5931\uff08\u5fc5\u9700\uff09"
    if status is PreflightStatus.MISSING_OPTIONAL:
        return "[WARN] \u7f3a\u5931\uff08\u53ef\u9009\uff0c\u964d\u7ea7\uff09"
    if requirement == "required":
        return "[OK] \u53ef\u7528\uff08\u5fc5\u9700\uff09"
    if requirement == "optional":
        return "[OK] \u53ef\u7528\uff08\u53ef\u9009\uff09"
    return "[OK] \u53ef\u7528"


def capability_diagnostic(
    agent: DiagnosticAgent,
    capability: str,
    flow: str | None = None,
) -> tuple[PreflightStatus, str]:
    if flow is not None:
        report = agent.run_preflight(flow)
        status = report.status_for(capability)
        if capability in report.required_capabilities:
            requirement = "required"
        elif capability in report.optional_capabilities:
            requirement = "optional"
        else:
            requirement = "not-applicable"
        return status, requirement

    required_flows = agent.preflight.required_flows(capability)
    optional_flows = agent.preflight.optional_flows(capability)
    if not required_flows and not optional_flows:
        return PreflightStatus.NOT_APPLICABLE, "not-applicable"
    available = agent.check_capability(capability)
    if available:
        return (
            PreflightStatus.AVAILABLE,
            "required" if required_flows else "optional",
        )
    if required_flows:
        return PreflightStatus.MISSING_REQUIRED, "required"
    return PreflightStatus.MISSING_OPTIONAL, "optional"


def _build_cli_diagnostic_lines(
    agent: DiagnosticAgent,
    flow: str | None,
) -> tuple[list[CapabilityStatus], list[str]]:
    lines = ["", "\u3010CLI\u5de5\u5177\u68c0\u67e5\u3011"]
    cli_status: list[CapabilityStatus] = []
    for tool in agent.cli_tools:
        capability = tool["name"]
        status, requirement = capability_diagnostic(agent, capability, flow=flow)
        cli_status.append((capability, status))
        lines.append(
            "  {}: {}".format(capability, diagnostic_status_text(status, requirement))
        )
        if status in {
            PreflightStatus.MISSING_REQUIRED,
            PreflightStatus.MISSING_OPTIONAL,
        }:
            lines.append(
                "     \u5b89\u88c5\u6307\u5357: {}".format(
                    agent.get_install_guide("cli", tool["name"])
                )
            )
    return cli_status, lines


def _build_mcp_diagnostic_lines(
    agent: DiagnosticAgent,
    flow: str | None,
) -> tuple[list[CapabilityStatus], list[str]]:
    lines = ["", "\u3010MCP\u670d\u52a1\u5668\u68c0\u67e5\u3011"]
    mcp_status: list[CapabilityStatus] = []
    for name, mcp in agent.mcp_servers.items():
        status, requirement = capability_diagnostic(agent, name, flow=flow)
        mcp_status.append((name, status))
        lines.append("  {}: {}".format(name, diagnostic_status_text(status, requirement)))
        if status in {
            PreflightStatus.MISSING_REQUIRED,
            PreflightStatus.MISSING_OPTIONAL,
        }:
            lines.append(
                "     \u5b89\u88c5\u6307\u5357: {}".format(
                    mcp.get("installGuide", "\u672a\u77e5")
                )
            )
    return mcp_status, lines


def _build_skill_diagnostic_lines(
    agent: DiagnosticAgent,
) -> tuple[list[tuple[str, bool]], list[str]]:
    lines = ["", "\u3010\u6280\u80fd\u6587\u4ef6\u68c0\u67e5\u3011"]
    skill_status: list[tuple[str, bool]] = []
    for skill in agent.agent_config["skills"]:
        skill_path = agent.resolve_skill_path(skill)
        exists = skill_path.exists()
        status = (
            agent.OK + " \u5b58\u5728"
            if exists
            else agent.NO + " \u7f3a\u5931"
        )
        skill_status.append((skill["name"], exists))
        lines.append("  {}: {}".format(skill["name"], status))
    return skill_status, lines


def _all_required_diagnostics_ok(
    cli_status: list[CapabilityStatus],
    mcp_status: list[CapabilityStatus],
    skill_status: list[tuple[str, bool]],
) -> bool:
    return (
        all(status is not PreflightStatus.MISSING_REQUIRED for _, status in cli_status)
        and all(status is not PreflightStatus.MISSING_REQUIRED for _, status in mcp_status)
        and all(exists for _, exists in skill_status)
    )


def build_diagnostic_report_lines(
    agent: DiagnosticAgent,
    flow: str | None = None,
) -> tuple[bool, list[str]]:
    lines = [
        "=" * 60,
        "\u6570\u5b57IC\u524d\u7aef\u8bbe\u8ba1Agent - \u73af\u5883\u8bca\u65ad",
        "=" * 60,
    ]

    if flow is not None:
        lines.append("\u8bca\u65ad\u52a8\u4f5c: {}".format(flow))

    cli_status, cli_lines = _build_cli_diagnostic_lines(agent, flow)
    mcp_status, mcp_lines = _build_mcp_diagnostic_lines(agent, flow)
    skill_status, skill_lines = _build_skill_diagnostic_lines(agent)
    all_ok = _all_required_diagnostics_ok(cli_status, mcp_status, skill_status)

    lines.extend(cli_lines)
    lines.extend(mcp_lines)
    lines.extend(skill_lines)
    lines.extend(["", "=" * 60])
    if all_ok:
        lines.append(
            "\u8bca\u65ad\u7ed3\u679c: "
            + agent.OK
            + " \u6240\u6709\u5de5\u5177\u548c\u6280\u80fd\u5747\u5df2\u5c31\u7eea"
        )
    else:
        lines.append(
            "\u8bca\u65ad\u7ed3\u679c: "
            + agent.WARN
            + " \u90e8\u5206\u5de5\u5177\u672a\u5b89\u88c5\uff0c\u8bf7\u6839\u636e\u4e0a\u8ff0\u6307\u5357\u5b89\u88c5"
        )
    lines.append("=" * 60)
    return all_ok, lines


def emit_diagnostic_lines(lines: list[str], output: TextIO | None = None) -> None:
    target_output = output or sys.stdout
    target_output.write("\n".join(lines) + "\n")


def run_agent_diagnostic(
    agent: DiagnosticAgent,
    flow: str | None = None,
    output: TextIO | None = None,
) -> bool:
    all_ok, lines = build_diagnostic_report_lines(agent, flow=flow)
    emit_diagnostic_lines(lines, output=output)
    return all_ok
