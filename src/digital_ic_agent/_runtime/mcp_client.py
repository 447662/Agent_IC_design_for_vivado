import json
import os
import queue
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from collections import deque
from contextlib import suppress
from types import TracebackType
from typing import Any, Protocol

from digital_ic_agent._runtime.agent_errors import sanitize_text


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
DEFAULT_ENVIRONMENT_ALLOWLIST = (
    "APPDATA",
    "COMSPEC",
    "HOME",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "PROGRAMDATA",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "UV_CACHE_DIR",
    "UV_LINK_MODE",
    "WINDIR",
)
DEFAULT_MAX_MESSAGE_BYTES = 1024 * 1024
DEFAULT_MAX_QUEUE_MESSAGES = 256
DEFAULT_MAX_STDERR_LINES = 100
DEFAULT_MAX_PENDING_RESPONSES = 128


class StdioMCPClient:
    def __init__(
        self,
        command: Sequence[str],
        *,
        request_timeout: float = 30.0,
        protocol_version: str = "2024-11-05",
        environment_allowlist: Sequence[str] = DEFAULT_ENVIRONMENT_ALLOWLIST,
        max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
        max_queue_messages: int = DEFAULT_MAX_QUEUE_MESSAGES,
        max_stderr_lines: int = DEFAULT_MAX_STDERR_LINES,
        max_pending_responses: int = DEFAULT_MAX_PENDING_RESPONSES,
    ) -> None:
        if not command:
            raise ValueError("MCP command must not be empty")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        for name, value in (
            ("max_message_bytes", max_message_bytes),
            ("max_queue_messages", max_queue_messages),
            ("max_stderr_lines", max_stderr_lines),
            ("max_pending_responses", max_pending_responses),
        ):
            if value <= 0:
                raise ValueError("{} must be positive".format(name))
        self.command = tuple(str(part) for part in command)
        self.request_timeout = float(request_timeout)
        self.protocol_version = protocol_version
        self.environment_allowlist = tuple(str(name) for name in environment_allowlist)
        self.max_message_bytes = int(max_message_bytes)
        self.max_pending_responses = int(max_pending_responses)
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[object] = queue.Queue(maxsize=max_queue_messages)
        self._stderr_lines: deque[str] = deque(maxlen=max_stderr_lines)
        self._reader_error: MCPProtocolError | None = None
        self._next_id = 1
        self._initialized = False
        self._pending_responses: dict[int, Mapping[str, Any]] = {}
        self._request_lock = threading.Lock()

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
            env=self._build_child_environment(),
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _build_child_environment(self) -> dict[str, str]:
        allowed = {name.casefold() for name in self.environment_allowlist}
        return {
            key: value
            for key, value in os.environ.items()
            if key.casefold() in allowed
        }

    def _set_reader_error(self, message: str) -> None:
        if self._reader_error is None:
            self._reader_error = MCPProtocolError(message)

    def _read_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            with suppress(queue.Full):
                self._messages.put_nowait(_EOF)
            return
        for line in process.stdout:
            if len(line.encode("utf-8")) > self.max_message_bytes:
                self._set_reader_error("MCP stdout exceeded message size limit")
                break
            try:
                self._messages.put_nowait(line)
            except queue.Full:
                self._set_reader_error("MCP stdout exceeded queue message limit")
                break
        with suppress(queue.Full):
            self._messages.put_nowait(_EOF)

    def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for line in process.stderr:
            self._stderr_lines.append(sanitize_text(line.rstrip()))

    def _process_error(self) -> MCPProcessError:
        process = self._process
        returncode = None if process is None else process.poll()
        detail = "\n".join(list(self._stderr_lines)[-10:]).strip()
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
        try:
            with self._request_lock:
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
                deadline = time.monotonic() + self.request_timeout
                message = self._wait_for_response(request_id, method, deadline)
            if "error" in message:
                error = message["error"]
                if isinstance(error, dict):
                    detail = error.get("message", error)
                else:
                    detail = error
                raise MCPProtocolError(
                    "MCP request {} id={} failed: {}".format(
                        method,
                        request_id,
                        sanitize_text(str(detail)),
                    )
                )
            result = message.get("result")
            if not isinstance(result, dict):
                raise MCPProtocolError("MCP response result must be an object")
            return result
        except MCPError:
            self.close()
            raise

    def _wait_for_response(
        self,
        request_id: int,
        method: str,
        deadline: float,
    ) -> Mapping[str, Any]:
        pending = self._pending_responses.pop(request_id, None)
        if pending is not None:
            return pending
        while True:
            if self._reader_error is not None:
                raise self._reader_error
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MCPTimeoutError(
                    "MCP request timed out: {} id={}".format(method, request_id)
                )
            try:
                raw_message = self._messages.get(timeout=remaining)
            except queue.Empty as exc:
                process = self._process
                if process is not None and process.poll() is not None:
                    raise self._process_error() from exc
                raise MCPTimeoutError(
                    "MCP request timed out: {} id={}".format(method, request_id)
                ) from exc
            if raw_message is _EOF:
                raise self._process_error()
            if len(str(raw_message).encode("utf-8")) > self.max_message_bytes:
                raise MCPProtocolError(
                    "MCP {} id={} response exceeded message size limit".format(
                        method,
                        request_id,
                    )
                )
            try:
                decoded = json.loads(str(raw_message))
            except json.JSONDecodeError as exc:
                raise MCPProtocolError(
                    "MCP {} id={} returned invalid JSON: {}".format(
                        method,
                        request_id,
                        str(raw_message).strip(),
                    )
                ) from exc
            if not isinstance(decoded, dict) or decoded.get("jsonrpc") != "2.0":
                raise MCPProtocolError(
                    "MCP {} id={} response is not a JSON-RPC 2.0 object".format(
                        method,
                        request_id,
                    )
                )
            response_id = decoded.get("id")
            if response_id is None and isinstance(decoded.get("method"), str):
                continue
            if not isinstance(response_id, int) or isinstance(response_id, bool):
                raise MCPProtocolError(
                    "MCP {} id={} response has an invalid id".format(method, request_id)
                )
            response = dict(decoded)
            if response_id != request_id:
                if (
                    response_id not in self._pending_responses
                    and len(self._pending_responses) >= self.max_pending_responses
                ):
                    raise MCPProtocolError(
                        "MCP {} id={} exceeded pending response limit".format(
                            method,
                            request_id,
                        )
                    )
                self._pending_responses[response_id] = response
                continue
            return response

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
