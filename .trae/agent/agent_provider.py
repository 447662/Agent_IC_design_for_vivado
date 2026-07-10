from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Protocol

from agent_contracts import AgentRequest, ExecutionPlan, ToolCall
from intent_router import analyze_requirement


class AgentProvider(Protocol):
    def create_plan(self, request: AgentRequest) -> ExecutionPlan:
        ...


class DeterministicProvider:
    def __init__(self, planner: Callable[[AgentRequest], ExecutionPlan]) -> None:
        self._planner = planner

    def create_plan(self, request: AgentRequest) -> ExecutionPlan:
        plan = self._planner(request)
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("Provider must return ExecutionPlan")
        if not plan.plan_id.strip():
            raise ValueError("ExecutionPlan plan_id must not be empty")
        if not plan.skill_name.strip():
            raise ValueError("ExecutionPlan skill_name must not be empty")
        return plan


RequirementRouter = Callable[
    [Iterable[Mapping[str, Any]], str],
    list[str],
]


class ConfiguredAgentProvider:
    def __init__(
        self,
        skills: Sequence[Mapping[str, Any]],
        router: RequirementRouter = analyze_requirement,
    ) -> None:
        self._skills = tuple(dict(skill) for skill in skills)
        self._router = router
        self._skills_by_name: dict[str, Mapping[str, Any]] = {}
        for skill in self._skills:
            name = str(skill.get("name", "")).strip()
            action = str(skill.get("action", "")).strip()
            if not name or not action:
                raise ValueError("Configured skills require non-empty name and action")
            if name in self._skills_by_name:
                raise ValueError("Duplicate configured skill: {}".format(name))
            self._skills_by_name[name] = skill

    def _selected_skills(self, request: AgentRequest) -> tuple[str, ...]:
        if "selected_skills" in request.context:
            raw_selected = request.context["selected_skills"]
            if not isinstance(raw_selected, (list, tuple)):
                raise ValueError("selected_skills context must be a list or tuple")
            selected = tuple(str(name).strip() for name in raw_selected)
        else:
            selected = tuple(self._router(self._skills, request.user_input))

        if not selected or any(not name for name in selected):
            raise ValueError("No skill selected for agent request")
        unknown = [name for name in selected if name not in self._skills_by_name]
        if unknown:
            raise ValueError(
                "Execution plan references unknown skills: {}".format(
                    ", ".join(unknown)
                )
            )
        if len(set(selected)) != len(selected):
            raise ValueError("Execution plan contains duplicate skills")
        return selected

    def create_plan(self, request: AgentRequest) -> ExecutionPlan:
        if not request.request_id.strip():
            raise ValueError("AgentRequest request_id must not be empty")
        selected = self._selected_skills(request)
        tool_calls = []
        for index, skill_name in enumerate(selected, start=1):
            skill = self._skills_by_name[skill_name]
            action = str(skill["action"]).strip()
            tool_calls.append(
                ToolCall(
                    tool_call_id="{}-skill-{}".format(request.request_id, index),
                    tool_name="skill:{}".format(action),
                    arguments={"skill_name": skill_name},
                )
            )
        return ExecutionPlan(
            plan_id="{}-plan".format(request.request_id),
            skill_name=selected[0],
            tool_calls=tuple(tool_calls),
        )
