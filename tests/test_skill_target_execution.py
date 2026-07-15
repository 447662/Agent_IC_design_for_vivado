import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent import DigitalICAgent  # noqa: E402
from digital_ic_agent._runtime.skill_runtime import (  # noqa: E402
    SkillExecutionRequest,
    SkillExecutionStatus,
)


def _design_spec(root: Path) -> Path:
    spec_path = root / "design_spec.md"
    spec_path.write_text(
        "# Design Specification\n\n## Requirements\n\nImplement the selected target.\n",
        encoding="utf-8",
    )
    return spec_path


def test_default_rtl_workflow_runs_real_target_generation_and_check(tmp_path):
    agent = DigitalICAgent()

    assert agent.execute_workflow(
        "Implement RTL and testbench for sync-fifo",
        output_dir=tmp_path,
        skip_tool_check=False,
    )

    artifacts = agent.last_agent_run.artifacts
    assert any(path.suffix == ".v" and "rtl" in path.parts for path in artifacts)
    assert any(path.suffix == ".v" and "tb" in path.parts for path in artifacts)
    assert all(path.is_file() and path.stat().st_size > 0 for path in artifacts)


def test_default_verification_skill_returns_validated_plan_without_vivado(
    tmp_path,
    monkeypatch,
):
    agent = DigitalICAgent()
    monkeypatch.setattr(agent, "check_capability", lambda _name: False)
    skill = agent.loaded_skills["digital-ic-verifier"]

    result = agent.skill_executor.execute(
        SkillExecutionRequest(
            skill=skill,
            user_input="Create a UVM plan for async-fifo",
            output_dir=tmp_path,
            context={
                "design_spec_path": str(_design_spec(tmp_path)),
                "target_name": "async-fifo",
            },
        )
    )

    assert result.status is SkillExecutionStatus.PARTIAL
    assert any(path.name == "verification_plan.md" for path in result.validated_artifacts)
    assert all(path.stat().st_size > 0 for path in result.validated_artifacts)
    assert not any("brief" in path.name for path in result.artifacts)


def test_successful_uvm_target_flow_produces_validator_accepted_artifacts(
    tmp_path,
    monkeypatch,
):
    agent = DigitalICAgent()
    skill = agent.loaded_skills["digital-ic-verifier"]
    calls: list[tuple[str, str]] = []

    class AvailablePreflight:
        ok = True
        missing_required: tuple[str, ...] = ()

    def run_target_flow(target: str, flow: str, **_kwargs: object) -> bool:
        calls.append((target, flow))
        project_dir = tmp_path / target
        uvm_dir = project_dir / "uvm"
        sim_dir = project_dir / "sim"
        reports_dir = project_dir / "reports"
        for directory in (uvm_dir, sim_dir, reports_dir):
            directory.mkdir(parents=True, exist_ok=True)
        (uvm_dir / "async_fifo_uvm_pkg.sv").write_text(
            "package async_fifo_uvm_pkg; endpackage\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_smoke.log").write_text(
            "UVM smoke PASS\n",
            encoding="utf-8",
        )
        (reports_dir / "uvm_smoke_report.md").write_text(
            "# UVM Smoke Report\n\nPASS\n",
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr(agent, "run_preflight", lambda _flow: AvailablePreflight())
    monkeypatch.setattr(agent, "run_target_flow", run_target_flow)

    result = agent.skill_executor.execute(
        SkillExecutionRequest(
            skill=skill,
            user_input="Run UVM smoke for async-fifo",
            output_dir=tmp_path,
            context={
                "design_spec_path": str(_design_spec(tmp_path)),
                "target_name": "async-fifo",
            },
        )
    )

    assert calls == [("async-fifo", "uvm-smoke")]
    assert result.status is SkillExecutionStatus.SUCCEEDED
    assert result.validated_artifacts
    assert all(path.stat().st_size > 0 for path in result.validated_artifacts)
    assert [run.name for run in result.tool_runs] == ["uvm-smoke"]
