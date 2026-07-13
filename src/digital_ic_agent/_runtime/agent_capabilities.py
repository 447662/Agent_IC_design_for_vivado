from typing import Any
import re
import subprocess

from digital_ic_agent._runtime.agent_config import normalize_configured_command


def check_capability(agent: Any, capability: Any) -> bool:
    if capability == "synthpilot":
        return bool(agent.check_mcp_server("synthpilot"))
    for tool in agent.cli_tools:
        if tool["name"] == capability:
            return bool(agent.check_cli_tool(tool["name"], tool["checkCommand"]))
    return False


def run_preflight(agent: Any, flow: Any) -> Any:
    return agent.preflight.evaluate(flow, agent.check_capability)


def normalize_command(_agent: Any, command: Any) -> Any:
    return normalize_configured_command(command)


def check_cli_tool(agent: Any, tool_name: Any, check_command: Any) -> bool:
    try:
        command = agent.normalize_command(check_command)
        if tool_name == "vivado" and command and command[0] == "vivado":
            vivado_command = agent.resolve_vivado_command()
            if vivado_command:
                command[0] = vivado_command
        result = agent.command_runner.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            return True
        if tool_name == "vivado":
            version_text = "{}\n{}".format(
                result.stdout or "",
                result.stderr or "",
            )
            return bool(
                re.search(
                    r"\bVivado\s+v?\d{4}\.\d+\b",
                    version_text,
                    re.IGNORECASE,
                )
            )
        return False
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired, ValueError):
        return False


def check_mcp_server(agent: Any, mcp_name: Any) -> bool:
    mcp = agent.mcp_servers.get(mcp_name)
    if not mcp:
        return False

    try:
        command = [mcp["command"], *mcp.get("args", []), "--version"]
        result = agent.command_runner.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return bool(result.returncode == 0)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False


def get_install_guide(agent: Any, tool_type: Any, tool_name: Any) -> str:
    if tool_type == "mcp":
        mcp = agent.mcp_servers.get(tool_name)
        return str(mcp.get("installGuide", "未知")) if mcp else "未知"
    if tool_type == "cli":
        for tool in agent.cli_tools:
            if tool["name"] == tool_name:
                return str(tool.get("installGuide", "未知"))
        return "未知"
    return "未知"
