from pathlib import Path
from typing import Any, Mapping

from agent_async_fifo_render import AsyncFifoRenderMixin
from agent_async_fifo_reports import AsyncFifoReportMixin
from agent_async_fifo_runtime import AsyncFifoRuntimeMixin
from agent_runtime import PluginServices


ASYNC_FIFO_SERVICE_NAMES = (
    "launch_vivado_gui",
    "render_vivado_tclstore_bootstrap",
    "resolve_rwave_command",
    "resolve_vivado_command",
    "run_rwave_batch_json",
    "run_vivado_batch",
    "run_waveform_analyzer_json",
    "write_target_dashboard",
)


class AsyncFifoPlugin(
    AsyncFifoRenderMixin,
    AsyncFifoReportMixin,
    AsyncFifoRuntimeMixin,
):
    plugin_id = "async-fifo"
    supported_flows = (
        "analyze-rtl-vcd",
        "check-rtl",
        "generate-rtl",
        "open-uvm-wave",
        "open-wave",
        "regress-rtl",
        "sim-rtl",
        "uvm-coverage",
        "uvm-random-regress",
        "uvm-smoke",
    )

    def __init__(self, target_name: str, services: PluginServices):
        self.target_name = target_name
        self.services = services.restrict(ASYNC_FIFO_SERVICE_NAMES)
        self.project_root = self.services.project_root

    def generate_rtl_project(
        self,
        target: str,
        output_dir: str | Path = "outputs",
        data_width: int = 8,
        addr_width: int = 4,
    ) -> Path:
        if str(target) != self.target_name:
            raise ValueError(
                "Async FIFO plugin cannot generate target: {}".format(target)
            )
        return Path(
            self.write_async_fifo_project(
                output_dir,
                data_width=data_width,
                addr_width=addr_width,
            )
        )

    def launch_vivado_gui(self, *args: Any, **kwargs: Any) -> Any:
        return self.services.call("launch_vivado_gui", *args, **kwargs)

    def render_vivado_tclstore_bootstrap(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return self.services.call(
            "render_vivado_tclstore_bootstrap",
            *args,
            **kwargs,
        )

    def resolve_rwave_command(self, *args: Any, **kwargs: Any) -> Any:
        return self.services.call("resolve_rwave_command", *args, **kwargs)

    def resolve_vivado_command(self, *args: Any, **kwargs: Any) -> Any:
        return self.services.call("resolve_vivado_command", *args, **kwargs)

    def run_rwave_batch_json(self, *args: Any, **kwargs: Any) -> Any:
        return self.services.call("run_rwave_batch_json", *args, **kwargs)

    def run_vivado_batch(self, *args: Any, **kwargs: Any) -> Any:
        return self.services.call("run_vivado_batch", *args, **kwargs)

    def run_waveform_analyzer_json(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return self.services.call(
            "run_waveform_analyzer_json",
            *args,
            **kwargs,
        )

    def write_target_dashboard(self, *args: Any, **kwargs: Any) -> Any:
        return self.services.call("write_target_dashboard", *args, **kwargs)

    def execute(
        self,
        flow: str,
        request: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        options = dict(request or {})
        options.update(kwargs)
        output_dir = options.pop("output_dir", "outputs")
        if flow == "generate-rtl":
            return self.write_async_fifo_project(
                output_dir,
                data_width=options.get("data_width", 8),
                addr_width=options.get("addr_width", 4),
            )
        if flow == "sim-rtl":
            return self.run_async_fifo_vivado_sim(
                output_dir=output_dir,
                open_wave_gui=options.get("open_wave_gui", True),
            )
        if flow == "regress-rtl":
            return self.run_async_fifo_regression(
                output_dir=output_dir,
                open_wave_gui=options.get("open_wave_gui", False),
            )
        if flow == "uvm-smoke":
            return self.run_async_fifo_uvm_smoke(
                output_dir=output_dir,
                open_wave_gui=options.get("open_wave_gui", True),
            )
        if flow == "uvm-coverage":
            return self.run_async_fifo_uvm_coverage(
                output_dir=output_dir,
                coverage_threshold=options.get("coverage_threshold"),
                coverage_percent=options.get("coverage_percent"),
                coverage_thresholds=options.get("coverage_thresholds"),
            )
        if flow == "uvm-random-regress":
            return self.run_async_fifo_uvm_random_regression(
                output_dir=output_dir,
                seeds=options.get("seeds"),
            )
        if flow == "analyze-rtl-vcd":
            return self.analyze_async_fifo_vcd(
                output_dir=output_dir,
                limit=options.get("limit", 20),
                waveform_backend=options.get("waveform_backend", "auto"),
            )
        if flow == "check-rtl":
            return self.check_async_fifo_rtl(output_dir=output_dir)
        project_dir = Path(output_dir) / self.target_name
        if flow == "open-wave":
            return self.open_async_fifo_project_gui(project_dir)
        if flow == "open-uvm-wave":
            return self.open_async_fifo_uvm_wave_gui(
                project_dir,
                wave_kind=options.get("wave_kind", "coverage"),
            )
        raise ValueError(
            "Target {} does not support flow: {}".format(
                self.target_name,
                flow,
            )
        )
