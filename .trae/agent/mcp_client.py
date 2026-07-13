import json
import queue
import subprocess
import threading
from collections.abc import Mapping, Sequence
from contextlib import suppress
from types import TracebackType
from typing import Any, Protocol


class MCPError(RuntimeError):
    pass


class MCPProtocolError(MCPError):
    pass


class MCPTimeoutError(MCPError):
    pass


class MCPProcessError(MCPError):
    pass


class MCPClient(Protocol):
    def initialize(self) -> Mapping[str, Any]:
        ...

    def list_tools(self) -> list[Mapping[str, Any]]:
        ...

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        ...

    def close(self) -> None:
        ...


_EOF = object()


class StdioMCPClient:
    def __init__(
        self,
        command: Sequence[str],
        *,
        request_timeout: float = 30.0,
        protocol_version: str = "2024-11-05",
    ) -> None:
        if not command:
            raise ValueError("MCP command must not be empty")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        self.command = tuple(str(part) for part in command)
        self.request_timeout = float(request_timeout)
        self.protocol_version = protocol_version
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[object] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._next_id = 1
        self._initialized = False

    def __enter__(self) -> "StdioMCPClient":
        self._start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _start(self) -> None:
        if self._process is not None:
            return
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            self._messages.put(_EOF)
            return
        for line in process.stdout:
            self._messages.put(line)
        self._messages.put(_EOF)

    def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for line in process.stderr:
            self._stderr_lines.append(line.rstrip())

    def _process_error(self) -> MCPProcessError:
        process = self._process
        returncode = None if process is None else process.poll()
        detail = "\n".join(self._stderr_lines[-10:]).strip()
        message = "MCP process exited"
        if returncode is not None:
            message += " with code {}".format(returncode)
        if detail:
            message += ": {}".format(detail)
        return MCPProcessError(message)

    def _write(self, message: Mapping[str, Any]) -> None:
        self._start()
        process = self._process
        if process is None or process.stdin is None:
            raise MCPProcessError("MCP process stdin is unavailable")
        if process.poll() is not None:
            raise self._process_error()
        try:
            process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise self._process_error() from exc

    def _request(
        self,
        method: str,
        params: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": dict(params),
            }
        )

        try:
            raw_message = self._messages.get(timeout=self.request_timeout)
        except queue.Empty as exc:
            process = self._process
            if process is not None and process.poll() is not None:
                raise self._process_error() from exc
            raise MCPTimeoutError(
                "MCP request timed out: {}".format(method)
            ) from exc
        if raw_message is _EOF:
            raise self._process_error()
        try:
            message = json.loads(str(raw_message))
        except json.JSONDecodeError as exc:
            raise MCPProtocolError(
                "MCP server returned invalid JSON: {}".format(str(raw_message).strip())
            ) from exc
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise MCPProtocolError("MCP response is not a JSON-RPC 2.0 object")
        if message.get("id") != request_id:
            raise MCPProtocolError("MCP response id does not match request id")
        if "error" in message:
            error = message["error"]
            if isinstance(error, dict):
                detail = error.get("message", error)
            else:
                detail = error
            raise MCPProtocolError("MCP request failed: {}".format(detail))
        result = message.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError("MCP response result must be an object")
        return result

    def _notify(self, method: str, params: Mapping[str, Any]) -> None:
        self._write(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": dict(params),
            }
        )

    def initialize(self) -> Mapping[str, Any]:
        if self._initialized:
            return {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
            }
        result = self._request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "digital-ic-agent",
                    "version": "1.0.0",
                },
            },
        )
        negotiated = result.get("protocolVersion")
        if not isinstance(negotiated, str) or not negotiated:
            raise MCPProtocolError("MCP initialize response missing protocolVersion")
        self.protocol_version = negotiated
        self._notify("notifications/initialized", {})
        self._initialized = True
        return result

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    def list_tools(self) -> list[Mapping[str, Any]]:
        self._ensure_initialized()
        result = self._request("tools/list", {})
        tools = result.get("tools")
        if not isinstance(tools, list) or not all(
            isinstance(item, dict) for item in tools
        ):
            raise MCPProtocolError("MCP tools/list result must contain a tools list")
        return tools

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self._ensure_initialized()
        if not name.strip():
            raise ValueError("MCP tool name must not be empty")
        return self._request(
            "tools/call",
            {
                "name": name,
                "arguments": dict(arguments),
            },
        )

    def close(self) -> None:
        process = self._process
        if process is None:
            return
        if process.stdin is not None:
            with suppress(OSError):
                process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
        self._process = None
