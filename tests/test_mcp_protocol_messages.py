import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.mcp_client import MCPProtocolError, MCPTimeoutError, StdioMCPClient  # noqa: E402


SERVER_SOURCE = r'''
import json
import sys
import time

mode = sys.argv[1]
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    request_id = message["id"]
    method = message["method"]
    if mode == "notification":
        print(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/progress",
            "params": {"progressToken": "token", "progress": 1},
        }), flush=True)
    if mode == "out-of-order" and request_id == 1:
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"tools": []},
        }), flush=True)
    if mode == "notification-timeout":
        for index in range(5):
            print(json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {"progress": index},
            }), flush=True)
            time.sleep(0.03)
        time.sleep(1)
        continue
    if mode == "invalid-rpc":
        print(json.dumps({"jsonrpc": "1.0", "id": request_id, "result": {}}), flush=True)
        continue
    if mode == "out-of-order" and request_id == 2:
        continue
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {"name": "message-flow-server", "version": "1"},
        }
    elif method == "tools/list":
        result = {"tools": []}
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}), flush=True)
'''.lstrip()


def _client(tmp_path: Path, mode: str, timeout: float = 0.5) -> StdioMCPClient:
    server = tmp_path / "message_flow_server.py"
    server.write_text(SERVER_SOURCE, encoding="utf-8")
    return StdioMCPClient(
        (sys.executable, "-u", str(server), mode),
        request_timeout=timeout,
    )


def test_mcp_request_skips_notifications_before_matching_response(tmp_path):
    with _client(tmp_path, "notification") as client:
        initialized = client.initialize()
        tools = client.list_tools()

    assert initialized["serverInfo"]["name"] == "message-flow-server"
    assert tools == []


def test_mcp_request_caches_out_of_order_response_by_id(tmp_path):
    with _client(tmp_path, "out-of-order") as client:
        initialized = client.initialize()
        tools = client.list_tools()

    assert initialized["serverInfo"]["name"] == "message-flow-server"
    assert tools == []


def test_mcp_notifications_do_not_reset_request_deadline(tmp_path):
    started = time.monotonic()
    with _client(tmp_path, "notification-timeout", timeout=0.08) as client:
        with pytest.raises(MCPTimeoutError, match=r"initialize.*id=1"):
            client.initialize()
        assert client._process is None

    assert time.monotonic() - started < 0.5


def test_mcp_protocol_errors_identify_method_and_request_id(tmp_path):
    with _client(tmp_path, "invalid-rpc") as client:
        with pytest.raises(MCPProtocolError, match=r"initialize.*id=1"):
            client.initialize()
