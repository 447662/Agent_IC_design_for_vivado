import sys
from pathlib import Path
from typing import Any

from artifact_manifest import snapshot_project_artifacts
from agent_runtime import PluginServices
from target_registry import (
    get_target as get_registered_target,
    list_targets as list_registered_targets,
    load_target_registry as load_registered_targets,
)
from target_plugins import (
    TargetHandlerRegistry,
    build_target_handlers as build_plugin_target_handlers,
    load_target_handler_plugins,
)


BUILTIN_HANDLER_MODULES = (
    "target_handlers.async_fifo",
    "target_handlers.round_robin_arbiter",
    "target_handlers.sync_fifo",
)


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


def _service_adapter(operation: Any) -> Any:
    def invoke(*args: Any, **kwargs: Any) -> Any:
        return operation(*args, **kwargs)

    return invoke


def _resolve_plugin_operation(agent: Any, name: str) -> Any:
    target_services = getattr(agent, "target_services", None)
    if target_services is not None:
        try:
            return getattr(target_services, name)
        except AttributeError:
            pass
    return getattr(agent, name)


def build_plugin_services(agent: Any) -> Any:
    return PluginServices(
        operations={
            name: _service_adapter(_resolve_plugin_operation(agent, name))
            for name in PLUGIN_OPERATION_NAMES
        },
    )


def build_target_handlers(agent: Any) -> Any:
    registry = TargetHandlerRegistry()
    load_target_handler_plugins(registry, BUILTIN_HANDLER_MODULES)
    handlers = build_plugin_target_handlers(
        build_plugin_services(agent),
        agent.targets,
        registry,
    )
    agent.target_plugins = {
        target_name: handler.plugin
        for target_name, handler in handlers.items()
        if handler.plugin is not None
    }
    return handlers


def build_target_registry(agent: Any) -> Any:
    return agent.load_target_registry()


def load_target_registry(agent: Any, targets_dir: Any = None) -> Any:
    resolved_targets_dir = Path(targets_dir) if targets_dir else agent.targets_dir
    return load_registered_targets(resolved_targets_dir)


def list_targets(agent: Any) -> Any:
    return list_registered_targets(agent.targets)


def get_target(agent: Any, target: Any) -> Any:
    return get_registered_target(agent.targets, target)


def print_targets(agent: Any) -> Any:
    print("Digital IC Agent registered targets")
    print("=" * 60)
    for target in agent.list_targets():
        print("{} ({})".format(target["name"], target["display_name"]))
        print("  family: {}".format(target["design_family"]))
        print("  aliases: {}".format(", ".join(target.get("aliases", [])) or "-"))
        print("  flows: {}".format(", ".join(target.get("flows", []))))
        print("  note: {}".format(target.get("description", "")))
    return True


def validate_target_handlers(agent: Any) -> Any:
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


def run_target_flow(agent: Any, target: Any, flow: Any, **kwargs: Any) -> Any:
    target_name = agent.normalize_rtl_target(target)
    if flow not in agent.targets[target_name].get("flows", []):
        raise ValueError(
            "Target {} does not declare flow: {}".format(target_name, flow)
        )
    output_dir = kwargs.get("output_dir", "outputs")
    project_dir = Path(output_dir) / target_name
    artifact_snapshot = snapshot_project_artifacts(project_dir)
    preflight_report = agent.run_preflight(flow)
    if not preflight_report.ok:
        error = "Missing required capabilities for {}: {}".format(
            flow,
            ", ".join(preflight_report.missing_required),
        )
        print(error, file=sys.stderr)
        agent.record_artifact_run(
            target_name,
            flow,
            output_dir=output_dir,
            status="FAIL",
            error=error,
            options=kwargs,
            artifact_snapshot=artifact_snapshot,
        )
        return False
    if preflight_report.missing_optional:
        print(
            "{} flow {} 将降级运行，缺少可选能力: {}".format(
                agent.WARN,
                flow,
                ", ".join(preflight_report.missing_optional),
            ),
            file=sys.stderr,
        )
    try:
        result = agent.target_handlers[target_name].run(flow, **kwargs)
    except Exception as exc:
        agent.record_artifact_run(
            target_name,
            flow,
            output_dir=output_dir,
            status="FAIL",
            error=exc,
            options=kwargs,
            artifact_snapshot=artifact_snapshot,
        )
        raise

    status = "PASS" if result else "FAIL"
    agent.record_artifact_run(
        target_name,
        flow,
        output_dir=output_dir,
        status=status,
        error=None if result else "flow returned a false result",
        options=kwargs,
        artifact_snapshot=artifact_snapshot,
    )
    return result
