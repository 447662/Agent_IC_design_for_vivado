from functools import partial
from typing import Any, Mapping

from digital_ic_agent._runtime.agent_runtime import PluginServices, TargetHandler
from digital_ic_agent._runtime.target_examples.async_fifo import AsyncFifoPlugin


HANDLER_ID = "async-fifo"


def create_handler(
    services: PluginServices,
    target: Mapping[str, Any],
) -> TargetHandler:
    target_name = str(target["name"])
    plugin = AsyncFifoPlugin(target_name, services)
    return TargetHandler(
        target_name,
        {
            flow: partial(plugin.execute, flow)
            for flow in plugin.supported_flows
        },
        extension_methods=tuple(
            sorted(
                name
                for name in dir(plugin)
                if name.startswith(
                    (
                        "analyze_async_fifo",
                        "check_async_fifo",
                        "open_async_fifo",
                        "render_async_fifo",
                        "run_async_fifo",
                        "write_async_fifo",
                    )
                )
            )
        ),
        plugin=plugin,
    )
