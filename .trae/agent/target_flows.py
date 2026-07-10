from typing import Any
from agent_runtime import PluginServices
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


def build_plugin_services(agent: Any) -> Any:
    return PluginServices(
        command_runner=agent.command_runner,
        project_root=agent.project_root,
        operations={
            name: _service_adapter(getattr(agent, name))
            for name in PLUGIN_OPERATION_NAMES
        },
    )


def build_target_handlers(agent: Any) -> Any:
    registry = TargetHandlerRegistry()
    load_target_handler_plugins(registry, BUILTIN_HANDLER_MODULES)
    return build_plugin_target_handlers(
        build_plugin_services(agent),
        agent.targets,
        registry,
    )
