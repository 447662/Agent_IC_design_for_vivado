import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Callable, Mapping, Protocol, cast

from digital_ic_agent._runtime.agent_contracts import (
    AgentRequest,
    AgentRun,
    AgentRunStatus,
    ExecutionPlan,
    PayloadMapping,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)
from digital_ic_agent._runtime.agent_provider import AgentProvider
from digital_ic_agent._runtime.agent_errors import sanitize_details, sanitize_text
from digital_ic_agent._runtime.mcp_client import MCPClient, MCPError


class ToolExecutor(Protocol):
    def execute(self, call: ToolCall, request: AgentRequest) -> ToolResult:
        ...


ToolHandler = Callable[[ToolCall, AgentRequest], ToolResult] | ToolExecutor


class AgentExecutionEngine:
    def __init__(
        self,
        provider: AgentProvider,
        tools: Mapping[str, ToolHandler],
    ) -> None:
        self.provider = provider
        self.tools = dict(tools)

    @staticmethod
    def _failed(
        request: AgentRequest,
        plan: ExecutionPlan | None,
        reason: str,
        results: tuple[ToolResult, ...] = (),
        artifacts: tuple[Path, ...] = (),
    ) -> AgentRun:
        return AgentRun(
            request=request,
            plan=plan,
            status=AgentRunStatus.FAILED,
            tool_results=results,
            artifacts=artifacts,
            failure_reason=reason,
        )

    @staticmethod
    def _invoke(
        executor: ToolHandler,
        call: ToolCall,
        request: AgentRequest,
    ) -> ToolResult:
        method = getattr(executor, "execute", None)
        if callable(method):
            return cast(ToolResult, method(call, request))
        if callable(executor):
            return executor(call, request)
        raise TypeError("Tool executor is not callable: {}".format(call.tool_name))

    @staticmethod
    def _validate_identity(call: ToolCall, result: ToolResult) -> str | None:
        if result.tool_call_id != call.tool_call_id:
            return "ToolResult tool_call_id does not match ToolCall"
        if result.tool_name != call.tool_name:
            return "ToolResult tool_name does not match ToolCall"
        return None

    @staticmethod
    def _sanitize_result(result: ToolResult) -> ToolResult:
        return replace(
            result,
            output=sanitize_text(result.output),
            error=sanitize_text(result.error) if result.error is not None else None,
            metadata=cast(
                PayloadMapping,
                sanitize_details(dict(result.metadata)),
            ),
        )

    @staticmethod
    def _resolve_artifacts(
        request: AgentRequest,
        result: ToolResult,
    ) -> tuple[tuple[Path, ...], str | None]:
        root = request.output_dir.resolve()
        resolved_artifacts = []
        for raw_path in result.artifacts:
            path = Path(raw_path)
            resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                return (), "Artifact escapes output directory: {}".format(path)
            if not resolved.is_file():
                return (), "Missing artifact: {}".format(path)
            if resolved.stat().st_size <= 0:
                return (), "Empty artifact: {}".format(path)
            resolved_artifacts.append(resolved)
        return tuple(resolved_artifacts), None

    def run(self, request: AgentRequest) -> AgentRun:
        try:
            plan = self.provider.create_plan(request)
        except (TypeError, ValueError) as exc:
            return self._failed(request, None, "Provider plan failed: {}".format(exc))

        if not plan.tool_calls:
            return self._failed(request, plan, "Execution plan has no tool calls")

        results: list[ToolResult] = []
        artifacts: list[Path] = []
        for call in plan.tool_calls:
            executor = self.tools.get(call.tool_name)
            if executor is None:
                result = ToolResult(
                    tool_call_id=call.tool_call_id,
                    tool_name=call.tool_name,
                    status=ToolResultStatus.FAILED,
                    returncode=127,
                    error="Tool is not registered: {}".format(call.tool_name),
                )
            else:
                try:
                    result = self._invoke(executor, call, request)
                except Exception as exc:
                    result = ToolResult(
                        tool_call_id=call.tool_call_id,
                        tool_name=call.tool_name,
                        status=ToolResultStatus.FAILED,
                        returncode=1,
                        error="Tool execution raised: {}".format(
                            sanitize_text(str(exc))
                        ),
                    )
            result = self._sanitize_result(result)
            results.append(result)

            identity_error = self._validate_identity(call, result)
            if identity_error:
                return self._failed(
                    request,
                    plan,
                    identity_error,
                    tuple(results),
                    tuple(artifacts),
                )
            if (
                result.status is not ToolResultStatus.SUCCEEDED
                or result.returncode != 0
            ):
                return self._failed(
                    request,
                    plan,
                    result.error or "Tool result did not succeed",
                    tuple(results),
                    tuple(artifacts),
                )
            if not result.artifacts:
                return self._failed(
                    request,
                    plan,
                    "Successful tool result has no artifacts",
                    tuple(results),
                    tuple(artifacts),
                )

            resolved, artifact_error = self._resolve_artifacts(request, result)
            if artifact_error:
                return self._failed(
                    request,
                    plan,
                    artifact_error,
                    tuple(results),
                    tuple(artifacts),
                )
            artifacts.extend(resolved)

        return AgentRun(
            request=request,
            plan=plan,
            status=AgentRunStatus.SUCCEEDED,
            tool_results=tuple(results),
            artifacts=tuple(artifacts),
        )


class MCPToolExecutor:
    def __init__(self, client: MCPClient) -> None:
        self.client = client

    def execute(self, call: ToolCall, request: AgentRequest) -> ToolResult:
        try:
            payload = self.client.call_tool(call.tool_name, dict(call.arguments))
        except MCPError as exc:
            return ToolResult(
                tool_call_id=call.tool_call_id,
                tool_name=call.tool_name,
                status=ToolResultStatus.FAILED,
                returncode=1,
                error=sanitize_text(str(exc)),
            )

        is_error = bool(payload.get("isError", False))
        sanitized_arguments = cast(
            PayloadMapping,
            sanitize_details(dict(call.arguments)),
        )
        sanitized_payload = cast(
            PayloadMapping,
            sanitize_details(dict(payload)),
        )
        evidence_dir = request.output_dir / "agent-evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_name = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            call.tool_call_id,
        ).strip("-")
        if not evidence_name:
            evidence_name = "mcp-tool-result"
        evidence_path = evidence_dir / "{}.json".format(evidence_name)
        evidence = {
            "schema_version": "digital-ic-agent.mcp-evidence.v1",
            "tool_call": {
                "tool_call_id": call.tool_call_id,
                "tool_name": call.tool_name,
                "arguments": sanitized_arguments,
            },
            "result": sanitized_payload,
        }
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return ToolResult(
            tool_call_id=call.tool_call_id,
            tool_name=call.tool_name,
            status=(
                ToolResultStatus.FAILED
                if is_error
                else ToolResultStatus.SUCCEEDED
            ),
            returncode=1 if is_error else 0,
            artifacts=(evidence_path,),
            output=json.dumps(sanitized_payload, ensure_ascii=False, sort_keys=True),
            error="MCP tool returned isError=true" if is_error else None,
            metadata={"mcp_result": sanitized_payload},
        )
