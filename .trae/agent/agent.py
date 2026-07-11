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
import re
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


AGENT_MODULE_DIR = Path(__file__).resolve().parent


def _load_local_module(module_name: str, relative_path: str | None = None) -> None:
    if module_name in sys.modules:
        return
    module_path = AGENT_MODULE_DIR / (relative_path or "{}.py".format(module_name))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load local agent module: {}".format(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


for _local_module_name in (
    "history_rotation",
    "agent_contracts",
    "intent_router",
    "mcp_client",
    "agent_runtime",
    "agent_provider",
    "agent_execution",
    "skill_runtime",
    "agent_skill_tool",
    "agent_skill_listing",
    "agent_cli_parser",
    "agent_cli",
    "agent_cli_dispatch",
    "agent_design_spec",
    "capability_preflight",
    "agent_diagnostics",
    "agent_composition",
    "agent_config",
    "agent_entrypoint",
    "report_templates",
    "agent_reports",
    "agent_waveform",
    "agent_sim_smoke",
    "coverage_gates",
    "artifact_manifest",
    "xcrg_coverage",
    "coverage_recommendations",
    "coverage_closure",
    "coverage_history",
    "environment_report",
    "failure_archive",
    "intent_router",
    "project_overview",
    "skill_runtime",
    "waveform_samples",
    "wave_visibility",
    "target_checks",
    "target_plugins",
    "target_registry",
    "target_scaffolder",
    "agent_sync_fifo",
    "agent_round_robin_arbiter",
    "agent_async_fifo_render",
    "agent_async_fifo_reports",
    "agent_async_fifo_runtime",
    "target_service_host",
    "target_flows",
):
    _load_local_module(_local_module_name)
for _adapter_module_name in ("report", "vivado", "waveform"):
    _load_local_module(
        "adapters.{}".format(_adapter_module_name),
        "adapters/{}.py".format(_adapter_module_name),
    )
_load_local_module("target_examples.async_fifo", "target_examples/async_fifo.py")
for _handler_module_name in ("async_fifo", "round_robin_arbiter", "sync_fifo"):
    _load_local_module(
        "target_handlers.{}".format(_handler_module_name),
        "target_handlers/{}.py".format(_handler_module_name),
    )

