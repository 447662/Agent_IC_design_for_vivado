from collections.abc import Mapping
from typing import Any, Protocol

from digital_ic_agent._runtime.agent_contracts import (
    AgentRequest,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)
from digital_ic_agent._runtime.skill_runtime import (
    SkillDefinition,
    SkillExecutionRequest,
    SkillExecutionStatus,
)


class SkillToolHost(Protocol):
    skill_executor: Any
    skill_result_validator: Any

    @property
    def loaded_skills(self) -> Mapping[str, SkillDefinition]:
        ...

    def generate_design_spec(
        self,
        user_input: str,
        matched_skills: tuple[str, ...],
        output_dir: Any,
    ) -> Any:
        ...


class SkillExecutionTool:
    def __init__(self, host: SkillToolHost) -> None:
        self.host = host

    @staticmethod
    def _selected_skills(
        request: AgentRequest,
        skill_name: str,
    ) -> tuple[str, ...]:
        raw_selected = request.context.get("selected_skills", (skill_name,))
        if not isinstance(raw_selected, list | tuple):
            raise ValueError("selected_skills context must be a list or tuple")
        selected = tuple(str(name).strip() for name in raw_selected)
        if not selected or any(not name for name in selected):
            raise ValueError("Agent request contains no selected skills")
        return selected

    def execute(self, call: ToolCall, request: AgentRequest) -> ToolResult:
        skill_name = str(call.arguments.get("skill_name", "")).strip()
        if not skill_name:
            raise ValueError("Skill tool call missing skill_name")
        try:
            skill = self.host.loaded_skills[skill_name]
        except KeyError as exc:
            raise ValueError(f"Skill is not loaded: {skill_name}") from exc
        expected_tool_name = f"skill:{skill.action}"
        if call.tool_name != expected_tool_name:
            raise ValueError(
                f"Skill tool mismatch: expected {expected_tool_name}, got {call.tool_name}"
            )

        selected_skills = self._selected_skills(request, skill_name)
        spec_path = self.host.generate_design_spec(
            request.user_input,
            selected_skills,
            request.output_dir,
        )
        skill_request = SkillExecutionRequest(
            skill=skill,
            user_input=request.user_input,
            output_dir=spec_path.parent,
            context={"design_spec_path": str(spec_path)},
        )
        result = self.host.skill_result_validator.validate(
            skill_request,
            self.host.skill_executor.execute(skill_request),
        )
        succeeded = result.status is SkillExecutionStatus.SUCCEEDED
        artifacts = result.validated_artifacts or result.artifacts
        return ToolResult(
            tool_call_id=call.tool_call_id,
            tool_name=call.tool_name,
            status=(
                ToolResultStatus.SUCCEEDED
                if succeeded
                else ToolResultStatus.FAILED
            ),
            returncode=0 if succeeded else 1,
            artifacts=tuple(artifacts),
            output=result.message,
            error=None if succeeded else (result.failure_reason or result.message),
            metadata={
                "skill_name": result.skill_name,
                "skill_action": result.action,
                "skill_status": result.status.value,
                "diagnostics": tuple(result.diagnostics),
            },
        )
