import ast
import json
import sys
from pathlib import Path
from collections.abc import Callable, Mapping
from typing import Any, get_args, get_type_hints

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


import agent_errors  # noqa: E402
import agent_sim_smoke  # noqa: E402
import agent_waveform  # noqa: E402


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError("function not found: {}".format(function_name))


def test_agent_errors_expose_structured_categories_and_exit_codes():
    assert set(get_args(agent_errors.ErrorCategory)) == {
        "artifact_validation",
        "capability",
        "configuration",
        "tool_execution",
    }

    expected = {
        agent_errors.ConfigurationError: ("configuration", 2),
        agent_errors.CapabilityError: ("capability", 3),
        agent_errors.ToolExecutionError: ("tool_execution", 4),
        agent_errors.ArtifactValidationError: ("artifact_validation", 5),
    }
    for error_type, (category, exit_code) in expected.items():
        error = error_type(
            "example failure",
            stage="preflight",
            details={"tool": "vivado", "secret": "abc123"},
        )
        payload = error.as_payload()

        assert payload["category"] == category
        assert payload["exit_code"] == exit_code
        assert payload["stage"] == "preflight"
        assert payload["message"] == "example failure"
        assert payload["details"] == {"tool": "vivado", "secret": "***"}
        assert category in str(error)


@pytest.mark.parametrize(
    ("error", "expected_exit_code"),
    (
        (agent_errors.ConfigurationError("bad config"), 2),
        (agent_errors.CapabilityError("missing tool"), 3),
        (agent_errors.ToolExecutionError("tool failed"), 4),
        (agent_errors.ArtifactValidationError("bad artifact"), 5),
    ),
)
def test_cli_boolean_flow_uses_structured_agent_error_exit_code(
    error: agent_errors.AgentError,
    expected_exit_code: int,
    capsys: pytest.CaptureFixture[str],
):
    import agent_cli_dispatch  # noqa: E402

    def fail() -> bool:
        raise error

    assert (
        agent_cli_dispatch._run_boolean_flow(
            "Structured flow",
            fail,
            (agent_errors.AgentError,),
        )
        == expected_exit_code
    )

    captured = capsys.readouterr()
    assert "Structured flow failed:" in captured.err
    assert error.message in captured.err


def test_target_flow_capability_failure_records_structured_manifest_error(tmp_path, monkeypatch):
    from agent import DigitalICAgent

    agent = DigitalICAgent()
    monkeypatch.setattr(
        agent,
        "run_preflight",
        lambda _flow: type(
            "PreflightReport",
            (),
            {
                "ok": False,
                "missing_required": ("vivado",),
                "missing_optional": (),
            },
        )(),
    )

    assert agent.run_target_flow("sync-fifo", "sim-rtl", output_dir=tmp_path) is False

    manifest = json.loads(
        (tmp_path / "sync-fifo" / "artifacts.json").read_text(encoding="utf-8")
    )
    run = manifest["runs"][-1]
    error_payload = json.loads(run["error"])

    assert run["status"] == "FAIL"
    assert run["error_category"] == "capability"
    assert run["error_stage"] == "preflight"
    assert run["error_exit_code"] == 3
    assert error_payload["category"] == "capability"
    assert error_payload["details"]["missing_required"] == ["vivado"]