from agent_runtime import (
    CommandRunner,
    TargetHandler,
)
from agent_contracts import AgentRequest, AgentRun, AgentRunStatus
from agent_execution import AgentExecutionEngine
from agent_provider import ConfiguredAgentProvider
from agent_skill_tool import SkillExecutionTool
from agent_cli import build_requirement, parse_args, parse_seed_list
from agent_composition import build_agent
from agent_config import load_agent_config, normalize_configured_command
from agent_entrypoint import run_cli
from agent_design_spec import (
    build_default_project_slug as _build_default_project_slug,
    render_default_design_spec,
    write_default_design_spec,
)
from agent_diagnostics import run_agent_diagnostic
from agent_reports import (
    render_markdown_document_html as render_markdown_html_document,
)
from agent_waveform import (
    analyze_vcd as analyze_vcd_flow,
    analyze_waveform as analyze_waveform_flow,
    resolve_rwave_command as get_rwave_command,
    resolve_rwave_source_dir as get_rwave_source_dir,
    resolve_vcd_analyzer_path as get_vcd_analyzer_path,
)
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
from capability_preflight import PreflightStatus, build_default_preflight
from artifact_manifest import (
    extract_tool_version,
    record_artifact_run as append_artifact_run,
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
from target_checks import check_rtl_project as run_rtl_project_checks
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
        return {
            "design-document": self.execute_design_document_skill,
            "rtl-implementation": self.execute_rtl_implementation_skill,
            "verification-plan": self.execute_verification_plan_skill,
        }

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
        return SkillExecutionResult(
            skill_name=request.skill.name,
            action=request.skill.action,
            status=status,
            artifacts=tuple(Path(path) for path in artifacts),
            diagnostics=tuple(str(item) for item in diagnostics),
            tool_runs=tuple(tool_runs),
            failure_reason=failure_reason,
            message=message,
        )

    def execute_design_document_skill(self, request: Any) -> Any:
        spec_path = Path(request.context["design_spec_path"])
        return self._skill_result(
            request,
            SkillExecutionStatus.SUCCEEDED,
            (spec_path,),
            "Design document skill executed",
        )

    def _write_skill_execution_brief(self, request: Any, filename: Any, heading: Any) -> Any:
        spec_path = Path(request.context["design_spec_path"])
        output_path = request.output_dir / filename
        output_path.write_text(
            """# {heading}

- Skill: `{skill_name}`
- Skill title: {skill_title}
- Skill source: `{skill_path}`
- Skill SHA-256: `{skill_digest}`
- Design specification: `{spec_path}`

## Requirement

{user_input}

## Execution Contract

The deterministic local executor loaded and validated the complete skill file.
The skill content remains the authoritative operating contract for a future
LLM-backed executor; this local executor does not fabricate an LLM result.
""".format(
                heading=heading,
                skill_name=request.skill.name,
                skill_title=request.skill.title,
                skill_path=request.skill.path,
                skill_digest=request.skill.content_digest,
                spec_path=spec_path,
                user_input=request.user_input,
            ),
            encoding="utf-8",
        )
        return output_path

    def execute_rtl_implementation_skill(self, request: Any) -> Any:
        brief_path = self._write_skill_execution_brief(
            request,
            "rtl_implementation_brief.md",
            "RTL Implementation Skill Execution",
        )
        return self._skill_result(
            request,
            SkillExecutionStatus.BLOCKED,
            (Path(request.context["design_spec_path"]), brief_path),
            "RTL implementation was not executed",
            failure_reason=(
                "blocked: No RTL generator and deterministic RTL checker are configured"
            ),
            diagnostics=(
                "The execution brief records the requested contract only.",
            ),
        )

    def execute_verification_plan_skill(self, request: Any) -> Any:
        brief_path = self._write_skill_execution_brief(
            request,
            "verification_execution_brief.md",
            "Verification Skill Execution",
        )
        return self._skill_result(
            request,
            SkillExecutionStatus.BLOCKED,
            (Path(request.context["design_spec_path"]), brief_path),
            "UVM verification was not executed",
            failure_reason="No UVM generator and simulator run are configured",
            diagnostics=(
                "The execution brief is not a verification plan or simulator result.",
            ),
        )

    def check_capability(self, capability: Any) -> Any:
        if capability == "synthpilot":
            return self.check_mcp_server("synthpilot")
        for tool in self.cli_tools:
            if tool["name"] == capability:
                return self.check_cli_tool(tool["name"], tool["checkCommand"])
        return False

    def run_preflight(self, flow: Any) -> Any:
        return self.preflight.evaluate(flow, self.check_capability)

    def load_config(self) -> Any:
        """加载Agent配置文件。"""
        return load_agent_config(self.config_path)

    def normalize_command(self, command: Any) -> Any:
        """将配置中的命令转换为 subprocess 可执行的参数列表。"""
        return normalize_configured_command(command)

    def check_cli_tool(self, tool_name: Any, check_command: Any) -> Any:
        """检查CLI工具是否安装。"""
        try:
            command = self.normalize_command(check_command)
            if tool_name == "vivado" and command and command[0] == "vivado":
                vivado_command = self.resolve_vivado_command()
                if vivado_command:
                    command[0] = vivado_command
            result = self.command_runner.run(command, capture_output=True, text=True, timeout=30, check=False)
            if result.returncode == 0:
                return True
            if tool_name == "vivado":
                version_text = "{}\n{}".format(
                    result.stdout or "",
                    result.stderr or "",
                )
                return bool(
                    re.search(
                        r"\bVivado\s+v?\d{4}\.\d+\b",
                        version_text,
                        re.IGNORECASE,
                    )
                )
            return False
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired, ValueError):
            return False

    def check_mcp_server(self, mcp_name: Any) -> Any:
        """检查MCP服务器是否可用。"""
        mcp = self.mcp_servers.get(mcp_name)
        if not mcp:
            return False

        try:
            command = [mcp["command"], *mcp.get("args", []), "--version"]
            result = self.command_runner.run(command, capture_output=True, text=True, timeout=30, check=False)
            return result.returncode == 0
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return False

    def analyze_requirement(self, user_input: Any) -> Any:
        """分析用户需求，匹配技能。"""
        return route_requirement(self.agent_config["skills"], user_input)

    def get_install_guide(self, tool_type: Any, tool_name: Any) -> Any:
        """获取工具安装指南。"""
        if tool_type == "mcp":
            mcp = self.mcp_servers.get(tool_name)
            return mcp.get("installGuide", "未知") if mcp else "未知"
        if tool_type == "cli":
            for tool in self.cli_tools:
                if tool["name"] == tool_name:
                    return tool.get("installGuide", "未知")
            return "未知"
        return "未知"

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
        return _build_default_project_slug(user_input)

    def render_design_spec(self, user_input: Any, matched_skills: Any) -> Any:
        """???????????"""
        return render_default_design_spec(
            user_input,
            matched_skills,
            self.skill_mapping,
        )

    def generate_design_spec(self, user_input: Any, matched_skills: Any, output_dir: Any) -> Any:
        """?? Markdown ???????"""
        return write_default_design_spec(
            user_input,
            matched_skills,
            output_dir,
            self.skill_mapping,
        )

    target_spec_catalog = adapter_target_spec_catalog
    target_scenario_catalog = adapter_target_scenario_catalog

    def render_markdown_document_html(self, title: Any, markdown_text: Any, variant: Any="doc") -> Any:
        return render_markdown_html_document(
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
        try:
            return self.write_project_overview(output_dir=output_dir)
        except (OSError, ValueError) as exc:
            print("项目总览自动刷新失败: {}".format(exc), file=sys.stderr)
            return None

    def record_artifact_run(self, *args: Any, **kwargs: Any) -> Any:
        manifest_path = append_artifact_run(self, *args, **kwargs)
        output_dir = kwargs.get(
            "output_dir",
            args[2] if len(args) > 2 else "outputs",
        )
        self.refresh_project_overview(output_dir)
        return manifest_path

    def resolve_vcd_analyzer_path(self) -> Any:
        return get_vcd_analyzer_path(self.project_root)

    def resolve_rwave_source_dir(self) -> Any:
        return get_rwave_source_dir(self.project_root)

    def resolve_rwave_command(self) -> Any:
        return get_rwave_command(
            self.project_root,
            env=os.environ,
            which=shutil.which,
            source_dir_resolver=self.resolve_rwave_source_dir,
        )

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
        return analyze_waveform_flow(
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
        return analyze_vcd_flow(self, vcd_path, condition, show, limit, waveform_backend)

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




    def open_rtl_wave(self, target: Any, output_dir: Any="outputs") -> Any:
        return self.run_target_flow(
            target,
            "open-wave",
            output_dir=output_dir,
        )

    def write_smoke_loop_vcd(self, output_dir: Any) -> Any:
        return write_smoke_loop_vcd_flow(output_dir)

    def run_smoke_loop(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
        return run_smoke_loop_flow(self, output_dir, limit, waveform_backend)

    def detect_simulator(self) -> Any:
        return detect_simulator_flow(self)

    resolve_vivado_command = adapter_resolve_vivado_command
    run_vivado_batch = adapter_run_vivado_batch
    launch_vivado_gui = adapter_launch_vivado_gui

    def write_sim_smoke_sources(self, output_dir: Any) -> Any:
        return write_sim_smoke_sources_flow(output_dir)

    def run_icarus_sim_smoke(self, output_dir: Any, limit: Any=20, waveform_backend: Any="auto") -> Any:
        return run_icarus_sim_smoke_flow(self, output_dir, limit, waveform_backend)

    def write_vivado_sim_script(self, sim_dir: Any, rtl_path: Any, tb_path: Any, vcd_path: Any) -> Any:
        return write_vivado_sim_script_flow(sim_dir, rtl_path, tb_path, vcd_path)

    def open_vivado_wave_gui(self, sim_dir: Any, vcd_path: Any) -> Any:
        return open_vivado_wave_gui_flow(self, sim_dir, vcd_path)

    def run_vivado_sim_smoke(self, output_dir: Any, limit: Any=20, open_wave_gui: Any=True, waveform_backend: Any="auto") -> Any:
        return run_vivado_sim_smoke_flow(
            self,
            output_dir,
            limit,
            open_wave_gui,
            waveform_backend,
        )

    def run_sim_smoke(self, output_dir: Any="outputs", limit: Any=20, open_wave_gui: Any=True, waveform_backend: Any="auto") -> Any:
        return run_sim_smoke_flow(self, output_dir, limit, open_wave_gui, waveform_backend)

    def normalize_rtl_target(self, target: Any) -> Any:
        return self.get_target(target)["name"]




    def render_vivado_tclstore_bootstrap(self) -> Any:
        return render_vivado_tclstore_bootstrap_flow()





    def generate_rtl_project(self, target: Any, output_dir: Any="outputs", data_width: Any=8, addr_width: Any=4) -> Any:
        return self.run_target_flow(
            target,
            "generate-rtl",
            output_dir=output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )































    def run_rtl_sim(self, target: Any, output_dir: Any="outputs", open_wave_gui: Any=True) -> Any:
        return self.run_target_flow(
            target,
            "sim-rtl",
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        )

    def run_uvm_smoke(self, target: Any, output_dir: Any="outputs", open_wave_gui: Any=True) -> Any:
        return self.run_target_flow(
            target,
            "uvm-smoke",
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
        return self.run_target_flow(
            target,
            "uvm-coverage",
            output_dir=output_dir,
            coverage_threshold=coverage_threshold,
            coverage_percent=coverage_percent,
            coverage_thresholds=coverage_thresholds,
        )

    def run_uvm_random_regression(self, target: Any, output_dir: Any="outputs", seeds: Any=None) -> Any:
        return self.run_target_flow(
            target,
            "uvm-random-regress",
            output_dir=output_dir,
            seeds=seeds,
        )

    def open_uvm_wave(self, target: Any, output_dir: Any="outputs", wave_kind: Any="coverage") -> Any:
        return self.run_target_flow(
            target,
            "open-uvm-wave",
            output_dir=output_dir,
            wave_kind=wave_kind,
        )

    def regress_rtl(self, target: Any, output_dir: Any="outputs", open_wave_gui: Any=False) -> Any:
        return self.run_target_flow(
            target,
            "regress-rtl",
            output_dir=output_dir,
            open_wave_gui=open_wave_gui,
        )

    def execute_workflow(self, user_input: Any, output_dir: Any="outputs", skip_tool_check: Any=False) -> Any:
        """执行完整工作流。"""
        print("=" * 60)
        print("数字IC前端设计Agent")
        print("=" * 60)

        print("\n【步骤1/4: 需求分析】")
        matched_skills = self.recommend_skills(user_input)
        try:
            loaded_skills = [self.loaded_skills[name] for name in matched_skills]
        except KeyError as exc:
            print("技能未加载: {}".format(exc), file=sys.stderr)
            return False

        if skip_tool_check:
            print("\n【步骤2/4: 工具检查】")
            print(self.WARN + " 已根据 --no-tool-check 跳过外部工具检查")
        else:
            print("\n【步骤2/4: 工具检查】")
            for skill in loaded_skills:
                report = self.run_preflight(skill.action)
                if not report.ok:
                    print(
                        "\n{} 技能 {} 缺少能力: {}".format(
                            self.WARN,
                            skill.name,
                            ", ".join(report.missing_required),
                        )
                    )
                    return False
            print(self.OK + " 当前技能动作所需能力已就绪")

        print("\n【步骤3/4: 执行计划】")
        request = AgentRequest(
            request_id=uuid4().hex,
            user_input=str(user_input),
            output_dir=Path(output_dir),
            context={"selected_skills": tuple(matched_skills)},
        )
        print("计划请求: {}".format(request.request_id))

        print("\n【步骤4/4: 工具执行与结果验证】")
        self.last_agent_run = self.agent_execution_engine.run(request)
        if self.last_agent_run.status is not AgentRunStatus.SUCCEEDED:
            print(
                "Agent 执行失败: {}".format(
                    self.last_agent_run.failure_reason or "unknown failure"
                ),
                file=sys.stderr,
            )
            return False
        for result in self.last_agent_run.tool_results:
            print(
                "{} {} -> {}".format(
                    self.OK,
                    result.tool_name,
                    ", ".join(str(path) for path in result.artifacts),
                )
            )

        print("\n【后续建议】")
        print("请补充文档中的人工确认项，再进入 RTL 实现或 UVM 验证阶段。")

        print("\n" + "=" * 60)
        print("工作流执行完成")
        print("=" * 60)

        return True


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
