from pathlib import Path
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from os import PathLike
from typing import Any, Literal, NotRequired, Protocol, TextIO, TypedDict, cast

from digital_ic_agent._runtime.agent_observability import append_observability_event, build_observability_event
from digital_ic_agent._runtime.artifact_manifest import (
    file_fingerprint,
    snapshot_project_artifacts,
)
from digital_ic_agent._runtime.agent_errors import AgentError, CapabilityError, ToolExecutionError
from digital_ic_agent._runtime.agent_runtime import PluginServices
from digital_ic_agent._runtime.capability_preflight import PreflightReport
from digital_ic_agent._runtime.target_registry import (
    get_target as get_registered_target,
    list_targets as list_registered_targets,
    load_target_registry as load_registered_targets,
)
from digital_ic_agent._runtime.target_plugins import (
    TargetHandlerRegistry,
    build_target_handlers as build_plugin_target_handlers,
    load_target_handler_plugins,
)
from digital_ic_agent._runtime.verification_verdict import (
    VerificationVerdict,
    failed_verdict,
    load_verification_verdict,
    write_verification_verdict,
)


BUILTIN_HANDLER_MODULES = (
    "digital_ic_agent._runtime.target_handlers.async_fifo",
    "digital_ic_agent._runtime.target_handlers.round_robin_arbiter",
    "digital_ic_agent._runtime.target_handlers.sync_fifo",
)

CANONICAL_VERDICT_FLOWS = {
    "regress-rtl",
    "sim-rtl",
    "uvm-smoke",
    "uvm-coverage",
    "uvm-random-regress",
}


PLUGIN_OPERATION_NAMES = (
    "analyze_round_robin_arbiter_vcd",
    "analyze_sync_fifo_vcd",
    "check_round_robin_arbiter_rtl",
    "check_sync_fifo_rtl",
    "generate_rtl_project",
    "launch_vivado_gui",
    "open_round_robin_arbiter_project_gui",
    "open_sync_fifo_project_gui",
    "render_vivado_tclstore_bootstrap",
    "resolve_rwave_command",
    "resolve_vivado_command",
    "run_round_robin_arbiter_vivado_sim",
    "run_rwave_batch_json",
    "run_sync_fifo_vivado_sim",
    "run_vivado_batch",
    "run_waveform_analyzer_json",
    "write_round_robin_arbiter_project",
    "write_sync_fifo_project",
    "write_target_dashboard",
)


class TargetInfo(TypedDict):
    name: str
    display_name: str
    design_family: str
    aliases: NotRequired[Sequence[str]]
    flows: NotRequired[Sequence[str]]
    description: NotRequired[str]


TargetMap = Mapping[str, TargetInfo]
TargetOperation = Callable[..., object]


class TargetRegistryAgent(Protocol):
    targets_dir: Path

    def load_target_registry(self) -> TargetMap:
        ...


class TargetPluginAgent(Protocol):
    targets: TargetMap


class TargetListAgent(Protocol):
    targets: TargetMap

    def list_targets(self) -> Sequence[TargetInfo]:
        ...


class TargetLookupAgent(Protocol):
    targets: TargetMap


class TargetHandlerLike(Protocol):
    flows: Mapping[str, TargetOperation]
    plugin: object | None

    def run(self, flow: str, **kwargs: object) -> object:
        ...


class TargetHandlerValidationAgent(Protocol):
    targets: TargetMap
    target_handlers: Mapping[str, TargetHandlerLike]


class RunTargetFlowAgent(Protocol):
    targets: TargetMap
    target_handlers: Mapping[str, TargetHandlerLike]

    def normalize_rtl_target(self, target: str) -> str:
        ...

    def run_preflight(self, flow: str) -> PreflightReport:
        ...

    def record_artifact_run(
        self,
        target: str,
        flow: str,
        **kwargs: object,
    ) -> Path:
        ...


def _service_adapter(operation: TargetOperation) -> TargetOperation:
    def invoke(*args: object, **kwargs: object) -> object:
        return operation(*args, **kwargs)

    return invoke


def _resolve_plugin_operation(agent: object, name: str) -> TargetOperation:
    target_services = getattr(agent, "target_services", None)
    if target_services is not None:
        try:
            return cast(TargetOperation, getattr(target_services, name))
        except AttributeError:
            pass
    return cast(TargetOperation, getattr(agent, name))


def build_plugin_services(agent: object) -> PluginServices:
    return PluginServices(
        operations={
            name: _service_adapter(_resolve_plugin_operation(agent, name))
            for name in PLUGIN_OPERATION_NAMES
        },
    )