def test_target_flow_handler_exception_records_tool_execution_error(tmp_path):
    import artifact_manifest  # noqa: E402
    import target_flows  # noqa: E402

    class PreflightReport:
        ok = True
        missing_required: tuple[str, ...] = ()

    class FailingHandler:
        flows = {"sim-rtl": object()}
        plugin = None

        def run(self, _flow: str, **_kwargs: object) -> object:
            raise RuntimeError("sim failed")

    class FakeAgent:
        targets = {
            "sample-target": {
                "name": "sample-target",
                "display_name": "Sample Target",
                "design_family": "test",
                "flows": ["sim-rtl"],
                "artifact_manifest": [],
            }
        }
        target_handlers = {"sample-target": FailingHandler()}

        def normalize_rtl_target(self, target: str) -> str:
            return target

        def run_preflight(self, _flow: str) -> PreflightReport:
            return PreflightReport()

        def get_target(self, target: str) -> dict[str, object]:
            return dict(self.targets[target])

        def record_artifact_run(self, target: str, flow: str, **kwargs: object) -> Path:
            return artifact_manifest.record_artifact_run(self, target, flow, **kwargs)

    with pytest.raises(RuntimeError, match="sim failed"):
        target_flows.run_target_flow(
            FakeAgent(),
            "sample-target",
            "sim-rtl",
            output_dir=tmp_path,
        )

    manifest = json.loads(
        (tmp_path / "sample-target" / "artifacts.json").read_text(encoding="utf-8")
    )
    run = manifest["runs"][-1]
    error_payload = json.loads(run["error"])

    assert run["status"] == "FAIL"
    assert run["error_category"] == "tool_execution"
    assert run["error_stage"] == "target_flow"
    assert run["error_exit_code"] == 4
    assert error_payload["details"]["exception_type"] == "RuntimeError"
    assert error_payload["details"]["target"] == "sample-target"


def test_target_flow_false_result_records_tool_execution_error(tmp_path):
    import artifact_manifest  # noqa: E402
    import target_flows  # noqa: E402

    class PreflightReport:
        ok = True
        missing_required: tuple[str, ...] = ()

    class FalseHandler:
        flows = {"sim-rtl": object()}
        plugin = None

        def run(self, _flow: str, **_kwargs: object) -> object:
            return False

    class FakeAgent:
        targets = {
            "sample-target": {
                "name": "sample-target",
                "display_name": "Sample Target",
                "design_family": "test",
                "flows": ["sim-rtl"],
                "artifact_manifest": [],
            }
        }
        target_handlers = {"sample-target": FalseHandler()}

        def normalize_rtl_target(self, target: str) -> str:
            return target

        def run_preflight(self, _flow: str) -> PreflightReport:
            return PreflightReport()

        def get_target(self, target: str) -> dict[str, object]:
            return dict(self.targets[target])

        def record_artifact_run(self, target: str, flow: str, **kwargs: object) -> Path:
            return artifact_manifest.record_artifact_run(self, target, flow, **kwargs)

    assert (
        target_flows.run_target_flow(
            FakeAgent(),
            "sample-target",
            "sim-rtl",
            output_dir=tmp_path,
        )
        is False
    )

    manifest = json.loads(
        (tmp_path / "sample-target" / "artifacts.json").read_text(encoding="utf-8")
    )
    run = manifest["runs"][-1]
    error_payload = json.loads(run["error"])

    assert run["status"] == "FAIL"
    assert run["error_category"] == "tool_execution"
    assert run["error_stage"] == "target_flow"
    assert run["error_exit_code"] == 4
    assert error_payload["details"]["reason"] == "false_result"
    assert error_payload["details"]["target"] == "sample-target"


def test_artifact_manifest_runtime_run_tracks_optional_error_fields():
    import artifact_manifest

    annotations = get_type_hints(artifact_manifest.RuntimeRun)

    assert annotations["error_category"] == agent_errors.ErrorCategory | None
    assert annotations["error_exit_code"] == int | None
    assert annotations["error_stage"] == str | None
    hints = get_type_hints(artifact_manifest.record_artifact_run)
    assert hints["return"] == Path


