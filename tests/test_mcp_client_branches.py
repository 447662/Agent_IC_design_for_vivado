import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime import mcp_client  # noqa: E402
from digital_ic_agent._runtime.mcp_client import (  # noqa: E402
    MCPProcessError,
    MCPProtocolError,
    StdioMCPClient,
)


def test_mcp_client_rejects_empty_command_and_nonpositive_timeout():
    with pytest.raises(ValueError, match="must not be empty"):
        StdioMCPClient(())
    with pytest.raises(ValueError, match="must be positive"):
        StdioMCPClient(("server",), request_timeout=0)


@pytest.mark.parametrize(
    "message",
    [
        [],
        {"jsonrpc": "2.0", "result": {}},
        {"jsonrpc": "2.0", "id": True, "result": {}},
    ],
)
def test_mcp_wait_rejects_invalid_response_envelopes(message):
    client = StdioMCPClient(("server",))
    client._messages.put(json.dumps(message))

    with pytest.raises(MCPProtocolError):
        client._wait_for_response(1, "tools/list", time.monotonic() + 1)


def test_mcp_wait_uses_cached_response_before_queue():
    client = StdioMCPClient(("server",))
    expected = {"jsonrpc": "2.0", "id": 7, "result": {}}
    client._pending_responses[7] = expected

    assert client._wait_for_response(7, "tools/list", time.monotonic() + 1) == expected


def test_mcp_request_rejects_non_object_result(monkeypatch):
    client = StdioMCPClient(("server",))
    monkeypatch.setattr(client, "_write", lambda _message: None)
    client._messages.put('{"jsonrpc":"2.0","id":1,"result":[]}')

    with pytest.raises(MCPProtocolError, match="result must be an object"):
        client._request("tools/list", {})


def test_mcp_readers_handle_missing_process_streams():
    client = StdioMCPClient(("server",))
    client._read_stdout()
    assert client._messages.get_nowait() is mcp_client._EOF
    client._read_stderr()
    assert client._stderr_lines == []


class ExitedProcess:
    stdin = None
    stdout = None
    stderr = None

    @staticmethod
    def poll():
        return 9


def test_mcp_process_error_and_write_report_unavailable_process():
    client = StdioMCPClient(("server",))
    client._process = ExitedProcess()
    client._stderr_lines = ["first", "last error"]

    with pytest.raises(MCPProcessError, match="stdin is unavailable"):
        client._write({"jsonrpc": "2.0"})

    client._process.stdin = object()
    with pytest.raises(MCPProcessError, match=r"(?s)code 9.*last error"):
        client._write({"jsonrpc": "2.0"})


class ClosingStream:
    def close(self):
        return None


class HangingProcess:
    stdin = ClosingStream()

    def __init__(self):
        self.waits = 0
        self.killed = False

    @staticmethod
    def poll():
        return None

    @staticmethod
    def terminate():
        return None

    def wait(self, timeout):
        self.waits += 1
        if self.waits == 1:
            raise subprocess.TimeoutExpired("server", timeout)
        return 0

    def kill(self):
        self.killed = True


def test_mcp_close_kills_process_that_ignores_terminate():
    client = StdioMCPClient(("server",))
    process = HangingProcess()
    client._process = process

    client.close()

    assert process.killed is True
    assert process.waits == 2
    assert client._process is None
