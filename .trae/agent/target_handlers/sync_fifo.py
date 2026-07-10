from pathlib import Path
from typing import Any, Mapping

from agent_runtime import PluginServices, TargetHandler


HANDLER_ID = "sync-fifo"
REQUIRED_SERVICES = (
    "analyze_sync_fifo_vcd",
    "check_sync_fifo_rtl",
    "open_sync_fifo_project_gui",
    "run_sync_fifo_vivado_sim",
    "write_sync_fifo_project",
)


def create_handler(
    services: PluginServices,
    target: Mapping[str, Any],
) -> TargetHandler:
    target_name = str(target["name"])
    services = services.restrict(REQUIRED_SERVICES)
    return TargetHandler(
        target_name,
        {
            "generate-rtl": (
                lambda output_dir="outputs", data_width=8, addr_width=4, **_:
                services.call(
                    "write_sync_fifo_project",
                    output_dir,
                    data_width=data_width,
                    addr_width=addr_width,
                )
            ),
            "sim-rtl": (
                lambda output_dir="outputs", open_wave_gui=True, **_:
                services.call(
                    "run_sync_fifo_vivado_sim",
                    output_dir=output_dir,
                    open_wave_gui=open_wave_gui,
                )
            ),
            "analyze-rtl-vcd": (
                lambda output_dir="outputs",
                limit=20,
                waveform_backend="auto",
                **_: services.call(
                    "analyze_sync_fifo_vcd",
                    output_dir=output_dir,
                    limit=limit,
                    waveform_backend=waveform_backend,
                )
            ),
            "check-rtl": (
                lambda output_dir="outputs", **_:
                services.call("check_sync_fifo_rtl", output_dir=output_dir)
            ),
            "open-wave": (
                lambda output_dir="outputs", **_:
                services.call(
                    "open_sync_fifo_project_gui",
                    Path(output_dir) / target_name
                )
            ),
        },
    )