def build_target_handlers(agent: TargetPluginAgent) -> dict[str, TargetHandlerLike]:
    registry = TargetHandlerRegistry()
    load_target_handler_plugins(registry, BUILTIN_HANDLER_MODULES)
    handlers = cast(
        dict[str, TargetHandlerLike],
        build_plugin_target_handlers(
            build_plugin_services(agent),
            cast(Mapping[str, Mapping[str, Any]], agent.targets),
            registry,
        ),
    )
    setattr(
        agent,
        "target_plugins",
        {
            target_name: handler.plugin
            for target_name, handler in handlers.items()
            if getattr(handler, "plugin", None) is not None
        },
    )
    return handlers


def build_target_registry(agent: TargetRegistryAgent) -> TargetMap:
    return agent.load_target_registry()


def load_target_registry(
    agent: TargetRegistryAgent,
    targets_dir: str | PathLike[str] | None = None,
) -> TargetMap:
    resolved_targets_dir = Path(targets_dir) if targets_dir else agent.targets_dir
    return cast(TargetMap, load_registered_targets(resolved_targets_dir))


def list_targets(agent: TargetListAgent) -> list[TargetInfo]:
    return cast(
        list[TargetInfo],
        list_registered_targets(cast(dict[str, dict[str, Any]], agent.targets)),
    )


def get_target(agent: TargetLookupAgent, target: str) -> TargetInfo:
    return cast(
        TargetInfo,
        get_registered_target(cast(dict[str, dict[str, Any]], agent.targets), target),
    )


def render_targets(targets: Sequence[TargetInfo]) -> str:
    lines = [
        "Digital IC Agent registered targets",
        "=" * 60,
    ]
    for target in targets:
        lines.extend(
            [
                "{} ({})".format(target["name"], target["display_name"]),
                "  family: {}".format(target["design_family"]),
                "  aliases: {}".format(", ".join(target.get("aliases", [])) or "-"),
                "  flows: {}".format(", ".join(target.get("flows", []))),
                "  note: {}".format(target.get("description", "")),
            ]
        )
    return "\n".join(lines) + "\n"


def print_targets(agent: TargetListAgent, output: TextIO | None = None) -> bool:
    target_output = output or sys.stdout
    target_output.write(render_targets(agent.list_targets()))
    return True


def validate_target_handlers(agent: TargetHandlerValidationAgent) -> bool:
    if set(agent.target_handlers) != set(agent.targets):
        missing_handlers = sorted(set(agent.targets) - set(agent.target_handlers))
        unknown_handlers = sorted(set(agent.target_handlers) - set(agent.targets))
        raise ValueError(
            "Target handler registry mismatch; missing={}, unknown={}".format(
                missing_handlers,
                unknown_handlers,
            )
        )

    for target_name, target in agent.targets.items():
        configured_flows = set(target.get("flows", []))
        implemented_flows = set(agent.target_handlers[target_name].flows)
        if configured_flows != implemented_flows:
            raise ValueError(
                "Target {} flow mismatch; configured={}, implemented={}".format(
                    target_name,
                    sorted(configured_flows),
                    sorted(implemented_flows),
                )
            )
    return True


def _failure_verdict(
    project_dir: Path,
    code: str,
    message: str,
) -> VerificationVerdict:
    verdict = failed_verdict(code, message, source="target_flow")
    write_verification_verdict(project_dir, verdict)
    return verdict


def _resolve_canonical_verdict(
    project_dir: Path,
    flow: str,
    handler_result: object,
    artifact_snapshot: Mapping[str, object],
) -> tuple[VerificationVerdict | None, object]:
    if flow not in CANONICAL_VERDICT_FLOWS:
        return None, handler_result

    verdict_path = project_dir / "reports" / "verification_verdict.json"
    if not verdict_path.is_file():
        verdict = _failure_verdict(
            project_dir,
            "CANONICAL_VERDICT_MISSING",
            "Verification flow did not produce verification_verdict.json",
        )
        return verdict, False
    try:
        verdict = load_verification_verdict(verdict_path)
    except ValueError as exc:
        verdict = _failure_verdict(
            project_dir,
            "CANONICAL_VERDICT_INVALID",
            str(exc),
        )
        return verdict, False

    baseline = artifact_snapshot.get("reports/verification_verdict.json")
    if isinstance(baseline, Mapping):
        baseline_digest = baseline.get("sha256")
        if baseline_digest == file_fingerprint(verdict_path)["sha256"]:
            verdict = _failure_verdict(
                project_dir,
                "CANONICAL_VERDICT_STALE",
                "Verification flow reused a verdict from an earlier run",
            )
            return verdict, False

    if verdict.passed and not bool(handler_result):
        verdict = _failure_verdict(
            project_dir,
            "VERDICT_RESULT_MISMATCH",
            "Handler returned failure while canonical verdict reported PASS",
        )
        return verdict, False
    return verdict, verdict.passed


