from collections.abc import Callable, Mapping
from typing import Protocol, cast

from digital_ic_agent._runtime.agent_round_robin_arbiter import RoundRobinArbiterMixin
from digital_ic_agent._runtime.agent_sync_fifo import SyncFifoMixin


class LegacyHelper(Protocol):
    def __get__(
        self,
        instance: object,
        owner: type[object],
    ) -> Callable[..., object]: ...


def _helper(owner: type[object], name: str) -> LegacyHelper:
    return cast(LegacyHelper, getattr(owner, name))


SYNC_FIFO_HELPERS = {
    name: _helper(SyncFifoMixin, name)
    for name in (
        "collect_sync_fifo_vcd_analysis",
        "analyze_sync_fifo_vcd",
        "open_sync_fifo_project_gui",
        "run_sync_fifo_vivado_sim",
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
    name: _helper(RoundRobinArbiterMixin, name)
    for name in (
        "collect_round_robin_arbiter_vcd_analysis",
        "analyze_round_robin_arbiter_vcd",
        "open_round_robin_arbiter_project_gui",
        "run_round_robin_arbiter_vivado_sim",
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
    def __init__(self, agent: object, helpers: Mapping[str, LegacyHelper]) -> None:
        self._agent = agent
        self._helpers = helpers

    def __getattr__(self, name: str) -> object:
        try:
            return cast(object, getattr(self._agent, name))
        except AttributeError:
            helper = self._helpers.get(name)
            if helper is None:
                raise
            return helper.__get__(self, type(self))


def _call_helper(
    agent: object,
    helpers: Mapping[str, LegacyHelper],
    name: str,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> object:
    proxy = LegacyTargetProxy(agent, helpers)
    helper = helpers[name].__get__(proxy, type(proxy))
    return helper(*args, **kwargs)


def collect_sync_fifo_vcd_analysis(
    self: object,
    *args: object,
    **kwargs: object,
) -> object:
    return _call_helper(self, SYNC_FIFO_HELPERS, "collect_sync_fifo_vcd_analysis", args, kwargs)


def analyze_sync_fifo_vcd(
    self: object,
    *args: object,
    **kwargs: object,
) -> object:
    return _call_helper(self, SYNC_FIFO_HELPERS, "analyze_sync_fifo_vcd", args, kwargs)


def open_sync_fifo_project_gui(
    self: object,
    *args: object,
    **kwargs: object,
) -> object:
    return _call_helper(self, SYNC_FIFO_HELPERS, "open_sync_fifo_project_gui", args, kwargs)


def run_sync_fifo_vivado_sim(
    self: object,
    *args: object,
    **kwargs: object,
) -> object:
    return _call_helper(self, SYNC_FIFO_HELPERS, "run_sync_fifo_vivado_sim", args, kwargs)


def collect_round_robin_arbiter_vcd_analysis(
    self: object,
    *args: object,
    **kwargs: object,
) -> object:
    return _call_helper(
        self,
        ROUND_ROBIN_HELPERS,
        "collect_round_robin_arbiter_vcd_analysis",
        args,
        kwargs,
    )


def analyze_round_robin_arbiter_vcd(
    self: object,
    *args: object,
    **kwargs: object,
) -> object:
    return _call_helper(
        self,
        ROUND_ROBIN_HELPERS,
        "analyze_round_robin_arbiter_vcd",
        args,
        kwargs,
    )


def open_round_robin_arbiter_project_gui(
    self: object,
    *args: object,
    **kwargs: object,
) -> object:
    return _call_helper(
        self,
        ROUND_ROBIN_HELPERS,
        "open_round_robin_arbiter_project_gui",
        args,
        kwargs,
    )


def run_round_robin_arbiter_vivado_sim(
    self: object,
    *args: object,
    **kwargs: object,
) -> object:
    return _call_helper(
        self,
        ROUND_ROBIN_HELPERS,
        "run_round_robin_arbiter_vivado_sim",
        args,
        kwargs,
    )


def install_legacy_target_facades(agent_cls: type[object]) -> type[object]:
    methods = {
        "collect_sync_fifo_vcd_analysis": collect_sync_fifo_vcd_analysis,
        "analyze_sync_fifo_vcd": analyze_sync_fifo_vcd,
        "open_sync_fifo_project_gui": open_sync_fifo_project_gui,
        "run_sync_fifo_vivado_sim": run_sync_fifo_vivado_sim,
        "collect_round_robin_arbiter_vcd_analysis": collect_round_robin_arbiter_vcd_analysis,
        "analyze_round_robin_arbiter_vcd": analyze_round_robin_arbiter_vcd,
        "open_round_robin_arbiter_project_gui": open_round_robin_arbiter_project_gui,
        "run_round_robin_arbiter_vivado_sim": run_round_robin_arbiter_vivado_sim,
    }
    for name, method in methods.items():
        setattr(agent_cls, name, method)
    return agent_cls