def test_waveform_helpers_expose_typed_contracts():
    report_hints = get_type_hints(agent_waveform.build_waveform_report_lines)
    analyzer_hints = get_type_hints(agent_waveform.resolve_vcd_analyzer_path)
    rwave_dir_hints = get_type_hints(agent_waveform.resolve_rwave_source_dir)
    rwave_command_hints = get_type_hints(agent_waveform.resolve_rwave_command)
    analyze_waveform_hints = get_type_hints(agent_waveform.analyze_waveform)
    analyze_vcd_hints = get_type_hints(agent_waveform.analyze_vcd)

    assert report_hints["report_title"] is str
    assert report_hints["waveform_file"] == str | Path
    assert report_hints["waveform_format"] is str
    assert report_hints["info"] == Mapping[str, object]
    assert report_hints["search_result"] == Mapping[str, object] | None
    assert report_hints["condition"] == str | None
    assert report_hints["show"] == str | None
    assert report_hints["limit"] is int
    assert report_hints["return"] == list[str]
    assert analyzer_hints["project_root"] == str | Path
    assert analyzer_hints["return"] == Path
    assert rwave_dir_hints["project_root"] == str | Path
    assert rwave_dir_hints["return"] == Path | None
    assert rwave_command_hints["project_root"] == str | Path
    assert rwave_command_hints["env"] == Mapping[str, str] | None
    assert rwave_command_hints["which"] == Callable[[str], str | None] | None
    assert rwave_command_hints["source_dir_resolver"] == Callable[[], Path | None] | None
    assert rwave_command_hints["return"] == str | None
    assert analyze_waveform_hints["waveform_path"] == str | Path
    assert analyze_waveform_hints["return"] is bool
    assert analyze_vcd_hints["vcd_path"] == str | Path
    assert analyze_vcd_hints["return"] is bool


def test_sim_smoke_helpers_expose_typed_contracts():
    smoke_loop_hints = get_type_hints(agent_sim_smoke.write_smoke_loop_vcd)
    emit_hints = get_type_hints(agent_sim_smoke.emit_lines)
    loop_start_hints = get_type_hints(agent_sim_smoke.build_smoke_loop_start_lines)
    generated_vcd_hints = get_type_hints(agent_sim_smoke.build_generated_vcd_lines)
    smoke_complete_hints = get_type_hints(agent_sim_smoke.build_sim_smoke_completed_lines)
    success_hints = get_type_hints(agent_sim_smoke.build_sim_smoke_success_lines)
    error_hints = get_type_hints(agent_sim_smoke.build_sim_smoke_error_lines)
    run_loop_hints = get_type_hints(agent_sim_smoke.run_smoke_loop)
    simulator_hints = get_type_hints(agent_sim_smoke.detect_simulator)
    sources_hints = get_type_hints(agent_sim_smoke.write_sim_smoke_sources)
    icarus_hints = get_type_hints(agent_sim_smoke.run_icarus_sim_smoke)
    vivado_script_hints = get_type_hints(agent_sim_smoke.write_vivado_sim_script)
    gui_hints = get_type_hints(agent_sim_smoke.open_vivado_wave_gui)
    vivado_hints = get_type_hints(agent_sim_smoke.run_vivado_sim_smoke)
    dispatch_hints = get_type_hints(agent_sim_smoke.run_sim_smoke)
    bootstrap_hints = get_type_hints(agent_sim_smoke.render_vivado_tclstore_bootstrap)

    assert smoke_loop_hints["output_dir"] == str | Path
    assert smoke_loop_hints["return"] == Path
    assert emit_hints["lines"] == list[str]
    assert emit_hints["return"] is type(None)
    assert loop_start_hints["return"] == list[str]
    assert generated_vcd_hints["vcd_path"] == str | Path
    assert generated_vcd_hints["return"] == list[str]
    assert smoke_complete_hints["return"] == list[str]
    assert success_hints["simulator"] is str
    assert success_hints["vcd_path"] == str | Path
    assert success_hints["return"] == list[str]
    assert error_hints["message"] is str
    assert error_hints["return"] == list[str]
    assert run_loop_hints["agent"] is agent_sim_smoke.SmokeLoopAgent
    assert run_loop_hints["output_dir"] == str | Path
    assert run_loop_hints["limit"] is int
    assert run_loop_hints["waveform_backend"] is str
    assert run_loop_hints["return"] is bool
    assert simulator_hints["agent"] is agent_sim_smoke.SimulatorDetector
    assert simulator_hints["return"] == str | None
    assert sources_hints["output_dir"] == str | Path
    assert sources_hints["return"] == tuple[Path, Path, Path, Path]
    assert icarus_hints["agent"] is agent_sim_smoke.IcarusSmokeAgent
    assert icarus_hints["output_dir"] == str | Path
    assert icarus_hints["return"] is bool
    assert vivado_script_hints["sim_dir"] == str | Path
    assert vivado_script_hints["rtl_path"] == str | Path
    assert vivado_script_hints["tb_path"] == str | Path
    assert vivado_script_hints["vcd_path"] == str | Path
    assert vivado_script_hints["return"] == Path
    assert gui_hints["agent"] is agent_sim_smoke.VivadoGuiAgent
    assert gui_hints["sim_dir"] == str | Path
    assert gui_hints["vcd_path"] == str | Path
    assert gui_hints["return"] is bool
    assert vivado_hints["agent"] is agent_sim_smoke.VivadoSmokeAgent
    assert vivado_hints["output_dir"] == str | Path
    assert vivado_hints["open_wave_gui"] is bool
    assert vivado_hints["return"] is bool
    assert dispatch_hints["agent"] is agent_sim_smoke.SimSmokeAgent
    assert dispatch_hints["output_dir"] == str | Path
    assert dispatch_hints["return"] is bool
    assert bootstrap_hints["return"] is str


