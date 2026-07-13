import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.capability_preflight import FlowPreflight, PreflightStatus  # noqa: E402
from digital_ic_agent._runtime.skill_runtime import (  # noqa: E402
    DeterministicSkillExecutor,
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillLoader,
    SkillResultValidator,
    ToolRunRecord,
)


def _write_skill(root: Path, name: str, title: str) -> dict[str, object]:
    skill_path = root / "skills" / name / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        "# {}\n\n## Contract\n\nExecute the declared action.\n".format(title),
        encoding="utf-8",
    )
    return {
        "name": name,
        "path": "./skills/{}/SKILL.md".format(name),
        "description": title,
        "action": name,
        "requiredCapabilities": [],
    }


def test_skill_loader_reads_markdown_and_executor_dispatches_distinct_actions(
    tmp_path,
):
    design_config = _write_skill(tmp_path, "design-document", "Design Skill")
    rtl_config = _write_skill(tmp_path, "rtl-implementation", "RTL Skill")
    loader = SkillLoader(tmp_path)

    design_skill = loader.load(design_config)
    rtl_skill = loader.load(rtl_config)

    assert design_skill.title == "Design Skill"
    assert "Execute the declared action." in design_skill.content
    assert rtl_skill.action == "rtl-implementation"

    calls = []

    def execute_design(request):
        calls.append(("design", request.skill.name))
        design_spec = request.output_dir / "design_spec.md"
        design_spec.write_text(
            "# Design Specification\n\n## Requirements\n\nValidated input.\n",
            encoding="utf-8",
        )
        return SkillExecutionResult(
            skill_name=request.skill.name,
            action=request.skill.action,
            status=SkillExecutionStatus.SUCCEEDED,
            artifacts=(design_spec,),
            message="design complete",
        )

    def execute_rtl(request):
        calls.append(("rtl", request.skill.name))
        return SkillExecutionResult(
            skill_name=request.skill.name,
            action=request.skill.action,
            status=SkillExecutionStatus.BLOCKED,
            message="rtl generation is unavailable",
            failure_reason="no RTL generator configured",
        )

    executor = DeterministicSkillExecutor(
        {
            "design-document": execute_design,
            "rtl-implementation": execute_rtl,
        }
    )
    design_result = executor.execute(
        SkillExecutionRequest(
            skill=design_skill,
            user_input="write a design",
            output_dir=tmp_path,
        )
    )
    rtl_result = executor.execute(
        SkillExecutionRequest(
            skill=rtl_skill,
            user_input="write rtl",
            output_dir=tmp_path,
        )
    )

    assert calls == [
        ("design", "design-document"),
        ("rtl", "rtl-implementation"),
    ]
    assert design_result.artifacts[0].name == "design_spec.md"
    assert design_result.validated_artifacts == design_result.artifacts
    assert rtl_result.status is SkillExecutionStatus.BLOCKED


def test_executor_rejects_succeeded_result_with_missing_artifacts(tmp_path):
    config = _write_skill(tmp_path, "design-document", "Design Skill")
    skill = SkillLoader(tmp_path).load(config)

    executor = DeterministicSkillExecutor(
        {
            "design-document": lambda request: SkillExecutionResult(
                skill_name=request.skill.name,
                action=request.skill.action,
                status=SkillExecutionStatus.SUCCEEDED,
                artifacts=(request.output_dir / "missing-design-spec.md",),
                message="incorrect success",
            )
        }
    )

    with pytest.raises(ValueError, match="missing artifact"):
        executor.execute(
            SkillExecutionRequest(
                skill=skill,
                user_input="write a design",
                output_dir=tmp_path,
            )
        )


