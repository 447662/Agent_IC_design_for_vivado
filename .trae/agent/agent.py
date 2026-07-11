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
    "agent_runtime",
    "agent_provider",
    "agent_execution",
    "agent_skill_tool",
    "agent_cli_parser",
    "agent_cli",
    "agent_cli_dispatch",
    "agent_design_spec",
    "agent_diagnostics",
    "agent_composition",
    "agent_config",
    "agent_entrypoint",
    "report_templates",
    "agent_reports",
    "agent_waveform",
    "capability_preflight",
    "artifact_manifest",
    "coverage_closure",
    "coverage_gates",
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
    "target_flows",
    "target_registry",
    "target_scaffolder",
    "agent_sync_fifo",
    "agent_round_robin_arbiter",
    "target_service_host",
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
    resolve_rwave_command as get_rwave_command,
    resolve_rwave_source_dir as get_rwave_source_dir,
    resolve_vcd_analyzer_path as get_vcd_analyzer_path,
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
    build_target_handlers as build_registered_target_handlers,
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
        return self.load_target_registry()

    def load_target_registry(self, targets_dir: Any=None) -> Any:
        targets_dir = Path(targets_dir) if targets_dir else self.targets_dir
        return load_registered_targets(targets_dir)

    def list_targets(self) -> Any:
        return list_registered_targets(self.targets)

    def get_target(self, target: Any) -> Any:
        return get_registered_target(self.targets, target)

    def print_targets(self) -> Any:
        print("Digital IC Agent registered targets")
        print("=" * 60)
        for target in self.list_targets():
            print("{} ({})".format(target["name"], target["display_name"]))
            print("  family: {}".format(target["design_family"]))
            print("  aliases: {}".format(", ".join(target.get("aliases", [])) or "-"))
            print("  flows: {}".format(", ".join(target.get("flows", []))))
            print("  note: {}".format(target.get("description", "")))
        return True

    def build_target_handlers(self) -> Any:
        handlers = build_registered_target_handlers(self)
        self.target_plugins = {
            target_name: handler.plugin
            for target_name, handler in handlers.items()
            if handler.plugin is not None
        }
        return handlers

    def validate_target_handlers(self) -> Any:
        if set(self.target_handlers) != set(self.targets):
            missing_handlers = sorted(set(self.targets) - set(self.target_handlers))
            unknown_handlers = sorted(set(self.target_handlers) - set(self.targets))
            raise ValueError(
                "Target handler registry mismatch; missing={}, unknown={}".format(
                    missing_handlers,
                    unknown_handlers,
                )
            )

        for target_name, target in self.targets.items():
            configured_flows = set(target.get("flows", []))
            implemented_flows = set(self.target_handlers[target_name].flows)
            if configured_flows != implemented_flows:
                raise ValueError(
                    "Target {} flow mismatch; configured={}, implemented={}".format(
                        target_name,
                        sorted(configured_flows),
                        sorted(implemented_flows),
                    )
                )
        return True

    def run_target_flow(self, target: Any, flow: Any, **kwargs: Any) -> Any:
        target_name = self.normalize_rtl_target(target)
        if flow not in self.targets[target_name].get("flows", []):
            raise ValueError(
                "Target {} does not declare flow: {}".format(target_name, flow)
            )
        output_dir = kwargs.get("output_dir", "outputs")
        project_dir = Path(output_dir) / target_name
        artifact_snapshot = snapshot_project_artifacts(project_dir)
        preflight_report = self.run_preflight(flow)
        if not preflight_report.ok:
            error = "Missing required capabilities for {}: {}".format(
                flow,
                ", ".join(preflight_report.missing_required),
            )
            print(error, file=sys.stderr)
            self.record_artifact_run(
                target_name,
                flow,
                output_dir=output_dir,
                status="FAIL",
                error=error,
                options=kwargs,
                artifact_snapshot=artifact_snapshot,
            )
            return False
        if preflight_report.missing_optional:
            print(
                "{} flow {} 将降级运行，缺少可选能力: {}".format(
                    self.WARN,
                    flow,
                    ", ".join(preflight_report.missing_optional),
                ),
                file=sys.stderr,
            )
        try:
            result = self.target_handlers[target_name].run(flow, **kwargs)
        except Exception as exc:
            self.record_artifact_run(
                target_name,
                flow,
                output_dir=output_dir,
                status="FAIL",
                error=exc,
                options=kwargs,
                artifact_snapshot=artifact_snapshot,
            )
            raise

        status = "PASS" if result else "FAIL"
        self.record_artifact_run(
            target_name,
            flow,
            output_dir=output_dir,
            status=status,
            error=None if result else "flow returned a false result",
            options=kwargs,
            artifact_snapshot=artifact_snapshot,
        )
        return result

    def resolve_skill_path(self, skill: Any) -> Any:
        """解析技能文件路径。"""
        return self.trae_dir / skill["path"]

    def run_diagnostic(self, flow: Any=None) -> Any:
        """???????"""
        return run_agent_diagnostic(self, flow=flow)

    def list_skills(self) -> Any:
        """列出当前配置的技能。"""
        print("数字IC前端设计Agent - 技能列表")
        print("=" * 60)
        for skill in sorted(self.agent_config["skills"], key=lambda x: x["priority"]):
            keywords = "、".join(skill.get("triggerKeywords", []))
            print("{}: {}".format(skill["name"], skill["description"]))
            print("  触发关键词: {}".format(keywords))
            print("  优先级: {}".format(skill["priority"]))
        return True

    def recommend_skills(self, user_input: Any) -> Any:
        """推荐合适的技能。"""
        matched_skills = self.analyze_requirement(user_input)
        print("\n【需求分析结果】")
        print("用户需求: {}".format(user_input))
        print("\n推荐技能:")
        for skill_name in matched_skills:
            skill = self.skill_mapping.get(skill_name)
            if skill:
                print("  {} {}: {}".format(self.OK, skill["name"], skill["description"]))

        return matched_skills

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
        waveform_file = Path(waveform_path)
        waveform_format = waveform_file.suffix.lstrip(".").upper()
        if waveform_format not in {"VCD", "FST", "GHW"}:
            print(
                "Unsupported waveform format: {}".format(
                    waveform_file.suffix or "<none>"
                ),
                file=sys.stderr,
            )
            return False
        if not waveform_file.exists():
            print("Waveform file not found: {}".format(waveform_file), file=sys.stderr)
            return False

        try:
            info = self.run_waveform_analyzer_json(
                "info",
                waveform_file,
                backend=waveform_backend,
            )
            search_result = None
            if condition:
                search_args = [
                    "search",
                    waveform_file,
                    "--condition",
                    condition,
                    "--limit",
                    limit,
                ]
                if show:
                    search_args.extend(["--show", show])
                search_result = self.run_waveform_analyzer_json(*search_args, backend=waveform_backend)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return False

        print(report_title)
        print("=" * 60)
        print("文件: {}".format(waveform_file))
        print("格式: {}".format(waveform_format))
        print("Backend: {}".format(info.get("_waveform_backend", "unknown")))
        print("信号数量: {}".format(info.get("signal_count", "unknown")))
        print("时间范围: {} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")))
        print("持续时间: {}".format(info.get("duration_h", "unknown")))
        print("Timescale: {}".format(info.get("timescale", "unknown")))
        scopes = info.get("scopes") or []
        if scopes:
            print("Scopes: {}".format(", ".join(scopes[:8])))

        if search_result is not None:
            print("\n条件搜索")
            print("- 条件: {}".format(condition))
            if show:
                print("- 观察信号: {}".format(show))
            print("- 模式: {}".format(search_result.get("mode", "unknown")))
            print("- 命中数量: {}".format(search_result.get("total", search_result.get("shown", "unknown"))))

            rows = (
                search_result.get("segments")
                or search_result.get("intervals")
                or search_result.get("events")
                or []
            )
            for index, row in enumerate(rows[: int(limit)], start=1):
                begin = row.get("begin_h") or row.get("time_h") or row.get("at_h") or "unknown"
                end = row.get("end_h")
                values = row.get("values") or {}
                if end:
                    print("  {}. {} -> {} {}".format(index, begin, end, values))
                else:
                    print("  {}. {} {}".format(index, begin, values))

        return True

    def analyze_vcd(
        self,
        vcd_path: Any,
        condition: Any=None,
        show: Any=None,
        limit: Any=20,
        waveform_backend: Any="auto",
    ) -> Any:
        vcd_file = Path(vcd_path)
        if not vcd_file.exists():
            print("VCD file not found: {}".format(vcd_file), file=sys.stderr)
            return False
        return self.analyze_waveform(
            vcd_file,
            condition=condition,
            show=show,
            limit=limit,
            waveform_backend=waveform_backend,
            report_title="VCD 分析报告",
        )










































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
        smoke_dir = Path(output_dir) / "smoke-loop"
        smoke_dir.mkdir(parents=True, exist_ok=True)
        vcd_path = smoke_dir / "handshake_trace.vcd"
        vcd_path.write_text(
            """$date
    Generated by DigitalICAgent smoke loop
$end
$version
    DigitalICAgent built-in handshake smoke loop
$end
$timescale 1ns $end
$scope module tb $end
$var wire 1 ! clk $end
$var wire 1 " valid $end
$var wire 1 # ready $end
$var wire 8 $ data $end
$upscope $end
$enddefinitions $end
#0
0!
0"
0#
b00000000 $
#5
1!
#10
1"
1#
b10101010 $
#15
0"
#20
1"
b01010101 $
#25
0"
#30
0#
0!
""",
            encoding="utf-8",
        )
        return vcd_path

    def run_smoke_loop(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
        print("Smoke loop: generating built-in handshake VCD")
        vcd_path = self.write_smoke_loop_vcd(output_dir)
        print("Generated VCD: {}".format(vcd_path))
        ok = self.analyze_vcd(
            vcd_path,
            condition="tb.valid=1,tb.ready=1",
            show="tb.data",
            limit=limit,
            waveform_backend=waveform_backend,
        )
        if ok:
            print("Smoke loop completed")
        return ok

    def detect_simulator(self) -> Any:
        if self.resolve_vivado_command():
            return "vivado"
        if shutil.which("iverilog") and shutil.which("vvp"):
            return "icarus"
        if shutil.which("verilator"):
            return "verilator"
        return None

    resolve_vivado_command = adapter_resolve_vivado_command
    run_vivado_batch = adapter_run_vivado_batch
    launch_vivado_gui = adapter_launch_vivado_gui

    def write_sim_smoke_sources(self, output_dir: Any) -> Any:
        sim_dir = Path(output_dir) / "sim-smoke"
        sim_dir.mkdir(parents=True, exist_ok=True)

        rtl_path = sim_dir / "handshake_passthrough.v"
        tb_path = sim_dir / "tb_handshake.v"
        vcd_path = sim_dir / "handshake_trace.vcd"

        rtl_path.write_text(
            """`timescale 1ns/1ps

module handshake_passthrough (
    input wire clk,
    input wire rst_n,
    input wire valid,
    input wire ready,
    input wire [7:0] data_in,
    output wire [7:0] data
);
    assign data = data_in;
endmodule
""",
            encoding="utf-8",
        )

        tb_path.write_text(
            """`timescale 1ns/1ps

module tb;
    reg clk;
    reg rst_n;
    reg valid;
    reg ready;
    reg [7:0] data_in;
    wire [7:0] data;

    handshake_passthrough dut (
        .clk(clk),
        .rst_n(rst_n),
        .valid(valid),
        .ready(ready),
        .data_in(data_in),
        .data(data)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        $dumpfile("handshake_trace.vcd");
        $dumpvars(0, tb);

        rst_n = 1'b0;
        valid = 1'b0;
        ready = 1'b0;
        data_in = 8'h00;

        #10;
        rst_n = 1'b1;
        valid = 1'b1;
        ready = 1'b1;
        data_in = 8'haa;

        #5;
        valid = 1'b0;

        #5;
        valid = 1'b1;
        data_in = 8'h55;

        #5;
        valid = 1'b0;

        #5;
        ready = 1'b0;
        #5;
        $finish;
    end
endmodule
""",
            encoding="utf-8",
        )

        return sim_dir, rtl_path, tb_path, vcd_path

    def run_icarus_sim_smoke(self, output_dir: Any, limit: Any=20, waveform_backend: Any="auto") -> Any:
        sim_dir, rtl_path, tb_path, vcd_path = self.write_sim_smoke_sources(output_dir)
        sim_out = sim_dir / "handshake_smoke.vvp"

        compile_result = self.command_runner.run(
            ["iverilog", "-g2012", "-o", sim_out, rtl_path, tb_path],
            cwd=sim_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if compile_result.returncode != 0:
            print(compile_result.stderr.strip() or "iverilog compile failed", file=sys.stderr)
            return False

        run_result = self.command_runner.run(
            ["vvp", sim_out],
            cwd=sim_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if run_result.returncode != 0:
            print(run_result.stderr.strip() or "vvp simulation failed", file=sys.stderr)
            return False

        if not vcd_path.exists():
            print("Simulation did not generate VCD: {}".format(vcd_path), file=sys.stderr)
            return False

        print("Simulator: icarus")
        print("Generated VCD: {}".format(vcd_path))
        ok = self.analyze_vcd(
            vcd_path,
            condition="tb.valid=1,tb.ready=1",
            show="tb.data",
            limit=limit,
            waveform_backend=waveform_backend,
        )
        if ok:
            print("Simulation smoke completed")
        return ok

    def write_vivado_sim_script(self, sim_dir: Any, rtl_path: Any, tb_path: Any, vcd_path: Any) -> Any:
        script_path = Path(sim_dir) / "run_vivado_sim.tcl"
        script_path.write_text(
            """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
file delete -force xsim.dir .Xil xvlog.pb xelab.pb xsim.jou xsim.log xvlog.log xelab.log
exec xvlog -sv handshake_passthrough.v tb_handshake.v
exec xelab tb -debug typical -s handshake_smoke
exec xsim handshake_smoke -R
if {![file exists handshake_trace.vcd]} {
    puts stderr "Simulation did not generate handshake_trace.vcd"
    exit 1
}
exit 0
""",
            encoding="utf-8",
        )
        return script_path

    def open_vivado_wave_gui(self, sim_dir: Any, vcd_path: Any) -> Any:
        wave_db_path = Path(sim_dir) / "handshake_smoke.wdb"
        gui_script_path = Path(sim_dir) / "open_vivado_wave.tcl"
        gui_script_path.write_text(
            """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set wave_db handshake_smoke.wdb
if {![file exists $wave_db]} {
    puts stderr "Waveform database not found: $wave_db"
    exit 1
}
start_gui
open_wave_database $wave_db
add_wave -r /*
""",
            encoding="utf-8",
        )

        if not wave_db_path.exists():
            print("Vivado waveform database not found: {}".format(wave_db_path), file=sys.stderr)
            return False

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found; cannot open waveform GUI.", file=sys.stderr)
            return False

        self.launch_vivado_gui(vivado_command, gui_script_path.name, sim_dir)
        print("Vivado waveform GUI launched: {}".format(wave_db_path))
        return True

    def run_vivado_sim_smoke(self, output_dir: Any, limit: Any=20, open_wave_gui: Any=True, waveform_backend: Any="auto") -> Any:
        sim_dir, rtl_path, tb_path, vcd_path = self.write_sim_smoke_sources(output_dir)
        script_path = self.write_vivado_sim_script(sim_dir, rtl_path, tb_path, vcd_path)
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        result = self.run_vivado_batch(
            vivado_command,
            script_path.name,
            sim_dir,
        )
        if result.returncode != 0:
            print(result.stderr.strip() or result.stdout.strip() or "vivado simulation failed", file=sys.stderr)
            return False

        if not vcd_path.exists():
            print("Simulation did not generate VCD: {}".format(vcd_path), file=sys.stderr)
            return False

        print("Simulator: vivado")
        print("Generated VCD: {}".format(vcd_path))
        ok = self.analyze_vcd(
            vcd_path,
            condition="tb.valid=1,tb.ready=1",
            show="tb.data",
            limit=limit,
            waveform_backend=waveform_backend,
        )
        if ok:
            print("Simulation smoke completed")
            if open_wave_gui:
                self.open_vivado_wave_gui(sim_dir, vcd_path)
        return ok

    def run_sim_smoke(self, output_dir: Any="outputs", limit: Any=20, open_wave_gui: Any=True, waveform_backend: Any="auto") -> Any:
        simulator = self.detect_simulator()
        if simulator is None:
            print(
                "No supported Verilog simulator found. Install iverilog/vvp, verilator, or vivado; "
                "use --smoke-loop for the built-in VCD fallback.",
                file=sys.stderr,
            )
            return False
        if simulator == "vivado":
            return self.run_vivado_sim_smoke(
                output_dir=output_dir,
                limit=limit,
                open_wave_gui=open_wave_gui,
                waveform_backend=waveform_backend,
            )
        if simulator == "icarus":
            return self.run_icarus_sim_smoke(
                output_dir=output_dir,
                limit=limit,
                waveform_backend=waveform_backend,
            )

        print(
            "{} detected, but sim smoke currently supports only Vivado or iverilog/vvp.".format(simulator),
            file=sys.stderr,
        )
        return False

    def normalize_rtl_target(self, target: Any) -> Any:
        return self.get_target(target)["name"]




    def render_vivado_tclstore_bootstrap(self) -> Any:
        return """proc source_pkg_index {index_file} {
    if {[file exists $index_file]} {
        set old_dir_exists [info exists ::dir]
        if {$old_dir_exists} {
            set old_dir $::dir
        }
        set ::dir [file dirname $index_file]
        uplevel #0 [list source $index_file]
        if {$old_dir_exists} {
            set ::dir $old_dir
        } else {
            unset -nocomplain ::dir
        }
    }
}

set vivado_exe [file normalize [info nameofexecutable]]
set vivado_root [file dirname [file dirname [file dirname [file dirname $vivado_exe]]]]
set install_store [file join $vivado_root data XilinxTclStore]
if {![file isdirectory $install_store]} {
    set install_store [file normalize "D:/vivado/2025.2/Vivado/data/XilinxTclStore"]
}
set support_dir [file join $install_store support]
set appinit_dir [file join $support_dir appinit]
set tclapp_dir [file join $install_store tclapp]
set xilinx_dir [file join $tclapp_dir xilinx]
set xsim_dir [file join $xilinx_dir xsim]
foreach dir_path [list $support_dir $appinit_dir $tclapp_dir $xilinx_dir $xsim_dir] {
    if {[file isdirectory $dir_path] && [lsearch -exact $::auto_path $dir_path] == -1} {
        lappend ::auto_path $dir_path
    }
}
foreach index_file [list \
    [file join $support_dir pkgIndex.tcl] \
    [file join $appinit_dir pkgIndex.tcl] \
    [file join $tclapp_dir pkgIndex.tcl] \
    [file join $xilinx_dir pkgIndex.tcl] \
    [file join $xsim_dir pkgIndex.tcl] \
] {
    source_pkg_index $index_file
}
catch {package require ::tclapp::support::appinit 1.2}
catch {package require ::tclapp::xilinx::xsim 2.520}
"""





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