def test_sim_smoke_runner_protocols_avoid_broad_any():
    runner_hints = get_type_hints(agent_sim_smoke.CommandRunnerLike.run)
    process_hints = get_type_hints(agent_sim_smoke.CompletedProcessLike)
    command_runner_property = agent_sim_smoke.IcarusSmokeAgent.command_runner
    assert command_runner_property.fget is not None
    icarus_agent_hints = get_type_hints(command_runner_property.fget)
    vivado_gui_hints = get_type_hints(agent_sim_smoke.VivadoGuiAgent.launch_vivado_gui)
    vivado_batch_hints = get_type_hints(agent_sim_smoke.VivadoSmokeAgent.run_vivado_batch)

    assert runner_hints["return"] is agent_sim_smoke.CompletedProcessLike
    assert process_hints["returncode"] is int
    assert process_hints["stdout"] is str
    assert process_hints["stderr"] is str
    assert icarus_agent_hints["return"] is agent_sim_smoke.CommandRunnerLike
    assert vivado_gui_hints["return"] is object
    assert vivado_batch_hints["return"] is agent_sim_smoke.CompletedProcessLike

    for hints in (
        runner_hints,
        process_hints,
        icarus_agent_hints,
        vivado_gui_hints,
        vivado_batch_hints,
    ):
        assert Any not in hints.values()


def test_sim_smoke_render_helpers_do_not_print_directly():
    for function_name in (
        "build_smoke_loop_start_lines",
        "build_generated_vcd_lines",
        "build_sim_smoke_completed_lines",
        "build_sim_smoke_success_lines",
        "build_sim_smoke_error_lines",
    ):
        helper_source = _function_source(AGENT_DIR / "agent_sim_smoke.py", function_name)
        assert "print(" not in helper_source


def test_core_sim_smoke_flows_emit_through_helper_only():
    for function_name in (
        "run_smoke_loop",
        "run_icarus_sim_smoke",
        "open_vivado_wave_gui",
        "run_vivado_sim_smoke",
        "run_sim_smoke",
    ):
        flow_source = _function_source(AGENT_DIR / "agent_sim_smoke.py", function_name)
        assert "print(" not in flow_source


def test_core_validation_helpers_do_not_print_directly():
    target_checks_source = (AGENT_DIR / "target_checks.py").read_text(encoding="utf-8")
    refresh_source = _function_source(
        AGENT_DIR / "agent_runtime_facades.py",
        "refresh_project_overview",
    )
    waveform_render_source = _function_source(
        AGENT_DIR / "agent_waveform.py",
        "build_waveform_report_lines",
    )

    assert "print(" not in target_checks_source
    assert "print(" not in refresh_source
    assert "print(" not in waveform_render_source


