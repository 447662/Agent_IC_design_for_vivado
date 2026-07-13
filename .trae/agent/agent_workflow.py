from pathlib import Path
from typing import Any, TextIO
from uuid import uuid4
import sys

from agent_contracts import AgentRequest, AgentRunStatus


def emit_workflow_lines(lines: list[str], stream: TextIO | None = None) -> None:
    target_stream = stream or sys.stdout
    for line in lines:
        print(line, file=target_stream)


def build_workflow_header_lines() -> list[str]:
    return [
        "=" * 60,
        "数字IC前端设计Agent",
        "=" * 60,
    ]


def build_workflow_tool_check_missing_lines(
    agent: Any,
    skill: Any,
    missing_required: list[str],
) -> list[str]:
    return [
        "\n{} 技能 {} 缺少能力: {}".format(
            agent.WARN,
            skill.name,
            ", ".join(missing_required),
        )
    ]


def build_workflow_tool_result_lines(agent: Any, tool_results: Any) -> list[str]:
    lines = []
    for result in tool_results:
        lines.append(
            "{} {} -> {}".format(
                agent.OK,
                result.tool_name,
                ", ".join(str(path) for path in result.artifacts),
            )
        )
    return lines


def build_workflow_footer_lines() -> list[str]:
    return [
        "\n【后续建议】",
        "请补充文档中的人工确认项，再进入 RTL 实现或 UVM 验证阶段。",
        "\n" + "=" * 60,
        "工作流执行完成",
        "=" * 60,
    ]


def execute_workflow(
    agent: Any,
    user_input: Any,
    output_dir: Any = "outputs",
    skip_tool_check: Any = False,
) -> bool:
    emit_workflow_lines(build_workflow_header_lines())

    emit_workflow_lines(["\n【步骤1/4: 需求分析】"])
    matched_skills = agent.recommend_skills(user_input)
    try:
        loaded_skills = [agent.loaded_skills[name] for name in matched_skills]
    except KeyError as exc:
        emit_workflow_lines(["技能未加载: {}".format(exc)], stream=sys.stderr)
        return False

    if skip_tool_check:
        emit_workflow_lines(
            [
                "\n【步骤2/4: 工具检查】",
                agent.WARN + " 已根据 --no-tool-check 跳过外部工具检查",
            ]
        )
    else:
        emit_workflow_lines(["\n【步骤2/4: 工具检查】"])
        for skill in loaded_skills:
            report = agent.run_preflight(skill.action)
            if not report.ok:
                emit_workflow_lines(
                    build_workflow_tool_check_missing_lines(
                        agent,
                        skill,
                        report.missing_required,
                    )
                )
                return False
        emit_workflow_lines([agent.OK + " 当前技能动作所需能力已就绪"])

    emit_workflow_lines(["\n【步骤3/4: 执行计划】"])
    request = AgentRequest(
        request_id=uuid4().hex,
        user_input=str(user_input),
        output_dir=Path(output_dir),
        context={"selected_skills": tuple(matched_skills)},
    )
    emit_workflow_lines(["计划请求: {}".format(request.request_id)])

    emit_workflow_lines(["\n【步骤4/4: 工具执行与结果验证】"])
    agent.last_agent_run = agent.agent_execution_engine.run(request)
    if agent.last_agent_run.status is not AgentRunStatus.SUCCEEDED:
        emit_workflow_lines(
            [
                "Agent 执行失败: {}".format(
                    agent.last_agent_run.failure_reason or "unknown failure"
                )
            ],
            stream=sys.stderr,
        )
        return False
    emit_workflow_lines(
        build_workflow_tool_result_lines(agent, agent.last_agent_run.tool_results)
    )

    emit_workflow_lines(build_workflow_footer_lines())

    return True
