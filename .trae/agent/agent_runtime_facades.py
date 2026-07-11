from typing import Any
import os
import shutil
import sys

from artifact_manifest import record_artifact_run as append_artifact_run
from agent_sim_smoke import (
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
from agent_waveform import (
    analyze_vcd as analyze_vcd_flow,
    analyze_waveform as analyze_waveform_flow,
    resolve_rwave_command as get_rwave_command,
    resolve_rwave_source_dir as get_rwave_source_dir,
    resolve_vcd_analyzer_path as get_vcd_analyzer_path,
)
from target_checks import check_rtl_project as run_rtl_project_checks


def refresh_project_overview(agent: Any, output_dir: Any = "outputs") -> Any:
    try:
        return agent.write_project_overview(output_dir=output_dir)
    except (OSError, ValueError) as exc:
        print("项目总览自动刷新失败: {}".format(exc), file=sys.stderr)
        return None


def record_artifact_run(agent: Any, *args: Any, **kwargs: Any) -> Any:
    manifest_path = append_artifact_run(agent, *args, **kwargs)
    output_dir = kwargs.get(
        "output_dir",
        args[2] if len(args) > 2 else "outputs",
    )
    agent.refresh_project_overview(output_dir)
    return manifest_path


def resolve_vcd_analyzer_path(agent: Any) -> Any:
    return get_vcd_analyzer_path(agent.project_root)


def resolve_rwave_source_dir(agent: Any) -> Any:
    return get_rwave_source_dir(agent.project_root)


def resolve_rwave_command(agent: Any) -> Any:
    return get_rwave_command(
        agent.project_root,
        env=os.environ,
        which=shutil.which,
        source_dir_resolver=agent.resolve_rwave_source_dir,
    )


def analyze_waveform(
    agent: Any,
    waveform_path: Any,
    condition: Any = None,
    show: Any = None,
    limit: Any = 20,
    waveform_backend: Any = "auto",
    report_title: Any = "波形分析报告",
) -> Any:
    return analyze_waveform_flow(
        agent,
        waveform_path,
        condition,
        show,
        limit,
        waveform_backend,
        report_title,
    )


def analyze_vcd(
    agent: Any,
    vcd_path: Any,
    condition: Any = None,
    show: Any = None,
    limit: Any = 20,
    waveform_backend: Any = "auto",
) -> Any:
    return analyze_vcd_flow(agent, vcd_path, condition, show, limit, waveform_backend)


def check_rtl_project(
    _agent: Any,
    target_name: Any,
    output_dir: Any,
    rtl_name: Any,
    tb_name: Any,
    sim_script_name: Any,
    project_script_name: Any,
    gui_script_name: Any,
    xpr_name: Any,
    vcd_name: Any,
    wave_db_resolver: Any,
    rtl_markers: Any,
    tb_markers: Any,
) -> Any:
    return run_rtl_project_checks(
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
    )


def open_rtl_wave(agent: Any, target: Any, output_dir: Any = "outputs") -> Any:
    return agent.run_target_flow(
        target,
        "open-wave",
        output_dir=output_dir,
    )


def write_smoke_loop_vcd(_agent: Any, output_dir: Any) -> Any:
    return write_smoke_loop_vcd_flow(output_dir)


def run_smoke_loop(
    agent: Any,
    output_dir: Any = "outputs",
    limit: Any = 20,
    waveform_backend: Any = "auto",
) -> Any:
    return run_smoke_loop_flow(agent, output_dir, limit, waveform_backend)


def detect_simulator(agent: Any) -> Any:
    return detect_simulator_flow(agent)


def write_sim_smoke_sources(_agent: Any, output_dir: Any) -> Any:
    return write_sim_smoke_sources_flow(output_dir)


def run_icarus_sim_smoke(
    agent: Any,
    output_dir: Any,
    limit: Any = 20,
    waveform_backend: Any = "auto",
) -> Any:
    return run_icarus_sim_smoke_flow(agent, output_dir, limit, waveform_backend)


def write_vivado_sim_script(
    _agent: Any,
    sim_dir: Any,
    rtl_path: Any,
    tb_path: Any,
    vcd_path: Any,
) -> Any:
    return write_vivado_sim_script_flow(sim_dir, rtl_path, tb_path, vcd_path)


def open_vivado_wave_gui(agent: Any, sim_dir: Any, vcd_path: Any) -> Any:
    return open_vivado_wave_gui_flow(agent, sim_dir, vcd_path)


def run_vivado_sim_smoke(
    agent: Any,
    output_dir: Any,
    limit: Any = 20,
    open_wave_gui: Any = True,
    waveform_backend: Any = "auto",
) -> Any:
    return run_vivado_sim_smoke_flow(
        agent,
        output_dir,
        limit,
        open_wave_gui,
        waveform_backend,
    )


def run_sim_smoke(
    agent: Any,
    output_dir: Any = "outputs",
    limit: Any = 20,
    open_wave_gui: Any = True,
    waveform_backend: Any = "auto",
) -> Any:
    return run_sim_smoke_flow(agent, output_dir, limit, open_wave_gui, waveform_backend)


def normalize_rtl_target(agent: Any, target: Any) -> Any:
    return agent.get_target(target)["name"]


def render_vivado_tclstore_bootstrap(_agent: Any) -> Any:
    return render_vivado_tclstore_bootstrap_flow()


def generate_rtl_project(
    agent: Any,
    target: Any,
    output_dir: Any = "outputs",
    data_width: Any = 8,
    addr_width: Any = 4,
) -> Any:
    return agent.run_target_flow(
        target,
        "generate-rtl",
        output_dir=output_dir,
        data_width=data_width,
        addr_width=addr_width,
    )


def run_rtl_sim(
    agent: Any,
    target: Any,
    output_dir: Any = "outputs",
    open_wave_gui: Any = True,
) -> Any:
    return agent.run_target_flow(
        target,
        "sim-rtl",
        output_dir=output_dir,
        open_wave_gui=open_wave_gui,
    )


def run_uvm_smoke(
    agent: Any,
    target: Any,
    output_dir: Any = "outputs",
    open_wave_gui: Any = True,
) -> Any:
    return agent.run_target_flow(
        target,
        "uvm-smoke",
        output_dir=output_dir,
        open_wave_gui=open_wave_gui,
    )


def run_uvm_coverage(
    agent: Any,
    target: Any,
    output_dir: Any = "outputs",
    coverage_threshold: Any = None,
    coverage_percent: Any = None,
    coverage_thresholds: Any = None,
) -> Any:
    return agent.run_target_flow(
        target,
        "uvm-coverage",
        output_dir=output_dir,
        coverage_threshold=coverage_threshold,
        coverage_percent=coverage_percent,
        coverage_thresholds=coverage_thresholds,
    )


def run_uvm_random_regression(
    agent: Any,
    target: Any,
    output_dir: Any = "outputs",
    seeds: Any = None,
) -> Any:
    return agent.run_target_flow(
        target,
        "uvm-random-regress",
        output_dir=output_dir,
        seeds=seeds,
    )


def open_uvm_wave(
    agent: Any,
    target: Any,
    output_dir: Any = "outputs",
    wave_kind: Any = "coverage",
) -> Any:
    return agent.run_target_flow(
        target,
        "open-uvm-wave",
        output_dir=output_dir,
        wave_kind=wave_kind,
    )


def regress_rtl(
    agent: Any,
    target: Any,
    output_dir: Any = "outputs",
    open_wave_gui: Any = False,
) -> Any:
    return agent.run_target_flow(
        target,
        "regress-rtl",
        output_dir=output_dir,
        open_wave_gui=open_wave_gui,
    )
