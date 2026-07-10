from pathlib import Path
from typing import Any, Mapping

from agent_runtime import PluginServices, TargetHandler


HANDLER_ID = "round-robin-arbiter"
REQUIRED_SERVICES = (
    "analyze_round_robin_arbiter_vcd",
    "check_round_robin_arbiter_rtl",
    "open_round_robin_arbiter_project_gui",
    "run_round_robin_arbiter_vivado_sim",
    "write_round_robin_arbiter_project",
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
                lambda output_dir="outputs", **_:
                services.call("write_round_robin_arbiter_project", output_dir)
            ),
            "sim-rtl": (
                lambda output_dir="outputs", open_wave_gui=True, **_:
                services.call(
                    "run_round_robin_arbiter_vivado_sim",
                    output_dir=output_dir,
                    open_wave_gui=open_wave_gui,
                )
            ),
            "analyze-rtl-vcd": (
                lambda output_dir="outputs",
                limit=20,
                waveform_backend="auto",
                **_: services.call(
                    "analyze_round_robin_arbiter_vcd",
                    output_dir=output_dir,
                    limit=limit,
                    waveform_backend=waveform_backend,
                )
            ),
            "check-rtl": (
                lambda output_dir="outputs", **_:
                services.call(
                    "check_round_robin_arbiter_rtl",
                    output_dir=output_dir
                )
            ),
            "open-wave": (
                lambda output_dir="outputs", **_:
                services.call(
                    "open_round_robin_arbiter_project_gui",
                    Path(output_dir) / target_name
                )
            ),
        },
    )
