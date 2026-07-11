from pathlib import Path
from typing import Any
from uuid import uuid4
import sys

from agent_contracts import AgentRequest, AgentRunStatus


def execute_workflow(
    agent: Any,
    user_input: Any,
    output_dir: Any = "outputs",
    skip_tool_check: Any = False,
) -> bool:
    print("=" * 60)
    print("数字IC前端设计Agent")
    print("=" * 60)

    print("\n【步骤1/4: 需求分析】")
    matched_skills = agent.recommend_skills(user_input)
    try:
        loaded_skills = [agent.loaded_skills[name] for name in matched_skills]
    except KeyError as exc:
        print("技能未加载: {}".format(exc), file=sys.stderr)
        return False

    if skip_tool_check:
        print("\n【步骤2/4: 工具检查】")
        print(agent.WARN + " 已根据 --no-tool-check 跳过外部工具检查")
    else:
        print("\n【步骤2/4: 工具检查】")
        for skill in loaded_skills:
            report = agent.run_preflight(skill.action)
            if not report.ok:
                print(
                    "\n{} 技能 {} 缺少能力: {}".format(
                        agent.WARN,
                        skill.name,
                        ", ".join(report.missing_required),
                    )
                )
                return False
        print(agent.OK + " 当前技能动作所需能力已就绪")

    print("\n【步骤3/4: 执行计划】")
    request = AgentRequest(
        request_id=uuid4().hex,
        user_input=str(user_input),
        output_dir=Path(output_dir),
        context={"selected_skills": tuple(matched_skills)},
    )
    print("计划请求: {}".format(request.request_id))

    print("\n【步骤4/4: 工具执行与结果验证】")
    agent.last_agent_run = agent.agent_execution_engine.run(request)
    if agent.last_agent_run.status is not AgentRunStatus.SUCCEEDED:
        print(
            "Agent 执行失败: {}".format(
                agent.last_agent_run.failure_reason or "unknown failure"
            ),
            file=sys.stderr,
        )
        return False
    for result in agent.last_agent_run.tool_results:
        print(
            "{} {} -> {}".format(
                agent.OK,
                result.tool_name,
                ", ".join(str(path) for path in result.artifacts),
            )
        )

    print("\n【后续建议】")
    print("请补充文档中的人工确认项，再进入 RTL 实现或 UVM 验证阶段。")

    print("\n" + "=" * 60)
    print("工作流执行完成")
    print("=" * 60)

    return True
