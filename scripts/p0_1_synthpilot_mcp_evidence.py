import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from mcp_client import StdioMCPClient  # noqa: E402


EVIDENCE_PATH = ROOT / "docs" / "testing" / "evidence" / "synthpilot_tools_list.json"
SAFE_TOOL_HINTS = (
    "version",
    "help",
    "list",
    "info",
    "diagnostic",
    "diagnostics",
    "ping",
    "echo",
)


def _repo_local_uv_env() -> None:
    env_paths = {
        "UV_CACHE_DIR": ROOT / ".tmp" / "uv-cache-synthpilot",
        "UV_PYTHON_INSTALL_DIR": ROOT / ".tmp" / "uv-python",
        "UV_TOOL_DIR": ROOT / ".tmp" / "uv-tools",
        "UV_TOOL_BIN_DIR": ROOT / ".tmp" / "uv-tool-bin",
    }
    for key, path in env_paths.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def _synthpilot_command() -> tuple[str, ...]:
    python_path = ROOT / ".venv" / "Scripts" / "python.exe"
    return ("uvx", "--python", str(python_path), "synthpilot")


def _tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    schema = tool.get("inputSchema")
    if isinstance(schema, dict):
        return schema
    schema = tool.get("input_schema")
    if isinstance(schema, dict):
        return schema
    return {}


def _requires_arguments(tool: dict[str, Any]) -> bool:
    schema = _tool_schema(tool)
    required = schema.get("required", [])
    return bool(required)


def _choose_safe_tool(tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = []
    for tool in tools:
        name = str(tool.get("name", "")).casefold()
        if not name or _requires_arguments(tool):
            continue
        if any(hint in name for hint in SAFE_TOOL_HINTS):
            candidates.append(tool)
    if candidates:
        return sorted(candidates, key=lambda item: str(item.get("name", "")))[0]
    no_arg_tools = [tool for tool in tools if not _requires_arguments(tool)]
    if len(no_arg_tools) == 1:
        return no_arg_tools[0]
    return None


def main() -> int:
    _repo_local_uv_env()
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)

    command = _synthpilot_command()
    evidence: dict[str, Any] = {
        "command": list(command),
        "steps": [],
        "safe_tool_selection": None,
    }
    exit_code = 1

    try:
        with StdioMCPClient(command, request_timeout=45.0) as client:
            initialized = client.initialize()
            evidence["steps"].append(
                {"method": "initialize", "status": "PASS", "result": initialized}
            )

            raw_tools = client.list_tools()
            tools = [dict(tool) for tool in raw_tools]
            evidence["steps"].append(
                {
                    "method": "tools/list",
                    "status": "PASS",
                    "tool_count": len(tools),
                    "tools": tools,
                }
            )

            selected_tool = _choose_safe_tool(tools)
            if selected_tool is None:
                evidence["status"] = "BLOCKED"
                evidence["safe_tool_selection"] = {
                    "reason": "No clearly safe zero-required-argument tool found",
                }
            else:
                tool_name = str(selected_tool["name"])
                payload = client.call_tool(tool_name, {})
                evidence["safe_tool_selection"] = {
                    "tool_name": tool_name,
                    "inputSchema": _tool_schema(selected_tool),
                    "arguments": {},
                }
                evidence["steps"].append(
                    {
                        "method": "tools/call",
                        "status": "PASS",
                        "tool_name": tool_name,
                        "arguments": {},
                        "result": payload,
                    }
                )
                evidence["status"] = "PASS"
                exit_code = 0
    except Exception as exc:
        evidence["status"] = "FAIL"
        evidence["error"] = {"type": type(exc).__name__, "message": str(exc)}

    EVIDENCE_PATH.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(str(EVIDENCE_PATH))
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "steps": [
                    {
                        "method": step.get("method"),
                        "status": step.get("status"),
                        "tool_count": step.get("tool_count"),
                        "tool_name": step.get("tool_name"),
                    }
                    for step in evidence["steps"]
                ],
                "error": evidence.get("error"),
                "safe_tool_selection": evidence.get("safe_tool_selection"),
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
