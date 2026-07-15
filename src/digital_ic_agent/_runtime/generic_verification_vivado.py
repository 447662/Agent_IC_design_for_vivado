from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, TypedDict

from digital_ic_agent._runtime.agent_sim_smoke import (
    render_vivado_tclstore_bootstrap,
)


VivadoLaunchMode = Literal["direct", "project"]


class ExecutionConfig(TypedDict):
    module: str
    testbench_top: str
    source_files: list[str]
    include_dirs: list[str]
    uvm_enabled: bool
    timescale: str
    pass_markers: list[str]
    code_thresholds: dict[str, float]
    code_coverage: bool
    functional_coverage: bool
    functional_threshold: float
    max_iterations: int
    max_time_seconds: int
    no_progress_limit: int


class VivadoToolError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        data: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = dict(data or {})


def _tool_path(bin_dir: Path | None, name: str) -> Path:
    candidates: list[Path] = []
    if bin_dir is not None:
        candidates.extend((bin_dir / f"{name}.bat", bin_dir / name))
    else:
        located = shutil.which(name) or shutil.which(f"{name}.bat")
        if located:
            candidates.append(Path(located))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise VivadoToolError(
        "VIVADO_TOOL_NOT_FOUND",
        f"Required Vivado tool was not found: {name}",
        data={"tool": name, "vivado_bin": None if bin_dir is None else str(bin_dir)},
    )


def resolve_tools(
    vivado_bin: Path | None,
    *,
    coverage_required: bool,
    vivado_launch_mode: VivadoLaunchMode = "direct",
) -> dict[str, Path]:
    bin_dir = None if vivado_bin is None else Path(vivado_bin).resolve()
    if bin_dir is not None and not bin_dir.is_dir():
        raise VivadoToolError(
            "VIVADO_BIN_NOT_FOUND",
            f"Vivado bin directory was not found: {bin_dir}",
        )
    names = (
        ["vivado"]
        if vivado_launch_mode == "project"
        else ["xvlog", "xelab", "xsim"]
    )
    if coverage_required:
        names.append("xcrg")
    return {name: _tool_path(bin_dir, name) for name in names}


def _tcl_string(value: str | Path) -> str:
    escaped = (
        str(value)
        .replace("\\", "/")
        .replace("$", "\\$")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def _tcl_list(values: Sequence[str | Path]) -> str:
    return "[list {}]".format(" ".join(_tcl_string(value) for value in values))


def render_project_verification_tcl(
    *,
    project_dir: Path,
    config: ExecutionConfig,
    source_paths: list[Path],
    include_paths: list[Path],
    coverage_required: bool,
) -> str:
    project_name = f"{config['module']}_verification"
    design_sources = [
        source
        for relative, source in zip(config["source_files"], source_paths, strict=True)
        if Path(relative).parts and Path(relative).parts[0].casefold() == "rtl"
    ]
    simulation_sources = [source for source in source_paths if source not in design_sources]
    if not design_sources:
        simulation_sources = list(source_paths)

    lines = [
        render_vivado_tclstore_bootstrap().rstrip(),
        "",
        f"set project_dir {_tcl_string(project_dir)}",
        f"create_project {_tcl_string(project_name)} $project_dir -force -part xc7vx485tffg1157-1",
        "set_property target_language Verilog [current_project]",
    ]
    if design_sources:
        lines.extend(
            (
                f"add_files -norecurse {_tcl_list(design_sources)}",
                f"set_property top {_tcl_string(config['module'])} [get_filesets sources_1]",
            )
        )
    if simulation_sources:
        lines.append(
            f"add_files -fileset sim_1 -norecurse {_tcl_list(simulation_sources)}"
        )
    lines.append(
        f"set_property top {_tcl_string(config['testbench_top'])} [get_filesets sim_1]"
    )
    if include_paths:
        include_list = _tcl_list(include_paths)
        lines.extend(
            (
                f"set_property include_dirs {include_list} [get_filesets sources_1]",
                f"set_property include_dirs {include_list} [get_filesets sim_1]",
            )
        )

    compile_options: list[str] = []
    elaborate_options = ["-timescale", config["timescale"]]
    if config["uvm_enabled"]:
        compile_options.extend(("-L", "uvm"))
        elaborate_options.extend(("-L", "uvm"))
    if compile_options:
        lines.append(
            "set_property -name {xsim.compile.xvlog.more_options} -value "
            f"{_tcl_string(' '.join(compile_options))} "
            "-objects [get_filesets sim_1]"
        )
    lines.append(
        "set_property -name {xsim.elaborate.xelab.more_options} -value "
        f"{_tcl_string(' '.join(elaborate_options))} "
        "-objects [get_filesets sim_1]"
    )
    if coverage_required:
        coverage_name = f"{config['module']}_cov"
        lines.extend(
            (
                "set_property -name {xsim.elaborate.coverage.type} "
                "-value {sbct} -objects [get_filesets sim_1]",
                "set_property -name {xsim.elaborate.coverage.name} -value "
                f"{_tcl_string(coverage_name)} -objects [get_filesets sim_1]",
                "set_property -name {xsim.elaborate.coverage.dir} "
                "-value {coverage} -objects [get_filesets sim_1]",
            )
        )
    lines.extend(
        (
            "set_property -name {xsim.simulate.runtime} "
            "-value {all} -objects [get_filesets sim_1]",
            "update_compile_order -fileset sources_1",
            "update_compile_order -fileset sim_1",
            "launch_simulation",
            'puts "DIGITAL_IC_AGENT_PROJECT_SIMULATION_COMPLETE"',
            "catch {close_sim}",
            "close_project",
            "exit 0",
            "",
        )
    )
    return "\n".join(lines)


def project_artifact(project_dir: Path, pattern: str) -> Path | None:
    candidates = sorted(path for path in project_dir.rglob(pattern) if path.is_file())
    if not candidates:
        return None
    return candidates[-1]


def copy_project_artifact(source: Path | None, destination: Path) -> Path:
    if source is not None and source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return destination
