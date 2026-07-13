#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Script Name: agent.py
# Description: 数字IC前端设计Agent主入口
#              智能分析用户需求，匹配合适的技能，检查工具环境，生成设计文档模板
# Author: Digital IC Designer Team
# Date: 2026-05-15
# -----------------------------------------------------------------------------

from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from types import TracebackType
from typing import Any, Protocol, cast
import hashlib
import html
import json
import os
import sys
from pathlib import Path
from uuid import uuid4


from digital_ic_agent._runtime import agent_capabilities as capabilities
from digital_ic_agent._runtime import agent_document_facades as document_facades
from digital_ic_agent._runtime import agent_legacy_target_facades as legacy_target_facades
from digital_ic_agent._runtime import agent_runtime_facades as runtime_facades
from digital_ic_agent._runtime import agent_skill_execution as skill_execution
from digital_ic_agent._runtime import agent_skill_listing as skill_listing
from digital_ic_agent._runtime import agent_waveform
from digital_ic_agent._runtime import agent_workflow as workflow
from digital_ic_agent._runtime import target_checks
from digital_ic_agent._runtime.adapters.report import (
    render_target_design_spec as adapter_render_target_design_spec,
    render_target_verification_plan as adapter_render_target_verification_plan,
    target_scenario_catalog as adapter_target_scenario_catalog,
    target_spec_catalog as adapter_target_spec_catalog,
    write_target_design_spec as adapter_write_target_design_spec,
    write_target_verification_plan as adapter_write_target_verification_plan,
)
from digital_ic_agent._runtime.adapters.vivado import launch_vivado_gui as adapter_launch_vivado_gui
from digital_ic_agent._runtime.adapters.vivado import resolve_vivado_command as adapter_resolve_vivado_command
from digital_ic_agent._runtime.adapters.vivado import run_vivado_batch as adapter_run_vivado_batch
from digital_ic_agent._runtime.adapters.waveform import (
    run_rwave_batch_json as adapter_run_rwave_batch_json,
    run_rwave_json as adapter_run_rwave_json,
    run_vcd_analyzer_json as adapter_run_vcd_analyzer_json,
    run_waveform_analyzer_json as adapter_run_waveform_analyzer_json,
)
from digital_ic_agent._runtime.agent_cli import build_requirement, parse_args, parse_seed_list
from digital_ic_agent._runtime.agent_composition import build_agent
from digital_ic_agent._runtime.agent_config import load_agent_config, normalize_configured_command
from digital_ic_agent._runtime.agent_contracts import AgentRequest, AgentRun, AgentRunStatus
from digital_ic_agent._runtime.agent_design_spec import (
    build_default_project_slug as _build_default_project_slug,
    render_default_design_spec,
    write_default_design_spec,
)
from digital_ic_agent._runtime.agent_diagnostics import run_agent_diagnostic
from digital_ic_agent._runtime.agent_entrypoint import run_cli
from digital_ic_agent._runtime.agent_execution import AgentExecutionEngine, ToolHandler
from digital_ic_agent._runtime.agent_errors import ConfigurationError
from digital_ic_agent._runtime.agent_provider import AgentProvider, ConfiguredAgentProvider
from digital_ic_agent._runtime.agent_reports import render_markdown_document_html as render_markdown_html_document
from digital_ic_agent._runtime.agent_runtime import CommandRunner, TargetHandler
from digital_ic_agent._runtime.agent_sim_smoke import CommandRunnerLike
from digital_ic_agent._runtime.agent_sim_smoke import run_sim_smoke as run_sim_smoke_flow
from digital_ic_agent._runtime.agent_skill_tool import SkillExecutionTool
from digital_ic_agent._runtime.agent_waveform import analyze_waveform as analyze_waveform_flow
from digital_ic_agent._runtime.artifact_manifest import extract_tool_version, snapshot_project_artifacts
from digital_ic_agent._runtime.capability_preflight import (
    FlowPreflight,
    PreflightReport,
    PreflightStatus,
    build_default_preflight,
)
from digital_ic_agent._runtime.coverage_closure import write_coverage_closure_report as build_coverage_closure_report
from digital_ic_agent._runtime.coverage_gates import (
    COVERAGE_METRIC_LABELS,
    COVERAGE_METRIC_ORDER,
    evaluate_coverage_gates,
)
from digital_ic_agent._runtime.coverage_history import append_coverage_history
from digital_ic_agent._runtime.environment_report import write_environment_report as build_environment_report
from digital_ic_agent._runtime.failure_archive import archive_failed_run
from digital_ic_agent._runtime.intent_router import analyze_requirement as route_requirement
from digital_ic_agent._runtime.project_overview import (
    write_project_overview as build_project_overview,
    write_target_dashboard as build_target_dashboard,
)
from digital_ic_agent._runtime.skill_runtime import (
    DeterministicSkillExecutor,
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillExecutor,
    SkillHandler,
    SkillLoader,
    SkillResultValidator,
    ToolRunRecord,
)
from digital_ic_agent._runtime.target_flows import (
    build_target_registry as build_target_registry_operation,
    build_target_handlers as build_registered_target_handlers,
    get_target as get_target_operation,
    list_targets as list_targets_operation,
    load_target_registry as load_target_registry_operation,
    print_targets as print_targets_operation,
    run_target_flow as run_target_flow_operation,
    validate_target_handlers as validate_target_handlers_operation,
)
from digital_ic_agent._runtime.target_registry import (
    get_target as get_registered_target,
    list_targets as list_registered_targets,
    load_target_registry as load_registered_targets,
)
from digital_ic_agent._runtime.target_scaffolder import create_target_scaffold as build_target_scaffold
from digital_ic_agent._runtime.target_service_host import TargetServiceHost
from digital_ic_agent._runtime.wave_visibility import (
    evaluate_wave_open_check,
    render_wave_open_probe_tcl,
    render_window_capture_script,
)
from digital_ic_agent._runtime.waveform_samples import write_waveform_sample_report as build_waveform_sample_report


