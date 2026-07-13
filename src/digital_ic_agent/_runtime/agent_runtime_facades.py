from collections.abc import Callable, Mapping, Sequence
import os
import shutil
from pathlib import Path
from typing import NotRequired, Protocol, TypedDict, cast

from digital_ic_agent._runtime.artifact_manifest import record_artifact_run as append_artifact_run
from digital_ic_agent._runtime.agent_sim_smoke import (
    IcarusSmokeAgent,
    SimSmokeAgent,
    SimulatorDetector,
    SmokeLoopAgent,
    VivadoGuiAgent,
    VivadoSmokeAgent,
    detect_simulator as detect_simulator_flow,
    open_vivado_wave_gui as open_vivado_wave_gui_flow,
    render_vivado_tclstore_bootstrap as render_vivado_tclstore_bootstrap_flow,
    run_icarus_sim_smoke as run_icarus_sim_smoke_flow,
    run_sim_smoke as run_sim_smoke_flow,
    run_smoke_loop as run_smoke_loop_flow,
    run_vivado_sim_smoke as run_vivado_sim_smoke_flow,
    write_sim_smoke_sources as write_sim_smoke_sources_flow,
    write_smoke_loop_vcd as write_smoke_loop_vcd_flow,
    write_vivado_sim_script as write_vivado_sim_script_flow,
)
from digital_ic_agent._runtime.agent_waveform import (
    WaveformAnalysisAgent,
    analyze_vcd as analyze_vcd_flow,
    analyze_waveform as analyze_waveform_flow,
    resolve_rwave_command as get_rwave_command,
    resolve_rwave_source_dir as get_rwave_source_dir,
    resolve_vcd_analyzer_path as get_vcd_analyzer_path,
)
from digital_ic_agent._runtime.target_checks import check_rtl_project as run_rtl_project_checks


PathLike = str | os.PathLike[str]
MaybeText = str | None


class TargetMetadata(TypedDict):
    name: str
    display_name: NotRequired[str]
    design_family: NotRequired[str]
    aliases: NotRequired[list[str]]
    flows: NotRequired[list[str]]
    description: NotRequired[str]


class ProjectOverviewResult(TypedDict):
    status: str
    target_count: int
    ready_target_count: int
    failed_target_count: int
    environment_status: str
    targets: Sequence[Mapping[str, object]]
    environment: Mapping[str, object]
    markdown_path: Path
    html_path: Path


class ProjectOverviewAgent(Protocol):
    def write_project_overview(
        self,
        output_dir: PathLike = "outputs",
    ) -> ProjectOverviewResult:
        ...


class ArtifactRefreshAgent(ProjectOverviewAgent, Protocol):
    def refresh_project_overview(
        self,
        output_dir: PathLike = "outputs",
    ) -> ProjectOverviewResult | None:
        ...


class WaveResolverAgent(Protocol):
    project_root: Path

    def resolve_rwave_source_dir(self) -> Path | None:
        ...


class TargetFlowAgent(Protocol):
    def run_target_flow(self, target: str, flow: str, **kwargs: object) -> object:
        ...

    def get_target(self, target: str) -> TargetMetadata:
        ...


def refresh_project_overview(
    agent: ProjectOverviewAgent,
    output_dir: PathLike = "outputs",
) -> ProjectOverviewResult | None:
    try:
        return agent.write_project_overview(output_dir=output_dir)
    except (OSError, ValueError):
        return None


def record_artifact_run(
    agent: ArtifactRefreshAgent,
    *args: object,
    **kwargs: object,
) -> Path:
    manifest_path = append_artifact_run(agent, *args, **kwargs)
    raw_output_dir = kwargs.get(
        "output_dir",
        args[2] if len(args) > 2 else "outputs",
    )
    output_dir: PathLike = (
        raw_output_dir
        if isinstance(raw_output_dir, str | os.PathLike)
        else "outputs"
    )
    agent.refresh_project_overview(output_dir)
    return manifest_path


