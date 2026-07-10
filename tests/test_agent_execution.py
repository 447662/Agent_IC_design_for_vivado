import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from agent_contracts import (  # noqa: E402
    AgentRequest,
    AgentRunStatus,
    ExecutionPlan,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)
from agent_execution import AgentExecutionEngine, MCPToolExecutor  # noqa: E402
from agent_provider import ConfiguredAgentProvider, DeterministicProvider  # noqa: E402
from mcp_client import (  # noqa: E402
    MCPProcessError,
    MCPProtocolError,
    MCPTimeoutError,
    StdioMCPClient,
)


def _request(tmp_path: Path, text: str = "generate rtl") -> AgentRequest:
    return AgentRequest(
        request_id="request-1",
        user_input=text,
        output_dir=tmp_path,
    )


def _plan(*calls: ToolCall) -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="plan-1",
        skill_name="digital-ic-rtl-designer",
        tool_calls=tuple(calls),
    )


def _call(call_id: str = "tool-call-1", tool_name: str = "write-rtl") -> ToolCall:
    return ToolCall(
        tool_call_id=call_id,
        tool_name=tool_name,
        arguments={"target": "demo"},
    )


def test_deterministic_provider_returns_typed_plan_offline(tmp_path):
    expected = _plan(_call())
    provider = DeterministicProvider(
        planner=lambda request: expected
        if request.user_input == "generate rtl"
        else ExecutionPlan(
            plan_id="fallback",
            skill_name="digital-ic-designer",
            tool_calls=(),
        )
    )

    result = provider.create_plan(_request(tmp_path))

    assert result is expected
    assert isinstance(result, ExecutionPlan)
    assert result.skill_name == "digital-ic-rtl-designer"
    assert result.tool_calls[0].tool_call_id == "tool-call-1"


def test_configured_provider_builds_code_constrained_skill_plan(tmp_path):
    provider = ConfiguredAgentProvider(
        (
            {
                "name": "digital-ic-designer",
                "action": "design-document",
                "priority": 1,
                "triggerKeywords": ["设计文档", "架构设计"],
            },
            {
                "name": "digital-ic-rtl-designer",
                "action": "rtl-implementation",
                "priority": 2,
                "triggerKeywords": ["RTL", "Verilog"],
            },
        )
    )

    plan = provider.create_plan(
        AgentRequest(
            request_id="request-configured",
            user_input="先生成设计文档，再实现 Verilog RTL",
            output_dir=tmp_path,
        )
    )

    assert plan.skill_name == "digital-ic-designer"
    assert [call.tool_name for call in plan.tool_calls] == [
        "skill:design-document",
        "skill:rtl-implementation",
    ]
    assert [call.arguments["skill_name"] for call in plan.tool_calls] == [
        "digital-ic-designer",
        "digital-ic-rtl-designer",
    ]
    assert len({call.tool_call_id for call in plan.tool_calls}) == 2


def test_engine_correlates_tool_call_and_result_ids(tmp_path):
    call = _call()
    artifact = tmp_path / "rtl" / "demo.v"
    artifact.parent.mkdir()
    artifact.write_text("module demo; endmodule\n", encoding="utf-8")

    provider = DeterministicProvider(planner=lambda _request: _plan(call))

    def execute(tool_call, _request):
        return ToolResult(
            tool_call_id=tool_call.tool_call_id,
            tool_name=tool_call.tool_name,
            status=ToolResultStatus.SUCCEEDED,
            returncode=0,
            artifacts=(artifact,),
        )

    run = AgentExecutionEngine(provider, {"write-rtl": execute}).run(
        _request(tmp_path)
    )

    assert run.status is AgentRunStatus.SUCCEEDED
    assert run.tool_results[0].tool_call_id == call.tool_call_id
    assert run.tool_results[0].tool_name == call.tool_name
    assert run.artifacts == (artifact.resolve(),)


def test_engine_rejects_success_without_artifact_list(tmp_path):
    provider = DeterministicProvider(planner=lambda _request: _plan(_call()))
    result = ToolResult(
        tool_call_id="tool-call-1",
        tool_name="write-rtl",
        status=ToolResultStatus.SUCCEEDED,
        returncode=0,
    )

    run = AgentExecutionEngine(
        provider,
        {"write-rtl": lambda _call, _request: result},
    ).run(_request(tmp_path))

    assert run.status is AgentRunStatus.FAILED
    assert "artifact" in run.failure_reason.lower()


@pytest.mark.parametrize(
    "result",
    [
        ToolResult(
            tool_call_id="tool-call-1",
            tool_name="write-rtl",
            status=ToolResultStatus.FAILED,
            returncode=1,
            error="tool failed",
        ),
        ToolResult(
            tool_call_id="tool-call-1",
            tool_name="write-rtl",
            status=ToolResultStatus.SUCCEEDED,
            returncode=None,
        ),
    ],
)
def test_engine_never_succeeds_without_successful_tool_result(tmp_path, result):
    provider = DeterministicProvider(planner=lambda _request: _plan(_call()))
    run = AgentExecutionEngine(
        provider,
        {"write-rtl": lambda _call, _request: result},
    ).run(_request(tmp_path))

    assert run.status is AgentRunStatus.FAILED
    assert run.failure_reason