PathLike = str | os.PathLike[str]
MaybeText = str | None


class AgentCommandRunner(CommandRunnerLike, Protocol):
    def cleanup(self, *, include_preserved: bool = False) -> None: ...


subprocess = capabilities.subprocess
get_vcd_analyzer_path = agent_waveform.resolve_vcd_analyzer_path
get_rwave_source_dir = agent_waveform.resolve_rwave_source_dir
get_rwave_command = agent_waveform.resolve_rwave_command
run_rtl_project_checks = target_checks.check_rtl_project
shutil = runtime_facades.shutil


def _configure_text_stream(stream: object) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    with suppress(OSError, ValueError):
        reconfigure(encoding="utf-8", errors="replace", write_through=True)


_configure_text_stream(sys.stdout)
_configure_text_stream(sys.stderr)


class DigitalICAgent:
    def __init__(
        self,
        config_path: PathLike | None = None,
        command_runner: AgentCommandRunner | None = None,
        skill_executor: SkillExecutor | None = None,
        preflight: FlowPreflight | None = None,
        agent_provider: AgentProvider | None = None,
        agent_tools: Mapping[str, ToolHandler] | None = None,
    ) -> None:
        self.base_dir = Path(__file__).resolve().parent
        package_dir = self.base_dir.parent
        source_trae_dir = package_dir.parents[1] / ".trae"
        self.trae_dir = package_dir if (package_dir / "skills").is_dir() else source_trae_dir
        self.project_root = self.trae_dir.parent
        self.command_runner: AgentCommandRunner = command_runner or CommandRunner()
        self.vivado_timeout = int(os.environ.get("VIVADO_TIMEOUT_SECONDS", "1800"))
        self.config_path = Path(config_path) if config_path else self.base_dir / "agent.json"
        self.agent_config = self.load_config()
        self.skill_mapping = {skill["name"]: skill for skill in self.agent_config["skills"]}
        self.skill_loader = SkillLoader(self.trae_dir)
        self.loaded_skills = self.skill_loader.load_many(self.agent_config["skills"])
        self.preflight = preflight or build_default_preflight()
        self.skill_result_validator = SkillResultValidator()
        self.skill_executor = skill_executor or DeterministicSkillExecutor(
            self.build_skill_action_handlers(),
            validator=self.skill_result_validator,
        )
        self.agent_provider = agent_provider or ConfiguredAgentProvider(self.agent_config["skills"])
        skill_tool = SkillExecutionTool(self)
        default_agent_tools = {
            "skill:{}".format(skill.action): skill_tool for skill in self.loaded_skills.values()
        }
        self.agent_execution_engine = AgentExecutionEngine(
            self.agent_provider,
            default_agent_tools if agent_tools is None else agent_tools,
        )
        self.last_agent_run: AgentRun | None = None
        self.mcp_servers = self.agent_config["mcpServers"]
        self.cli_tools = self.agent_config["cliTools"]
        self.targets_dir = self.base_dir / "targets"
        self.targets = self.load_target_registry()
        self.target_services = TargetServiceHost(self)
        self.target_handlers = self.build_target_handlers()
        self.validate_target_handlers()
        self.OK = "[OK]"
        self.NO = "[NO]"
        self.WARN = "[WARN]"

    def close(self) -> None:
        self.command_runner.cleanup()

    def __enter__(self) -> "DigitalICAgent":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def build_skill_action_handlers(self) -> Mapping[str, SkillHandler]:
        return skill_execution.build_skill_action_handlers(self)

    @staticmethod
    def _skill_result(
        request: SkillExecutionRequest,
        status: SkillExecutionStatus,
        artifacts: Sequence[PathLike],
        message: str,
        failure_reason: str | None = None,
        diagnostics: Sequence[str] = (),
        tool_runs: Sequence[ToolRunRecord] = (),
    ) -> SkillExecutionResult:
        return skill_execution.skill_result(
            request,
            status,
            artifacts,
            message,
            failure_reason=failure_reason,
            diagnostics=diagnostics,
            tool_runs=tool_runs,
        )

    def execute_design_document_skill(
        self,
        request: SkillExecutionRequest,
    ) -> SkillExecutionResult:
        return skill_execution.execute_design_document_skill(self, request)

    def execute_rtl_implementation_skill(
        self,
        request: SkillExecutionRequest,
    ) -> SkillExecutionResult:
        return skill_execution.execute_rtl_implementation_skill(self, request)

    def execute_verification_plan_skill(
        self,
        request: SkillExecutionRequest,
    ) -> SkillExecutionResult:
        return skill_execution.execute_verification_plan_skill(self, request)

    def check_capability(self, capability: str) -> bool:
        return bool(capabilities.check_capability(self, capability))

    def run_preflight(self, flow: str) -> PreflightReport:
        return cast(PreflightReport, capabilities.run_preflight(self, flow))

    def load_config(self) -> Any:
        """加载Agent配置文件。"""
        try:
            return load_agent_config(self.config_path)
        except (OSError, ValueError) as exc:
            raise ConfigurationError(
                "Agent configuration could not be loaded",
                details={
                    "config_path": str(self.config_path),
                    "reason": str(exc),
                },
            ) from exc

    def normalize_command(self, command: Any) -> Any:
        """将配置中的命令转换为可执行参数列表。"""
        return capabilities.normalize_command(self, command)

    def check_cli_tool(self, tool_name: Any, check_command: Any) -> Any:
        """检查CLI工具是否安装。"""
        return capabilities.check_cli_tool(self, tool_name, check_command)

    def check_mcp_server(self, mcp_name: Any) -> Any:
        """检查MCP服务器是否可用。"""
        return capabilities.check_mcp_server(self, mcp_name)

    def analyze_requirement(self, user_input: Any) -> Any:
        """分析用户需求，匹配技能。"""
        return route_requirement(self.agent_config["skills"], user_input)

    def get_install_guide(self, tool_type: Any, tool_name: Any) -> Any:
        """获取工具安装指南。"""
        return capabilities.get_install_guide(self, tool_type, tool_name)

    def build_target_registry(self) -> Any:
        return build_target_registry_operation(self)

    def load_target_registry(self, targets_dir: Any = None) -> Any:
        return load_target_registry_operation(self, targets_dir)

    def list_targets(self) -> Any:
        return list_targets_operation(self)

    def get_target(self, target: Any) -> Any:
        return get_target_operation(self, target)

    def print_targets(self) -> Any:
        return print_targets_operation(self)

    def build_target_handlers(self) -> Any:
        return build_registered_target_handlers(self)

    def validate_target_handlers(self) -> Any:
        return validate_target_handlers_operation(self)

    def run_target_flow(self, target: Any, flow: Any, **kwargs: Any) -> Any:
        return run_target_flow_operation(self, target, flow, **kwargs)

    def resolve_skill_path(self, skill: Any) -> Any:
        """解析技能文件路径。"""
        return skill_listing.resolve_skill_path(self, skill)

    def run_diagnostic(self, flow: Any = None) -> Any:
        """运行环境诊断。"""
        return run_agent_diagnostic(self, flow=flow)

    def list_skills(self) -> Any:
        """列出当前配置的技能。"""
        return skill_listing.list_skills(self)

    def recommend_skills(self, user_input: Any) -> Any:
        """推荐合适的技能。"""
        return skill_listing.recommend_skills(self, user_input)

    def build_project_slug(self, user_input: Any) -> Any:
        """根据用户需求生成项目目录名。"""
        return document_facades.build_project_slug(self, user_input)

    def render_design_spec(self, user_input: Any, matched_skills: Any) -> Any:
        """渲染设计规格文档。"""
        return document_facades.render_design_spec(self, user_input, matched_skills)

    def generate_design_spec(self, user_input: Any, matched_skills: Any, output_dir: Any) -> Any:
        """生成 Markdown 设计规格文档。"""
        return document_facades.generate_design_spec(self, user_input, matched_skills, output_dir)

    target_spec_catalog = adapter_target_spec_catalog
    target_scenario_catalog = adapter_target_scenario_catalog
    _default_project_slug_builder = staticmethod(_build_default_project_slug)
    _default_design_spec_renderer = staticmethod(render_default_design_spec)
    _default_design_spec_writer = staticmethod(write_default_design_spec)
    _markdown_document_html_renderer = staticmethod(render_markdown_html_document)

    def render_markdown_document_html(
        self, title: Any, markdown_text: Any, variant: Any = "doc"
    ) -> Any:
        return document_facades.render_markdown_document_html(
            self,
            title,
            markdown_text,
            variant=variant,
        )

    render_target_design_spec = adapter_render_target_design_spec
    write_target_design_spec = adapter_write_target_design_spec
    render_target_verification_plan = adapter_render_target_verification_plan
    write_target_verification_plan = adapter_write_target_verification_plan
    create_target_scaffold = build_target_scaffold
    write_environment_report = build_environment_report
    write_project_overview = build_project_overview
    write_target_dashboard = build_target_dashboard
    write_waveform_sample_report = build_waveform_sample_report
    write_coverage_closure_report = build_coverage_closure_report

    def refresh_project_overview(self, output_dir: PathLike = "outputs") -> Any:
        return runtime_facades.refresh_project_overview(self, output_dir)

    def record_artifact_run(self, *args: object, **kwargs: object) -> Any:
        return runtime_facades.record_artifact_run(self, *args, **kwargs)

    def resolve_vcd_analyzer_path(self) -> Path:
        return runtime_facades.resolve_vcd_analyzer_path(self)

    def resolve_rwave_source_dir(self) -> Path | None:
        return runtime_facades.resolve_rwave_source_dir(self)

    def resolve_rwave_command(self) -> str | None:
        return runtime_facades.resolve_rwave_command(self)

    run_rwave_json = adapter_run_rwave_json
    run_rwave_batch_json = adapter_run_rwave_batch_json
    run_vcd_analyzer_json = adapter_run_vcd_analyzer_json
    run_waveform_analyzer_json = adapter_run_waveform_analyzer_json

    def analyze_waveform(
        self,
        waveform_path: PathLike,
        condition: MaybeText = None,
        show: MaybeText = None,
        limit: int = 20,
        waveform_backend: str = "auto",
        report_title: str = "波形分析报告",
    ) -> Any:
        return runtime_facades.analyze_waveform(
            self,
            waveform_path,
            condition,
            show,
            limit,
            waveform_backend,
            report_title,
        )

    def analyze_vcd(
        self,
        vcd_path: PathLike,
        condition: MaybeText = None,
        show: MaybeText = None,
        limit: int = 20,
        waveform_backend: str = "auto",
    ) -> Any:
        return runtime_facades.analyze_vcd(self, vcd_path, condition, show, limit, waveform_backend)

    def check_rtl_project(
        self,
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
        return runtime_facades.check_rtl_project(
            self,
            target_name,
            output_dir,
            rtl_name,
            tb_name,
            sim_script_name,
            project_script_name,
            gui_script_name,
            xpr_name,
            vcd_name,
            wave_db_resolver,
            rtl_markers,
            tb_markers,
        )

    def open_rtl_wave(self, target: str, output_dir: PathLike = "outputs") -> Any:
        return runtime_facades.open_rtl_wave(self, target, output_dir=output_dir)

    def write_smoke_loop_vcd(self, output_dir: PathLike) -> Path:
        return runtime_facades.write_smoke_loop_vcd(self, output_dir)

    def run_smoke_loop(
        self, output_dir: PathLike = "outputs", limit: int = 20, waveform_backend: str = "auto"
    ) -> bool:
        return runtime_facades.run_smoke_loop(self, output_dir, limit, waveform_backend)

    def detect_simulator(self) -> str | None:
        return runtime_facades.detect_simulator(self)

    resolve_vivado_command = adapter_resolve_vivado_command
    run_vivado_batch = adapter_run_vivado_batch
    launch_vivado_gui = adapter_launch_vivado_gui

    def write_sim_smoke_sources(self, output_dir: PathLike) -> tuple[Path, Path, Path, Path]:
        return runtime_facades.write_sim_smoke_sources(self, output_dir)

    def run_icarus_sim_smoke(
        self, output_dir: PathLike, limit: int = 20, waveform_backend: str = "auto"
    ) -> bool:
        return runtime_facades.run_icarus_sim_smoke(self, output_dir, limit, waveform_backend)

    def write_vivado_sim_script(
        self, sim_dir: PathLike, rtl_path: PathLike, tb_path: PathLike, vcd_path: PathLike
    ) -> Path:
        return runtime_facades.write_vivado_sim_script(self, sim_dir, rtl_path, tb_path, vcd_path)

    def open_vivado_wave_gui(self, sim_dir: PathLike, vcd_path: PathLike) -> bool:
        return runtime_facades.open_vivado_wave_gui(self, sim_dir, vcd_path)

    def run_vivado_sim_smoke(
        self,
        output_dir: PathLike,
        limit: int = 20,
        open_wave_gui: bool = True,
        waveform_backend: str = "auto",
    ) -> bool:
        return runtime_facades.run_vivado_sim_smoke(
            self,
            output_dir,
            limit,
            open_wave_gui,
            waveform_backend,
        )

    def run_sim_smoke(
        self,
        output_dir: PathLike = "outputs",
        limit: int = 20,
        open_wave_gui: bool = True,
        waveform_backend: str = "auto",
    ) -> bool:
        return runtime_facades.run_sim_smoke(self, output_dir, limit, open_wave_gui, waveform_backend)

    def normalize_rtl_target(self, target: str) -> str:
        return runtime_facades.normalize_rtl_target(self, target)

    def render_vivado_tclstore_bootstrap(self) -> str:
        return runtime_facades.render_vivado_tclstore_bootstrap(self)

    def generate_rtl_project(
        self, target: str, output_dir: PathLike = "outputs", data_width: int = 8, addr_width: int = 4
    ) -> Any:
        return runtime_facades.generate_rtl_project(
            self,
            target,
            output_dir=output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )

    def run_rtl_sim(
        self, target: str, output_dir: PathLike = "outputs", open_wave_gui: bool = True
    ) -> Any:
        return runtime_facades.run_rtl_sim(
            self,
            target,
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        )

    def run_uvm_smoke(
        self, target: str, output_dir: PathLike = "outputs", open_wave_gui: bool = True
    ) -> Any:
        return runtime_facades.run_uvm_smoke(
            self,
            target,
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        )

    def run_uvm_coverage(
        self,
        target: str,
        output_dir: PathLike = "outputs",
        coverage_threshold: float | None = None,
        coverage_percent: float | None = None,
        coverage_thresholds: Mapping[str, float] | None = None,
    ) -> Any:
        return runtime_facades.run_uvm_coverage(
            self,
            target,
            output_dir=output_dir,
            coverage_threshold=coverage_threshold,
            coverage_percent=coverage_percent,
            coverage_thresholds=coverage_thresholds,
        )

    def run_uvm_random_regression(
        self, target: str, output_dir: PathLike = "outputs", seeds: Sequence[int] | None = None
    ) -> Any:
        return runtime_facades.run_uvm_random_regression(self, target, output_dir=output_dir, seeds=seeds)

    def open_uvm_wave(
        self, target: str, output_dir: PathLike = "outputs", wave_kind: str = "coverage"
    ) -> Any:
        return runtime_facades.open_uvm_wave(self, target, output_dir=output_dir, wave_kind=wave_kind)

    def regress_rtl(
        self, target: str, output_dir: PathLike = "outputs", open_wave_gui: bool = False
    ) -> Any:
        return runtime_facades.regress_rtl(
            self,
            target,
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        )

    def execute_workflow(
        self,
        user_input: str,
        output_dir: PathLike = "outputs",
        skip_tool_check: bool = False,
    ) -> bool:
        """执行完整工作流。"""
        return workflow.execute_workflow(
            cast(workflow.WorkflowAgent, self),
            user_input,
            output_dir=output_dir,
            skip_tool_check=skip_tool_check,
        )


legacy_target_facades.install_legacy_target_facades(DigitalICAgent)


def create_agent() -> Any:
    return build_agent(DigitalICAgent)


def main(argv: Any = None) -> Any:
    agent = create_agent()
    if agent is None:
        return 1
    with agent:
        return run_cli(argv, lambda: agent)


if __name__ == "__main__":
    sys.exit(main())