def resolve_vcd_analyzer_path(agent: WaveResolverAgent) -> Path:
    return get_vcd_analyzer_path(agent.project_root)


def resolve_rwave_source_dir(agent: WaveResolverAgent) -> Path | None:
    return get_rwave_source_dir(agent.project_root)


def resolve_rwave_command(agent: WaveResolverAgent) -> str | None:
    return get_rwave_command(
        agent.project_root,
        env=os.environ,
        which=shutil.which,
        source_dir_resolver=agent.resolve_rwave_source_dir,
    )


def analyze_waveform(
    agent: WaveformAnalysisAgent,
    waveform_path: PathLike,
    condition: MaybeText = None,
    show: MaybeText = None,
    limit: int = 20,
    waveform_backend: str = "auto",
    report_title: str = "波形分析报告",
) -> bool:
    return analyze_waveform_flow(
        agent,
        Path(waveform_path),
        condition,
        show,
        limit,
        waveform_backend,
        report_title,
    )


def analyze_vcd(
    agent: WaveformAnalysisAgent,
    vcd_path: PathLike,
    condition: MaybeText = None,
    show: MaybeText = None,
    limit: int = 20,
    waveform_backend: str = "auto",
) -> bool:
    return analyze_vcd_flow(agent, Path(vcd_path), condition, show, limit, waveform_backend)


def check_rtl_project(
    _agent: object,
    target_name: str,
    output_dir: PathLike,
    rtl_name: str,
    tb_name: str,
    sim_script_name: str,
    project_script_name: str,
    gui_script_name: str,
    xpr_name: str,
    vcd_name: str,
    wave_db_resolver: Callable[[Path], Path],
    rtl_markers: Sequence[tuple[str, str]],
    tb_markers: Sequence[tuple[str, str]],
) -> bool:
    return cast(
        bool,
        run_rtl_project_checks(
            target_name=target_name,
            output_dir=output_dir,
            rtl_name=rtl_name,
            tb_name=tb_name,
            sim_script_name=sim_script_name,
            project_script_name=project_script_name,
            gui_script_name=gui_script_name,
            xpr_name=xpr_name,
            vcd_name=vcd_name,
            wave_db_resolver=wave_db_resolver,
            rtl_markers=rtl_markers,
            tb_markers=tb_markers,
        ),
    )


def open_rtl_wave(agent: TargetFlowAgent, target: str, output_dir: PathLike = "outputs") -> bool:
    return cast(
        bool,
        agent.run_target_flow(
            target,
            "open-wave",
            output_dir=output_dir,
        ),
    )


def write_smoke_loop_vcd(_agent: object, output_dir: PathLike) -> Path:
    return write_smoke_loop_vcd_flow(Path(output_dir))


def run_smoke_loop(
    agent: SmokeLoopAgent,
    output_dir: PathLike = "outputs",
    limit: int = 20,
    waveform_backend: str = "auto",
) -> bool:
    return run_smoke_loop_flow(agent, Path(output_dir), limit, waveform_backend)


def detect_simulator(agent: SimulatorDetector) -> str | None:
    return detect_simulator_flow(agent)


def write_sim_smoke_sources(
    _agent: object,
    output_dir: PathLike,
) -> tuple[Path, Path, Path, Path]:
    return write_sim_smoke_sources_flow(Path(output_dir))


def run_icarus_sim_smoke(
    agent: IcarusSmokeAgent,
    output_dir: PathLike,
    limit: int = 20,
    waveform_backend: str = "auto",
) -> bool:
    return run_icarus_sim_smoke_flow(agent, Path(output_dir), limit, waveform_backend)


def write_vivado_sim_script(
    _agent: object,
    sim_dir: PathLike,
    rtl_path: PathLike,
    tb_path: PathLike,
    vcd_path: PathLike,
) -> Path:
    return write_vivado_sim_script_flow(
        Path(sim_dir),
        Path(rtl_path),
        Path(tb_path),
        Path(vcd_path),
    )