def test_core_waveform_flows_emit_through_helper_only():
    for function_name in (
        "analyze_waveform",
        "analyze_vcd",
    ):
        flow_source = _function_source(AGENT_DIR / "agent_waveform.py", function_name)
        assert "print(" not in flow_source


def test_sync_fifo_vcd_analysis_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_sync_fifo.py",
        "analyze_sync_fifo_vcd",
    )
    assert "print(" not in flow_source


def test_round_robin_vcd_analysis_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_round_robin_arbiter.py",
        "analyze_round_robin_arbiter_vcd",
    )
    assert "print(" not in flow_source


def test_async_fifo_vcd_analysis_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_async_fifo_runtime.py",
        "analyze_async_fifo_vcd",
    )
    assert "print(" not in flow_source


def test_agent_composition_build_agent_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_composition.py",
        "build_agent",
    )
    assert "print(" not in flow_source


def test_agent_skill_listing_flows_emit_through_helper_only():
    for function_name in (
        "list_skills",
        "recommend_skills",
    ):
        flow_source = _function_source(AGENT_DIR / "agent_skill_listing.py", function_name)
        assert "print(" not in flow_source


def test_agent_workflow_execute_workflow_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_workflow.py",
        "execute_workflow",
    )
    assert "print(" not in flow_source


def test_async_fifo_rtl_check_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_async_fifo_runtime.py",
        "check_async_fifo_rtl",
    )
    assert "print(" not in flow_source


def test_async_fifo_gui_open_flows_emit_through_helper_only():
    for function_name in (
        "open_async_fifo_project_gui",
        "open_async_fifo_uvm_wave_gui",
    ):
        flow_source = _function_source(AGENT_DIR / "agent_async_fifo_runtime.py", function_name)
        assert "print(" not in flow_source


def test_sync_fifo_and_round_robin_gui_open_flows_emit_through_helper_only():
    for path, function_name in (
        (AGENT_DIR / "agent_sync_fifo.py", "open_sync_fifo_project_gui"),
        (
            AGENT_DIR / "agent_round_robin_arbiter.py",
            "open_round_robin_arbiter_project_gui",
        ),
    ):
        flow_source = _function_source(path, function_name)
        assert "print(" not in flow_source


def test_sync_fifo_and_round_robin_vivado_sim_flows_emit_through_helper_only():
    for path, function_name in (
        (AGENT_DIR / "agent_sync_fifo.py", "run_sync_fifo_vivado_sim"),
        (
            AGENT_DIR / "agent_round_robin_arbiter.py",
            "run_round_robin_arbiter_vivado_sim",
        ),
    ):
        flow_source = _function_source(path, function_name)
        assert "print(" not in flow_source


def test_async_fifo_vivado_sim_flow_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_async_fifo_runtime.py",
        "run_async_fifo_vivado_sim",
    )
    assert "print(" not in flow_source


def test_async_fifo_uvm_smoke_flow_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_async_fifo_runtime.py",
        "run_async_fifo_uvm_smoke",
    )
    assert "print(" not in flow_source


def test_async_fifo_uvm_coverage_flow_emits_through_helper_only():
    flow_source = _function_source(
        AGENT_DIR / "agent_async_fifo_runtime.py",
        "run_async_fifo_uvm_coverage",
    )
    assert "print(" not in flow_source


