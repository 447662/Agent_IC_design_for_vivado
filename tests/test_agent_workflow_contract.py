import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from agent import DigitalICAgent  # noqa: E402
from agent_contracts import AgentRunStatus, ToolResultStatus  # noqa: E402
from skill_runtime import (  # noqa: E402
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutionStatus,
)


def test_diagnostic_reports_required_optional_and_not_applicable(
    capsys,
    monkeypatch,
):
    agent = DigitalICAgent()
    monkeypatch.setattr(agent, "check_capability", lambda _name: False)

    assert agent.run_diagnostic(flow="design-document") is True
    document_output = capsys.readouterr().out
    assert "vivado" in document_output
    assert "N/A" in document_output
    assert "当前动作不适用" in document_output

    assert agent.run_diagnostic(flow="sim-rtl") is False
    simulation_output = capsys.readouterr().out
    assert "vivado" in simulation_output
    assert "必需" in simulation_output
    assert "synthpilot" in simulation_output
    assert "可选" in simulation_output
    assert "降级" in simulation_output


def test_default_document_workflow_executes_loaded_skill_without_external_tools(
    tmp_path,
    monkeypatch,
):
    calls = []

    class RecordingExecutor:
        def execute(self, request):
            calls.append(request)
            return SkillExecutionResult(
                skill_name=request.skill.name,
                action=request.skill.action,
                status=SkillExecutionStatus.SUCCEEDED,
                artifacts=(Path(request.context["design_spec_path"]),),
                message="recorded",
            )

    agent = DigitalICAgent(skill_executor=RecordingExecutor())
    monkeypatch.setattr(agent, "check_cli_tool", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(agent, "check_mcp_server", lambda *_args, **_kwargs: False)

    assert agent.execute_workflow(
        "请生成设计文档和架构方案",
        output_dir=tmp_path,
        skip_tool_check=False,
    )
    assert len(calls) == 1
    assert calls[0].skill.name == "digital-ic-designer"
    assert calls[0].skill.title == "数字IC设计架构师"
    assert 'name: "digital-ic-designer"' in calls[0].skill.content
    assert len(calls[0].skill.content_digest) == 64
    assert Path(calls[0].context["design_spec_path"]).exists()


def test_default_document_workflow_records_real_agent_run(tmp_path):
    agent = DigitalICAgent()

    assert agent.execute_workflow(
        "请生成设计文档和架构方案",
        output_dir=tmp_path,
        skip_tool_check=False,
    )
    assert agent.last_agent_run.status is AgentRunStatus.SUCCEEDED
    assert agent.last_agent_run.tool_results
    assert all(
        result.status is ToolResultStatus.SUCCEEDED
        and result.returncode == 0
        and result.artifacts
        for result in agent.last_agent_run.tool_results
    )
    assert agent.last_agent_run.artifacts


def test_workflow_rejects_empty_skill_selection(tmp_path):
    agent = DigitalICAgent()

    assert (
        agent.execute_workflow(
            "不要 RTL",
            output_dir=tmp_path,
            skip_tool_check=True,
        )
        is False
    )
    assert agent.last_agent_run.status is AgentRunStatus.FAILED
    assert "skill" in agent.last_agent_run.failure_reason.lower()


def test_default_rtl_and_verification_skills_do_not_report_success(tmp_path):
    agent = DigitalICAgent()
    spec_path = tmp_path / "design_spec.md"
    spec_path.write_text(
        "# Design Specification\n\n## Requirements\n\nExample.\n",
        encoding="utf-8",
    )

    for skill_name in ("digital-ic-rtl-designer", "digital-ic-verifier"):
        skill = agent.loaded_skills[skill_name]
        result = agent.skill_executor.execute(
            SkillExecutionRequest(
                skill=skill,
                user_input="execute the requested skill",
                output_dir=tmp_path,
                context={"design_spec_path": str(spec_path)},
            )
        )

        assert result.status is SkillExecutionStatus.BLOCKED
        assert result.failure_reason
        assert (
            not result.validated_artifacts
            or spec_path.resolve() in result.validated_artifacts
        )


def test_workflow_rejects_partial_result_from_custom_executor(tmp_path):
    class PartialExecutor:
        def execute(self, request):
            plan_path = request.output_dir / "verification_plan.md"
            plan_path.write_text("# Verification Plan\n", encoding="utf-8")
            return SkillExecutionResult(
                skill_name=request.skill.name,
                action=request.skill.action,
                status=SkillExecutionStatus.PARTIAL,
                artifacts=(plan_path,),
                message="plan generated",
            )

    agent = DigitalICAgent(skill_executor=PartialExecutor())

    assert (
        agent.execute_workflow(
            "请使用 UVM 进行验证",
            output_dir=tmp_path,
            skip_tool_check=True,
        )
        is False
    )