def open_vivado_wave_gui(
    agent: VivadoGuiAgent,
    sim_dir: PathLike,
    vcd_path: PathLike,
) -> bool:
    return open_vivado_wave_gui_flow(agent, Path(sim_dir), Path(vcd_path))


def run_vivado_sim_smoke(
    agent: VivadoSmokeAgent,
    output_dir: PathLike,
    limit: int = 20,
    open_wave_gui: bool = True,
    waveform_backend: str = "auto",
) -> bool:
    return run_vivado_sim_smoke_flow(
        agent,
        Path(output_dir),
        limit,
        open_wave_gui,
        waveform_backend,
    )


def run_sim_smoke(
    agent: SimSmokeAgent,
    output_dir: PathLike = "outputs",
    limit: int = 20,
    open_wave_gui: bool = True,
    waveform_backend: str = "auto",
) -> bool:
    return run_sim_smoke_flow(
        agent,
        Path(output_dir),
        limit,
        open_wave_gui,
        waveform_backend,
    )


def normalize_rtl_target(agent: TargetFlowAgent, target: str) -> str:
    return agent.get_target(target)["name"]


def render_vivado_tclstore_bootstrap(_agent: object) -> str:
    return render_vivado_tclstore_bootstrap_flow()


def generate_rtl_project(
    agent: TargetFlowAgent,
    target: str,
    output_dir: PathLike = "outputs",
    data_width: int = 8,
    addr_width: int = 4,
) -> bool:
    return cast(
        bool,
        agent.run_target_flow(
            target,
            "generate-rtl",
            output_dir=output_dir,
            data_width=data_width,
            addr_width=addr_width,
        ),
    )


def run_rtl_sim(
    agent: TargetFlowAgent,
    target: str,
    output_dir: PathLike = "outputs",
    open_wave_gui: bool = True,
) -> bool:
    return cast(
        bool,
        agent.run_target_flow(
            target,
            "sim-rtl",
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        ),
    )


def run_uvm_smoke(
    agent: TargetFlowAgent,
    target: str,
    output_dir: PathLike = "outputs",
    open_wave_gui: bool = True,
) -> bool:
    return cast(
        bool,
        agent.run_target_flow(
            target,
            "uvm-smoke",
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        ),
    )


def run_uvm_coverage(
    agent: TargetFlowAgent,
    target: str,
    output_dir: PathLike = "outputs",
    coverage_threshold: float | None = None,
    coverage_percent: float | None = None,
    coverage_thresholds: Mapping[str, float] | None = None,
) -> bool:
    return cast(
        bool,
        agent.run_target_flow(
            target,
            "uvm-coverage",
            output_dir=output_dir,
            coverage_threshold=coverage_threshold,
            coverage_percent=coverage_percent,
            coverage_thresholds=coverage_thresholds,
        ),
    )


def run_uvm_random_regression(
    agent: TargetFlowAgent,
    target: str,
    output_dir: PathLike = "outputs",
    seeds: Sequence[int] | None = None,
) -> bool:
    return cast(
        bool,
        agent.run_target_flow(
            target,
            "uvm-random-regress",
            output_dir=output_dir,
            seeds=seeds,
        ),
    )


def open_uvm_wave(
    agent: TargetFlowAgent,
    target: str,
    output_dir: PathLike = "outputs",
    wave_kind: str = "coverage",
) -> bool:
    return cast(
        bool,
        agent.run_target_flow(
            target,
            "open-uvm-wave",
            output_dir=output_dir,
            wave_kind=wave_kind,
        ),
    )


def regress_rtl(
    agent: TargetFlowAgent,
    target: str,
    output_dir: PathLike = "outputs",
    open_wave_gui: bool = False,
) -> bool:
    return cast(
        bool,
        agent.run_target_flow(
            target,
            "regress-rtl",
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        ),
    )
