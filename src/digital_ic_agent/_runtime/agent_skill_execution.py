from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from digital_ic_agent._runtime.capability_preflight import PreflightReport
from digital_ic_agent._runtime.skill_runtime import (
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillHandler,
    ToolRunRecord,
)


PathValue = str | os.PathLike[str]
TargetDefinition = Mapping[str, object]


class SkillExecutionAgent(Protocol):
    targets: Mapping[str, TargetDefinition]

    def execute_design_document_skill(
        self,
        request: SkillExecutionRequest,
    ) -> SkillExecutionResult: ...

    def execute_rtl_implementation_skill(
        self,
        request: SkillExecutionRequest,
    ) -> SkillExecutionResult: ...

    def execute_verification_plan_skill(
        self,
        request: SkillExecutionRequest,
    ) -> SkillExecutionResult: ...

    def normalize_rtl_target(self, target: str) -> str: ...

    def run_preflight(self, flow: str) -> PreflightReport: ...

    def run_target_flow(
        self,
        target: str,
        flow: str,
        **kwargs: object,
    ) -> object: ...

    def write_target_verification_plan(
        self,
        target: str,
        output_dir: PathValue = "outputs",
    ) -> Mapping[str, object]: ...


def build_skill_action_handlers(
    agent: SkillExecutionAgent,
) -> Mapping[str, SkillHandler]:
    return {
        "design-document": agent.execute_design_document_skill,
        "rtl-implementation": agent.execute_rtl_implementation_skill,
        "verification-plan": agent.execute_verification_plan_skill,
    }


def skill_result(
    request: SkillExecutionRequest,
    status: SkillExecutionStatus,
    artifacts: Sequence[PathValue],
    message: str,
    failure_reason: str | None = None,
    diagnostics: Sequence[str] = (),
    tool_runs: Sequence[ToolRunRecord] = (),
) -> SkillExecutionResult:
    return SkillExecutionResult(
        skill_name=request.skill.name,
        action=request.skill.action,
        status=status,
        artifacts=tuple(Path(path) for path in artifacts),
        diagnostics=tuple(str(item) for item in diagnostics),
        tool_runs=tuple(tool_runs),
        failure_reason=failure_reason,
        message=message,
    )


def execute_design_document_skill(
    _agent: SkillExecutionAgent,
    request: SkillExecutionRequest,
) -> SkillExecutionResult:
    spec_path = Path(str(request.context["design_spec_path"]))
    return skill_result(
        request,
        SkillExecutionStatus.SUCCEEDED,
        (spec_path,),
        "Design document skill executed",
    )


