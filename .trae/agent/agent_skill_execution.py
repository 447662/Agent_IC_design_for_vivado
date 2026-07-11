from pathlib import Path
from typing import Any

from skill_runtime import SkillExecutionResult, SkillExecutionStatus


def build_skill_action_handlers(agent: Any) -> Any:
    return {
        "design-document": agent.execute_design_document_skill,
        "rtl-implementation": agent.execute_rtl_implementation_skill,
        "verification-plan": agent.execute_verification_plan_skill,
    }


def skill_result(
    request: Any,
    status: Any,
    artifacts: Any,
    message: Any,
    failure_reason: Any = None,
    diagnostics: Any = (),
    tool_runs: Any = (),
) -> Any:
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


def execute_design_document_skill(_agent: Any, request: Any) -> Any:
    spec_path = Path(request.context["design_spec_path"])
    return skill_result(
        request,
        SkillExecutionStatus.SUCCEEDED,
        (spec_path,),
        "Design document skill executed",
    )


def write_skill_execution_brief(
    _agent: Any,
    request: Any,
    filename: Any,
    heading: Any,
) -> Any:
    spec_path = Path(request.context["design_spec_path"])
    output_path = request.output_dir / filename
    output_path.write_text(
        """# {heading}

- Skill: `{skill_name}`
- Skill title: {skill_title}
- Skill source: `{skill_path}`
- Skill SHA-256: `{skill_digest}`
- Design specification: `{spec_path}`

## Requirement

{user_input}

## Execution Contract

The deterministic local executor loaded and validated the complete skill file.
The skill content remains the authoritative operating contract for a future
LLM-backed executor; this local executor does not fabricate an LLM result.
""".format(
            heading=heading,
            skill_name=request.skill.name,
            skill_title=request.skill.title,
            skill_path=request.skill.path,
            skill_digest=request.skill.content_digest,
            spec_path=spec_path,
            user_input=request.user_input,
        ),
        encoding="utf-8",
    )
    return output_path


def execute_rtl_implementation_skill(agent: Any, request: Any) -> Any:
    brief_path = agent._write_skill_execution_brief(
        request,
        "rtl_implementation_brief.md",
        "RTL Implementation Skill Execution",
    )
    return agent._skill_result(
        request,
        SkillExecutionStatus.BLOCKED,
        (Path(request.context["design_spec_path"]), brief_path),
        "RTL implementation was not executed",
        failure_reason=(
            "blocked: No RTL generator and deterministic RTL checker are configured"
        ),
        diagnostics=(
            "The execution brief records the requested contract only.",
        ),
    )


def execute_verification_plan_skill(agent: Any, request: Any) -> Any:
    brief_path = agent._write_skill_execution_brief(
        request,
        "verification_execution_brief.md",
        "Verification Skill Execution",
    )
    return agent._skill_result(
        request,
        SkillExecutionStatus.BLOCKED,
        (Path(request.context["design_spec_path"]), brief_path),
        "UVM verification was not executed",
        failure_reason="No UVM generator and simulator run are configured",
        diagnostics=(
            "The execution brief is not a verification plan or simulator result.",
        ),
    )
