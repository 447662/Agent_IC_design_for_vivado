from typing import Any

from capability_preflight import PreflightStatus


def diagnostic_status_text(status: Any, requirement: Any) -> Any:
    if status is PreflightStatus.NOT_APPLICABLE:
        return "[N/A] 当前动作不适用"
    if status is PreflightStatus.MISSING_REQUIRED:
        return "[NO] 缺失（必需）"
    if status is PreflightStatus.MISSING_OPTIONAL:
        return "[WARN] 缺失（可选，降级）"
    if requirement == "required":
        return "[OK] 可用（必需）"
    if requirement == "optional":
        return "[OK] 可用（可选）"
    return "[OK] 可用"


def capability_diagnostic(agent: Any, capability: Any, flow: Any=None) -> Any:
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


def _print_cli_diagnostics(agent: Any, flow: Any) -> list[tuple[Any, Any]]:
    print("\n【CLI工具检查】")
    cli_status = []
    for tool in agent.cli_tools:
        capability = tool["name"]
        status, requirement = capability_diagnostic(agent, capability, flow=flow)
        cli_status.append((capability, status))
        print("  {}: {}".format(capability, diagnostic_status_text(status, requirement)))
        if status in {PreflightStatus.MISSING_REQUIRED, PreflightStatus.MISSING_OPTIONAL}:
            print("     安装指南: {}".format(agent.get_install_guide("cli", tool["name"])))
    return cli_status


def _print_mcp_diagnostics(agent: Any, flow: Any) -> list[tuple[Any, Any]]:
    print("\n【MCP服务器检查】")
    mcp_status = []
    for name, mcp in agent.mcp_servers.items():
        status, requirement = capability_diagnostic(agent, name, flow=flow)
        mcp_status.append((name, status))
        print("  {}: {}".format(name, diagnostic_status_text(status, requirement)))
        if status in {PreflightStatus.MISSING_REQUIRED, PreflightStatus.MISSING_OPTIONAL}:
            print("     安装指南: {}".format(mcp.get("installGuide", "未知")))
    return mcp_status


def _print_skill_diagnostics(agent: Any) -> list[tuple[Any, bool]]:
    print("\n【技能文件检查】")
    skill_status = []
    for skill in agent.agent_config["skills"]:
        skill_path = agent.resolve_skill_path(skill)
        exists = skill_path.exists()
        status = agent.OK + " 存在" if exists else agent.NO + " 缺失"
        skill_status.append((skill["name"], exists))
        print("  {}: {}".format(skill["name"], status))
    return skill_status


def _all_required_diagnostics_ok(
    cli_status: list[tuple[Any, Any]],
    mcp_status: list[tuple[Any, Any]],
    skill_status: list[tuple[Any, bool]],
) -> bool:
    return (
        all(status is not PreflightStatus.MISSING_REQUIRED for _, status in cli_status)
        and all(status is not PreflightStatus.MISSING_REQUIRED for _, status in mcp_status)
        and all(exists for _, exists in skill_status)
    )


def run_agent_diagnostic(agent: Any, flow: Any=None) -> Any:
    print("=" * 60)
    print("数字IC前端设计Agent - 环境诊断")
    print("=" * 60)

    if flow is not None:
        print("诊断动作: {}".format(flow))

    cli_status = _print_cli_diagnostics(agent, flow)
    mcp_status = _print_mcp_diagnostics(agent, flow)
    skill_status = _print_skill_diagnostics(agent)
    all_ok = _all_required_diagnostics_ok(cli_status, mcp_status, skill_status)

    print("\n" + "=" * 60)
    if all_ok:
        print("诊断结果: " + agent.OK + " 所有工具和技能均已就绪")
    else:
        print("诊断结果: " + agent.WARN + " 部分工具未安装，请根据上述指南安装")
    print("=" * 60)

    return all_ok