def _normalized_words(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", str(value).casefold())).strip()


def _contains_target_name(requirement: str, candidate: object) -> bool:
    normalized = _normalized_words(candidate)
    if not normalized:
        return False
    return bool(
        re.search(
            r"(?<![a-z0-9]){}(?![a-z0-9])".format(re.escape(normalized)),
            requirement,
        )
    )


def _resolve_target(
    agent: SkillExecutionAgent,
    request: SkillExecutionRequest,
) -> str:
    for context_key in ("target_name", "target"):
        raw_target = request.context.get(context_key)
        if raw_target is not None and str(raw_target).strip():
            return agent.normalize_rtl_target(str(raw_target))

    requirement = _normalized_words(request.user_input)
    matches: set[str] = set()
    for target_name, target in agent.targets.items():
        candidates: list[object] = [target_name, target.get("display_name", "")]
        aliases = target.get("aliases", ())
        if isinstance(aliases, list | tuple):
            candidates.extend(aliases)
        if any(_contains_target_name(requirement, candidate) for candidate in candidates):
            matches.add(agent.normalize_rtl_target(target_name))

    if len(matches) == 1:
        return matches.pop()
    if matches:
        raise ValueError(
            "Skill request matches multiple RTL targets: {}".format(
                ", ".join(sorted(matches))
            )
        )
    raise ValueError(
        "Skill request must name one configured RTL target: {}".format(
            ", ".join(sorted(agent.targets))
        )
    )


def _collect_nonempty_files(*roots: PathValue) -> tuple[Path, ...]:
    collected: dict[Path, None] = {}
    for raw_root in roots:
        root = Path(raw_root)
        candidates = root.rglob("*") if root.is_dir() else (root,)
        for candidate in candidates:
            if candidate.is_file() and candidate.stat().st_size > 0:
                collected[candidate.resolve()] = None
    return tuple(sorted(collected, key=lambda path: path.as_posix()))


def _failed_tool_run(name: str, reason: str) -> ToolRunRecord:
    return ToolRunRecord(
        name=name,
        status=SkillExecutionStatus.FAILED,
        returncode=1,
        diagnostics=(reason,),
    )


def _is_testbench(path: Path) -> bool:
    lowered_parts = {part.casefold() for part in path.parts}
    lowered_name = path.name.casefold()
    return (
        "tb" in lowered_parts
        or "testbench" in lowered_parts
        or lowered_name.startswith("tb_")
        or "_tb." in lowered_name
    )


def _looks_like_rtl_source(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace").casefold()
    if path.suffix.casefold() in {".v", ".sv"}:
        return "module" in text and "endmodule" in text
    if path.suffix.casefold() in {".vhd", ".vhdl"}:
        return "entity" in text and "architecture" in text
    return False


def _check_generated_rtl_project(project_dir: Path) -> tuple[bool, tuple[str, ...]]:
    rtl_suffixes = {".v", ".sv", ".vhd", ".vhdl"}
    source_files = [
        path
        for path in project_dir.rglob("*")
        if path.is_file()
        and path.suffix.casefold() in rtl_suffixes
        and not _is_testbench(path)
    ]
    testbench_files = [
        path
        for path in project_dir.rglob("*")
        if path.is_file()
        and path.suffix.casefold() in rtl_suffixes
        and _is_testbench(path)
    ]
    diagnostics: list[str] = []
    if not source_files:
        diagnostics.append("Generated project has no RTL source file")
    if not testbench_files:
        diagnostics.append("Generated project has no testbench file")
    malformed = [
        path.relative_to(project_dir).as_posix()
        for path in (*source_files, *testbench_files)
        if not _looks_like_rtl_source(path)
    ]
    if malformed:
        diagnostics.append(
            "Generated HDL is missing structural declarations: {}".format(
                ", ".join(malformed)
            )
        )
    return not diagnostics, tuple(diagnostics)


def execute_rtl_implementation_skill(
    agent: SkillExecutionAgent,
    request: SkillExecutionRequest,
) -> SkillExecutionResult:
    try:
        target_name = _resolve_target(agent, request)
    except ValueError as exc:
        return skill_result(
            request,
            SkillExecutionStatus.FAILED,
            (),
            "RTL target selection failed",
            failure_reason=str(exc),
        )

    project_dir = request.output_dir / target_name
    spec_path = Path(str(request.context["design_spec_path"]))
    tool_runs: list[ToolRunRecord] = []
    try:
        generated = bool(
            agent.run_target_flow(
                target_name,
                "generate-rtl",
                output_dir=request.output_dir,
            )
        )
        tool_runs.append(
            ToolRunRecord(
                name="generate-rtl",
                status=(
                    SkillExecutionStatus.SUCCEEDED
                    if generated
                    else SkillExecutionStatus.FAILED
                ),
                returncode=0 if generated else 1,
            )
        )
        if not generated:
            return skill_result(
                request,
                SkillExecutionStatus.FAILED,
                _collect_nonempty_files(spec_path, project_dir),
                "RTL target generation failed",
                failure_reason="Target generate-rtl flow returned a false result",
                tool_runs=tool_runs,
            )

        checked, check_diagnostics = _check_generated_rtl_project(project_dir)
        tool_runs.append(
            ToolRunRecord(
                name="rtl-check",
                status=(
                    SkillExecutionStatus.SUCCEEDED
                    if checked
                    else SkillExecutionStatus.FAILED
                ),
                returncode=0 if checked else 1,
                diagnostics=check_diagnostics,
            )
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        reason = "{}: {}".format(type(exc).__name__, exc)
        tool_runs.append(_failed_tool_run("rtl-check", reason))
        return skill_result(
            request,
            SkillExecutionStatus.FAILED,
            _collect_nonempty_files(spec_path, project_dir),
            "RTL target execution failed",
            failure_reason=reason,
            tool_runs=tool_runs,
        )

    artifacts = _collect_nonempty_files(spec_path, project_dir)
    if not checked:
        return skill_result(
            request,
            SkillExecutionStatus.FAILED,
            artifacts,
            "RTL target check failed",
            failure_reason="Deterministic generated RTL check failed",
            tool_runs=tool_runs,
        )
    return skill_result(
        request,
        SkillExecutionStatus.SUCCEEDED,
        artifacts,
        "RTL target generated and checked successfully",
        tool_runs=tool_runs,
    )


def _verification_plan_artifacts(
    plan: Mapping[str, object],
) -> tuple[Path, ...]:
    paths = [
        Path(value)
        for value in plan.values()
        if isinstance(value, str | os.PathLike)
    ]
    return _collect_nonempty_files(*paths)


def _target_flows(
    agent: SkillExecutionAgent,
    target_name: str,
) -> tuple[str, ...]:
    raw_flows = agent.targets[target_name].get("flows", ())
    if not isinstance(raw_flows, list | tuple):
        raise ValueError("Target flows must be a list or tuple")
    return tuple(str(flow) for flow in raw_flows)


def execute_verification_plan_skill(
    agent: SkillExecutionAgent,
    request: SkillExecutionRequest,
) -> SkillExecutionResult:
    try:
        target_name = _resolve_target(agent, request)
        plan = agent.write_target_verification_plan(
            target_name,
            output_dir=request.output_dir,
        )
        plan_artifacts = _verification_plan_artifacts(plan)
        target_flows = _target_flows(agent, target_name)
    except (OSError, TypeError, ValueError) as exc:
        return skill_result(
            request,
            SkillExecutionStatus.FAILED,
            (),
            "Verification plan generation failed",
            failure_reason="{}: {}".format(type(exc).__name__, exc),
        )

    if "uvm-smoke" not in target_flows:
        return skill_result(
            request,
            SkillExecutionStatus.PARTIAL,
            plan_artifacts,
            "Verification plan generated; target has no UVM smoke flow",
            failure_reason="Target does not declare uvm-smoke",
            diagnostics=("Generated the target verification plan without simulation.",),
        )

    preflight = agent.run_preflight("uvm-smoke")
    if not preflight.ok:
        return skill_result(
            request,
            SkillExecutionStatus.PARTIAL,
            plan_artifacts,
            "Verification plan generated; UVM smoke prerequisites are unavailable",
            failure_reason="Missing required capabilities: {}".format(
                ", ".join(preflight.missing_required)
            ),
            diagnostics=("Generated the target verification plan without simulation.",),
        )

    project_dir = request.output_dir / target_name
    try:
        passed = bool(
            agent.run_target_flow(
                target_name,
                "uvm-smoke",
                output_dir=request.output_dir,
                open_wave_gui=False,
            )
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        reason = "{}: {}".format(type(exc).__name__, exc)
        return skill_result(
            request,
            SkillExecutionStatus.FAILED,
            _collect_nonempty_files(*plan_artifacts, project_dir),
            "UVM smoke execution failed",
            failure_reason=reason,
            tool_runs=(_failed_tool_run("uvm-smoke", reason),),
        )

    artifacts = _collect_nonempty_files(*plan_artifacts, project_dir)
    tool_run = ToolRunRecord(
        name="uvm-smoke",
        status=(
            SkillExecutionStatus.SUCCEEDED
            if passed
            else SkillExecutionStatus.FAILED
        ),
        returncode=0 if passed else 1,
    )
    if not passed:
        return skill_result(
            request,
            SkillExecutionStatus.FAILED,
            artifacts,
            "UVM smoke flow failed",
            failure_reason="Target uvm-smoke flow returned a false result",
            tool_runs=(tool_run,),
        )
    return skill_result(
        request,
        SkillExecutionStatus.SUCCEEDED,
        artifacts,
        "UVM smoke flow completed successfully",
        tool_runs=(tool_run,),
    )