def test_non_cli_print_calls_are_limited_to_output_emitters():
    allowed_print_functions = {
        ("agent_async_fifo_runtime.py", "emit_async_fifo_lines"),
        ("agent_composition.py", "emit_agent_composition_lines"),
        ("agent_round_robin_arbiter.py", "emit_round_robin_arbiter_lines"),
        ("agent_sim_smoke.py", "emit_lines"),
        ("agent_skill_listing.py", "emit_skill_listing_lines"),
        ("agent_sync_fifo.py", "emit_sync_fifo_lines"),
        ("agent_waveform.py", "emit_waveform_lines"),
            ("agent_workflow.py", "emit_workflow_lines"),
            ("plugin_guard_runner.py", "_emit_payload"),
        }
    allowed_cli_modules = {
        "agent_cli.py",
        "agent_cli_dispatch.py",
    }

    violations: list[str] = []
    for path in AGENT_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                continue
            function_name = "<module>"
            current = node
            while current in parents:
                current = parents[current]
                if isinstance(current, ast.FunctionDef):
                    function_name = current.name
                    break

            module_name = path.name
            if module_name in allowed_cli_modules:
                continue
            if (module_name, function_name) in allowed_print_functions:
                continue
            violations.append("{}:{} in {}".format(module_name, node.lineno, function_name))

    assert violations == []


def test_observability_json_event_redacts_and_truncates_details(tmp_path):
    import agent_observability  # noqa: E402

    event = agent_observability.build_observability_event(
        run_id="run-123",
        flow="sim-rtl",
        stage="vivado_batch",
        event="tool_finished",
        status="FAIL",
        duration_ms=125,
        exit_code=4,
        error_category="tool_execution",
        tool_versions={"vivado": "2025.2"},
        details={
            "license_key": "do-not-log",
            "command": ["vivado", "-mode", "batch"],
            "stdout": "x" * 3000,
            "nested": {"api_key": "secret-value"},
        },
    )
    line = agent_observability.dumps_observability_event(event)
    payload = json.loads(line)

    assert payload["schema_version"] == "digital-ic-agent.observability.v1"
    assert payload["run_id"] == "run-123"
    assert payload["flow"] == "sim-rtl"
    assert payload["stage"] == "vivado_batch"
    assert payload["event"] == "tool_finished"
    assert payload["status"] == "FAIL"
    assert payload["duration_ms"] == 125
    assert payload["exit_code"] == 4
    assert payload["error_category"] == "tool_execution"
    assert payload["tool_versions"] == {"vivado": "2025.2"}
    assert payload["details"]["license_key"] == "***"
    assert payload["details"]["nested"]["api_key"] == "***"
    assert payload["details"]["command"] == ["vivado", "-mode", "batch"]
    assert len(payload["details"]["stdout"]) <= agent_observability.MAX_DETAIL_TEXT_LENGTH
    assert payload["details"]["stdout"].endswith("...[truncated]")

    log_path = agent_observability.append_observability_event(
        tmp_path / "timeline.jsonl",
        event,
    )
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["run_id"] for line in lines] == ["run-123"]


def test_observability_timeline_can_be_rebuilt_by_run_id(tmp_path):
    import agent_observability  # noqa: E402

    timeline_path = tmp_path / "timeline.jsonl"
    for run_id, stage in (
        ("run-1", "preflight"),
        ("run-2", "preflight"),
        ("run-1", "artifact_manifest"),
    ):
        agent_observability.append_observability_event(
            timeline_path,
            agent_observability.build_observability_event(
                run_id=run_id,
                flow="sim-rtl",
                stage=stage,
                event="stage_finished",
                status="PASS",
                duration_ms=1,
            ),
        )

    run_events = agent_observability.load_observability_timeline(
        timeline_path,
        run_id="run-1",
    )

    assert [event["run_id"] for event in run_events] == ["run-1", "run-1"]
    assert [event["stage"] for event in run_events] == [
        "preflight",
        "artifact_manifest",
    ]


