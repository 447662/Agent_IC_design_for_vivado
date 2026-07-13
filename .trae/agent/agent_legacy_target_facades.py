from typing import Any

from agent_round_robin_arbiter import RoundRobinArbiterMixin
from agent_sync_fifo import SyncFifoMixin


SYNC_FIFO_HELPERS = {
    name: getattr(SyncFifoMixin, name)
    for name in (
        "resolve_sync_fifo_vcd_path",
        "write_sync_fifo_sim_report",
        "check_sync_fifo_rtl",
        "render_sync_fifo_rtl",
        "render_sync_fifo_tb",
        "render_sync_fifo_vivado_script",
        "render_sync_fifo_xsim_tcl",
        "render_sync_fifo_project_script",
        "render_sync_fifo_open_project_gui_script",
        "render_sync_fifo_readme",
        "write_sync_fifo_project",
        "resolve_sync_fifo_wave_db",
    )
}

ROUND_ROBIN_HELPERS = {
    name: getattr(RoundRobinArbiterMixin, name)
    for name in (
        "resolve_round_robin_arbiter_vcd_path",
        "write_round_robin_arbiter_sim_report",
        "check_round_robin_arbiter_rtl",
        "render_round_robin_arbiter_rtl",
        "render_round_robin_arbiter_tb",
        "render_round_robin_arbiter_vivado_script",
        "render_round_robin_arbiter_xsim_tcl",
        "render_round_robin_arbiter_project_script",
        "render_round_robin_arbiter_open_project_gui_script",
        "render_round_robin_arbiter_readme",
        "write_round_robin_arbiter_project",
        "resolve_round_robin_arbiter_wave_db",
    )
}


class LegacyTargetProxy:
    def __init__(self, agent: Any, helpers: dict[str, Any]) -> None:
        self._agent = agent
        self._helpers = helpers

    def __getattr__(self, name: str) -> Any:
        try:
            return getattr(self._agent, name)
        except AttributeError:
            if name not in self._helpers:
                raise
            return self._helpers[name].__get__(self, type(self))


def _sync_proxy(agent: Any) -> Any:
    return LegacyTargetProxy(agent, SYNC_FIFO_HELPERS)


def _round_robin_proxy(agent: Any) -> Any:
    return LegacyTargetProxy(agent, ROUND_ROBIN_HELPERS)


def collect_sync_fifo_vcd_analysis(self: Any, *args: Any, **kwargs: Any) -> Any:
    return SyncFifoMixin.collect_sync_fifo_vcd_analysis(_sync_proxy(self), *args, **kwargs)


def analyze_sync_fifo_vcd(self: Any, *args: Any, **kwargs: Any) -> Any:
    return SyncFifoMixin.analyze_sync_fifo_vcd(_sync_proxy(self), *args, **kwargs)


def open_sync_fifo_project_gui(self: Any, *args: Any, **kwargs: Any) -> Any:
    return SyncFifoMixin.open_sync_fifo_project_gui(_sync_proxy(self), *args, **kwargs)


def run_sync_fifo_vivado_sim(self: Any, *args: Any, **kwargs: Any) -> Any:
    return SyncFifoMixin.run_sync_fifo_vivado_sim(_sync_proxy(self), *args, **kwargs)


def collect_round_robin_arbiter_vcd_analysis(
    self: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    return RoundRobinArbiterMixin.collect_round_robin_arbiter_vcd_analysis(
        _round_robin_proxy(self),
        *args,
        **kwargs,
    )


def analyze_round_robin_arbiter_vcd(
    self: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    return RoundRobinArbiterMixin.analyze_round_robin_arbiter_vcd(
        _round_robin_proxy(self),
        *args,
        **kwargs,
    )


def open_round_robin_arbiter_project_gui(
    self: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    return RoundRobinArbiterMixin.open_round_robin_arbiter_project_gui(
        _round_robin_proxy(self),
        *args,
        **kwargs,
    )


def run_round_robin_arbiter_vivado_sim(
    self: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    return RoundRobinArbiterMixin.run_round_robin_arbiter_vivado_sim(
        _round_robin_proxy(self),
        *args,
        **kwargs,
    )


def install_legacy_target_facades(agent_cls: Any) -> Any:
    agent_cls.collect_sync_fifo_vcd_analysis = collect_sync_fifo_vcd_analysis
    agent_cls.analyze_sync_fifo_vcd = analyze_sync_fifo_vcd
    agent_cls.open_sync_fifo_project_gui = open_sync_fifo_project_gui
    agent_cls.run_sync_fifo_vivado_sim = run_sync_fifo_vivado_sim
    agent_cls.collect_round_robin_arbiter_vcd_analysis = (
        collect_round_robin_arbiter_vcd_analysis
    )
    agent_cls.analyze_round_robin_arbiter_vcd = analyze_round_robin_arbiter_vcd
    agent_cls.open_round_robin_arbiter_project_gui = open_round_robin_arbiter_project_gui
    agent_cls.run_round_robin_arbiter_vivado_sim = run_round_robin_arbiter_vivado_sim
    return agent_cls