def run_target_flow(
    agent: RunTargetFlowAgent,
    target: str,
    flow: str,
    **kwargs: object,
) -> object:
    run_id = uuid.uuid4().hex
    target_name = agent.normalize_rtl_target(target)
    if flow not in agent.targets[target_name].get("flows", []):
        raise ValueError(
            "Target {} does not declare flow: {}".format(target_name, flow)
        )
    output_dir = cast(str | PathLike[str], kwargs.get("output_dir", "outputs"))
    project_dir = Path(output_dir) / target_name
    timeline_path = project_dir / "artifacts.timeline.jsonl"
    artifact_snapshot = snapshot_project_artifacts(project_dir)
    preflight_started = time.perf_counter()
    preflight_report = agent.run_preflight(flow)
    append_observability_event(
        timeline_path,
        build_observability_event(
            run_id=run_id,
            flow=str(flow),
            stage="preflight",
            event="stage_finished",
            status="PASS" if preflight_report.ok else "FAIL",
            duration_ms=max(0, int((time.perf_counter() - preflight_started) * 1000)),
            exit_code=None if preflight_report.ok else 3,
            error_category=None if preflight_report.ok else "capability",
            details={
                "missing_required": tuple(preflight_report.missing_required),
                "target": target_name,
            },
        ),
    )
    if not preflight_report.ok:
        error_message = "Missing required capabilities for {}: {}".format(
            flow,
            ", ".join(preflight_report.missing_required),
        )
        capability_error = CapabilityError(
            error_message,
            stage="preflight",
            details={
                "flow": str(flow),
                "missing_required": tuple(preflight_report.missing_required),
                "target": target_name,
            },
        )
        verdict = None
        if flow in CANONICAL_VERDICT_FLOWS:
            verdict = _failure_verdict(
                project_dir,
                "PREFLIGHT_FAILED",
                error_message,
            )
        agent.record_artifact_run(
            target_name,
            flow,
            output_dir=output_dir,
            status="FAIL",
            error=capability_error,
            options=kwargs,
            artifact_snapshot=artifact_snapshot,
            run_id=run_id,
            verification_verdict=(
                None if verdict is None else verdict.to_dict()
            ),
        )
        return False
    try:
        target_flow_started = time.perf_counter()
        result = agent.target_handlers[target_name].run(flow, **kwargs)
    except Exception as exc:
        handler_error = (
            exc
            if isinstance(exc, AgentError)
            else ToolExecutionError(
                str(exc),
                stage="target_flow",
                details={
                    "exception_type": type(exc).__name__,
                    "flow": str(flow),
                    "target": target_name,
                },
            )
        )
        event_details = {
            "exception_type": type(exc).__name__,
            "target": target_name,
            **handler_error.details,
        }
        append_observability_event(
            timeline_path,
            build_observability_event(
                run_id=run_id,
                flow=str(flow),
                stage="target_flow",
                event="stage_finished",
                status="FAIL",
                duration_ms=max(0, int((time.perf_counter() - target_flow_started) * 1000)),
                exit_code=handler_error.exit_code,
                error_category=handler_error.category,
                details=event_details,
            ),
        )
        verdict = None
        if flow in CANONICAL_VERDICT_FLOWS:
            verdict = _failure_verdict(
                project_dir,
                "TARGET_FLOW_EXCEPTION",
                str(handler_error),
            )
        agent.record_artifact_run(
            target_name,
            flow,
            output_dir=output_dir,
            status="FAIL",
            error=handler_error,
            options=kwargs,
            artifact_snapshot=artifact_snapshot,
            run_id=run_id,
            verification_verdict=(
                None if verdict is None else verdict.to_dict()
            ),
        )
        raise

    verdict, result = _resolve_canonical_verdict(
        project_dir,
        flow,
        result,
        artifact_snapshot,
    )
    status: Literal["PASS", "FAIL"] = "PASS" if result else "FAIL"
    tool_error = None
    if not result:
        tool_error = ToolExecutionError(
            "flow returned a false result",
            stage="target_flow",
            details={
                "flow": str(flow),
                "reason": "false_result",
                "target": target_name,
            },
        )
    append_observability_event(
        timeline_path,
        build_observability_event(
            run_id=run_id,
            flow=str(flow),
            stage="target_flow",
            event="stage_finished",
            status=status,
            duration_ms=max(0, int((time.perf_counter() - target_flow_started) * 1000)),
            exit_code=None if tool_error is None else tool_error.exit_code,
            error_category=None if tool_error is None else tool_error.category,
            details={
                "target": target_name,
                "result": bool(result),
            },
        ),
    )
    agent.record_artifact_run(
        target_name,
        flow,
        output_dir=output_dir,
        status=status,
        error=tool_error,
        options=kwargs,
        artifact_snapshot=artifact_snapshot,
        run_id=run_id,
        verification_verdict=(
            None if verdict is None else verdict.to_dict()
        ),
    )
    return result