def test_engine_rejects_zero_step_plan(tmp_path):
    provider = DeterministicProvider(
        planner=lambda _request: ExecutionPlan(
            plan_id="empty-plan",
            skill_name="digital-ic-rtl-designer",
            tool_calls=(),
        )
    )

    run = AgentExecutionEngine(provider, {}).run(_request(tmp_path))

    assert run.status is AgentRunStatus.FAILED
    assert "no tool calls" in run.failure_reason.lower()


@pytest.mark.parametrize("artifact_state", ["missing", "empty"])
def test_engine_rejects_missing_or_empty_success_artifacts(tmp_path, artifact_state):
    artifact = tmp_path / "rtl" / "demo.v"
    if artifact_state == "empty":
        artifact.parent.mkdir()
        artifact.write_text("", encoding="utf-8")

    provider = DeterministicProvider(planner=lambda _request: _plan(_call()))
    result = ToolResult(
        tool_call_id="tool-call-1",
        tool_name="write-rtl",
        status=ToolResultStatus.SUCCEEDED,
        returncode=0,
        artifacts=(artifact,),
    )

    run = AgentExecutionEngine(
        provider,
        {"write-rtl": lambda _call, _request: result},
    ).run(_request(tmp_path))

    assert run.status is AgentRunStatus.FAILED
    assert artifact_state in run.failure_reason.lower()


def test_engine_rejects_mismatched_tool_result_identity(tmp_path):
    provider = DeterministicProvider(planner=lambda _request: _plan(_call()))
    result = ToolResult(
        tool_call_id="different-call",
        tool_name="write-rtl",
        status=ToolResultStatus.SUCCEEDED,
        returncode=0,
    )

    run = AgentExecutionEngine(
        provider,
        {"write-rtl": lambda _call, _request: result},
    ).run(_request(tmp_path))

    assert run.status is AgentRunStatus.FAILED
    assert "tool_call_id" in run.failure_reason


def _write_fake_mcp_server(path: Path) -> None:
    path.write_text(
        r'''
import json
import sys
import time

mode = sys.argv[1]
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        continue
    if mode == "exit":
        raise SystemExit(7)
    if mode == "hang":
        time.sleep(5)
        continue
    if mode == "invalid":
        print("not-json", flush=True)
        continue
    if mode == "error":
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": "fake failure"},
        }), flush=True)
        continue
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake-mcp", "version": "1.0"},
        }
    elif method == "tools/list":
        result = {
            "tools": [{
                "name": "echo",
                "description": "Echo arguments",
                "inputSchema": {"type": "object"},
            }]
        }
    elif method == "tools/call":
        result = {
            "content": [{
                "type": "text",
                "text": json.dumps(message["params"]["arguments"], sort_keys=True),
            }],
            "isError": False,
        }
    else:
        result = {}
    print(json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }), flush=True)
'''.lstrip(),
        encoding="utf-8",
    )


def _client(tmp_path: Path, mode: str = "normal", timeout: float = 1.0):
    server = tmp_path / "fake_mcp_server.py"
    _write_fake_mcp_server(server)
    return StdioMCPClient(
        (sys.executable, "-u", str(server), mode),
        request_timeout=timeout,
    )


def test_stdio_mcp_client_initializes_lists_and_calls_tools(tmp_path):
    with _client(tmp_path) as client:
        initialized = client.initialize()
        tools = client.list_tools()
        result = client.call_tool("echo", {"value": 7})

    assert initialized["serverInfo"]["name"] == "fake-mcp"
    assert [tool["name"] for tool in tools] == ["echo"]
    assert result["isError"] is False
    assert '"value": 7' in result["content"][0]["text"]


def test_mcp_tool_success_persists_evidence_artifact(tmp_path):
    call = ToolCall(
        tool_call_id="mcp-call-success",
        tool_name="echo",
        arguments={"value": 7},
    )
    provider = DeterministicProvider(planner=lambda _request: _plan(call))

    with _client(tmp_path) as client:
        run = AgentExecutionEngine(
            provider,
            {"echo": MCPToolExecutor(client)},
        ).run(_request(tmp_path))

    assert run.status is AgentRunStatus.SUCCEEDED
    assert len(run.artifacts) == 1
    assert run.artifacts[0].name == "mcp-call-success.json"
    assert '"value": 7' in run.artifacts[0].read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("mode", "error_type"),
    [
        ("error", MCPProtocolError),
        ("invalid", MCPProtocolError),
        ("hang", MCPTimeoutError),
        ("exit", MCPProcessError),
    ],
)
def test_stdio_mcp_client_reports_protocol_timeout_and_exit_errors(
    tmp_path,
    mode,
    error_type,
):
    with _client(tmp_path, mode=mode, timeout=0.1) as client:
        with pytest.raises(error_type):
            client.initialize()


@pytest.mark.parametrize("mode", ["error", "invalid", "hang", "exit"])
def test_mcp_failures_become_failed_tool_results(tmp_path, mode):
    call = ToolCall(
        tool_call_id="mcp-call-1",
        tool_name="echo",
        arguments={"value": 7},
    )
    provider = DeterministicProvider(planner=lambda _request: _plan(call))

    with _client(tmp_path, mode=mode, timeout=0.1) as client:
        run = AgentExecutionEngine(
            provider,
            {"echo": MCPToolExecutor(client)},
        ).run(_request(tmp_path))

    assert run.status is AgentRunStatus.FAILED
    assert run.tool_results
    assert run.tool_results[0].status is ToolResultStatus.FAILED
    assert run.tool_results[0].tool_call_id == "mcp-call-1"
    assert run.tool_results[0].returncode != 0