def test_artifact_manifest_run_appends_observability_timeline(tmp_path):
    import artifact_manifest  # noqa: E402

    class FakeAgent:
        def get_target(self, target: str) -> dict[str, object]:
            return {
                "name": target,
                "artifact_manifest": [
                    {
                        "id": "rtl",
                        "path": "rtl/example.v",
                        "status": "PASS",
                    }
                ],
            }

    project_dir = tmp_path / "sample-target"
    rtl_path = project_dir / "rtl" / "example.v"
    rtl_path.parent.mkdir(parents=True)
    rtl_path.write_text("module example; endmodule\n", encoding="utf-8")

    manifest_path = artifact_manifest.record_artifact_run(
        FakeAgent(),
        "sample-target",
        "generate-rtl",
        output_dir=tmp_path,
        project_dir=project_dir,
        options={"license_key": "do-not-log"},
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run = manifest["runs"][-1]
    timeline_path = project_dir / "artifacts.timeline.jsonl"
    timeline_events = [
        json.loads(line)
        for line in timeline_path.read_text(encoding="utf-8").splitlines()
    ]

    assert timeline_events[-1]["run_id"] == run["run_id"]
    assert timeline_events[-1]["flow"] == "generate-rtl"
    assert timeline_events[-1]["stage"] == "artifact_manifest"
    assert timeline_events[-1]["event"] == "flow_finished"
    assert timeline_events[-1]["status"] == "PASS"
    assert isinstance(timeline_events[-1]["duration_ms"], int)
    assert timeline_events[-1]["duration_ms"] >= 0
    assert timeline_events[-1]["details"]["target"] == "sample-target"
    assert timeline_events[-1]["details"]["options"]["license_key"] == "***"


def test_artifact_manifest_accepts_caller_supplied_run_id(tmp_path):
    import artifact_manifest  # noqa: E402
    import agent_observability  # noqa: E402

    class FakeAgent:
        def get_target(self, target: str) -> dict[str, object]:
            return {
                "name": target,
                "artifact_manifest": [],
            }

    project_dir = tmp_path / "sample-target"

    manifest_path = artifact_manifest.record_artifact_run(
        FakeAgent(),
        "sample-target",
        "sim-rtl",
        output_dir=tmp_path,
        project_dir=project_dir,
        run_id="run-from-target-flow",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    timeline_events = agent_observability.load_observability_timeline(
        project_dir / "artifacts.timeline.jsonl",
        run_id="run-from-target-flow",
    )

    assert manifest["runs"][-1]["run_id"] == "run-from-target-flow"
    assert [event["run_id"] for event in timeline_events] == ["run-from-target-flow"]


def test_target_flow_timeline_rebuilds_preflight_handler_and_manifest_stages(tmp_path):
    import agent_observability  # noqa: E402
    import artifact_manifest  # noqa: E402
    import target_flows  # noqa: E402

    class PreflightReport:
        ok = True
        missing_required: tuple[str, ...] = ()

    class PassingHandler:
        flows = {"sim-rtl": object()}
        plugin = None

        def run(self, _flow: str, **_kwargs: object) -> object:
            return True

    class FakeAgent:
        targets = {
            "sample-target": {
                "name": "sample-target",
                "display_name": "Sample Target",
                "design_family": "test",
                "flows": ["sim-rtl"],
                "artifact_manifest": [],
            }
        }
        target_handlers = {"sample-target": PassingHandler()}

        def normalize_rtl_target(self, target: str) -> str:
            return target

        def run_preflight(self, _flow: str) -> PreflightReport:
            return PreflightReport()

        def get_target(self, target: str) -> dict[str, object]:
            return dict(self.targets[target])

        def record_artifact_run(self, target: str, flow: str, **kwargs: object) -> Path:
            return artifact_manifest.record_artifact_run(self, target, flow, **kwargs)

    assert (
        target_flows.run_target_flow(
            FakeAgent(),
            "sample-target",
            "sim-rtl",
            output_dir=tmp_path,
        )
        is True
    )

    manifest_path = tmp_path / "sample-target" / "artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = manifest["runs"][-1]["run_id"]
    timeline_events = agent_observability.load_observability_timeline(
        tmp_path / "sample-target" / "artifacts.timeline.jsonl",
        run_id=run_id,
    )

    assert [event["stage"] for event in timeline_events] == [
        "preflight",
        "target_flow",
        "artifact_manifest",
    ]
    assert {event["run_id"] for event in timeline_events} == {run_id}
