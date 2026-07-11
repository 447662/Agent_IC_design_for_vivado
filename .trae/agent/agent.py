#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Script Name: agent.py
# Description: 数字IC前端设计Agent主入口
#              智能分析用户需求，匹配合适的技能，检查工具环境，生成设计文档模板
# Author: Digital IC Designer Team
# Date: 2026-05-15
# -----------------------------------------------------------------------------

from typing import Any
import importlib.util
import hashlib
import html
import json
import os
import sys
from pathlib import Path
from uuid import uuid4


AGENT_MODULE_DIR = Path(__file__).resolve().parent


def _load_bootstrap_module() -> Any:
    module_name = "agent_bootstrap"
    if module_name in sys.modules:
        return sys.modules[module_name]
    module_path = AGENT_MODULE_DIR / "agent_bootstrap.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load local agent bootstrap: {}".format(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


load_local_modules = _load_bootstrap_module().load_local_modules
load_local_modules(AGENT_MODULE_DIR)

from agent_runtime import (
    CommandRunner,
    TargetHandler,
)
from agent_contracts import AgentRequest, AgentRun, AgentRunStatus
from agent_execution import AgentExecutionEngine
from agent_provider import ConfiguredAgentProvider
from agent_skill_tool import SkillExecutionTool
from agent_skill_execution import (
    build_skill_action_handlers as build_skill_action_handlers_operation,
    execute_design_document_skill as execute_design_document_skill_operation,
    execute_rtl_implementation_skill as execute_rtl_implementation_skill_operation,
    execute_verification_plan_skill as execute_verification_plan_skill_operation,
    skill_result as skill_result_operation,
    write_skill_execution_brief as write_skill_execution_brief_operation,
)
from agent_cli import build_requirement, parse_args, parse_seed_list
from agent_composition import build_agent
from agent_config import load_agent_config, normalize_configured_command
from agent_entrypoint import run_cli
from agent_capabilities import (
    check_capability as check_capability_operation,
    check_cli_tool as check_cli_tool_operation,
    check_mcp_server as check_mcp_server_operation,
    get_install_guide as get_install_guide_operation,
    normalize_command as normalize_command_operation,
    run_preflight as run_preflight_operation,
)
from agent_capabilities import subprocess as _capability_subprocess
from agent_design_spec import (
    build_default_project_slug as _build_default_project_slug,
    render_default_design_spec,
    write_default_design_spec,
)
from agent_diagnostics import run_agent_diagnostic
from agent_reports import (
    render_markdown_document_html as render_markdown_html_document,
)
from agent_document_facades import (
    build_project_slug as build_project_slug_operation,
    generate_design_spec as generate_design_spec_operation,
    render_design_spec as render_design_spec_operation,
    render_markdown_document_html as render_markdown_document_html_operation,
)
from agent_waveform import (
    analyze_waveform as analyze_waveform_flow,
)
from agent_sim_smoke import (
    run_sim_smoke as run_sim_smoke_flow,
)
from capability_preflight import PreflightStatus, build_default_preflight
from artifact_manifest import (
    extract_tool_version,
    snapshot_project_artifacts,
)
from coverage_closure import (
    write_coverage_closure_report as build_coverage_closure_report,
)
from coverage_gates import (
    COVERAGE_METRIC_LABELS,
    COVERAGE_METRIC_ORDER,
    evaluate_coverage_gates,
)
from coverage_history import append_coverage_history
from environment_report import write_environment_report as build_environment_report
from failure_archive import archive_failed_run
from intent_router import analyze_requirement as route_requirement
from project_overview import (
    write_project_overview as build_project_overview,
    write_target_dashboard as build_target_dashboard,
)
from skill_runtime import (
    DeterministicSkillExecutor,
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillLoader,
    SkillResultValidator,
)
from agent_skill_listing import (
    list_skills as list_skills_operation,
    recommend_skills as recommend_skills_operation,
    resolve_skill_path as resolve_skill_path_operation,
)
from agent_workflow import (
    execute_workflow as execute_workflow_operation,
)
from agent_runtime_facades import (
    analyze_vcd as analyze_vcd_operation,
    analyze_waveform as analyze_waveform_operation,
    check_rtl_project as check_rtl_project_operation,
    detect_simulator as detect_simulator_operation,
    generate_rtl_project as generate_rtl_project_operation,
    normalize_rtl_target as normalize_rtl_target_operation,
    open_rtl_wave as open_rtl_wave_operation,
    open_uvm_wave as open_uvm_wave_operation,
    open_vivado_wave_gui as open_vivado_wave_gui_operation,
    record_artifact_run as record_artifact_run_operation,
    refresh_project_overview as refresh_project_overview_operation,
    regress_rtl as regress_rtl_operation,
    render_vivado_tclstore_bootstrap as render_vivado_tclstore_bootstrap_operation,
    resolve_rwave_command as resolve_rwave_command_operation,
    resolve_rwave_source_dir as resolve_rwave_source_dir_operation,
    resolve_vcd_analyzer_path as resolve_vcd_analyzer_path_operation,
    run_icarus_sim_smoke as run_icarus_sim_smoke_operation,
    run_rtl_sim as run_rtl_sim_operation,
    run_sim_smoke as run_sim_smoke_operation,
    run_smoke_loop as run_smoke_loop_operation,
    run_uvm_coverage as run_uvm_coverage_operation,
    run_uvm_random_regression as run_uvm_random_regression_operation,
    run_uvm_smoke as run_uvm_smoke_operation,
    run_vivado_sim_smoke as run_vivado_sim_smoke_operation,
    write_sim_smoke_sources as write_sim_smoke_sources_operation,
    write_smoke_loop_vcd as write_smoke_loop_vcd_operation,
    write_vivado_sim_script as write_vivado_sim_script_operation,
)
from waveform_samples import write_waveform_sample_report as build_waveform_sample_report
from wave_visibility import (
    evaluate_wave_open_check,
    render_wave_open_probe_tcl,
    render_window_capture_script,
)
from adapters.report import (
    render_target_design_spec as adapter_render_target_design_spec,
    render_target_verification_plan as adapter_render_target_verification_plan,
    target_scenario_catalog as adapter_target_scenario_catalog,
    target_spec_catalog as adapter_target_spec_catalog,
    write_target_design_spec as adapter_write_target_design_spec,
    write_target_verification_plan as adapter_write_target_verification_plan,
)
from adapters.vivado import (
    launch_vivado_gui as adapter_launch_vivado_gui,
    resolve_vivado_command as adapter_resolve_vivado_command,
    run_vivado_batch as adapter_run_vivado_batch,
)
from adapters.waveform import (
    run_rwave_batch_json as adapter_run_rwave_batch_json,
    run_rwave_json as adapter_run_rwave_json,
    run_vcd_analyzer_json as adapter_run_vcd_analyzer_json,
    run_waveform_analyzer_json as adapter_run_waveform_analyzer_json,
)
from target_flows import (
    build_target_registry as build_target_registry_operation,
    build_target_handlers as build_registered_target_handlers,
    get_target as get_target_operation,
    list_targets as list_targets_operation,
    load_target_registry as load_target_registry_operation,
    print_targets as print_targets_operation,
    run_target_flow as run_target_flow_operation,
    validate_target_handlers as validate_target_handlers_operation,
)
from target_registry import (
    get_target as get_registered_target,
    list_targets as list_registered_targets,
    load_target_registry as load_registered_targets,
)
from target_scaffolder import create_target_scaffold as build_target_scaffold
from target_service_host import TargetServiceHost


subprocess = _capability_subprocess


def _configure_text_stream(stream: Any) -> Any:
    try:
        stream.reconfigure(encoding="utf-8", errors="replace", write_through=True)
    except (AttributeError, OSError, ValueError):
        pass


_configure_text_stream(sys.stdout)
_configure_text_stream(sys.stderr)


class DigitalICAgent:
    def __init__(
        self,
        config_path: Any=None,
        command_runner: Any=None,
        skill_executor: Any=None,
        preflight: Any=None,
        agent_provider: Any=None,
        agent_tools: Any=None,
    ) -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.trae_dir = self.base_dir.parent
        self.project_root = self.trae_dir.parent
        self.command_runner = command_runner or CommandRunner()
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
        self.agent_provider = agent_provider or ConfiguredAgentProvider(
            self.agent_config["skills"]
        )
        skill_tool = SkillExecutionTool(self)
        default_agent_tools = {
            "skill:{}".format(skill.action): skill_tool
            for skill in self.loaded_skills.values()
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
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:
        self.close()

    def build_skill_action_handlers(self) -> Any:
        return build_skill_action_handlers_operation(self)

    @staticmethod
    def _skill_result(
        request: Any,
        status: Any,
        artifacts: Any,
        message: Any,
        failure_reason: Any=None,
        diagnostics: Any=(),
        tool_runs: Any=(),
    ) -> Any:
        return skill_result_operation(
            request,
            status,
            artifacts,
            message,
            failure_reason=failure_reason,
            diagnostics=diagnostics,
            tool_runs=tool_runs,
        )

    def execute_design_document_skill(self, request: Any) -> Any:
        return execute_design_document_skill_operation(self, request)

    def _write_skill_execution_brief(self, request: Any, filename: Any, heading: Any) -> Any:
        return write_skill_execution_brief_operation(self, request, filename, heading)

    def execute_rtl_implementation_skill(self, request: Any) -> Any:
        return execute_rtl_implementation_skill_operation(self, request)

    def execute_verification_plan_skill(self, request: Any) -> Any:
        return execute_verification_plan_skill_operation(self, request)

    def check_capability(self, capability: Any) -> Any:
        return check_capability_operation(self, capability)

    def run_preflight(self, flow: Any) -> Any:
        return run_preflight_operation(self, flow)

    def load_config(self) -> Any:
        """加载Agent配置文件。"""
        return load_agent_config(self.config_path)

    def normalize_command(self, command: Any) -> Any:
        """将配置中的命令转换为可执行参数列表。"""
        return normalize_command_operation(self, command)

    def check_cli_tool(self, tool_name: Any, check_command: Any) -> Any:
        """检查CLI工具是否安装。"""
        return check_cli_tool_operation(self, tool_name, check_command)

    def check_mcp_server(self, mcp_name: Any) -> Any:
        """检查MCP服务器是否可用。"""
        return check_mcp_server_operation(self, mcp_name)

    def analyze_requirement(self, user_input: Any) -> Any:
        """分析用户需求，匹配技能。"""
        return route_requirement(self.agent_config["skills"], user_input)

    def get_install_guide(self, tool_type: Any, tool_name: Any) -> Any:
        """获取工具安装指南。"""
        return get_install_guide_operation(self, tool_type, tool_name)

    def build_target_registry(self) -> Any:
        return build_target_registry_operation(self)

    def load_target_registry(self, targets_dir: Any=None) -> Any:
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
        return resolve_skill_path_operation(self, skill)

    def run_diagnostic(self, flow: Any=None) -> Any:
        """???????"""
        return run_agent_diagnostic(self, flow=flow)

    def list_skills(self) -> Any:
        """列出当前配置的技能。"""
        return list_skills_operation(self)

    def recommend_skills(self, user_input: Any) -> Any:
        """推荐合适的技能。"""
        return recommend_skills_operation(self, user_input)

    def build_project_slug(self, user_input: Any) -> Any:
        """?????????????????"""
        return build_project_slug_operation(self, user_input)

    def render_design_spec(self, user_input: Any, matched_skills: Any) -> Any:
        """???????????"""
        return render_design_spec_operation(self, user_input, matched_skills)

    def generate_design_spec(self, user_input: Any, matched_skills: Any, output_dir: Any) -> Any:
        """?? Markdown ???????"""
        return generate_design_spec_operation(self, user_input, matched_skills, output_dir)

    target_spec_catalog = adapter_target_spec_catalog
    target_scenario_catalog = adapter_target_scenario_catalog
    _default_project_slug_builder = staticmethod(_build_default_project_slug)
    _default_design_spec_renderer = staticmethod(render_default_design_spec)
    _default_design_spec_writer = staticmethod(write_default_design_spec)
    _markdown_document_html_renderer = staticmethod(render_markdown_html_document)

    def render_markdown_document_html(self, title: Any, markdown_text: Any, variant: Any="doc") -> Any:
        return render_markdown_document_html_operation(
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

    def refresh_project_overview(self, output_dir: Any="outputs") -> Any:
        return refresh_project_overview_operation(self, output_dir)

    def record_artifact_run(self, *args: Any, **kwargs: Any) -> Any:
        return record_artifact_run_operation(self, *args, **kwargs)

    def resolve_vcd_analyzer_path(self) -> Any:
        return resolve_vcd_analyzer_path_operation(self)

    def resolve_rwave_source_dir(self) -> Any:
        return resolve_rwave_source_dir_operation(self)

    def resolve_rwave_command(self) -> Any:
        return resolve_rwave_command_operation(self)

    run_rwave_json = adapter_run_rwave_json
    run_rwave_batch_json = adapter_run_rwave_batch_json
    run_vcd_analyzer_json = adapter_run_vcd_analyzer_json
    run_waveform_analyzer_json = adapter_run_waveform_analyzer_json

    def analyze_waveform(
        self,
        waveform_path: Any,
        condition: Any=None,
        show: Any=None,
        limit: Any=20,
        waveform_backend: Any="auto",
        report_title: Any="波形分析报告",
    ) -> Any:
        return analyze_waveform_operation(
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
        vcd_path: Any,
        condition: Any=None,
        show: Any=None,
        limit: Any=20,
        waveform_backend: Any="auto",
    ) -> Any:
        return analyze_vcd_operation(self, vcd_path, condition, show, limit, waveform_backend)

    def check_rtl_project(
        self,
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
        return check_rtl_project_operation(
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




    def open_rtl_wave(self, target: Any, output_dir: Any="outputs") -> Any:
        return open_rtl_wave_operation(self, target, output_dir=output_dir)

    def write_smoke_loop_vcd(self, output_dir: Any) -> Any:
        return write_smoke_loop_vcd_operation(self, output_dir)

    def run_smoke_loop(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
        return run_smoke_loop_operation(self, output_dir, limit, waveform_backend)

    def detect_simulator(self) -> Any:
        return detect_simulator_operation(self)

    resolve_vivado_command = adapter_resolve_vivado_command
    run_vivado_batch = adapter_run_vivado_batch
    launch_vivado_gui = adapter_launch_vivado_gui

    def write_sim_smoke_sources(self, output_dir: Any) -> Any:
        return write_sim_smoke_sources_operation(self, output_dir)

    def run_icarus_sim_smoke(self, output_dir: Any, limit: Any=20, waveform_backend: Any="auto") -> Any:
        return run_icarus_sim_smoke_operation(self, output_dir, limit, waveform_backend)

    def write_vivado_sim_script(self, sim_dir: Any, rtl_path: Any, tb_path: Any, vcd_path: Any) -> Any:
        return write_vivado_sim_script_operation(self, sim_dir, rtl_path, tb_path, vcd_path)

    def open_vivado_wave_gui(self, sim_dir: Any, vcd_path: Any) -> Any:
        return open_vivado_wave_gui_operation(self, sim_dir, vcd_path)

    def run_vivado_sim_smoke(self, output_dir: Any, limit: Any=20, open_wave_gui: Any=True, waveform_backend: Any="auto") -> Any:
        return run_vivado_sim_smoke_operation(
            self,
            output_dir,
            limit,
            open_wave_gui,
            waveform_backend,
        )

    def run_sim_smoke(self, output_dir: Any="outputs", limit: Any=20, open_wave_gui: Any=True, waveform_backend: Any="auto") -> Any:
        return run_sim_smoke_operation(self, output_dir, limit, open_wave_gui, waveform_backend)

    def normalize_rtl_target(self, target: Any) -> Any:
        return normalize_rtl_target_operation(self, target)




    def render_vivado_tclstore_bootstrap(self) -> Any:
        return render_vivado_tclstore_bootstrap_operation(self)





    def generate_rtl_project(self, target: Any, output_dir: Any="outputs", data_width: Any=8, addr_width: Any=4) -> Any:
        return generate_rtl_project_operation(
            self,
            target,
            output_dir=output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )































    def run_rtl_sim(self, target: Any, output_dir: Any="outputs", open_wave_gui: Any=True) -> Any:
        return run_rtl_sim_operation(
            self,
            target,
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        )

    def run_uvm_smoke(self, target: Any, output_dir: Any="outputs", open_wave_gui: Any=True) -> Any:
        return run_uvm_smoke_operation(
            self,
            target,
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        )

    def run_uvm_coverage(
        self,
        target: Any,
        output_dir: Any="outputs",
        coverage_threshold: Any=None,
        coverage_percent: Any=None,
        coverage_thresholds: Any=None,
    ) -> Any:
        return run_uvm_coverage_operation(
            self,
            target,
            output_dir=output_dir,
            coverage_threshold=coverage_threshold,
            coverage_percent=coverage_percent,
            coverage_thresholds=coverage_thresholds,
        )

    def run_uvm_random_regression(self, target: Any, output_dir: Any="outputs", seeds: Any=None) -> Any:
        return run_uvm_random_regression_operation(self, target, output_dir=output_dir, seeds=seeds)

    def open_uvm_wave(self, target: Any, output_dir: Any="outputs", wave_kind: Any="coverage") -> Any:
        return open_uvm_wave_operation(self, target, output_dir=output_dir, wave_kind=wave_kind)

    def regress_rtl(self, target: Any, output_dir: Any="outputs", open_wave_gui: Any=False) -> Any:
        return regress_rtl_operation(
            self,
            target,
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        )

    def execute_workflow(self, user_input: Any, output_dir: Any="outputs", skip_tool_check: Any=False) -> Any:
        """执行完整工作流。"""
        return execute_workflow_operation(
            self,
            user_input,
            output_dir=output_dir,
            skip_tool_check=skip_tool_check,
        )


def create_agent() -> Any:
    return build_agent(DigitalICAgent)


def main(argv: Any=None) -> Any:
    agent = create_agent()
    if agent is None:
        return 1
    with agent:
        return run_cli(argv, lambda: agent)


if __name__ == "__main__":
    sys.exit(main())