def test_executor_requires_rtl_testbench_and_successful_check_for_rtl_success(
    tmp_path,
):
    config = _write_skill(tmp_path, "rtl-implementation", "RTL Skill")
    skill = SkillLoader(tmp_path).load(config)
    rtl_path = tmp_path / "rtl" / "demo.v"
    rtl_path.parent.mkdir()
    rtl_path.write_text("module demo; endmodule\n", encoding="utf-8")

    executor = DeterministicSkillExecutor(
        {
            "rtl-implementation": lambda request: SkillExecutionResult(
                skill_name=request.skill.name,
                action=request.skill.action,
                status=SkillExecutionStatus.SUCCEEDED,
                artifacts=(rtl_path,),
                tool_runs=(
                    ToolRunRecord(
                        name="rtl-check",
                        status=SkillExecutionStatus.SUCCEEDED,
                        returncode=0,
                    ),
                ),
                message="incomplete rtl result",
            )
        }
    )

    with pytest.raises(ValueError, match="testbench"):
        executor.execute(
            SkillExecutionRequest(
                skill=skill,
                user_input="write rtl",
                output_dir=tmp_path,
            )
        )


def test_skill_validator_rejects_none_returncode_for_rtl_success(tmp_path):
    config = _write_skill(tmp_path, "rtl-implementation", "RTL Skill")
    skill = SkillLoader(tmp_path).load(config)
    rtl_path = tmp_path / "rtl" / "demo.v"
    tb_path = tmp_path / "tb" / "tb_demo.v"
    rtl_path.parent.mkdir()
    tb_path.parent.mkdir()
    rtl_path.write_text("module demo; endmodule\n", encoding="utf-8")
    tb_path.write_text("module tb_demo; demo dut(); endmodule\n", encoding="utf-8")

    with pytest.raises(ValueError, match="successful RTL check"):
        SkillResultValidator().validate(
            SkillExecutionRequest(
                skill=skill,
                user_input="write rtl",
                output_dir=tmp_path,
            ),
            SkillExecutionResult(
                skill_name=skill.name,
                action=skill.action,
                status=SkillExecutionStatus.SUCCEEDED,
                artifacts=(rtl_path, tb_path),
                tool_runs=(
                    ToolRunRecord(
                        name="rtl-check",
                        status=SkillExecutionStatus.SUCCEEDED,
                        returncode=None,
                    ),
                ),
                message="incorrect success",
            ),
        )


def test_skill_loader_rejects_missing_empty_and_actionless_skills(tmp_path):
    loader = SkillLoader(tmp_path)

    with pytest.raises(FileNotFoundError, match="Skill file not found"):
        loader.load(
            {
                "name": "missing",
                "path": "./skills/missing/SKILL.md",
                "description": "missing",
                "action": "design-document",
            }
        )

    empty_path = tmp_path / "skills" / "empty" / "SKILL.md"
    empty_path.parent.mkdir(parents=True)
    empty_path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Skill file is empty"):
        loader.load(
            {
                "name": "empty",
                "path": "./skills/empty/SKILL.md",
                "description": "empty",
                "action": "design-document",
            }
        )

    valid_path = tmp_path / "skills" / "actionless" / "SKILL.md"
    valid_path.parent.mkdir(parents=True)
    valid_path.write_text("# Actionless\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing action"):
        loader.load(
            {
                "name": "actionless",
                "path": "./skills/actionless/SKILL.md",
                "description": "actionless",
            }
        )


def test_flow_preflight_is_capability_aware():
    preflight = FlowPreflight(
        {
            "design-document": {"required": (), "optional": ()},
            "sim-rtl": {
                "required": ("vivado",),
                "optional": ("synthpilot",),
            },
        }
    )

    document_report = preflight.evaluate("design-document", lambda _name: False)
    simulation_report = preflight.evaluate("sim-rtl", lambda _name: False)

    assert document_report.ok is True
    assert document_report.status_for("vivado") is PreflightStatus.NOT_APPLICABLE
    assert simulation_report.ok is False
    assert simulation_report.status_for("vivado") is PreflightStatus.MISSING_REQUIRED
    assert simulation_report.status_for("synthpilot") is PreflightStatus.MISSING_OPTIONAL

    with pytest.raises(ValueError, match="Unknown flow"):
        preflight.evaluate("unknown-flow", lambda _name: True)
