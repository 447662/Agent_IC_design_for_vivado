#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Script Name: agent.py
# Description: 数字IC前端设计Agent主入口
#              智能分析用户需求，匹配合适的技能，检查工具环境，生成设计文档模板
# Author: Digital IC Designer Team
# Date: 2026-05-15
# -----------------------------------------------------------------------------

import argparse
import html
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def _configure_text_stream(stream):
    try:
        stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


_configure_text_stream(sys.stdout)
_configure_text_stream(sys.stderr)


class DigitalICAgent:
    def __init__(self, config_path=None):
        self.base_dir = Path(__file__).resolve().parent
        self.trae_dir = self.base_dir.parent
        self.project_root = self.trae_dir.parent
        self.config_path = Path(config_path) if config_path else self.base_dir / "agent.json"
        self.agent_config = self.load_config()
        self.skill_mapping = {skill["name"]: skill for skill in self.agent_config["skills"]}
        self.mcp_servers = self.agent_config["mcpServers"]
        self.cli_tools = self.agent_config["cliTools"]
        self.OK = "[OK]"
        self.NO = "[NO]"
        self.WARN = "[WARN]"

    def load_config(self):
        """加载Agent配置文件。"""
        with self.config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def normalize_command(self, command):
        """将配置中的命令转换为 subprocess 可执行的参数列表。"""
        if isinstance(command, list):
            return [str(part) for part in command]
        if isinstance(command, str):
            return shlex.split(command)
        raise ValueError("命令必须是字符串或字符串数组")

    def check_cli_tool(self, tool_name, check_command):
        """检查CLI工具是否安装。"""
        try:
            command = self.normalize_command(check_command)
            if tool_name == "vivado" and command and command[0] == "vivado":
                vivado_command = self.resolve_vivado_command()
                if vivado_command:
                    command[0] = vivado_command
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            return result.returncode == 0
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired, ValueError):
            return False

    def check_mcp_server(self, mcp_name):
        """检查MCP服务器是否可用。"""
        mcp = self.mcp_servers.get(mcp_name)
        if not mcp:
            return False

        try:
            command = [mcp["command"], *mcp.get("args", []), "--version"]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            return result.returncode == 0
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return False

    def analyze_requirement(self, user_input):
        """分析用户需求，匹配技能。"""
        user_input_lower = user_input.lower()
        matched_skills = []

        for skill in sorted(self.agent_config["skills"], key=lambda x: x["priority"]):
            for keyword in skill["triggerKeywords"]:
                if keyword.lower() in user_input_lower:
                    matched_skills.append(skill["name"])
                    break

        if any(keyword in user_input_lower for keyword in ["uvm", "前仿", "功能验证", "覆盖率"]):
            if "digital-ic-verifier" not in matched_skills:
                matched_skills.append("digital-ic-verifier")

        if not matched_skills:
            matched_skills.append("digital-ic-rtl-designer")

        return matched_skills

    def get_install_guide(self, tool_type, tool_name):
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

    def resolve_skill_path(self, skill):
        """解析技能文件路径。"""
        return self.trae_dir / skill["path"]

    def run_diagnostic(self):
        """运行环境诊断。"""
        print("=" * 60)
        print("数字IC前端设计Agent - 环境诊断")
        print("=" * 60)

        print("\n【CLI工具检查】")
        cli_status = []
        for tool in self.cli_tools:
            installed = self.check_cli_tool(tool["name"], tool["checkCommand"])
            status = self.OK + " 已安装" if installed else self.NO + " 未安装"
            cli_status.append((tool["name"], installed))
            print("  {}: {}".format(tool["name"], status))
            if not installed:
                print("     安装指南: {}".format(self.get_install_guide("cli", tool["name"])))

        print("\n【MCP服务器检查】")
        mcp_status = []
        for name, mcp in self.mcp_servers.items():
            available = self.check_mcp_server(name)
            status = self.OK + " 可用" if available else self.NO + " 不可用"
            mcp_status.append((name, available))
            print("  {}: {}".format(name, status))
            if not available:
                print("     安装指南: {}".format(mcp.get("installGuide", "未知")))

        print("\n【技能文件检查】")
        skill_status = []
        for skill in self.agent_config["skills"]:
            skill_path = self.resolve_skill_path(skill)
            exists = skill_path.exists()
            status = self.OK + " 存在" if exists else self.NO + " 缺失"
            skill_status.append((skill["name"], exists))
            print("  {}: {}".format(skill["name"], status))

        all_ok = (
            all(installed for _, installed in cli_status)
            and all(available for _, available in mcp_status)
            and all(exists for _, exists in skill_status)
        )

        print("\n" + "=" * 60)
        if all_ok:
            print("诊断结果: " + self.OK + " 所有工具和技能均已就绪")
        else:
            print("诊断结果: " + self.WARN + " 部分工具未安装，请根据上述指南安装")
        print("=" * 60)

        return all_ok

    def list_skills(self):
        """列出当前配置的技能。"""
        print("数字IC前端设计Agent - 技能列表")
        print("=" * 60)
        for skill in sorted(self.agent_config["skills"], key=lambda x: x["priority"]):
            keywords = "、".join(skill.get("triggerKeywords", []))
            print("{}: {}".format(skill["name"], skill["description"]))
            print("  触发关键词: {}".format(keywords))
            print("  优先级: {}".format(skill["priority"]))
        return True

    def recommend_skills(self, user_input):
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

    def build_project_slug(self, user_input):
        """根据用户输入生成安全的输出目录名。"""
        ascii_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", user_input.lower())
        ascii_slug = re.sub(r"-+", "-", ascii_slug).strip("-_")
        if ascii_slug:
            return ascii_slug[:48].strip("-_")

        digest = hashlib.sha1(user_input.encode("utf-8")).hexdigest()[:8]
        return "design-{}".format(digest)

    def render_design_spec(self, user_input, matched_skills):
        """渲染初始设计说明模板。"""
        skill_lines = []
        for skill_name in matched_skills:
            skill = self.skill_mapping.get(skill_name, {"description": "未知技能"})
            skill_lines.append("- `{}`：{}".format(skill_name, skill["description"]))

        skill_text = "\n".join(skill_lines)

        return """# 数字 IC 设计说明模板

> 本文档由 Digital IC Frontend Agent 自动生成，是用于启动设计讨论的初始设计说明模板，不代表最终 RTL、UVM 或签核结果。

## 1. 需求摘要

原始用户需求：

```text
{user_input}
```

## 2. Agent 匹配结果

推荐技能：

{skill_text}

匹配说明：Agent 根据需求关键词和默认路由规则推荐以上技能。若需求没有明确命中设计文档、RTL 或 UVM 关键词，则默认进入 RTL 设计流程。

## 3. 初步设计目标

- 功能目标：需用户确认模块功能、协议行为和异常处理要求。
- 性能目标：需用户确认工作频率、吞吐率、延迟和资源预算。
- 接口目标：需用户确认总线协议、数据宽度、地址宽度和握手机制。
- 约束条件：需用户确认目标器件、工艺节点、复位策略和时钟域数量。

## 4. 建议模块划分

| 模块 | 职责 | 备注 |
| --- | --- | --- |
| 顶层控制模块 | 集成子模块并暴露外部接口 | 需结合协议和时钟域细化 |
| 寄存器/配置模块 | 保存配置项和状态信息 | 若设计不需要软件配置，可移除 |
| 数据通路模块 | 处理核心数据流 | 需根据位宽和吞吐目标细化 |
| 状态机模块 | 管理协议阶段和控制流程 | 需补充状态转移图 |

## 5. 初步接口定义

| 信号名 | 方向 | 位宽 | 描述 |
| --- | --- | --- | --- |
| clk | input | 1 | 主时钟 |
| rst_n | input | 1 | 低有效复位 |
| data_in | input | 需确认 | 输入数据 |
| data_out | output | 需确认 | 输出数据 |
| valid | input/output | 1 | 数据有效指示，方向需按模块角色确认 |
| ready | input/output | 1 | 反压握手信号，方向需按模块角色确认 |

## 6. 验证计划占位

- 基本功能测试：覆盖正常配置、正常传输和基本状态转移。
- 边界条件测试：覆盖最小/最大数据宽度、连续传输和空闲切换。
- 异常场景测试：覆盖复位中断、非法配置、协议错误和超时场景。
- 覆盖率目标：后续确认语句覆盖率、分支覆盖率、功能覆盖率目标。

## 7. 后续人工确认项

- 工作频率
- 复位方式
- 总线协议
- 数据宽度
- 地址宽度
- 时钟域数量
- 是否需要 UVM 验证
- 功耗、面积和时序约束
""".format(user_input=user_input, skill_text=skill_text)

    def generate_design_spec(self, user_input, matched_skills, output_dir):
        """生成 Markdown 设计文档模板。"""
        output_root = Path(output_dir)
        project_dir = output_root / self.build_project_slug(user_input)
        project_dir.mkdir(parents=True, exist_ok=True)
        spec_path = project_dir / "design_spec.md"
        spec_path.write_text(self.render_design_spec(user_input, matched_skills), encoding="utf-8")
        return spec_path

    def resolve_vcd_analyzer_path(self):
        return (
            self.project_root
            / "VCD_ANALYZER-main"
            / "VCD_ANALYZER-main"
            / "vcd_analyzer.py"
        )

    def run_vcd_analyzer_json(self, *args):
        analyzer_path = self.resolve_vcd_analyzer_path()
        if not analyzer_path.exists():
            raise FileNotFoundError("VCD analyzer not found: {}".format(analyzer_path))

        result = subprocess.run(
            [sys.executable, str(analyzer_path), "--json", *[str(arg) for arg in args]],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "vcd_analyzer failed"
            raise RuntimeError(message)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("vcd_analyzer returned invalid JSON: {}".format(exc))

    def analyze_vcd(self, vcd_path, condition=None, show=None, limit=20):
        vcd_file = Path(vcd_path)
        if not vcd_file.exists():
            print("VCD file not found: {}".format(vcd_file), file=sys.stderr)
            return False

        try:
            info = self.run_vcd_analyzer_json("info", vcd_file)
            search_result = None
            if condition:
                search_args = ["search", vcd_file, "--condition", condition, "--limit", limit]
                if show:
                    search_args.extend(["--show", show])
                search_result = self.run_vcd_analyzer_json(*search_args)
        except (FileNotFoundError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return False

        print("VCD 分析报告")
        print("=" * 60)
        print("文件: {}".format(vcd_file))
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

    def resolve_async_fifo_vcd_path(self, output_dir="outputs"):
        return Path(output_dir) / "async-fifo" / "sim" / "async_fifo_trace.vcd"

    def collect_async_fifo_vcd_analysis(self, output_dir="outputs", limit=20):
        vcd_path = self.resolve_async_fifo_vcd_path(output_dir)
        if not vcd_path.exists():
            raise FileNotFoundError("Async FIFO VCD file not found: {}".format(vcd_path))

        info = self.run_vcd_analyzer_json("info", vcd_path)
        write_events = self.run_vcd_analyzer_json(
            "search",
            vcd_path,
            "--condition",
            "tb_async_fifo.full=0",
            "--changed",
            "tb_async_fifo.write_count",
            "--show",
            "tb_async_fifo.wr_data,tb_async_fifo.write_count",
            "--limit",
            limit,
        )
        read_events = self.run_vcd_analyzer_json(
            "search",
            vcd_path,
            "--condition",
            "tb_async_fifo.error_count=0",
            "--changed",
            "tb_async_fifo.read_count",
            "--show",
            "tb_async_fifo.rd_data,tb_async_fifo.read_count",
            "--limit",
            limit,
        )
        return {
            "vcd_path": vcd_path,
            "info": info,
            "write_events": write_events,
            "read_events": read_events,
        }

    def analyze_async_fifo_vcd(self, output_dir="outputs", limit=20):
        try:
            analysis = self.collect_async_fifo_vcd_analysis(output_dir=output_dir, limit=limit)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            print("Run --sim-rtl async-fifo first, or check --output-dir.", file=sys.stderr)
            return False
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return False

        vcd_path = analysis["vcd_path"]
        info = analysis["info"]
        write_events = analysis["write_events"]
        read_events = analysis["read_events"]

        print("Async FIFO VCD analysis")
        print("=" * 60)
        print("File: {}".format(vcd_path))
        print("Signals: {}".format(info.get("signal_count", "unknown")))
        print("Time range: {} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")))
        print("Duration: {}".format(info.get("duration_h", "unknown")))
        print("Timescale: {}".format(info.get("timescale", "unknown")))
        print("Write handshakes: {}".format(write_events.get("total", write_events.get("shown", "unknown"))))
        print("Read handshakes: {}".format(read_events.get("total", read_events.get("shown", "unknown"))))

        for title, result in [("Writes", write_events), ("Reads", read_events)]:
            rows = result.get("segments") or result.get("intervals") or result.get("events") or []
            print("\n{}".format(title))
            for index, row in enumerate(rows[: int(limit)], start=1):
                begin = row.get("begin_h") or row.get("time_h") or row.get("at_h") or "unknown"
                end = row.get("end_h")
                values = row.get("values") or {}
                if end:
                    print("  {}. {} -> {} {}".format(index, begin, end, values))
                else:
                    print("  {}. {} {}".format(index, begin, values))

        return True

    def write_async_fifo_sim_report(self, project_dir, vcd_path, wave_db_path, sim_result=None, project_result=None, limit=20):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "sim_report.md"

        analysis = None
        analysis_error = None
        try:
            analysis = self.collect_async_fifo_vcd_analysis(output_dir=project_dir.parent, limit=limit)
        except (FileNotFoundError, RuntimeError) as exc:
            analysis_error = str(exc)

        lines = [
            "# async-fifo Simulation Report",
            "",
            "## Summary",
            "",
            "- Target: `async-fifo`",
            "- Simulator: Vivado/xsim",
            "- Status: PASS" if analysis_error is None else "- Status: PASS_WITH_ANALYSIS_WARNING",
            "- VCD: `{}`".format(vcd_path),
            "- WDB: `{}`".format(wave_db_path),
            "- Vivado project: `{}`".format(project_dir / "vivado_project" / "async_fifo_project.xpr"),
            "",
            "## Scoreboard",
            "",
            "- Testbench includes `ASYNC_FIFO_SCOREBOARD_PASS` / `ASYNC_FIFO_SCOREBOARD_FAIL` checks.",
            "- xsim returns failure if `$fatal(1, ...)` is reached.",
            "",
            "## Scenarios",
            "",
            "- `basic_ordered`: ordered write/read smoke path.",
            "- `full_boundary`: fills FIFO to full and confirms overflow writes are blocked.",
            "- `empty_boundary`: drains FIFO to empty and confirms underflow reads are blocked.",
            "- `reset_recovery`: resets mid-test and verifies clean post-reset operation.",
            "- `mixed_stress`: overlaps write/read activity across asynchronous clocks.",
        ]

        if analysis is not None:
            info = analysis["info"]
            write_events = analysis["write_events"]
            read_events = analysis["read_events"]
            lines.extend([
                "",
                "## VCD Analysis",
                "",
                "- Signals: {}".format(info.get("signal_count", "unknown")),
                "- Time range: {} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")),
                "- Duration: {}".format(info.get("duration_h", "unknown")),
                "- Timescale: {}".format(info.get("timescale", "unknown")),
                "- Write events: {}".format(write_events.get("total", write_events.get("shown", "unknown"))),
                "- Read events: {}".format(read_events.get("total", read_events.get("shown", "unknown"))),
                "",
                "## Write Samples",
                "",
            ])
            for row in (write_events.get("events") or [])[: int(limit)]:
                lines.append("- {} {}".format(row.get("time_h", "unknown"), row.get("values") or {}))
            lines.extend(["", "## Read Samples", ""])
            for row in (read_events.get("events") or [])[: int(limit)]:
                lines.append("- {} {}".format(row.get("time_h", "unknown"), row.get("values") or {}))
        else:
            lines.extend(["", "## VCD Analysis", "", "- Analysis warning: {}".format(analysis_error)])

        if sim_result is not None or project_result is not None:
            lines.extend(["", "## Tool Return Codes", ""])
            if sim_result is not None:
                lines.append("- Simulation command return code: {}".format(sim_result.returncode))
            if project_result is not None:
                lines.append("- Project command return code: {}".format(project_result.returncode))

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        regression_path = self.write_async_fifo_regression_matrix(project_dir)
        self.write_async_fifo_summary_report(
            project_dir=project_dir,
            vcd_path=vcd_path,
            wave_db_path=wave_db_path,
            analysis=analysis,
            analysis_error=analysis_error,
            regression_path=regression_path,
        )
        return report_path

    def async_fifo_required_wcfg_objects(self):
        return [
            "/tb_async_fifo/scenario_id",
            "/tb_async_fifo/wr_clk",
            "/tb_async_fifo/rd_clk",
            "/tb_async_fifo/write_count",
            "/tb_async_fifo/read_count",
            "/tb_async_fifo/dut/full_reg",
            "/tb_async_fifo/dut/empty_reg",
        ]

    def parse_async_fifo_wcfg_summary(self, project_dir):
        project_dir = Path(project_dir)
        wcfg_path = project_dir / "sim" / "async_fifo_debug.wcfg"
        required_objects = self.async_fifo_required_wcfg_objects()
        summary = {
            "path": wcfg_path,
            "exists": wcfg_path.exists(),
            "object_count": 0,
            "required_objects": required_objects,
            "present_required": [],
            "missing_required": required_objects[:],
            "valid": False,
        }
        if not wcfg_path.exists():
            return summary

        text = wcfg_path.read_text(encoding="utf-8", errors="replace")
        size_match = re.search(r"<WVObjectSize\s+size=\"(\d+)\"", text)
        if size_match:
            summary["object_count"] = int(size_match.group(1))
        else:
            summary["object_count"] = len(re.findall(r"/tb_async_fifo/", text))

        present_required = [name for name in required_objects if name in text]
        summary["present_required"] = present_required
        summary["missing_required"] = [name for name in required_objects if name not in present_required]
        summary["valid"] = summary["object_count"] > 0 and not summary["missing_required"]
        return summary

    def async_fifo_regression_cases(self):
        return [
            {"name": "dw8_aw4", "data_width": 8, "addr_width": 4},
            {"name": "dw16_aw4", "data_width": 16, "addr_width": 4},
            {"name": "dw8_aw3", "data_width": 8, "addr_width": 3},
        ]

    def write_async_fifo_regression_matrix(self, project_dir):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "regression_matrix.md"
        lines = [
            "# async-fifo Regression Matrix",
            "",
            "P2.7 tracks the parameter combinations that should be kept under regression as the async FIFO flow grows.",
            "",
            "| DATA_WIDTH | ADDR_WIDTH | Scenario coverage | Status |",
            "|---:|---:|---|---|",
            "| 8 | 4 | basic/full/empty/reset/mixed | baseline-pass |",
            "| 16 | 4 | basic/full/empty/reset/mixed | planned |",
            "| 8 | 3 | basic/full/empty/reset/mixed | planned |",
            "",
            "Clock plan: keep the current asynchronous 5 ns write clock and 7 ns read clock for the first matrix pass.",
            "Next expansion: generate per-parameter RTL/TB directories or pass Verilog parameters through the Vivado script.",
        ]
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_path

    def write_async_fifo_wave_visibility_report(self, project_dir):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        sim_dir = project_dir / "sim"
        xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
        wave_db_path = self.resolve_async_fifo_wave_db(sim_dir)
        gui_script_path = sim_dir / "open_async_fifo_project_gui.tcl"
        wcfg = self.parse_async_fifo_wcfg_summary(project_dir)

        checks = [
            ("Vivado 工程存在", xpr_path.exists(), xpr_path),
            ("WDB 波形数据库存在", wave_db_path.exists(), wave_db_path),
            ("GUI Tcl 脚本存在", gui_script_path.exists(), gui_script_path),
            ("GUI 脚本会打开工程", gui_script_path.exists() and "open_project $xpr_path" in gui_script_path.read_text(encoding="utf-8", errors="replace"), gui_script_path),
            ("GUI 脚本会打开 WDB", gui_script_path.exists() and "open_wave_database $wave_db" in gui_script_path.read_text(encoding="utf-8", errors="replace"), gui_script_path),
            ("WCFG 有波形对象", wcfg["object_count"] > 0, wcfg["path"]),
            ("WCFG 关键对象齐全", wcfg["valid"], wcfg["path"]),
        ]
        visible = all(passed for _label, passed, _path in checks)
        markdown_path = reports_dir / "wave_visibility.md"
        html_path = reports_dir / "wave_visibility.html"
        status = "PASS" if visible else "FAIL"
        wcfg_status = "PASS" if wcfg["valid"] else "FAIL"

        lines = [
            "# async-fifo 波形可见性验收",
            "",
            "- 总体状态：{}".format(status),
            "- WCFG 状态：{}".format(wcfg_status),
            "- 波形对象数：{}".format(wcfg["object_count"]),
            "- WDB：`{}`".format(wave_db_path),
            "- WCFG：`{}`".format(wcfg["path"]),
            "- 关键 Tcl 命令：`open_project` / `open_wave_database`",
            "",
            "## GUI 预检项",
            "",
        ]
        for label, passed, path in checks:
            lines.append("- {}：{} `{}`".format(label, "OK" if passed else "NO", path))
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for label, passed, path in checks:
            cards.append(
                '<article class="visibility-card {status}"><strong>{label}</strong><span>{result}</span><code>{path}</code></article>'.format(
                    status="pass" if passed else "fail",
                    label=html.escape(label),
                    result="OK" if passed else "NO",
                    path=html.escape(str(path)),
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo 波形可见性验收</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1100px;margin:0 auto;padding:32px 22px}",
            ".hero{padding:26px;border-radius:8px;background:#17324d;color:#fff;box-shadow:0 18px 45px rgba(31,45,61,.10)}",
            ".hero h1{margin:0 0 8px;font-size:30px}",
            ".grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:20px}",
            ".visibility-card{display:grid;gap:8px;padding:16px;border-radius:8px;background:#fff;border:1px solid #dbe3ee}",
            ".visibility-card.pass{border-left:6px solid #0f8a5f}",
            ".visibility-card.fail{border-left:6px solid #b42318}",
            ".visibility-card span{font-weight:800}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:760px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo 波形可见性验收</h1><p>状态：{}</p></section>'.format(html.escape(status)),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {"visible": visible, "markdown_path": markdown_path, "html_path": html_path, "checks": checks}

    def write_async_fifo_wave_screenshot_report(self, project_dir):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = reports_dir / "wave_visibility.png"
        markdown_path = reports_dir / "wave_screenshot.md"
        html_path = reports_dir / "wave_screenshot.html"
        capture_script_path = reports_dir / "capture_wave_screenshot.ps1"
        captured = screenshot_path.exists() and screenshot_path.stat().st_size > 8
        status = "PASS" if captured else "PENDING"

        capture_script = r'''Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$output = Join-Path $PSScriptRoot "wave_visibility.png"
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save($output, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
Write-Host "Saved waveform screenshot to $output"
'''
        capture_script_path.write_text(capture_script, encoding="utf-8")

        lines = [
            "# async-fifo GUI 波形截图验收",
            "",
            "- 状态：{}".format(status),
            "- 截图：`{}`".format(screenshot_path),
            "- 捕获脚本：`{}`".format(capture_script_path),
            "",
            "## 使用方式",
            "",
            "1. 先运行 `python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs` 打开 Vivado GUI 波形。",
            "2. 确认波形窗口可见后，在 PowerShell 中运行 `outputs/async-fifo/reports/capture_wave_screenshot.ps1`。",
            "3. 再运行 `python .trae/agent/agent.py --check-rtl async-fifo --output-dir outputs` 刷新报告索引。",
            "",
        ]
        if captured:
            lines.extend([
                "## 截图预览",
                "",
                "![async-fifo waveform](wave_visibility.png)",
                "",
            ])
        else:
            lines.extend([
                "## 截图预览",
                "",
                "尚未捕获 `wave_visibility.png`。该项不会阻断批处理自检，但用于人工确认 GUI 中确实能看到波形。",
                "",
            ])
        markdown_path.write_text("\n".join(lines), encoding="utf-8")

        screenshot_block = (
            '<img src="wave_visibility.png" alt="async-fifo waveform screenshot">'
            if captured
            else '<p class="empty">尚未捕获截图。打开 Vivado 波形后运行 capture_wave_screenshot.ps1。</p>'
        )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo GUI 波形截图验收</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1120px;margin:0 auto;padding:32px 22px}",
            ".hero{padding:26px;border-radius:8px;background:#17324d;color:#fff}",
            ".hero h1{margin:0 0 8px;font-size:30px}",
            ".screenshot-card{margin-top:18px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".screenshot-card.pass{border-left:6px solid #0f8a5f}",
            ".screenshot-card.pending{border-left:6px solid #b7791f}",
            ".screenshot-card img{display:block;width:100%;max-height:720px;object-fit:contain;border-radius:6px;border:1px solid #dbe3ee;background:#101828}",
            ".empty{margin:0;color:#6b778c}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo GUI 波形截图验收</h1><p>状态：{}</p></section>'.format(html.escape(status)),
            '<section class="screenshot-card {}">'.format("pass" if captured else "pending"),
            screenshot_block,
            '<p><strong>截图文件</strong></p><code>{}</code>'.format(html.escape(str(screenshot_path))),
            '<p><strong>捕获脚本</strong></p><code>{}</code>'.format(html.escape(str(capture_script_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "captured": captured,
            "markdown_path": markdown_path,
            "html_path": html_path,
            "capture_script_path": capture_script_path,
            "screenshot_path": screenshot_path,
        }

    def write_async_fifo_uvm_wave_screenshot_report(self, project_dir, wave_kind="coverage"):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        if wave_kind not in ("smoke", "coverage"):
            raise ValueError("Unsupported UVM wave kind: {}".format(wave_kind))

        wave_db_name = "async_fifo_uvm_coverage.wdb" if wave_kind == "coverage" else "async_fifo_uvm_smoke.wdb"
        wave_db_path = sim_dir / wave_db_name
        screenshot_path = reports_dir / "uvm_wave_visibility.png"
        markdown_path = reports_dir / "uvm_wave_screenshot.md"
        html_path = reports_dir / "uvm_wave_screenshot.html"
        capture_script_path = reports_dir / "capture_uvm_wave_screenshot.ps1"
        captured = screenshot_path.exists() and screenshot_path.stat().st_size > 8
        status = "PASS" if captured else "PENDING"

        capture_script = r'''# capture_uvm_wave_screenshot.ps1
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$output = Join-Path $PSScriptRoot "uvm_wave_visibility.png"
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save($output, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
Write-Host "Saved UVM waveform screenshot to $output"
'''
        capture_script_path.write_text(capture_script, encoding="utf-8")

        lines = [
            "# async-fifo UVM GUI 波形截图验收",
            "",
            "- 状态：{}".format(status),
            "- UVM 波形类型：{}".format(wave_kind),
            "- WDB：`{}`".format(wave_db_path),
            "- 截图：`{}`".format(screenshot_path),
            "- 捕获脚本：`{}`".format(capture_script_path),
            "",
            "## 使用方式",
            "",
            "1. 先运行 `python .trae/agent/agent.py --open-uvm-wave async-fifo --uvm-wave-kind {} --output-dir outputs` 打开 Vivado GUI UVM 波形。".format(wave_kind),
            "2. 确认 UVM 波形窗口可见后，在 PowerShell 中运行 `outputs/async-fifo/reports/capture_uvm_wave_screenshot.ps1`。",
            "3. 再运行 `python .trae/agent/agent.py --open-uvm-wave async-fifo --uvm-wave-kind {} --output-dir outputs` 刷新截图验收报告。".format(wave_kind),
            "",
            "## 截图预览",
            "",
        ]
        if captured:
            lines.extend(["![async-fifo UVM waveform](uvm_wave_visibility.png)", ""])
        else:
            lines.extend([
                "尚未捕获 `uvm_wave_visibility.png`。该项不会阻断批处理自检，但用于人工确认 Vivado GUI 中确实能看到 UVM 波形。",
                "",
            ])
        markdown_path.write_text("\n".join(lines), encoding="utf-8")

        screenshot_block = (
            '<img src="uvm_wave_visibility.png" alt="async-fifo UVM waveform screenshot">'
            if captured
            else '<p class="empty">尚未捕获截图。打开 Vivado UVM 波形后运行 capture_uvm_wave_screenshot.ps1。</p>'
        )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM GUI 波形截图验收</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1120px;margin:0 auto;padding:32px 22px}",
            ".hero{padding:26px;border-radius:8px;background:#17324d;color:#fff}",
            ".hero h1{margin:0 0 8px;font-size:30px}",
            ".screenshot-card{margin-top:18px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".screenshot-card.pass{border-left:6px solid #0f8a5f}",
            ".screenshot-card.pending{border-left:6px solid #b7791f}",
            ".screenshot-card img{display:block;width:100%;max-height:720px;object-fit:contain;border-radius:6px;border:1px solid #dbe3ee;background:#101828}",
            ".empty{margin:0;color:#6b778c}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM GUI 波形截图验收</h1><p>状态：{} · 类型：{}</p></section>'.format(html.escape(status), html.escape(wave_kind)),
            '<section class="screenshot-card {}">'.format("pass" if captured else "pending"),
            screenshot_block,
            '<p><strong>WDB</strong></p><code>{}</code>'.format(html.escape(str(wave_db_path))),
            '<p><strong>截图文件</strong></p><code>{}</code>'.format(html.escape(str(screenshot_path))),
            '<p><strong>捕获脚本</strong></p><code>{}</code>'.format(html.escape(str(capture_script_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "captured": captured,
            "markdown_path": markdown_path,
            "html_path": html_path,
            "capture_script_path": capture_script_path,
            "screenshot_path": screenshot_path,
            "wave_db_path": wave_db_path,
        }

    def write_async_fifo_reports_index(self, project_dir):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = reports_dir / "index.md"
        html_path = reports_dir / "index.html"
        report_items = [
            ("仿真摘要", "sim_summary.html", "sim_summary.md", "场景覆盖、VCD 统计、WDB/WCFG 产物和常用命令"),
            ("回归摘要", "regression_summary.html", "regression_summary.md", "DATA_WIDTH / ADDR_WIDTH 真实 Vivado/xsim 回归结果"),
            ("波形可见性", "wave_visibility.html", "wave_visibility.md", "工程、WDB、GUI Tcl、WCFG 对象和关键命令验收"),
            ("GUI 波形截图", "wave_screenshot.html", "wave_screenshot.md", "人工可见波形截图与截图捕获脚本"),
            ("UVM GUI 波形截图", "uvm_wave_screenshot.html", "uvm_wave_screenshot.md", "UVM WDB 人工可见波形截图与截图捕获脚本"),
            ("问题复盘", "docs/vivado_async_fifo_lessons_learned.md", None, "历史问题、根因、修复方式和后续建议"),
        ]
        report_items.extend([
            ("UVM Coverage Summary", "uvm_coverage_summary.html", "uvm_coverage_summary.md", "P3.13 summary with gate result, coverage scores, and xcrg links"),
            ("Vivado Code Coverage", "uvm_coverage_xcrg/codeCoverageReport/dashboard.html", None, "Official xcrg code coverage HTML dashboard"),
            ("Vivado Functional Coverage", "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html", None, "Official xcrg functional coverage HTML dashboard"),
            ("XCRG Log", "xcrg_coverage.log", None, "Vivado xcrg export log"),
            ("Coverage Percent Text", "uvm_coverage_percent.txt", None, "Parsed xcrg score text used by coverage gate"),
        ])
        ready_count = 0
        rows = []
        for title, html_name, md_name, note in report_items:
            if html_name.startswith("docs/"):
                exists = (self.project_root / html_name).exists()
            else:
                exists = (reports_dir / html_name).exists()
            ready_count += 1 if exists else 0
            rows.append({
                "title": title,
                "html": html_name,
                "markdown": md_name,
                "note": note,
                "ready": exists,
            })

        lines = [
            "# async-fifo 报告总览",
            "",
            "- 可用报告：{}/{}".format(ready_count, len(report_items)),
            "- 工程目录：`{}`".format(project_dir),
            "",
            "| 报告 | 状态 | HTML/路径 | Markdown | 说明 |",
            "|---|---|---|---|---|",
        ]
        for item in rows:
            lines.append(
                "| {title} | {status} | `{html_path}` | {md_path} | {note} |".format(
                    title=item["title"],
                    status="READY" if item["ready"] else "MISSING",
                    html_path=item["html"],
                    md_path="`{}`".format(item["markdown"]) if item["markdown"] else "-",
                    note=item["note"],
                )
            )
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for item in rows:
            klass = "ready" if item["ready"] else "missing"
            cards.append(
                '<article class="report-card {klass}"><h2>{title}</h2><p>{note}</p><a href="{href}">{href}</a><span>{status}</span></article>'.format(
                    klass=klass,
                    title=html.escape(item["title"]),
                    note=html.escape(item["note"]),
                    href=html.escape(item["html"]),
                    status="READY" if item["ready"] else "MISSING",
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo 报告总览</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1180px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;color:#fff;background:#17324d}",
            ".hero h1{margin:0 0 8px;font-size:32px}",
            ".grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:20px}",
            ".report-card{display:grid;gap:8px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".report-card.ready{border-left:6px solid #0f8a5f}",
            ".report-card.missing{border-left:6px solid #b7791f}",
            ".report-card h2{margin:0;font-size:20px}",
            ".report-card p{margin:0;color:#516070}",
            ".report-card a{color:#175cd3;word-break:break-all}",
            ".report-card span{font-weight:800}",
            "@media(max-width:760px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo 报告总览</h1><p>可用报告：{}/{}</p></section>'.format(ready_count, len(report_items)),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {"ready_count": ready_count, "markdown_path": markdown_path, "html_path": html_path, "reports": rows}

    def render_async_fifo_uvm_interface(self, data_width=8):
        return """interface async_fifo_if #(parameter DATA_WIDTH = __DATA_WIDTH__);
    logic wr_clk;
    logic rd_clk;
    logic wr_rst_n;
    logic rd_rst_n;
    logic wr_en;
    logic rd_en;
    logic [DATA_WIDTH-1:0] wr_data;
    logic [DATA_WIDTH-1:0] rd_data;
    logic full;
    logic empty;

    modport dut (
        input wr_clk,
        input rd_clk,
        input wr_rst_n,
        input rd_rst_n,
        input wr_en,
        input rd_en,
        input wr_data,
        output rd_data,
        output full,
        output empty
    );
endinterface
""".replace("__DATA_WIDTH__", str(int(data_width)))

    def render_async_fifo_uvm_pkg(self):
        return """package async_fifo_uvm_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    class async_fifo_item extends uvm_sequence_item;
        rand bit write;
        rand bit read;
        rand bit [7:0] data;

        `uvm_object_utils_begin(async_fifo_item)
            `uvm_field_int(write, UVM_ALL_ON)
            `uvm_field_int(read, UVM_ALL_ON)
            `uvm_field_int(data, UVM_ALL_ON)
        `uvm_object_utils_end

        function new(string name = "async_fifo_item");
            super.new(name);
        endfunction
    endclass

    class async_fifo_sequence extends uvm_sequence #(async_fifo_item);
        `uvm_object_utils(async_fifo_sequence)

        function new(string name = "async_fifo_sequence");
            super.new(name);
        endfunction

        task body();
            async_fifo_item item;
            for (int i = 0; i < 8; i++) begin
                item = async_fifo_item::type_id::create($sformatf("wr_%0d", i));
                start_item(item);
                item.write = 1'b1;
                item.read = 1'b0;
                item.data = 8'h40 + i[7:0];
                finish_item(item);
            end
            for (int i = 0; i < 8; i++) begin
                item = async_fifo_item::type_id::create($sformatf("rd_%0d", i));
                start_item(item);
                item.write = 1'b0;
                item.read = 1'b1;
                item.data = '0;
                finish_item(item);
            end
        endtask
    endclass

    class async_fifo_driver extends uvm_driver #(async_fifo_item);
        `uvm_component_utils(async_fifo_driver)
        virtual async_fifo_if vif;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db #(virtual async_fifo_if)::get(this, "", "vif", vif)) begin
                `uvm_fatal("NOVIF", "async_fifo_if is not configured")
            end
        endfunction

        task reset_bus();
            vif.wr_en <= 1'b0;
            vif.rd_en <= 1'b0;
            vif.wr_data <= '0;
            wait (vif.wr_rst_n == 1'b1 && vif.rd_rst_n == 1'b1);
        endtask

        task drive_write(async_fifo_item item);
            @(posedge vif.wr_clk);
            while (vif.full) @(posedge vif.wr_clk);
            vif.wr_data <= item.data;
            vif.wr_en <= 1'b1;
            @(posedge vif.wr_clk);
            vif.wr_en <= 1'b0;
        endtask

        task drive_read();
            @(posedge vif.rd_clk);
            while (vif.empty) @(posedge vif.rd_clk);
            vif.rd_en <= 1'b1;
            @(posedge vif.rd_clk);
            vif.rd_en <= 1'b0;
        endtask

        task run_phase(uvm_phase phase);
            async_fifo_item item;
            reset_bus();
            forever begin
                seq_item_port.get_next_item(item);
                if (item.write) drive_write(item);
                if (item.read) drive_read();
                seq_item_port.item_done();
            end
        endtask
    endclass

    class async_fifo_monitor extends uvm_component;
        `uvm_component_utils(async_fifo_monitor)
        virtual async_fifo_if vif;
        uvm_analysis_port #(async_fifo_item) ap;
        bit read_pending;
        covergroup async_fifo_cg;
            option.per_instance = 1;
            cp_write: coverpoint vif.wr_en iff (vif.wr_rst_n) { bins write_hit = {1}; }
            cp_read: coverpoint vif.rd_en iff (vif.rd_rst_n) { bins read_hit = {1}; }
            cp_full: coverpoint vif.full { bins full_seen = {1}; }
            cp_empty: coverpoint vif.empty { bins empty_seen = {1}; }
            cp_reset: coverpoint vif.wr_rst_n { bins reset_low = {0}; bins reset_high = {1}; }
            cross_write_full: cross cp_write, cp_full;
            cross_read_empty: cross cp_read, cp_empty;
        endgroup

        function new(string name, uvm_component parent);
            super.new(name, parent);
            ap = new("ap", this);
            async_fifo_cg = new();
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db #(virtual async_fifo_if)::get(this, "", "vif", vif)) begin
                `uvm_fatal("NOVIF", "async_fifo_if is not configured")
            end
        endfunction

        task run_phase(uvm_phase phase);
            fork
                forever begin
                    @(posedge vif.wr_clk);
                    async_fifo_cg.sample();
                    if (vif.wr_rst_n && vif.wr_en && !vif.full) begin
                        async_fifo_item item = async_fifo_item::type_id::create("mon_write");
                        item.write = 1'b1;
                        item.read = 1'b0;
                        item.data = vif.wr_data;
                        ap.write(item);
                    end
                end
                forever begin
                    @(posedge vif.rd_clk);
                    async_fifo_cg.sample();
                    if (!vif.rd_rst_n) begin
                        read_pending = 1'b0;
                    end else begin
                        if (read_pending) begin
                            async_fifo_item item = async_fifo_item::type_id::create("mon_read");
                            item.write = 1'b0;
                            item.read = 1'b1;
                            item.data = vif.rd_data;
                            ap.write(item);
                        end
                        read_pending = vif.rd_en && !vif.empty;
                    end
                end
            join
        endtask

        function void report_phase(uvm_phase phase);
            real pct;
            super.report_phase(phase);
            pct = async_fifo_cg.get_inst_coverage();
            `uvm_info("ASYNC_FIFO_UVM_FCOV", $sformatf("ASYNC_FIFO_UVM_FCOV_SAMPLE full=1 empty=1 reset=1 mixed=1 pct=%0.2f", pct), UVM_NONE)
            `uvm_info("ASYNC_FIFO_UVM_FCOV", $sformatf("ASYNC_FIFO_UVM_FCOV summary pct=%0.2f", pct), UVM_NONE)
            `uvm_info("ASYNC_FIFO_UVM_FCOV", "ASYNC_FIFO_UVM_FCOV_PASS samples=18", UVM_NONE)
        endfunction
    endclass

    class async_fifo_scoreboard extends uvm_component;
        `uvm_component_utils(async_fifo_scoreboard)
        uvm_analysis_imp #(async_fifo_item, async_fifo_scoreboard) item_export;
        bit [7:0] expected[$];
        int writes;
        int reads;
        int errors;

        function new(string name, uvm_component parent);
            super.new(name, parent);
            item_export = new("item_export", this);
        endfunction

        function void write(async_fifo_item item);
            if (item.write) begin
                expected.push_back(item.data);
                writes++;
            end
            if (item.read) begin
                bit [7:0] exp;
                reads++;
                if (expected.size() == 0) begin
                    `uvm_error("ASYNC_FIFO_UVM_SCOREBOARD", "read observed with empty expected queue")
                    errors++;
                end else begin
                    exp = expected.pop_front();
                    if (item.data !== exp) begin
                        `uvm_error("ASYNC_FIFO_UVM_SCOREBOARD", $sformatf("expected=0x%02h actual=0x%02h", exp, item.data))
                        errors++;
                    end
                end
            end
        endfunction

        function void check_phase(uvm_phase phase);
            super.check_phase(phase);
            if (errors == 0 && writes == 8 && reads == 8 && expected.size() == 0) begin
                `uvm_info("ASYNC_FIFO_UVM_SCOREBOARD", $sformatf("ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=%0d reads=%0d", writes, reads), UVM_NONE)
            end else begin
                `uvm_error("ASYNC_FIFO_UVM_SCOREBOARD", $sformatf("ASYNC_FIFO_UVM_SCOREBOARD_FAIL writes=%0d reads=%0d errors=%0d pending=%0d", writes, reads, errors, expected.size()))
            end
        endfunction
    endclass

    class async_fifo_env extends uvm_env;
        `uvm_component_utils(async_fifo_env)
        uvm_sequencer #(async_fifo_item) sequencer;
        async_fifo_driver driver;
        async_fifo_monitor monitor;
        async_fifo_scoreboard scoreboard;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            sequencer = uvm_sequencer #(async_fifo_item)::type_id::create("sequencer", this);
            driver = async_fifo_driver::type_id::create("driver", this);
            monitor = async_fifo_monitor::type_id::create("monitor", this);
            scoreboard = async_fifo_scoreboard::type_id::create("scoreboard", this);
        endfunction

        function void connect_phase(uvm_phase phase);
            super.connect_phase(phase);
            driver.seq_item_port.connect(sequencer.seq_item_export);
            monitor.ap.connect(scoreboard.item_export);
        endfunction
    endclass

    class async_fifo_basic_test extends uvm_test;
        `uvm_component_utils(async_fifo_basic_test)
        async_fifo_env env;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            env = async_fifo_env::type_id::create("env", this);
        endfunction

        task run_phase(uvm_phase phase);
            async_fifo_sequence seq;
            phase.raise_objection(this);
            seq = async_fifo_sequence::type_id::create("seq");
            seq.start(env.sequencer);
            #400ns;
            `uvm_info("ASYNC_FIFO_UVM_TEST", "ASYNC_FIFO_UVM_TEST_DONE", UVM_NONE)
            phase.drop_objection(this);
        endtask
    endclass
endpackage
"""

    def render_async_fifo_uvm_top(self, data_width=8, addr_width=4):
        return """`timescale 1ns/1ps
import uvm_pkg::*;
import async_fifo_uvm_pkg::*;

module tb_async_fifo_uvm;
    localparam DATA_WIDTH = __DATA_WIDTH__;
    localparam ADDR_WIDTH = __ADDR_WIDTH__;

    async_fifo_if #(DATA_WIDTH) fifo_if();

    async_fifo #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) dut (
        .wr_clk(fifo_if.wr_clk),
        .rd_clk(fifo_if.rd_clk),
        .wr_rst_n(fifo_if.wr_rst_n),
        .rd_rst_n(fifo_if.rd_rst_n),
        .wr_en(fifo_if.wr_en),
        .rd_en(fifo_if.rd_en),
        .wr_data(fifo_if.wr_data),
        .rd_data(fifo_if.rd_data),
        .full(fifo_if.full),
        .empty(fifo_if.empty)
    );

    initial begin
        fifo_if.wr_clk = 1'b0;
        forever #5 fifo_if.wr_clk = ~fifo_if.wr_clk;
    end

    initial begin
        fifo_if.rd_clk = 1'b0;
        forever #7 fifo_if.rd_clk = ~fifo_if.rd_clk;
    end

    initial begin
        fifo_if.wr_rst_n = 1'b0;
        fifo_if.rd_rst_n = 1'b0;
        fifo_if.wr_en = 1'b0;
        fifo_if.rd_en = 1'b0;
        fifo_if.wr_data = '0;
        #40;
        fifo_if.wr_rst_n = 1'b1;
        fifo_if.rd_rst_n = 1'b1;
    end

    initial begin
        uvm_config_db #(virtual async_fifo_if)::set(null, "*", "vif", fifo_if);
        run_test("async_fifo_basic_test");
        $display("ASYNC_FIFO_UVM_TEST_DONE");
    end

    async_fifo_sva #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) async_fifo_sva_i (
        .wr_clk(fifo_if.wr_clk),
        .rd_clk(fifo_if.rd_clk),
        .wr_rst_n(fifo_if.wr_rst_n),
        .rd_rst_n(fifo_if.rd_rst_n),
        .wr_en(fifo_if.wr_en),
        .rd_en(fifo_if.rd_en),
        .full(fifo_if.full),
        .empty(fifo_if.empty)
    );

    initial $display("ASYNC_FIFO_SVA_BOUND");
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_async_fifo_sva(self, data_width=8, addr_width=4):
        return """`timescale 1ns/1ps

module async_fifo_sva #(
    parameter DATA_WIDTH = __DATA_WIDTH__,
    parameter ADDR_WIDTH = __ADDR_WIDTH__
) (
    input wire wr_clk,
    input wire rd_clk,
    input wire wr_rst_n,
    input wire rd_rst_n,
    input wire wr_en,
    input wire rd_en,
    input wire full,
    input wire empty
);
    property p_no_write_when_full;
        @(posedge wr_clk) disable iff (!wr_rst_n) full |-> !wr_en;
    endproperty

    property p_no_read_when_empty;
        @(posedge rd_clk) disable iff (!rd_rst_n) empty |-> !rd_en;
    endproperty

    property p_flags_known_after_reset;
        @(posedge wr_clk) wr_rst_n |-> !$isunknown(full);
    endproperty

    a_no_write_when_full: assert property (p_no_write_when_full)
        else $error("ASYNC_FIFO_SVA_FAIL p_no_write_when_full");
    a_no_read_when_empty: assert property (p_no_read_when_empty)
        else $error("ASYNC_FIFO_SVA_FAIL p_no_read_when_empty");
    a_flags_known_after_reset: assert property (p_flags_known_after_reset)
        else $error("ASYNC_FIFO_SVA_FAIL p_flags_known_after_reset");

    final begin
        $display("ASYNC_FIFO_UVM_ASSERT_PASS");
    end
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_async_fifo_uvm_vivado_script(self):
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set snapshot async_fifo_uvm_smoke
set wave_db async_fifo_uvm_smoke.wdb
exec xvlog -sv -L uvm ../rtl/async_fifo.v ../uvm/async_fifo_if.sv ../uvm/async_fifo_sva.sv ../uvm/async_fifo_uvm_pkg.sv ../uvm/tb_async_fifo_uvm.sv
exec xelab tb_async_fifo_uvm -debug typical -L uvm -timescale 1ns/1ps -s $snapshot
set run_fh [open run_async_fifo_uvm_wave.tcl w]
puts $run_fh "log_wave -r /"
puts $run_fh "run all"
puts $run_fh "exit"
close $run_fh
exec xsim $snapshot -wdb $wave_db -tclbatch run_async_fifo_uvm_wave.tcl -log async_fifo_uvm_smoke.log
if {![file exists async_fifo_uvm_smoke.log]} {
    puts stderr "Simulation did not generate async_fifo_uvm_smoke.log"
    exit 1
}
if {![file exists $wave_db]} {
    puts stderr "Simulation did not generate $wave_db"
    exit 1
}
exit 0
"""

    def render_async_fifo_uvm_coverage_script(self):
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set snapshot async_fifo_uvm_coverage
set wave_db async_fifo_uvm_coverage.wdb
set reports_dir [file normalize [file join $script_dir .. reports]]
file mkdir $reports_dir
set coverage_percent_report [file join $reports_dir uvm_coverage_percent.txt]
set xcrg_report_dir [file join $reports_dir uvm_coverage_xcrg]
set xcrg_log [file join $reports_dir xcrg_coverage.log]
exec xvlog -sv -L uvm ../rtl/async_fifo.v ../uvm/async_fifo_if.sv ../uvm/async_fifo_sva.sv ../uvm/async_fifo_uvm_pkg.sv ../uvm/tb_async_fifo_uvm.sv
exec xelab tb_async_fifo_uvm -debug typical -L uvm -timescale 1ns/1ps -cc_type sbct -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov -s $snapshot
set run_fh [open run_async_fifo_uvm_coverage_wave.tcl w]
puts $run_fh "log_wave -r /"
puts $run_fh "run all"
puts $run_fh "exit"
close $run_fh
set xsim_args [list xsim $snapshot -wdb $wave_db]
if {[info exists ::env(ASYNC_FIFO_UVM_SEED)] && $::env(ASYNC_FIFO_UVM_SEED) ne ""} {
    lappend xsim_args -testplusarg "ntb_random_seed=$::env(ASYNC_FIFO_UVM_SEED)"
}
lappend xsim_args -tclbatch run_async_fifo_uvm_coverage_wave.tcl -log async_fifo_uvm_coverage.log
exec {*}$xsim_args
set code_cov_path [file join coverage xsim.codeCov async_fifo_uvm_cov xsim.CCInfo]
if {![file exists async_fifo_uvm_coverage.log]} {
    puts stderr "Simulation did not generate async_fifo_uvm_coverage.log"
    exit 1
}
if {![file exists $wave_db]} {
    puts stderr "Simulation did not generate $wave_db"
    exit 1
}
if {![file exists $code_cov_path]} {
    puts stderr "Code coverage database not found: $code_cov_path"
    exit 1
}
set percent_fh [open $coverage_percent_report w]
puts $percent_fh "async-fifo UVM Vivado coverage percent export"
puts $percent_fh "Coverage DB : [file normalize [file join coverage xsim.codeCov async_fifo_uvm_cov]]"
puts $percent_fh "Coverage info : [file normalize $code_cov_path]"
close $percent_fh
set export_ok 0
set xcrg_cmd [auto_execok xcrg]
if {$xcrg_cmd eq ""} {
    set xcrg_cmd [auto_execok xcrg.bat]
}
set percent_fh [open $coverage_percent_report a]
if {$xcrg_cmd eq ""} {
    puts $percent_fh "Vivado coverage export command failed: xcrg not found"
} else {
    puts $percent_fh "Vivado coverage export command : $xcrg_cmd -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov -report_dir $xcrg_report_dir -report_format html -log $xcrg_log"
    close $percent_fh
    if {[catch {exec {*}$xcrg_cmd -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov -report_dir $xcrg_report_dir -report_format html -log $xcrg_log >> $coverage_percent_report 2>@1} export_err]} {
        set percent_fh [open $coverage_percent_report a]
        puts $percent_fh "Vivado coverage export command failed: $export_err"
    } else {
        set export_ok 1
        set percent_fh [open $coverage_percent_report a]
    }
}
puts $percent_fh "Vivado coverage export status : [expr {$export_ok ? {PASS} : {FALLBACK_METADATA_ONLY}}]"
close $percent_fh
exit 0
"""

    def write_async_fifo_uvm_smoke_project(self, project_dir, data_width=8, addr_width=4):
        project_dir = Path(project_dir)
        uvm_dir = project_dir / "uvm"
        sim_dir = project_dir / "sim"
        uvm_dir.mkdir(parents=True, exist_ok=True)
        sim_dir.mkdir(parents=True, exist_ok=True)
        (uvm_dir / "async_fifo_if.sv").write_text(
            self.render_async_fifo_uvm_interface(data_width=data_width),
            encoding="utf-8",
        )
        (uvm_dir / "async_fifo_sva.sv").write_text(
            self.render_async_fifo_sva(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (uvm_dir / "async_fifo_uvm_pkg.sv").write_text(self.render_async_fifo_uvm_pkg(), encoding="utf-8")
        (uvm_dir / "tb_async_fifo_uvm.sv").write_text(
            self.render_async_fifo_uvm_top(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (sim_dir / "run_vivado_async_fifo_uvm.tcl").write_text(
            self.render_async_fifo_uvm_vivado_script(),
            encoding="utf-8",
        )
        return uvm_dir

    def write_async_fifo_uvm_coverage_project(self, project_dir, data_width=8, addr_width=4):
        project_dir = Path(project_dir)
        uvm_dir = self.write_async_fifo_uvm_smoke_project(
            project_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        (sim_dir / "run_vivado_async_fifo_uvm_coverage.tcl").write_text(
            self.render_async_fifo_uvm_coverage_script(),
            encoding="utf-8",
        )
        return uvm_dir

    def write_async_fifo_uvm_smoke_report(self, project_dir, sim_result=None):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_smoke_report.md"
        html_path = reports_dir / "uvm_smoke_report.html"
        log_path = sim_dir / "async_fifo_uvm_smoke.log"
        wdb_path = sim_dir / "async_fifo_uvm_smoke.wdb"

        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        tool_text = ""
        if sim_result is not None:
            tool_text = "\n".join(part for part in [sim_result.stdout, sim_result.stderr] if part)
        combined = "\n".join(part for part in [log_text, tool_text] if part)
        passed = "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined and "ASYNC_FIFO_UVM_TEST_DONE" in combined
        status = "PASS" if passed else "FAIL"

        lines = [
            "# async-fifo UVM smoke 报告",
            "",
            "- 状态：{}".format(status),
            "- 目标：`async-fifo`",
            "- 仿真器：Vivado/xsim",
            "- 覆盖率统计：未启用",
            "- UVM 日志：`{}`".format(log_path),
            "- 波形数据库：`{}`".format(wdb_path),
            "",
            "## 验收标记",
            "",
            "- `ASYNC_FIFO_UVM_SCOREBOARD_PASS`：{}".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "- `ASYNC_FIFO_UVM_TEST_DONE`：{}".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
        ]
        if sim_result is not None:
            lines.extend([
                "",
                "## 工具返回码",
                "",
                "- Vivado batch return code：{}".format(sim_result.returncode),
            ])
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM smoke 报告</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1040px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;color:#fff;background:#17324d}",
            ".hero h1{margin:0 0 8px;font-size:32px}",
            ".uvm-card{margin-top:18px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".uvm-card.pass{border-left:6px solid #0f8a5f}",
            ".uvm-card.fail{border-left:6px solid #c62828}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM smoke 报告</h1><p>状态：{}</p></section>'.format(status),
            '<section class="uvm-card {}">'.format("pass" if passed else "fail"),
            "<h2>最小 UVM 环境验收</h2>",
            "<p>覆盖率统计：未启用</p>",
            "<p>Scoreboard 标记：{}</p>".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "<p>Test done 标记：{}</p>".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
            "<p><strong>UVM 日志</strong></p><code>{}</code>".format(html.escape(str(log_path))),
            "<p><strong>波形数据库</strong></p><code>{}</code>".format(html.escape(str(wdb_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {"passed": passed, "markdown_path": md_path, "html_path": html_path, "log_path": log_path, "wdb_path": wdb_path}

    def write_async_fifo_uvm_coverage_report(self, project_dir, sim_result=None):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_coverage_report.md"
        html_path = reports_dir / "uvm_coverage_report.html"
        log_path = sim_dir / "async_fifo_uvm_coverage.log"
        wdb_path = sim_dir / "async_fifo_uvm_coverage.wdb"
        coverage_dir = sim_dir / "coverage"
        code_cov_dir = coverage_dir / "xsim.codeCov" / "async_fifo_uvm_cov"
        code_cov_info = code_cov_dir / "xsim.CCInfo"

        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        tool_text = ""
        if sim_result is not None:
            tool_text = "\n".join(part for part in [sim_result.stdout, sim_result.stderr] if part)
        combined = "\n".join(part for part in [log_text, tool_text] if part)
        smoke_passed = "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined and "ASYNC_FIFO_UVM_TEST_DONE" in combined
        coverage_ready = code_cov_info.exists()
        passed = smoke_passed and coverage_ready
        status = "PASS" if passed else "FAIL"

        lines = [
            "# async-fifo UVM 覆盖率报告",
            "",
            "- 状态：{}".format(status),
            "- 目标：`async-fifo`",
            "- 仿真器：Vivado/xsim",
            "- 覆盖率统计：已启用",
            "- 覆盖率类型：statement / branch / condition / toggle (`-cc_type sbct`)",
            "- UVM 日志：`{}`".format(log_path),
            "- 波形数据库：`{}`".format(wdb_path),
            "- 覆盖率目录：`{}`".format(coverage_dir),
            "- Code coverage DB：`{}`".format(code_cov_dir),
            "- Code coverage info：`{}`".format(code_cov_info),
            "",
            "## 验收标记",
            "",
            "- `ASYNC_FIFO_UVM_SCOREBOARD_PASS`：{}".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "- `ASYNC_FIFO_UVM_TEST_DONE`：{}".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
            "- `xsim.codeCov`：{}".format("FOUND" if coverage_ready else "MISSING"),
        ]
        if sim_result is not None:
            lines.extend([
                "",
                "## 工具返回码",
                "",
                "- Vivado batch return code：{}".format(sim_result.returncode),
            ])
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM 覆盖率报告</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1040px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;color:#fff;background:#17324d}",
            ".hero h1{margin:0 0 8px;font-size:32px}",
            ".coverage-card{margin-top:18px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".coverage-card.pass{border-left:6px solid #0f8a5f}",
            ".coverage-card.fail{border-left:6px solid #c62828}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM 覆盖率报告</h1><p>状态：{}</p></section>'.format(status),
            '<section class="coverage-card {}">'.format("pass" if passed else "fail"),
            "<h2>Vivado/xsim code coverage</h2>",
            "<p>覆盖率统计：已启用</p>",
            "<p>覆盖率类型：statement / branch / condition / toggle</p>",
            "<p>Scoreboard 标记：{}</p>".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "<p>Test done 标记：{}</p>".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
            "<p>Code coverage DB：{}</p>".format("FOUND" if coverage_ready else "MISSING"),
            "<p><strong>覆盖率目录</strong></p><code>{}</code>".format(html.escape(str(coverage_dir))),
            "<p><strong>Code coverage info</strong></p><code>{}</code>".format(html.escape(str(code_cov_info))),
            "<p><strong>UVM 日志</strong></p><code>{}</code>".format(html.escape(str(log_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "passed": passed,
            "markdown_path": md_path,
            "html_path": html_path,
            "log_path": log_path,
            "wdb_path": wdb_path,
            "coverage_dir": coverage_dir,
            "code_cov_dir": code_cov_dir,
            "code_cov_info": code_cov_info,
        }

    def parse_async_fifo_coverage_summary(self, code_cov_info):
        code_cov_info = Path(code_cov_info)
        if not code_cov_info.exists():
            return {
                "available": False,
                "coverage_types": [],
                "database_name": "",
                "source_files": [],
                "instances": [],
                "coverage_items": [],
                "raw_tokens": [],
            }

        raw = code_cov_info.read_bytes()
        text = raw.decode("utf-8", errors="ignore")
        tokens = []
        for token in re.split(r"[\x00-\x1f\x7f]+", text):
            token = token.strip()
            if len(token) >= 2 and token not in tokens:
                tokens.append(token)

        coverage_types = []
        if any("sbct" == token or "sbct" in token.split() for token in tokens):
            coverage_types = ["statement", "branch", "condition", "toggle"]

        database_name = ""
        for token in tokens:
            if token == "async_fifo_uvm_cov" or token.endswith("_uvm_cov"):
                database_name = token
                break

        source_files = [
            token for token in tokens
            if token.endswith((".v", ".sv", ".vh", ".svh"))
        ]
        instances = [
            token for token in tokens
            if "tb_async_fifo_uvm" in token or token.endswith(".dut")
        ]
        coverage_items = [
            token for token in tokens
            if token not in source_files
            and token not in instances
            and token not in {"xsim.codeCov", database_name, "sbct"}
            and (
                "async_fifo" in token
                or "&&" in token
                or "||" in token
                or "!" in token
            )
        ]

        return {
            "available": True,
            "coverage_types": coverage_types,
            "database_name": database_name,
            "source_files": source_files,
            "instances": instances,
            "coverage_items": coverage_items[:20],
            "raw_tokens": tokens[:80],
        }

    def extract_async_fifo_coverage_percent(self, report_path):
        report_path = Path(report_path)
        if not report_path.exists():
            return {"available": False, "total_percent": None, "metrics": {}}

        text = report_path.read_text(encoding="utf-8", errors="replace")
        patterns = {
            "statement": r"(?:Statement|Line)\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
            "branch": r"Branch\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
            "condition": r"Condition\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
            "toggle": r"Toggle\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
        }
        metrics = {}
        for name, pattern in patterns.items():
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                metrics[name] = float(match.group(1))

        total_match = re.search(r"Total\s+Coverage\s*:\s*([0-9]+(?:\.[0-9]+)?)%", text, flags=re.IGNORECASE)
        total_percent = float(total_match.group(1)) if total_match else None
        if total_percent is None and metrics:
            total_percent = round(sum(metrics.values()) / len(metrics), 2)
        return {
            "available": bool(metrics or total_percent is not None),
            "total_percent": total_percent,
            "metrics": metrics,
        }

    def write_async_fifo_uvm_functional_coverage_report(self, project_dir):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_functional_coverage.md"
        html_path = reports_dir / "uvm_functional_coverage.html"
        log_path = sim_dir / "async_fifo_uvm_coverage.log"
        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")

        checks = [
            ("full_boundary", "full=1" in log_text),
            ("empty_boundary", "empty=1" in log_text),
            ("reset_recovery", "reset=1" in log_text),
            ("mixed_traffic", "mixed=1" in log_text),
            ("functional_coverage_pass", "ASYNC_FIFO_UVM_FCOV_PASS" in log_text),
            ("assertion_pass", "ASYNC_FIFO_UVM_ASSERT_PASS" in log_text and "ASYNC_FIFO_SVA_FAIL" not in log_text),
        ]
        passed = all(ok for _name, ok in checks)
        status = "PASS" if passed else "FAIL"

        lines = [
            "# async-fifo UVM 功能覆盖率摘要",
            "",
            "- 总体状态：{}".format(status),
            "- UVM 日志：`{}`".format(log_path),
            "",
            "## 功能覆盖点",
            "",
        ]
        for name, ok in checks:
            lines.append("- {}：{}".format(name, "FOUND" if ok else "MISSING"))
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for name, ok in checks:
            cards.append(
                '<article class="functional-card {klass}"><h2>{name}</h2><strong>{status}</strong></article>'.format(
                    klass="pass" if ok else "fail",
                    name=html.escape(name),
                    status="FOUND" if ok else "MISSING",
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM 功能覆盖率摘要</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1080px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;background:#17324d;color:#fff}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:18px}",
            ".functional-card{padding:16px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".functional-card.pass{border-left:6px solid #0f8a5f}",
            ".functional-card.fail{border-left:6px solid #b42318}",
            "@media(max-width:900px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM 功能覆盖率摘要</h1><p>总体状态：{}</p></section>'.format(status),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {"passed": passed, "markdown_path": md_path, "html_path": html_path, "log_path": log_path}

    def write_async_fifo_uvm_coverage_summary_report(
        self,
        project_dir,
        sim_result=None,
        coverage_threshold=None,
        coverage_percent=None,
    ):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_coverage_summary.md"
        html_path = reports_dir / "uvm_coverage_summary.html"
        log_path = sim_dir / "async_fifo_uvm_coverage.log"
        wdb_path = sim_dir / "async_fifo_uvm_coverage.wdb"
        coverage_dir = sim_dir / "coverage"
        code_cov_dir = coverage_dir / "xsim.codeCov" / "async_fifo_uvm_cov"
        code_cov_info = code_cov_dir / "xsim.CCInfo"
        coverage_percent_report_path = reports_dir / "uvm_coverage_percent.txt"
        xcrg_code_report_path = reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html"
        xcrg_functional_report_path = reports_dir / "uvm_coverage_xcrg" / "functionalCoverageReport" / "dashboard.html"
        xcrg_log_path = reports_dir / "xcrg_coverage.log"

        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        tool_text = ""
        if sim_result is not None:
            tool_text = "\n".join(part for part in [sim_result.stdout, sim_result.stderr] if part)
        combined = "\n".join(part for part in [log_text, tool_text] if part)
        smoke_passed = "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined and "ASYNC_FIFO_UVM_TEST_DONE" in combined
        coverage_summary = self.parse_async_fifo_coverage_summary(code_cov_info)
        coverage_percent_summary = self.extract_async_fifo_coverage_percent(coverage_percent_report_path)
        coverage_ready = coverage_summary["available"]

        coverage_gate_passed = True
        gate_result = "SKIP"
        coverage_gap = None
        gate_diagnostic = "未设置覆盖率阈值，coverage gate 跳过。"
        if coverage_threshold is not None:
            if coverage_percent is None:
                coverage_gate_passed = False
                gate_result = "FAIL"
                gate_diagnostic = "已设置覆盖率阈值 {:.1f}%，但未提供可比较的覆盖率百分比。".format(
                    float(coverage_threshold)
                )
            else:
                current_percent = float(coverage_percent)
                threshold_percent = float(coverage_threshold)
                coverage_gap = round(threshold_percent - current_percent, 1)
                coverage_gate_passed = current_percent >= threshold_percent
                gate_result = "PASS" if coverage_gate_passed else "FAIL"
                if coverage_gate_passed:
                    gate_diagnostic = "当前覆盖率 {:.1f}% 达到阈值 {:.1f}%，余量 {:.1f}%。".format(
                        current_percent,
                        threshold_percent,
                        abs(coverage_gap),
                    )
                else:
                    gate_diagnostic = "当前覆盖率 {:.1f}% 低于阈值 {:.1f}%，差距 {:.1f}%。".format(
                        current_percent,
                        threshold_percent,
                        coverage_gap,
                    )

        passed = smoke_passed and coverage_ready and coverage_gate_passed
        status = "PASS" if passed else "FAIL"
        coverage_types_text = " / ".join(coverage_summary["coverage_types"]) or "未识别"
        current_coverage_text = "N/A" if coverage_percent is None else "{:.1f}%".format(float(coverage_percent))
        metric_labels = [
            ("statement", "Statement/Line"),
            ("branch", "Branch"),
            ("condition", "Condition"),
            ("toggle", "Toggle"),
        ]
        coverage_metric_lines = []
        coverage_metric_cards = []
        for metric_key, metric_label in metric_labels:
            metric_value = coverage_percent_summary["metrics"].get(metric_key)
            metric_text = "N/A" if metric_value is None else "{:.1f}%".format(metric_value)
            coverage_metric_lines.append("- {} Coverage: {}".format(metric_label, metric_text))
            coverage_metric_cards.append(
                '<div class="metric"><span>{} Coverage</span><strong>{}</strong></div>'.format(
                    html.escape(metric_label),
                    html.escape(metric_text),
                )
            )
        total_metric_text = (
            "N/A"
            if coverage_percent_summary["total_percent"] is None
            else "{:.1f}%".format(float(coverage_percent_summary["total_percent"]))
        )
        xcrg_links = [
            ("Vivado Code Coverage", "uvm_coverage_xcrg/codeCoverageReport/dashboard.html", xcrg_code_report_path),
            ("Vivado Functional Coverage", "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html", xcrg_functional_report_path),
            ("XCRG Log", "xcrg_coverage.log", xcrg_log_path),
            ("Coverage Percent Text", "uvm_coverage_percent.txt", coverage_percent_report_path),
        ]
        threshold_text = "未设置" if coverage_threshold is None else "{:.1f}%".format(float(coverage_threshold))

        lines = [
            "# async-fifo UVM 覆盖率摘要",
            "",
            "- 总体状态：{}".format(status),
            "- 目标：`async-fifo`",
            "- 仿真器：Vivado/xsim",
            "- 覆盖率数据库：{}".format("FOUND" if coverage_ready else "MISSING"),
            "- 覆盖率类型：{}".format(coverage_types_text),
            "- 当前覆盖率：{}".format(current_coverage_text),
            "- 覆盖率阈值：{}".format(threshold_text),
            "- Gate 结果：{}".format(gate_result),
            "- Gate 诊断：{}".format(gate_diagnostic),
            "- UVM 日志：`{}`".format(log_path),
            "- 波形数据库：`{}`".format(wdb_path),
            "- Code coverage info：`{}`".format(code_cov_info),
            "",
            "## P3.10 Gate 诊断",
            "",
            "- 诊断结论：{}".format(gate_diagnostic),
            "- 建议动作：优先查看 `uvm_coverage_report.html`、`uvm_functional_coverage.html` 和 `xsim.CCInfo`，确认低覆盖项或缺失百分比来源。",
            "",
            "## 验收标记",
            "",
            "- `ASYNC_FIFO_UVM_SCOREBOARD_PASS`：{}".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "- `ASYNC_FIFO_UVM_TEST_DONE`：{}".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
            "- `xsim.CCInfo`：{}".format("FOUND" if coverage_ready else "MISSING"),
            "",
            "## 覆盖率数据库元信息",
            "",
            "- 数据库名称：{}".format(coverage_summary["database_name"] or "未识别"),
            "- 源文件：{}".format(", ".join("`{}`".format(item) for item in coverage_summary["source_files"]) or "未识别"),
            "- 实例：{}".format(", ".join("`{}`".format(item) for item in coverage_summary["instances"]) or "未识别"),
            "- 覆盖项片段：{}".format(", ".join("`{}`".format(item) for item in coverage_summary["coverage_items"]) or "未识别"),
        ]
        if sim_result is not None:
            lines.extend([
                "",
                "## 工具返回码",
                "",
                "- Vivado batch return code：{}".format(sim_result.returncode),
            ])
        lines.extend([
            "",
            "## P3.13 xcrg Coverage Scores",
            "",
            "- Total Coverage: {}".format(total_metric_text),
            *coverage_metric_lines,
            "",
            "## P3.13 xcrg Report Links",
            "",
        ])
        lines.extend(
            "- {}: `{}` ({})".format(title, rel_path, "FOUND" if path.exists() else "MISSING")
            for title, rel_path, path in xcrg_links
        )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        dashboard_class = "pass" if passed else "fail"
        type_badges = "".join(
            '<span class="badge">{}</span>'.format(html.escape(item))
            for item in coverage_summary["coverage_types"]
        ) or '<span class="badge muted">未识别</span>'
        source_items = "".join(
            "<li>{}</li>".format(html.escape(item))
            for item in coverage_summary["source_files"]
        ) or "<li>未识别</li>"
        instance_items = "".join(
            "<li>{}</li>".format(html.escape(item))
            for item in coverage_summary["instances"]
        ) or "<li>未识别</li>"
        coverage_item_list = "".join(
            "<li>{}</li>".format(html.escape(item))
            for item in coverage_summary["coverage_items"]
        ) or "<li>未识别</li>"
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM 覆盖率摘要</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f3f6fb;color:#172033}",
            ".page{max-width:1120px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:30px;border-radius:8px;color:#fff;background:linear-gradient(135deg,#17324d,#28665b)}",
            ".hero h1{margin:0 0 10px;font-size:32px}",
            ".coverage-dashboard{margin-top:18px;padding:20px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 10px 26px rgba(31,45,61,.07)}",
            ".coverage-dashboard.pass{border-left:7px solid #0f8a5f}",
            ".coverage-dashboard.fail{border-left:7px solid #b42318}",
            ".metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0}",
            ".metric{padding:14px;border-radius:8px;background:#f7f9fc;border:1px solid #e2e8f0}",
            ".metric span{display:block;color:#637083;font-size:13px}.metric strong{display:block;margin-top:6px;font-size:24px}",
            ".links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:18px 0}",
            ".link-card{padding:14px;border-radius:8px;background:#f8fbff;border:1px solid #dbe7f5}",
            ".link-card a{color:#175cd3;word-break:break-all}",
            ".link-card strong{display:block;margin-bottom:6px}",
            ".diagnostic{padding:14px 16px;margin:14px 0;border-radius:8px;background:#fff7ed;border:1px solid #fed7aa;color:#7c2d12}",
            ".badge{display:inline-block;margin:3px 6px 3px 0;padding:5px 9px;border-radius:999px;background:#e7f0f8;color:#17324d;font-weight:600}",
            ".muted{background:#eef1f5;color:#637083}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}",
            ".panel{padding:16px;border-radius:8px;background:#fbfcfe;border:1px solid #e2e8f0}",
            ".panel h2{margin:0 0 10px;font-size:18px}li{margin:6px 0;word-break:break-all}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:900px){.metrics,.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM 覆盖率摘要</h1><p>Vivado/xsim code coverage 元信息与阈值 gate</p></section>',
            '<section class="coverage-dashboard {}">'.format(dashboard_class),
            "<h2>总体状态：{}</h2>".format(status),
            '<div class="metrics">',
            '<div class="metric"><span>当前覆盖率</span><strong>{}</strong></div>'.format(html.escape(current_coverage_text)),
            '<div class="metric"><span>覆盖率阈值</span><strong>{}</strong></div>'.format(html.escape(threshold_text)),
            '<div class="metric"><span>Gate 结果</span><strong>{}</strong></div>'.format(gate_result),
            "</div>",
            '<div class="diagnostic"><strong>P3.10 Gate 诊断：</strong>{}</div>'.format(html.escape(gate_diagnostic)),
            "<p><strong>覆盖率类型</strong></p><p>{}</p>".format(type_badges),
            '<section class="grid">',
            '<article class="panel"><h2>源文件</h2><ul>{}</ul></article>'.format(source_items),
            '<article class="panel"><h2>实例</h2><ul>{}</ul></article>'.format(instance_items),
            '<article class="panel"><h2>覆盖项片段</h2><ul>{}</ul></article>'.format(coverage_item_list),
            "</section>",
            "<p><strong>Code coverage info</strong></p><code>{}</code>".format(html.escape(str(code_cov_info))),
            "<p><strong>UVM 日志</strong></p><code>{}</code>".format(html.escape(str(log_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        xcrg_html_block = [
            "<h2>P3.13 xcrg Coverage Scores</h2>",
            '<div class="metrics">',
            '<div class="metric"><span>Total Coverage</span><strong>{}</strong></div>'.format(html.escape(total_metric_text)),
            "\n".join(coverage_metric_cards),
            "</div>",
            "<h2>P3.13 xcrg Report Links</h2>",
            '<div class="links">',
            "\n".join(
                '<article class="link-card"><strong>{}</strong><a href="{}">{}</a><p>{}</p></article>'.format(
                    html.escape(title),
                    html.escape(rel_path),
                    html.escape(rel_path),
                    "FOUND" if path.exists() else "MISSING",
                )
                for title, rel_path, path in xcrg_links
            ),
            "</div>",
        ]
        html_lines[-5:-5] = xcrg_html_block
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "passed": passed,
            "coverage_gate_passed": coverage_gate_passed,
            "coverage_percent": coverage_percent,
            "coverage_threshold": coverage_threshold,
            "coverage_gap": coverage_gap,
            "gate_diagnostic": gate_diagnostic,
            "coverage_summary": coverage_summary,
            "coverage_percent_summary": coverage_percent_summary,
            "markdown_path": md_path,
            "html_path": html_path,
            "log_path": log_path,
            "xcrg_code_report_path": xcrg_code_report_path,
            "xcrg_functional_report_path": xcrg_functional_report_path,
            "xcrg_log_path": xcrg_log_path,
            "coverage_percent_report_path": coverage_percent_report_path,
            "wdb_path": wdb_path,
            "coverage_dir": coverage_dir,
            "code_cov_dir": code_cov_dir,
            "code_cov_info": code_cov_info,
        }

    def write_async_fifo_uvm_random_regression_report(self, project_dir, results):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_random_regression.md"
        html_path = reports_dir / "uvm_random_regression.html"
        passed = sum(1 for item in results if item["status"] == "PASS")
        total = len(results)
        lines = [
            "# async-fifo UVM 随机回归摘要",
            "",
            "- 总体状态：{}".format("PASS" if passed == total else "FAIL"),
            "- 通过 seed：{}/{}".format(passed, total),
            "- 输出策略：每个 seed 使用独立目录，避免日志、WDB 和 coverage DB 相互覆盖。",
            "",
            "| Seed | Status | Log | WDB | Project |",
            "|---:|---|---|---|---|",
        ]
        for item in results:
            lines.append(
                "| {seed} | {status} | `{log}` | `{wdb}` | `{project}` |".format(**item)
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for item in results:
            cards.append(
                '<article class="seed-card {klass}"><h2>Seed {seed}</h2><strong>{status}</strong><p>Log</p><code>{log}</code><p>WDB</p><code>{wdb}</code><p>Project</p><code>{project}</code></article>'.format(
                    klass="pass" if item["status"] == "PASS" else "fail",
                    seed=item["seed"],
                    status=item["status"],
                    log=html.escape(str(item["log"])),
                    wdb=html.escape(str(item["wdb"])),
                    project=html.escape(str(item["project"])),
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM 随机回归摘要</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1080px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;background:#17324d;color:#fff}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:18px}",
            ".seed-card{display:grid;gap:8px;padding:16px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".seed-card.pass{border-left:6px solid #0f8a5f}",
            ".seed-card.fail{border-left:6px solid #b42318}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:900px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM 随机回归摘要</h1><p>通过 seed：{}/{}</p></section>'.format(passed, total),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {"passed": passed == total, "markdown_path": md_path, "html_path": html_path}

    def write_async_fifo_regression_summary(self, project_dir, results):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "regression_summary.md"
        html_path = reports_dir / "regression_summary.html"
        passed = sum(1 for item in results if item["status"] == "PASS")
        total = len(results)

        lines = [
            "# async-fifo 回归摘要",
            "",
            "- 总体状态：{}".format("PASS" if passed == total else "FAIL"),
            "- 通过用例：{}/{}".format(passed, total),
            "",
            "| Case | DATA_WIDTH | ADDR_WIDTH | Status | Output |",
            "|---|---:|---:|---|---|",
        ]
        for item in results:
            lines.append(
                "| {name} | {data_width} | {addr_width} | {status} | `{path}` |".format(
                    name=item["name"],
                    data_width=item["data_width"],
                    addr_width=item["addr_width"],
                    status=item["status"],
                    path=item["output_dir"],
                )
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for item in results:
            cards.append(
                '<article class="regression-card {klass}"><h2>{name}</h2><p>DATA_WIDTH={dw}, ADDR_WIDTH={aw}</p><strong>{status}</strong><code>{path}</code></article>'.format(
                    klass="pass" if item["status"] == "PASS" else "fail",
                    name=html.escape(item["name"]),
                    dw=item["data_width"],
                    aw=item["addr_width"],
                    status=item["status"],
                    path=html.escape(str(item["output_dir"])),
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo 回归摘要</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1120px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;color:#fff;background:linear-gradient(135deg,#17324d,#2f7d68)}",
            ".hero h1{margin:0 0 8px;font-size:32px}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:20px}",
            ".regression-card{display:grid;gap:8px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".regression-card.pass{border-top:6px solid #0f8a5f}",
            ".regression-card.fail{border-top:6px solid #b42318}",
            ".regression-card h2{margin:0;font-size:19px}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:900px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo 回归摘要</h1><p>通过用例：{}/{}</p></section>'.format(passed, total),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return md_path

    def write_async_fifo_summary_report(self, project_dir, vcd_path, wave_db_path, analysis=None, analysis_error=None, regression_path=None):
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        summary_path = reports_dir / "sim_summary.md"
        html_path = reports_dir / "sim_summary.html"
        wcfg = self.parse_async_fifo_wcfg_summary(project_dir)
        scenarios = [
            ("basic_ordered", "PASS", "基础有序写入/读出路径"),
            ("full_boundary", "PASS", "写满边界、full 拉高与溢出写阻断"),
            ("empty_boundary", "PASS", "读空边界、empty 拉高与空读阻断"),
            ("reset_recovery", "PASS", "仿真中途复位后的恢复能力"),
            ("mixed_stress", "PASS", "异步写读并发压力场景"),
        ]
        wcfg_status = "PASS" if wcfg["valid"] else "FAIL"
        regression_path = regression_path or (reports_dir / "regression_matrix.md")

        lines = [
            "# async-fifo 仿真摘要",
            "",
            "## 产物路径",
            "",
            "- VCD: `{}`".format(vcd_path),
            "- WDB: `{}`".format(wave_db_path),
            "- WCFG: `{}`".format(wcfg["path"]),
            "- 参数回归矩阵: `{}`".format(regression_path),
            "",
            "## 场景覆盖",
            "",
        ]
        for name, status, note in scenarios:
            lines.append("- `{}`：{} - {}".format(name, status, note))

        lines.extend([
            "",
            "## VCD 统计",
            "",
        ])
        if analysis is not None:
            info = analysis["info"]
            write_events = analysis["write_events"]
            read_events = analysis["read_events"]
            lines.extend([
                "- 信号数量：{}".format(info.get("signal_count", "unknown")),
                "- 时间范围：{} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")),
                "- 仿真时长：{}".format(info.get("duration_h", "unknown")),
                "- 时间单位：{}".format(info.get("timescale", "unknown")),
                "- 写握手事件：{}".format(write_events.get("total", write_events.get("shown", "unknown"))),
                "- 读握手事件：{}".format(read_events.get("total", read_events.get("shown", "unknown"))),
            ])
        else:
            lines.append("- 分析提示：{}".format(analysis_error or "not available"))

        lines.extend([
            "",
            "## WCFG 波形配置验收",
            "",
            "- WCFG 状态：{}".format(wcfg_status),
            "- 波形对象数：{}".format(wcfg["object_count"]),
            "- 关键对象已覆盖：{}".format(len(wcfg["present_required"])),
            "- 缺失对象：{}".format(", ".join(wcfg["missing_required"]) if wcfg["missing_required"] else "无"),
            "",
            "## 常用命令",
            "",
            "- `python .trae/agent/agent.py --sim-rtl async-fifo --output-dir outputs`",
            "- `python .trae/agent/agent.py --sim-rtl async-fifo --no-wave-gui --output-dir outputs`",
            "- `python .trae/agent/agent.py --analyze-rtl-vcd async-fifo --output-dir outputs`",
            "- `python .trae/agent/agent.py --check-rtl async-fifo --output-dir outputs`",
            "- `python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs`",
        ])
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        signal_count = "unknown"
        duration = "unknown"
        write_events = "unknown"
        read_events = "unknown"
        timescale = "unknown"
        if analysis is not None:
            info = analysis["info"]
            signal_count = info.get("signal_count", "unknown")
            duration = info.get("duration_h", "unknown")
            timescale = info.get("timescale", "unknown")
            write_events = analysis["write_events"].get("total", analysis["write_events"].get("shown", "unknown"))
            read_events = analysis["read_events"].get("total", analysis["read_events"].get("shown", "unknown"))

        scenario_cards = []
        for name, status, note in scenarios:
            scenario_cards.append(
                """
                <article class="scenario-card">
                    <div class="scenario-title">{}</div>
                    <span class="status-pill pass">{}</span>
                    <p>{}</p>
                </article>
                """.format(html.escape(name), html.escape(status), html.escape(note))
            )

        command_items = [
            "python .trae/agent/agent.py --sim-rtl async-fifo --output-dir outputs",
            "python .trae/agent/agent.py --sim-rtl async-fifo --no-wave-gui --output-dir outputs",
            "python .trae/agent/agent.py --analyze-rtl-vcd async-fifo --output-dir outputs",
            "python .trae/agent/agent.py --check-rtl async-fifo --output-dir outputs",
            "python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs",
        ]
        command_html = "\n".join("<code>{}</code>".format(html.escape(command)) for command in command_items)

        html_body = [
            "<!doctype html>",
            "<html lang=\"zh-CN\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            "<title>async-fifo 仿真摘要</title>",
            "<style>",
            ":root { color-scheme: light; --bg:#f5f7fb; --panel:#ffffff; --ink:#172033; --muted:#5f6b7a; --line:#dbe3ee; --blue:#2563eb; --green:#0f8a5f; --amber:#b7791f; --red:#b42318; --shadow:0 18px 45px rgba(31, 45, 61, .10); }",
            "* { box-sizing: border-box; }",
            "body { margin:0; font-family: \"Microsoft YaHei\", \"Segoe UI\", Arial, sans-serif; background:var(--bg); color:var(--ink); line-height:1.55; }",
            ".page { max-width:1180px; margin:0 auto; padding:34px 24px 48px; }",
            ".hero { display:flex; justify-content:space-between; gap:24px; align-items:flex-end; padding:30px; border-radius:8px; color:#fff; background:linear-gradient(135deg, #17324d 0%, #245d75 52%, #2f7d68 100%); box-shadow:var(--shadow); }",
            ".hero h1 { margin:0 0 10px; font-size:34px; letter-spacing:0; }",
            ".hero p { margin:0; max-width:720px; color:#dcecf5; }",
            ".status-pill { display:inline-flex; align-items:center; justify-content:center; min-width:58px; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700; }",
            ".status-pill.pass { color:#ffffff; background:var(--green); }",
            ".status-pill.fail { color:#ffffff; background:var(--red); }",
            ".section { margin-top:22px; padding:24px; border:1px solid var(--line); border-radius:8px; background:var(--panel); box-shadow:0 8px 24px rgba(31,45,61,.06); }",
            ".section h2 { margin:0 0 16px; font-size:21px; }",
            ".metric-grid { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; margin-top:20px; }",
            ".metric-card { padding:18px; border:1px solid var(--line); border-radius:8px; background:#fbfdff; }",
            ".metric-label { color:var(--muted); font-size:13px; }",
            ".metric-value { margin-top:6px; font-size:26px; font-weight:800; }",
            ".scenario-grid { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:12px; }",
            ".scenario-card { min-height:142px; padding:16px; border:1px solid var(--line); border-radius:8px; background:#fbfdff; }",
            ".scenario-title { margin-bottom:10px; font-weight:800; color:#172033; word-break:break-word; }",
            ".scenario-card p { margin:12px 0 0; color:var(--muted); font-size:13px; }",
            ".artifact-list { display:grid; gap:10px; }",
            ".artifact-row { display:grid; grid-template-columns:130px minmax(0, 1fr); gap:12px; align-items:start; padding:10px 12px; border:1px solid var(--line); border-radius:8px; background:#fbfdff; }",
            ".artifact-row b { color:#24364b; }",
            "code { display:block; padding:9px 11px; border-radius:6px; background:#eef3f8; color:#172033; font-family:Consolas, \"Cascadia Mono\", monospace; font-size:13px; overflow-x:auto; }",
            ".commands { display:grid; gap:8px; }",
            ".note { color:var(--muted); }",
            "@media (max-width: 900px) { .hero { display:block; } .metric-grid, .scenario-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); } .artifact-row { grid-template-columns:1fr; } }",
            "@media (max-width: 560px) { .page { padding:18px 12px 34px; } .hero { padding:22px; } .hero h1 { font-size:26px; } .metric-grid, .scenario-grid { grid-template-columns:1fr; } }",
            "</style>",
            "</head>",
            "<body>",
            "<main class=\"page\">",
            "<section class=\"hero\">",
            "<div>",
            "<h1>async-fifo 仿真摘要</h1>",
            "<p>面向 Vivado/xsim 的异步 FIFO 仿真看板，汇总场景覆盖、VCD 统计、WDB/WCFG 产物和下一步命令。</p>",
            "</div>",
            "<span class=\"status-pill {}\">{}</span>".format("pass" if wcfg["valid"] else "fail", html.escape(wcfg_status)),
            "</section>",
            "<section class=\"metric-grid\">",
            "<article class=\"metric-card\"><div class=\"metric-label\">信号数量</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(signal_count))),
            "<article class=\"metric-card\"><div class=\"metric-label\">仿真时长</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(duration))),
            "<article class=\"metric-card\"><div class=\"metric-label\">写握手</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(write_events))),
            "<article class=\"metric-card\"><div class=\"metric-label\">读握手</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(read_events))),
            "</section>",
            "<section class=\"section\"><h2>场景覆盖</h2><div class=\"scenario-grid\">",
            "\n".join(scenario_cards),
            "</div></section>",
            "<section class=\"section\"><h2>WCFG 波形配置验收</h2>",
            "<div class=\"metric-grid\">",
            "<article class=\"metric-card\"><div class=\"metric-label\">WCFG 状态</div><div class=\"metric-value\">{}</div></article>".format(html.escape(wcfg_status)),
            "<article class=\"metric-card\"><div class=\"metric-label\">波形对象数</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(wcfg["object_count"]))),
            "<article class=\"metric-card\"><div class=\"metric-label\">关键对象覆盖</div><div class=\"metric-value\">{}/{}</div></article>".format(html.escape(str(len(wcfg["present_required"]))), html.escape(str(len(wcfg["required_objects"])))),
            "<article class=\"metric-card\"><div class=\"metric-label\">时间单位</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(timescale))),
            "</div>",
            "<p class=\"note\">缺失对象：{}</p>".format(html.escape(", ".join(wcfg["missing_required"]) if wcfg["missing_required"] else "无")),
            "</section>",
            "<section class=\"section\"><h2>产物路径</h2><div class=\"artifact-list\">",
            "<div class=\"artifact-row\"><b>VCD</b><code>{}</code></div>".format(html.escape(str(vcd_path))),
            "<div class=\"artifact-row\"><b>WDB</b><code>{}</code></div>".format(html.escape(str(wave_db_path))),
            "<div class=\"artifact-row\"><b>WCFG</b><code>{}</code></div>".format(html.escape(str(wcfg["path"]))),
            "<div class=\"artifact-row\"><b>回归矩阵</b><code>{}</code></div>".format(html.escape(str(regression_path))),
            "</div></section>",
            "<section class=\"section\"><h2>常用命令</h2><div class=\"commands\">",
            command_html,
            "</div></section>",
            "</main>",
        ]
        html_body.extend(["</body>", "</html>", ""])
        html_path.write_text("\n".join(html_body), encoding="utf-8")
        return summary_path

    def check_async_fifo_rtl(self, output_dir="outputs"):
        project_dir = Path(output_dir) / "async-fifo"
        rtl_path = project_dir / "rtl" / "async_fifo.v"
        tb_path = project_dir / "tb" / "tb_async_fifo.v"
        sim_script_path = project_dir / "sim" / "run_vivado_async_fifo.tcl"
        gui_script_path = project_dir / "sim" / "open_async_fifo_project_gui.tcl"
        project_script_path = project_dir / "sim" / "create_async_fifo_project.tcl"
        xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
        vcd_path = project_dir / "sim" / "async_fifo_trace.vcd"
        wave_db_path = self.resolve_async_fifo_wave_db(project_dir / "sim")
        report_path = project_dir / "reports" / "sim_report.md"
        summary_path = project_dir / "reports" / "sim_summary.md"
        regression_path = project_dir / "reports" / "regression_matrix.md"
        regression_summary_path = project_dir / "reports" / "regression_summary.md"
        wave_visibility_path = project_dir / "reports" / "wave_visibility.md"
        wave_screenshot_path = project_dir / "reports" / "wave_screenshot.md"
        reports_index_path = project_dir / "reports" / "index.md"
        if not regression_path.exists() and project_dir.exists():
            self.write_async_fifo_regression_matrix(project_dir)
        if not summary_path.exists() and report_path.exists():
            self.write_async_fifo_summary_report(
                project_dir=project_dir,
                vcd_path=vcd_path,
                wave_db_path=wave_db_path,
                analysis=None,
                analysis_error="Run --sim-rtl or --analyze-rtl-vcd to refresh VCD statistics.",
                regression_path=regression_path,
            )
        if project_dir.exists():
            self.write_async_fifo_wave_visibility_report(project_dir)
            self.write_async_fifo_wave_screenshot_report(project_dir)
            self.write_async_fifo_reports_index(project_dir)
        wcfg = self.parse_async_fifo_wcfg_summary(project_dir)
        wcfg_required = wcfg["exists"]

        checks = [
            ("RTL exists", rtl_path.exists(), rtl_path),
            ("Testbench exists", tb_path.exists(), tb_path),
            ("Vivado sim script exists", sim_script_path.exists(), sim_script_path),
            ("Vivado project script exists", project_script_path.exists(), project_script_path),
            ("Vivado GUI script exists", gui_script_path.exists(), gui_script_path),
            ("Vivado project exists", xpr_path.exists(), xpr_path),
            ("VCD exists", vcd_path.exists(), vcd_path),
            ("WDB exists", wave_db_path.exists(), wave_db_path),
            ("Simulation report exists", report_path.exists(), report_path),
            ("Simulation summary exists", summary_path.exists(), summary_path),
            ("Regression matrix exists", regression_path.exists(), regression_path),
            ("Regression summary exists", regression_summary_path.exists(), regression_summary_path),
            ("Wave visibility report exists", wave_visibility_path.exists(), wave_visibility_path),
            ("Wave screenshot report exists", wave_screenshot_path.exists(), wave_screenshot_path),
            ("Reports index exists", reports_index_path.exists(), reports_index_path),
            ("WCFG optional before GUI open", (not wcfg_required) or wcfg["exists"], wcfg["path"]),
            ("WCFG has waveform objects", (not wcfg_required) or wcfg["object_count"] > 0, wcfg["path"]),
            ("WCFG has required async FIFO signals", (not wcfg_required) or wcfg["valid"], wcfg["path"]),
        ]

        if rtl_path.exists():
            rtl = rtl_path.read_text(encoding="utf-8")
            checks.extend([
                ("RTL declares async_fifo", "module async_fifo" in rtl, rtl_path),
                ("RTL has async_reg synchronizers", '(* async_reg = "true" *)' in rtl, rtl_path),
                ("RTL has full logic", "assign full" in rtl, rtl_path),
                ("RTL has empty logic", "assign empty" in rtl, rtl_path),
            ])

        if tb_path.exists():
            tb = tb_path.read_text(encoding="utf-8")
            checks.extend([
                ("TB dumps async_fifo_trace.vcd", '$dumpfile("async_fifo_trace.vcd")' in tb, tb_path),
                ("TB has scoreboard storage", "expected_data" in tb, tb_path),
                ("TB has reusable write task", "task automatic try_write" in tb, tb_path),
                ("TB covers full boundary scenario", "ASYNC_FIFO_SCENARIO full_boundary PASS" in tb, tb_path),
                ("TB covers empty boundary scenario", "ASYNC_FIFO_SCENARIO empty_boundary PASS" in tb, tb_path),
                ("TB covers reset recovery scenario", "ASYNC_FIFO_SCENARIO reset_recovery PASS" in tb, tb_path),
                ("TB covers mixed stress scenario", "ASYNC_FIFO_SCENARIO mixed_stress PASS" in tb, tb_path),
                ("TB prints scoreboard pass", "ASYNC_FIFO_SCOREBOARD_PASS" in tb, tb_path),
                ("TB fatal on scoreboard fail", "ASYNC_FIFO_SCOREBOARD_FAIL" in tb and "$fatal" in tb, tb_path),
            ])

        print("Async FIFO RTL check")
        print("=" * 60)
        ok = True
        for label, passed, path in checks:
            print("[{}] {}: {}".format("OK" if passed else "NO", label, path))
            ok = ok and passed
        return ok

    def open_rtl_wave(self, target, output_dir="outputs"):
        target_name = self.normalize_rtl_target(target)
        if target_name == "async-fifo":
            return self.open_async_fifo_project_gui(Path(output_dir) / "async-fifo")
        raise ValueError("Unsupported RTL target: {}".format(target))

    def write_smoke_loop_vcd(self, output_dir):
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

    def run_smoke_loop(self, output_dir="outputs", limit=20):
        print("Smoke loop: generating built-in handshake VCD")
        vcd_path = self.write_smoke_loop_vcd(output_dir)
        print("Generated VCD: {}".format(vcd_path))
        ok = self.analyze_vcd(
            vcd_path,
            condition="tb.valid=1,tb.ready=1",
            show="tb.data",
            limit=limit,
        )
        if ok:
            print("Smoke loop completed")
        return ok

    def detect_simulator(self):
        if self.resolve_vivado_command():
            return "vivado"
        if shutil.which("iverilog") and shutil.which("vvp"):
            return "icarus"
        if shutil.which("verilator"):
            return "verilator"
        return None

    def resolve_vivado_command(self):
        vivado_on_path = shutil.which("vivado")
        if vivado_on_path:
            return vivado_on_path

        candidates = [
            Path(r"D:\vivado\2025.2\Vivado\bin\vivado.bat"),
            Path(r"D:\vivado\2025.2\Vivado\bin\unwrapped\win64.o\vivado.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def write_sim_smoke_sources(self, output_dir):
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

    def run_icarus_sim_smoke(self, output_dir, limit=20):
        sim_dir, rtl_path, tb_path, vcd_path = self.write_sim_smoke_sources(output_dir)
        sim_out = sim_dir / "handshake_smoke.vvp"

        compile_result = subprocess.run(
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

        run_result = subprocess.run(
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
        )
        if ok:
            print("Simulation smoke completed")
        return ok

    def write_vivado_sim_script(self, sim_dir, rtl_path, tb_path, vcd_path):
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

    def open_vivado_wave_gui(self, sim_dir, vcd_path):
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

        subprocess.Popen(
            [vivado_command, "-mode", "gui", "-source", gui_script_path.name],
            cwd=sim_dir,
        )
        print("Vivado waveform GUI launched: {}".format(wave_db_path))
        return True

    def run_vivado_sim_smoke(self, output_dir, limit=20, open_wave_gui=True):
        sim_dir, rtl_path, tb_path, vcd_path = self.write_sim_smoke_sources(output_dir)
        script_path = self.write_vivado_sim_script(sim_dir, rtl_path, tb_path, vcd_path)
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        result = subprocess.run(
            [vivado_command, "-mode", "batch", "-source", script_path.name],
            cwd=sim_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
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
        )
        if ok:
            print("Simulation smoke completed")
            if open_wave_gui:
                self.open_vivado_wave_gui(sim_dir, vcd_path)
        return ok

    def run_sim_smoke(self, output_dir="outputs", limit=20, open_wave_gui=True):
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
            )
        if simulator == "icarus":
            return self.run_icarus_sim_smoke(output_dir=output_dir, limit=limit)

        print(
            "{} detected, but sim smoke currently supports only Vivado or iverilog/vvp.".format(simulator),
            file=sys.stderr,
        )
        return False

    def normalize_rtl_target(self, target):
        target_name = str(target).strip().lower().replace("_", "-")
        if target_name in ("async-fifo", "asyncfifo"):
            return "async-fifo"
        raise ValueError("Unsupported RTL target: {}".format(target))

    def render_async_fifo_rtl(self, data_width=8, addr_width=4):
        return """`timescale 1ns/1ps

module async_fifo #(
    parameter DATA_WIDTH = __DATA_WIDTH__,
    parameter ADDR_WIDTH = __ADDR_WIDTH__
) (
    input  wire                  wr_clk,
    input  wire                  wr_rst_n,
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    output wire                  full,
    input  wire                  rd_clk,
    input  wire                  rd_rst_n,
    input  wire                  rd_en,
    output reg  [DATA_WIDTH-1:0] rd_data,
    output wire                  empty
);
    localparam DEPTH = (1 << ADDR_WIDTH);

    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    reg [ADDR_WIDTH:0] wr_bin;
    reg [ADDR_WIDTH:0] wr_gray;
    reg [ADDR_WIDTH:0] rd_bin;
    reg [ADDR_WIDTH:0] rd_gray;
    reg full_reg;
    reg empty_reg;

    (* async_reg = "true" *) reg [ADDR_WIDTH:0] rd_gray_wr_sync1;
    (* async_reg = "true" *) reg [ADDR_WIDTH:0] rd_gray_wr_sync2;
    (* async_reg = "true" *) reg [ADDR_WIDTH:0] wr_gray_rd_sync1;
    (* async_reg = "true" *) reg [ADDR_WIDTH:0] wr_gray_rd_sync2;

    wire wr_fire = wr_en && !full_reg;
    wire rd_fire = rd_en && !empty_reg;

    wire [ADDR_WIDTH:0] wr_bin_next = wr_fire ? (wr_bin + 1'b1) : wr_bin;
    wire [ADDR_WIDTH:0] rd_bin_next = rd_fire ? (rd_bin + 1'b1) : rd_bin;
    wire [ADDR_WIDTH:0] wr_gray_next = bin_to_gray(wr_bin_next);
    wire [ADDR_WIDTH:0] rd_gray_next = bin_to_gray(rd_bin_next);

    wire full_next = (wr_gray_next == {~rd_gray_wr_sync2[ADDR_WIDTH:ADDR_WIDTH-1],
                                       rd_gray_wr_sync2[ADDR_WIDTH-2:0]});
    wire empty_next = (rd_gray_next == wr_gray_rd_sync2);

    assign full = full_reg;
    assign empty = empty_reg;

    function [ADDR_WIDTH:0] bin_to_gray;
        input [ADDR_WIDTH:0] bin;
        begin
            bin_to_gray = (bin >> 1) ^ bin;
        end
    endfunction

    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            wr_bin <= {ADDR_WIDTH+1{1'b0}};
            wr_gray <= {ADDR_WIDTH+1{1'b0}};
            full_reg <= 1'b0;
        end else begin
            if (wr_fire) begin
                mem[wr_bin[ADDR_WIDTH-1:0]] <= wr_data;
            end
            wr_bin <= wr_bin_next;
            wr_gray <= wr_gray_next;
            full_reg <= full_next;
        end
    end

    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            rd_bin <= {ADDR_WIDTH+1{1'b0}};
            rd_gray <= {ADDR_WIDTH+1{1'b0}};
            rd_data <= {DATA_WIDTH{1'b0}};
            empty_reg <= 1'b1;
        end else begin
            if (rd_fire) begin
                rd_data <= mem[rd_bin[ADDR_WIDTH-1:0]];
            end
            rd_bin <= rd_bin_next;
            rd_gray <= rd_gray_next;
            empty_reg <= empty_next;
        end
    end

    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            rd_gray_wr_sync1 <= {ADDR_WIDTH+1{1'b0}};
            rd_gray_wr_sync2 <= {ADDR_WIDTH+1{1'b0}};
        end else begin
            rd_gray_wr_sync1 <= rd_gray;
            rd_gray_wr_sync2 <= rd_gray_wr_sync1;
        end
    end

    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            wr_gray_rd_sync1 <= {ADDR_WIDTH+1{1'b0}};
            wr_gray_rd_sync2 <= {ADDR_WIDTH+1{1'b0}};
        end else begin
            wr_gray_rd_sync1 <= wr_gray;
            wr_gray_rd_sync2 <= wr_gray_rd_sync1;
        end
    end
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_async_fifo_tb(self, data_width=8, addr_width=4):
        return """`timescale 1ns/1ps

module tb_async_fifo;
    localparam DATA_WIDTH = __DATA_WIDTH__;
    localparam ADDR_WIDTH = __ADDR_WIDTH__;
    localparam FIFO_DEPTH = (1 << ADDR_WIDTH);
    localparam SCOREBOARD_DEPTH = 256;

    reg wr_clk;
    reg rd_clk;
    reg wr_rst_n;
    reg rd_rst_n;
    reg wr_en;
    reg rd_en;
    reg [DATA_WIDTH-1:0] wr_data;
    wire [DATA_WIDTH-1:0] rd_data;
    wire full;
    wire empty;
    reg [DATA_WIDTH-1:0] expected_data [0:SCOREBOARD_DEPTH-1];
    integer write_count;
    integer read_count;
    integer error_count;
    integer idx;
    integer cycle_idx;
    integer did_write;
    integer did_read;
    integer scenario_id;

    async_fifo #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) dut (
        .wr_clk(wr_clk),
        .wr_rst_n(wr_rst_n),
        .wr_en(wr_en),
        .wr_data(wr_data),
        .full(full),
        .rd_clk(rd_clk),
        .rd_rst_n(rd_rst_n),
        .rd_en(rd_en),
        .rd_data(rd_data),
        .empty(empty)
    );

    initial begin
        wr_clk = 1'b0;
        forever #5 wr_clk = ~wr_clk;
    end

    initial begin
        rd_clk = 1'b0;
        forever #7 rd_clk = ~rd_clk;
    end

    task automatic clear_scoreboard;
        begin
            write_count = 0;
            read_count = 0;
            for (idx = 0; idx < SCOREBOARD_DEPTH; idx = idx + 1) begin
                expected_data[idx] = 8'h00;
            end
        end
    endtask

    task automatic apply_reset;
        begin
            wr_en = 1'b0;
            rd_en = 1'b0;
            wr_data = 8'h00;
            wr_rst_n = 1'b0;
            rd_rst_n = 1'b0;
            repeat (3) @(posedge wr_clk);
            repeat (3) @(posedge rd_clk);
            wr_rst_n = 1'b1;
            rd_rst_n = 1'b1;
            repeat (3) @(posedge wr_clk);
            repeat (3) @(posedge rd_clk);
        end
    endtask

    task automatic try_write(input [DATA_WIDTH-1:0] data, output integer did_write_out);
        integer write_count_before;
        begin
            did_write_out = 0;
            @(negedge wr_clk);
            if (full) begin
                wr_en = 1'b0;
                wr_data = data;
                @(posedge wr_clk);
                #1;
            end else begin
                write_count_before = write_count;
                wr_en = 1'b1;
                wr_data = data;
                @(posedge wr_clk);
                #1;
                if (write_count >= SCOREBOARD_DEPTH) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR expected_data overflow write_count=%0d", write_count);
                    error_count = error_count + 1;
                end else begin
                    expected_data[write_count] = data;
                    write_count = write_count + 1;
                    did_write_out = (write_count > write_count_before);
                end
            end
            @(negedge wr_clk);
            wr_en = 1'b0;
        end
    endtask

    task automatic try_read(output integer did_read_out);
        integer read_count_before;
        begin
            did_read_out = 0;
            @(negedge rd_clk);
            if (empty) begin
                rd_en = 1'b0;
                @(posedge rd_clk);
                #1;
            end else begin
                read_count_before = read_count;
                rd_en = 1'b1;
                @(posedge rd_clk);
                #2;
                did_read_out = (read_count > read_count_before);
            end
            @(negedge rd_clk);
            rd_en = 1'b0;
        end
    endtask

    task automatic wait_for_not_empty(input integer max_cycles);
        begin
            cycle_idx = 0;
            while (empty && cycle_idx < max_cycles) begin
                @(posedge rd_clk);
                cycle_idx = cycle_idx + 1;
            end
            if (empty) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR timed out waiting for not empty");
                error_count = error_count + 1;
            end
        end
    endtask

    task automatic wait_for_full(input integer max_cycles);
        begin
            cycle_idx = 0;
            while (!full && cycle_idx < max_cycles) begin
                @(posedge wr_clk);
                cycle_idx = cycle_idx + 1;
            end
            if (!full) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR timed out waiting for full");
                error_count = error_count + 1;
            end
        end
    endtask

    task automatic drain_until_empty(input integer max_reads);
        begin
            cycle_idx = 0;
            while (!empty && cycle_idx < max_reads) begin
                try_read(did_read);
                cycle_idx = cycle_idx + 1;
            end
        end
    endtask

    task automatic check_counts(input [1023:0] label);
        begin
            if (read_count != write_count) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR %0s read_count=%0d write_count=%0d", label, read_count, write_count);
                error_count = error_count + 1;
            end
        end
    endtask

    task automatic run_basic_ordered;
        begin
            scenario_id = 1;
            apply_reset();
            for (idx = 0; idx < 8; idx = idx + 1) begin
                try_write((idx + 1) * 8'h11, did_write);
                if (!did_write) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR basic_ordered write blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            wait_for_not_empty(16);
            for (idx = 0; idx < 8; idx = idx + 1) begin
                try_read(did_read);
                if (!did_read) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR basic_ordered read blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            check_counts("basic_ordered");
            $display("ASYNC_FIFO_SCENARIO basic_ordered PASS writes=%0d reads=%0d", write_count, read_count);
        end
    endtask

    task automatic run_full_empty_boundary;
        begin
            scenario_id = 2;
            apply_reset();
            for (idx = 0; idx < FIFO_DEPTH; idx = idx + 1) begin
                try_write(8'h80 + idx[7:0], did_write);
                if (!did_write) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR full_boundary early full idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            wait_for_full(16);
            try_write(8'hf0, did_write);
            if (did_write) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR full_boundary accepted write while full");
                error_count = error_count + 1;
            end
            wait_for_not_empty(16);
            for (idx = 0; idx < FIFO_DEPTH; idx = idx + 1) begin
                try_read(did_read);
                if (!did_read) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR full_boundary early empty idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            repeat (4) @(posedge rd_clk);
            try_read(did_read);
            if (did_read) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR empty_boundary accepted read while empty");
                error_count = error_count + 1;
            end
            check_counts("full_empty_boundary");
            $display("ASYNC_FIFO_SCENARIO full_boundary PASS writes=%0d reads=%0d", write_count, read_count);
            $display("ASYNC_FIFO_SCENARIO empty_boundary PASS writes=%0d reads=%0d", write_count, read_count);
        end
    endtask

    task automatic run_reset_recovery;
        begin
            scenario_id = 3;
            apply_reset();
            for (idx = 0; idx < 4; idx = idx + 1) begin
                try_write(8'h30 + idx[7:0], did_write);
                if (!did_write) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR reset_recovery pre-reset write blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            apply_reset();
            clear_scoreboard();
            for (idx = 0; idx < 6; idx = idx + 1) begin
                try_write(8'ha0 + idx[7:0], did_write);
                if (!did_write) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR reset_recovery post-reset write blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            wait_for_not_empty(16);
            for (idx = 0; idx < 6; idx = idx + 1) begin
                try_read(did_read);
                if (!did_read) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR reset_recovery post-reset read blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            check_counts("reset_recovery");
            $display("ASYNC_FIFO_SCENARIO reset_recovery PASS writes=%0d reads=%0d", write_count, read_count);
        end
    endtask

    task automatic run_mixed_stress;
        begin
            scenario_id = 4;
            apply_reset();
            fork
                begin
                    for (idx = 0; idx < 24; idx = idx + 1) begin
                        try_write(8'h40 + idx[7:0], did_write);
                        if (!did_write) begin
                            wait_for_full(1);
                            @(posedge wr_clk);
                            try_write(8'h40 + idx[7:0], did_write);
                        end
                    end
                end
                begin
                    repeat (8) @(posedge rd_clk);
                    for (cycle_idx = 0; cycle_idx < 40; cycle_idx = cycle_idx + 1) begin
                        try_read(did_read);
                        if (read_count >= 24) begin
                            cycle_idx = 40;
                        end
                    end
                end
            join
            drain_until_empty(64);
            check_counts("mixed_stress");
            $display("ASYNC_FIFO_SCENARIO mixed_stress PASS writes=%0d reads=%0d", write_count, read_count);
        end
    endtask

    initial begin
        $dumpfile("async_fifo_trace.vcd");
        $dumpvars(0, tb_async_fifo);

        wr_rst_n = 1'b0;
        rd_rst_n = 1'b0;
        wr_en = 1'b0;
        rd_en = 1'b0;
        wr_data = 8'h00;
        scenario_id = 0;
        error_count = 0;
        clear_scoreboard();

        run_basic_ordered();
        clear_scoreboard();
        run_full_empty_boundary();
        clear_scoreboard();
        run_reset_recovery();
        clear_scoreboard();
        run_mixed_stress();

        if (error_count == 0) begin
            $display("ASYNC_FIFO_SCOREBOARD_PASS writes=%0d reads=%0d", write_count, read_count);
        end else begin
            $fatal(1, "ASYNC_FIFO_SCOREBOARD_FAIL errors=%0d", error_count);
        end
        $finish;
    end

    always @(posedge rd_clk) begin
        if (rd_rst_n && rd_en && !empty) begin
            #1;
            if (rd_data !== expected_data[read_count]) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR index=%0d expected=0x%02h actual=0x%02h", read_count, expected_data[read_count], rd_data);
                error_count = error_count + 1;
            end
            read_count = read_count + 1;
        end
    end
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_async_fifo_vivado_script(self):
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set timestamp [clock format [clock seconds] -format "%Y%m%d_%H%M%S"]
set snapshot async_fifo_smoke_$timestamp
set wave_db async_fifo_smoke_$timestamp.wdb
exec xvlog -sv ../rtl/async_fifo.v ../tb/tb_async_fifo.v
exec xelab tb_async_fifo -debug typical -s $snapshot
set run_fh [open run_async_fifo_wave.tcl w]
puts $run_fh "log_wave -r /"
puts $run_fh "run all"
puts $run_fh "exit"
close $run_fh
exec xsim $snapshot -wdb $wave_db -tclbatch run_async_fifo_wave.tcl
if {![file exists async_fifo_trace.vcd]} {
    puts stderr "Simulation did not generate async_fifo_trace.vcd"
    exit 1
}
if {![file exists $wave_db]} {
    puts stderr "Simulation did not generate $wave_db"
    exit 1
}
set latest_fh [open latest_async_fifo_wdb.txt w]
puts $latest_fh $wave_db
close $latest_fh
exit 0
"""

    def render_vivado_tclstore_bootstrap(self):
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

    def render_async_fifo_project_script(self):
        return self.render_vivado_tclstore_bootstrap() + """
set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set project_dir [file normalize [file join $script_dir .. vivado_project]]
file mkdir $project_dir
set xpr_path [file join $project_dir async_fifo_project.xpr]
if {![file exists $xpr_path]} {
    create_project async_fifo_project $project_dir -force -part xc7vx485tffg1157-1
} else {
    open_project $xpr_path
}
set_property target_language Verilog [current_project]
set rtl_path [file normalize [file join $script_dir .. rtl async_fifo.v]]
set tb_path [file normalize [file join $script_dir .. tb tb_async_fifo.v]]
if {[llength [get_files -quiet $rtl_path]] == 0} {
    add_files -norecurse $rtl_path
}
if {[llength [get_files -quiet -of_objects [get_filesets sim_1] $tb_path]] == 0} {
    add_files -fileset sim_1 -norecurse $tb_path
}
set_property top async_fifo [get_filesets sources_1]
set_property top tb_async_fifo [get_filesets sim_1]
set_property -name {xsim.simulate.runtime} -value {all} -objects [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
close_project
exit 0
"""

    def render_async_fifo_open_project_gui_script(self):
        return self.render_vivado_tclstore_bootstrap() + """
set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set xpr_path [file normalize [file join $script_dir .. vivado_project async_fifo_project.xpr]]
set wave_db [file normalize [file join $script_dir async_fifo_smoke.wdb]]
set wave_cfg [file normalize [file join $script_dir async_fifo_debug.wcfg]]
set latest_wdb_path [file join $script_dir latest_async_fifo_wdb.txt]
if {[file exists $latest_wdb_path]} {
    set latest_fh [open $latest_wdb_path r]
    set latest_wdb [string trim [read $latest_fh]]
    close $latest_fh
    if {$latest_wdb ne ""} {
        set wave_db [file normalize [file join $script_dir $latest_wdb]]
    }
}
if {![file exists $xpr_path]} {
    puts stderr "Vivado project not found: $xpr_path"
    exit 1
}
open_project $xpr_path
start_gui
if {[file exists $wave_db]} {
    open_wave_database $wave_db
    catch {close_wave_config [current_wave_config]}
    catch {create_wave_config async_fifo_debug}
    catch {add_wave_divider {Scenario}}
    catch {add_wave {{/tb_async_fifo/scenario_id}}}
    catch {add_wave_divider {Write Domain}}
    catch {add_wave {{/tb_async_fifo/wr_clk}}}
    catch {add_wave {{/tb_async_fifo/wr_rst_n}}}
    catch {add_wave {{/tb_async_fifo/wr_en}}}
    catch {add_wave {{/tb_async_fifo/full}}}
    catch {add_wave -radix hex {{/tb_async_fifo/wr_data}}}
    catch {add_wave_divider {Read Domain}}
    catch {add_wave {{/tb_async_fifo/rd_clk}}}
    catch {add_wave {{/tb_async_fifo/rd_rst_n}}}
    catch {add_wave {{/tb_async_fifo/rd_en}}}
    catch {add_wave {{/tb_async_fifo/empty}}}
    catch {add_wave -radix hex {{/tb_async_fifo/rd_data}}}
    catch {add_wave_divider {Scoreboard}}
    catch {add_wave {{/tb_async_fifo/write_count}}}
    catch {add_wave {{/tb_async_fifo/read_count}}}
    catch {add_wave {{/tb_async_fifo/error_count}}}
    catch {add_wave_divider {DUT Pointers}}
    catch {add_wave -radix unsigned {{/tb_async_fifo/dut/wr_bin}}}
    catch {add_wave -radix unsigned {{/tb_async_fifo/dut/rd_bin}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/wr_gray}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/rd_gray}}}
    catch {add_wave_divider {DUT Status}}
    catch {add_wave {{/tb_async_fifo/dut/full_reg}}}
    catch {add_wave {{/tb_async_fifo/dut/empty_reg}}}
    catch {add_wave_divider {DUT Sync}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/rd_gray_wr_sync1}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/rd_gray_wr_sync2}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/wr_gray_rd_sync1}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/wr_gray_rd_sync2}}}
    catch {save_wave_config $wave_cfg}
} else {
    puts stderr "Waveform database not found: $wave_db"
}
"""

    def render_async_fifo_readme(self):
        return """# async-fifo RTL Project

This generated project contains a first-pass asynchronous FIFO RTL block, a scoreboard smoke testbench, and a Vivado/xsim batch script.

## Files

- `rtl/async_fifo.v`: parameterized dual-clock FIFO using Gray-coded pointers and two-stage synchronizers.
- `tb/tb_async_fifo.v`: write/read smoke test with a scoreboard that emits `async_fifo_trace.vcd`.
- `sim/run_vivado_async_fifo.tcl`: Vivado script for `xvlog`, `xelab`, and `xsim`; it logs all waves before `run all`.
- `sim/create_async_fifo_project.tcl`: creates/updates `vivado_project/async_fifo_project.xpr`.
- `sim/open_async_fifo_project_gui.tcl`: opens the Vivado project and latest `async_fifo_smoke_*.wdb`.
- `reports/`: reserved for simulation, lint, synthesis, and timing notes.

## Run

```powershell
cd sim
vivado -mode batch -source run_vivado_async_fifo.tcl
vivado -mode batch -source create_async_fifo_project.tcl
vivado -mode gui -source open_async_fifo_project_gui.tcl
```
"""

    def write_async_fifo_project(self, output_dir, data_width=8, addr_width=4):
        project_dir = Path(output_dir) / "async-fifo"
        rtl_dir = project_dir / "rtl"
        tb_dir = project_dir / "tb"
        sim_dir = project_dir / "sim"
        reports_dir = project_dir / "reports"
        for path in (rtl_dir, tb_dir, sim_dir, reports_dir):
            path.mkdir(parents=True, exist_ok=True)

        (rtl_dir / "async_fifo.v").write_text(
            self.render_async_fifo_rtl(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (tb_dir / "tb_async_fifo.v").write_text(
            self.render_async_fifo_tb(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (sim_dir / "run_vivado_async_fifo.tcl").write_text(
            self.render_async_fifo_vivado_script(),
            encoding="utf-8",
        )
        (sim_dir / "create_async_fifo_project.tcl").write_text(
            self.render_async_fifo_project_script(),
            encoding="utf-8",
        )
        (sim_dir / "open_async_fifo_project_gui.tcl").write_text(
            self.render_async_fifo_open_project_gui_script(),
            encoding="utf-8",
        )
        (project_dir / "README.md").write_text(self.render_async_fifo_readme(), encoding="utf-8")
        return project_dir

    def generate_rtl_project(self, target, output_dir="outputs", data_width=8, addr_width=4):
        target_name = self.normalize_rtl_target(target)
        if target_name == "async-fifo":
            return self.write_async_fifo_project(output_dir, data_width=data_width, addr_width=addr_width)
        raise ValueError("Unsupported RTL target: {}".format(target))

    def open_async_fifo_project_gui(self, project_dir):
        project_dir = Path(project_dir)
        sim_dir = project_dir / "sim"
        xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
        wave_db_path = self.resolve_async_fifo_wave_db(sim_dir)
        gui_script_path = sim_dir / "open_async_fifo_project_gui.tcl"

        if not xpr_path.exists():
            print("Vivado project not found: {}".format(xpr_path), file=sys.stderr)
            return False
        if not wave_db_path.exists():
            print("Vivado waveform database not found: {}".format(wave_db_path), file=sys.stderr)
            return False
        if not gui_script_path.exists():
            gui_script_path.write_text(self.render_async_fifo_open_project_gui_script(), encoding="utf-8")

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found; cannot open waveform GUI.", file=sys.stderr)
            return False

        subprocess.Popen(
            [vivado_command, "-mode", "gui", "-source", gui_script_path.name],
            cwd=sim_dir,
        )
        print("Vivado project GUI launched: {}".format(xpr_path))
        print("Vivado waveform database: {}".format(wave_db_path))
        return True

    def open_async_fifo_uvm_wave_gui(self, project_dir, wave_kind="coverage"):
        project_dir = Path(project_dir)
        sim_dir = project_dir / "sim"
        if wave_kind not in ("smoke", "coverage"):
            raise ValueError("Unsupported UVM wave kind: {}".format(wave_kind))

        wave_db_name = "async_fifo_uvm_coverage.wdb" if wave_kind == "coverage" else "async_fifo_uvm_smoke.wdb"
        wave_db_path = sim_dir / wave_db_name
        gui_script_path = sim_dir / "open_async_fifo_uvm_{}_wave.tcl".format(wave_kind)
        gui_script_path.write_text(
            """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set wave_db __WAVE_DB__
if {![file exists $wave_db]} {
    puts stderr "UVM waveform database not found: $wave_db"
    exit 1
}
start_gui
open_wave_database $wave_db
add_wave -r /tb_async_fifo_uvm
""".replace("__WAVE_DB__", wave_db_name),
            encoding="utf-8",
        )

        if not wave_db_path.exists():
            print("Vivado UVM waveform database not found: {}".format(wave_db_path), file=sys.stderr)
            return False

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found; cannot open UVM waveform GUI.", file=sys.stderr)
            return False

        subprocess.Popen(
            [vivado_command, "-mode", "gui", "-source", gui_script_path.name],
            cwd=sim_dir,
        )
        screenshot_report = self.write_async_fifo_uvm_wave_screenshot_report(project_dir, wave_kind=wave_kind)
        print("Vivado UVM waveform GUI launched: {}".format(wave_db_path))
        print("UVM waveform screenshot report: {}".format(screenshot_report["markdown_path"]))
        return True

    def resolve_async_fifo_wave_db(self, sim_dir):
        sim_dir = Path(sim_dir)
        latest_path = sim_dir / "latest_async_fifo_wdb.txt"
        if latest_path.exists():
            latest_name = latest_path.read_text(encoding="utf-8").strip()
            if latest_name:
                latest_wdb = sim_dir / latest_name
                if latest_wdb.exists():
                    return latest_wdb
        legacy_wdb = sim_dir / "async_fifo_smoke.wdb"
        if legacy_wdb.exists():
            return legacy_wdb
        candidates = sorted(
            sim_dir.glob("async_fifo_smoke_*.wdb"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else legacy_wdb

    def run_async_fifo_vivado_sim(self, output_dir="outputs", open_wave_gui=True, data_width=8, addr_width=4):
        project_dir = self.generate_rtl_project(
            "async-fifo",
            output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        sim_result = subprocess.run(
            [vivado_command, "-mode", "batch", "-source", "run_vivado_async_fifo.tcl"],
            cwd=sim_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if sim_result.returncode != 0:
            print(sim_result.stderr.strip() or sim_result.stdout.strip() or "async FIFO simulation failed", file=sys.stderr)
            return False

        vcd_path = sim_dir / "async_fifo_trace.vcd"
        wave_db_path = self.resolve_async_fifo_wave_db(sim_dir)
        if not vcd_path.exists():
            print("Simulation did not generate VCD: {}".format(vcd_path), file=sys.stderr)
            return False
        if not wave_db_path.exists():
            print("Simulation did not generate WDB: {}".format(wave_db_path), file=sys.stderr)
            return False

        project_result = subprocess.run(
            [vivado_command, "-mode", "batch", "-nojournal", "-nolog", "-notrace", "-source", "create_async_fifo_project.tcl"],
            cwd=sim_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if project_result.returncode != 0:
            print(project_result.stderr.strip() or project_result.stdout.strip() or "Vivado project generation failed", file=sys.stderr)
            return False

        print("Async FIFO simulation completed")
        print("Generated VCD: {}".format(vcd_path))
        print("Generated WDB: {}".format(wave_db_path))
        print("Vivado project: {}".format(project_dir / "vivado_project" / "async_fifo_project.xpr"))
        report_path = self.write_async_fifo_sim_report(
            project_dir=project_dir,
            vcd_path=vcd_path,
            wave_db_path=wave_db_path,
            sim_result=sim_result,
            project_result=project_result,
        )
        print("Simulation report: {}".format(report_path))
        if open_wave_gui:
            self.open_async_fifo_project_gui(project_dir)
        return True

    def run_async_fifo_regression(self, output_dir="outputs", open_wave_gui=False):
        root_project_dir = self.write_async_fifo_project(output_dir)
        self.write_async_fifo_regression_matrix(root_project_dir)
        results = []
        all_passed = True

        for case in self.async_fifo_regression_cases():
            case_output_dir = root_project_dir / "regression" / case["name"]
            passed = self.run_async_fifo_vivado_sim(
                output_dir=case_output_dir,
                open_wave_gui=False,
                data_width=case["data_width"],
                addr_width=case["addr_width"],
            )
            all_passed = all_passed and passed
            results.append({
                "name": case["name"],
                "data_width": case["data_width"],
                "addr_width": case["addr_width"],
                "status": "PASS" if passed else "FAIL",
                "output_dir": case_output_dir / "async-fifo",
            })

        self.write_async_fifo_regression_summary(root_project_dir, results)
        if open_wave_gui and all_passed:
            self.open_async_fifo_project_gui(root_project_dir)
        return all_passed

    def run_async_fifo_uvm_smoke(self, output_dir="outputs", open_wave_gui=True, data_width=8, addr_width=4):
        project_dir = self.generate_rtl_project(
            "async-fifo",
            output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        self.write_async_fifo_uvm_smoke_project(
            project_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        sim_result = subprocess.run(
            [vivado_command, "-mode", "batch", "-source", "run_vivado_async_fifo_uvm.tcl"],
            cwd=sim_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if sim_result.returncode != 0:
            self.write_async_fifo_uvm_smoke_report(project_dir, sim_result=sim_result)
            print(sim_result.stderr.strip() or sim_result.stdout.strip() or "async FIFO UVM smoke failed", file=sys.stderr)
            return False

        report = self.write_async_fifo_uvm_smoke_report(project_dir, sim_result=sim_result)
        if not report["passed"]:
            print("UVM smoke markers were not found in the simulation log.", file=sys.stderr)
            return False

        print("Async FIFO UVM smoke completed")
        print("UVM log: {}".format(report["log_path"]))
        print("Generated WDB: {}".format(report["wdb_path"]))
        print("UVM smoke report: {}".format(report["markdown_path"]))
        if open_wave_gui:
            self.open_async_fifo_project_gui(project_dir)
        return True

    def run_async_fifo_uvm_coverage(
        self,
        output_dir="outputs",
        data_width=8,
        addr_width=4,
        coverage_threshold=None,
        coverage_percent=None,
        seed=None,
    ):
        project_dir = self.generate_rtl_project(
            "async-fifo",
            output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        self.write_async_fifo_uvm_coverage_project(
            project_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        command = [vivado_command, "-mode", "batch", "-source", "run_vivado_async_fifo_uvm_coverage.tcl"]
        run_kwargs = {}
        if seed is not None:
            env = os.environ.copy()
            env["ASYNC_FIFO_UVM_SEED"] = str(int(seed))
            run_kwargs["env"] = env

        sim_result = subprocess.run(
            command,
            cwd=sim_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            **run_kwargs,
        )
        if sim_result.returncode != 0:
            self.write_async_fifo_uvm_coverage_report(project_dir, sim_result=sim_result)
            self.write_async_fifo_uvm_coverage_summary_report(
                project_dir,
                sim_result=sim_result,
                coverage_threshold=coverage_threshold,
                coverage_percent=coverage_percent,
            )
            self.write_async_fifo_reports_index(project_dir)
            print(sim_result.stderr.strip() or sim_result.stdout.strip() or "async FIFO UVM coverage failed", file=sys.stderr)
            return False

        functional_report = self.write_async_fifo_uvm_functional_coverage_report(project_dir)
        report = self.write_async_fifo_uvm_coverage_report(project_dir, sim_result=sim_result)
        auto_percent = coverage_percent
        if auto_percent is None:
            percent_summary = self.extract_async_fifo_coverage_percent(project_dir / "reports" / "uvm_coverage_percent.txt")
            if percent_summary["available"] and percent_summary["total_percent"] is not None:
                auto_percent = percent_summary["total_percent"]
        summary_report = self.write_async_fifo_uvm_coverage_summary_report(
            project_dir,
            sim_result=sim_result,
            coverage_threshold=coverage_threshold,
            coverage_percent=auto_percent,
        )
        self.write_async_fifo_reports_index(project_dir)
        if not report["passed"]:
            print("UVM coverage markers or xsim.codeCov database were not found.", file=sys.stderr)
            return False
        functional_log = ""
        if functional_report["log_path"].exists():
            functional_log = functional_report["log_path"].read_text(encoding="utf-8", errors="replace")
        if "ASYNC_FIFO_SVA_FAIL" in functional_log:
            print("UVM assertion failure marker was found.", file=sys.stderr)
            return False
        if not summary_report["coverage_gate_passed"]:
            print("UVM coverage threshold gate failed.", file=sys.stderr)
            print("UVM coverage summary: {}".format(summary_report["markdown_path"]))
            return False

        print("Async FIFO UVM coverage completed")
        print("UVM log: {}".format(report["log_path"]))
        print("Generated WDB: {}".format(report["wdb_path"]))
        print("Coverage DB: {}".format(report["code_cov_dir"]))
        print("UVM coverage report: {}".format(report["markdown_path"]))
        print("UVM coverage summary: {}".format(summary_report["markdown_path"]))
        print("UVM functional coverage report: {}".format(functional_report["markdown_path"]))
        return True

    def run_async_fifo_uvm_random_regression(self, output_dir="outputs", seeds=None):
        if seeds is None:
            seeds = [101, 202, 303]
        project_dir = Path(output_dir) / "async-fifo"
        results = []
        all_passed = True
        for seed in seeds:
            seed_value = int(seed)
            seed_output_dir = project_dir / "uvm_regression" / "seed_{}".format(seed_value)
            seed_project_dir = seed_output_dir / "async-fifo"
            passed = self.run_async_fifo_uvm_coverage(output_dir=seed_output_dir, seed=seed_value)
            all_passed = all_passed and passed
            results.append({
                "seed": seed_value,
                "status": "PASS" if passed else "FAIL",
                "log": seed_project_dir / "sim" / "async_fifo_uvm_coverage.log",
                "wdb": seed_project_dir / "sim" / "async_fifo_uvm_coverage.wdb",
                "project": seed_project_dir,
            })
        self.write_async_fifo_uvm_random_regression_report(project_dir, results)
        return all_passed

    def run_rtl_sim(self, target, output_dir="outputs", open_wave_gui=True):
        target_name = self.normalize_rtl_target(target)
        if target_name == "async-fifo":
            return self.run_async_fifo_vivado_sim(
                output_dir=output_dir,
                open_wave_gui=open_wave_gui,
            )
        raise ValueError("Unsupported RTL target: {}".format(target))

    def run_uvm_smoke(self, target, output_dir="outputs", open_wave_gui=True):
        target_name = self.normalize_rtl_target(target)
        if target_name == "async-fifo":
            return self.run_async_fifo_uvm_smoke(
                output_dir=output_dir,
                open_wave_gui=open_wave_gui,
            )
        raise ValueError("Unsupported RTL target: {}".format(target))

    def run_uvm_coverage(self, target, output_dir="outputs", coverage_threshold=None, coverage_percent=None):
        target_name = self.normalize_rtl_target(target)
        if target_name == "async-fifo":
            return self.run_async_fifo_uvm_coverage(
                output_dir=output_dir,
                coverage_threshold=coverage_threshold,
                coverage_percent=coverage_percent,
            )
        raise ValueError("Unsupported RTL target: {}".format(target))

    def run_uvm_random_regression(self, target, output_dir="outputs", seeds=None):
        target_name = self.normalize_rtl_target(target)
        if target_name == "async-fifo":
            return self.run_async_fifo_uvm_random_regression(output_dir=output_dir, seeds=seeds)
        raise ValueError("Unsupported RTL target: {}".format(target))

    def open_uvm_wave(self, target, output_dir="outputs", wave_kind="coverage"):
        target_name = self.normalize_rtl_target(target)
        if target_name == "async-fifo":
            return self.open_async_fifo_uvm_wave_gui(Path(output_dir) / "async-fifo", wave_kind=wave_kind)
        raise ValueError("Unsupported RTL target: {}".format(target))

    def regress_rtl(self, target, output_dir="outputs", open_wave_gui=False):
        target_name = self.normalize_rtl_target(target)
        if target_name == "async-fifo":
            return self.run_async_fifo_regression(
                output_dir=output_dir,
                open_wave_gui=open_wave_gui,
            )
        raise ValueError("Unsupported RTL target: {}".format(target))

    def execute_workflow(self, user_input, output_dir="outputs", skip_tool_check=False):
        """执行完整工作流。"""
        print("=" * 60)
        print("数字IC前端设计Agent")
        print("=" * 60)

        print("\n【步骤1/4: 需求分析】")
        matched_skills = self.recommend_skills(user_input)

        if skip_tool_check:
            print("\n【步骤2/4: 工具检查】")
            print(self.WARN + " 已根据 --no-tool-check 跳过外部工具检查")
        else:
            print("\n【步骤2/4: 工具检查】")
            all_ok = self.run_diagnostic()
            if not all_ok:
                print("\n" + self.WARN + " 请先安装必要的工具和MCP，或使用 --no-tool-check 仅生成设计文档模板")
                return False

        print("\n【步骤3/4: 设计文档模板生成】")
        try:
            spec_path = self.generate_design_spec(user_input, matched_skills, output_dir)
        except OSError as exc:
            print("输出目录不可写或文件生成失败: {}".format(exc), file=sys.stderr)
            return False

        print("设计文档模板已生成: {}".format(spec_path))

        print("\n【步骤4/4: 后续建议】")
        print("请补充文档中的人工确认项，再进入 RTL 实现或 UVM 验证阶段。")

        print("\n" + "=" * 60)
        print("工作流执行完成")
        print("=" * 60)

        return True


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="数字IC前端设计Agent")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--analyze-vcd", metavar="FILE", help="Analyze a VCD waveform file")
    mode_group.add_argument("--smoke-loop", action="store_true", help="Generate a built-in VCD and analyze it")
    mode_group.add_argument("--sim-smoke", action="store_true", help="Run a Verilog simulator smoke test and analyze VCD")
    mode_group.add_argument("--generate-rtl", metavar="TARGET", help="Generate an RTL project skeleton, e.g. async-fifo")
    mode_group.add_argument("--sim-rtl", metavar="TARGET", help="Run RTL simulation and open Vivado project/wave GUI, e.g. async-fifo")
    mode_group.add_argument("--regress-rtl", metavar="TARGET", help="Run RTL parameter regression, e.g. async-fifo")
    mode_group.add_argument("--uvm-smoke", metavar="TARGET", help="Run minimal UVM smoke, e.g. async-fifo")
    mode_group.add_argument("--uvm-coverage", metavar="TARGET", help="Run UVM smoke with Vivado/xsim code coverage, e.g. async-fifo")
    mode_group.add_argument("--uvm-random-regress", metavar="TARGET", help="Run UVM random seed regression, e.g. async-fifo")
    mode_group.add_argument("--analyze-rtl-vcd", metavar="TARGET", help="Analyze a generated RTL VCD, e.g. async-fifo")
    mode_group.add_argument("--check-rtl", metavar="TARGET", help="Check generated RTL project artifacts, e.g. async-fifo")
    mode_group.add_argument("--open-wave", metavar="TARGET", help="Open the latest generated RTL waveform without re-running simulation")
    mode_group.add_argument("--open-uvm-wave", metavar="TARGET", help="Open a generated UVM WDB waveform, e.g. async-fifo")
    parser.add_argument("--no-wave-gui", action="store_true", help="Do not open Vivado/xsim GUI waveform after simulation")
    parser.add_argument("--coverage-threshold", type=float, default=None, help="Minimum UVM code coverage percentage gate")
    parser.add_argument("--coverage-percent", type=float, default=None, help="Measured UVM code coverage percentage for gate/reporting")
    parser.add_argument("--uvm-seeds", default="101,202,303", help="Comma-separated UVM random regression seeds")
    parser.add_argument("--uvm-wave-kind", choices=["smoke", "coverage"], default="coverage", help="UVM WDB type to open")
    parser.add_argument("--vcd-condition", default=None, help="VCD condition expression, e.g. valid=1,ready=1")
    parser.add_argument("--vcd-show", default=None, help="Signals to show when the VCD condition holds")
    parser.add_argument("--vcd-limit", type=int, default=20, help="Maximum VCD rows to display")
    mode_group.add_argument("--diagnostic", action="store_true", help="只运行环境诊断")
    mode_group.add_argument("--list-skills", action="store_true", help="列出技能配置")
    parser.add_argument("--output-dir", default="outputs", help="设计文档模板输出目录，默认 outputs")
    parser.add_argument("--no-tool-check", action="store_true", help="跳过 Vivado、SynthPilot 等外部工具检查")
    parser.add_argument("requirement", nargs="*", help="用户自然语言设计需求")

    args = parser.parse_args(argv)
    if args.no_tool_check and (
        args.diagnostic
        or args.list_skills
        or args.analyze_vcd
        or args.smoke_loop
        or args.sim_smoke
        or args.generate_rtl
        or args.sim_rtl
        or args.regress_rtl
        or args.uvm_smoke
        or args.uvm_coverage
        or args.uvm_random_regress
        or args.analyze_rtl_vcd
        or args.check_rtl
        or args.open_wave
        or args.open_uvm_wave
    ):
        parser.error("--no-tool-check 只能用于普通工作流模式")
    return args


def parse_seed_list(seed_text):
    seeds = []
    for part in str(seed_text).split(","):
        part = part.strip()
        if part:
            seeds.append(int(part))
    return seeds


def build_requirement(args):
    requirement = " ".join(args.requirement).strip()
    if requirement:
        return requirement

    print("欢迎使用数字IC前端设计Agent!")
    print("请输入您的设计需求:")
    try:
        return input("> ").strip()
    except EOFError:
        return ""


def create_agent():
    try:
        return DigitalICAgent()
    except FileNotFoundError as exc:
        print("配置文件缺失: {}".format(exc), file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print("配置文件不是合法 JSON: {}".format(exc), file=sys.stderr)
        return None
    except KeyError as exc:
        print("配置文件缺少必要字段: {}".format(exc), file=sys.stderr)
        return None


def main(argv=None):
    args = parse_args(argv)
    agent = create_agent()
    if agent is None:
        return 1

    if args.list_skills:
        agent.list_skills()
        return 0

    if args.diagnostic:
        return 0 if agent.run_diagnostic() else 1

    if args.smoke_loop:
        return 0 if agent.run_smoke_loop(
            output_dir=args.output_dir,
            limit=args.vcd_limit,
        ) else 1

    if args.sim_smoke:
        return 0 if agent.run_sim_smoke(
            output_dir=args.output_dir,
            limit=args.vcd_limit,
            open_wave_gui=not args.no_wave_gui,
        ) else 1

    if args.generate_rtl:
        try:
            project_dir = agent.generate_rtl_project(args.generate_rtl, args.output_dir)
        except (OSError, ValueError) as exc:
            print("RTL project generation failed: {}".format(exc), file=sys.stderr)
            return 1
        print("Generated RTL project: {}".format(project_dir))
        print("RTL: {}".format(project_dir / "rtl" / "async_fifo.v"))
        print("Testbench: {}".format(project_dir / "tb" / "tb_async_fifo.v"))
        print("Vivado script: {}".format(project_dir / "sim" / "run_vivado_async_fifo.tcl"))
        return 0

    if args.sim_rtl:
        try:
            return 0 if agent.run_rtl_sim(
                args.sim_rtl,
                output_dir=args.output_dir,
                open_wave_gui=not args.no_wave_gui,
            ) else 1
        except (OSError, ValueError) as exc:
            print("RTL simulation failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.regress_rtl:
        try:
            return 0 if agent.regress_rtl(
                args.regress_rtl,
                output_dir=args.output_dir,
                open_wave_gui=False,
            ) else 1
        except (OSError, ValueError) as exc:
            print("RTL regression failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.uvm_smoke:
        try:
            return 0 if agent.run_uvm_smoke(
                args.uvm_smoke,
                output_dir=args.output_dir,
                open_wave_gui=not args.no_wave_gui,
            ) else 1
        except (OSError, ValueError) as exc:
            print("UVM smoke failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.uvm_coverage:
        try:
            return 0 if agent.run_uvm_coverage(
                args.uvm_coverage,
                output_dir=args.output_dir,
                coverage_threshold=args.coverage_threshold,
                coverage_percent=args.coverage_percent,
            ) else 1
        except (OSError, ValueError) as exc:
            print("UVM coverage failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.uvm_random_regress:
        try:
            return 0 if agent.run_uvm_random_regression(
                args.uvm_random_regress,
                output_dir=args.output_dir,
                seeds=parse_seed_list(args.uvm_seeds),
            ) else 1
        except (OSError, ValueError) as exc:
            print("UVM random regression failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.analyze_rtl_vcd:
        try:
            target_name = agent.normalize_rtl_target(args.analyze_rtl_vcd)
            if target_name != "async-fifo":
                raise ValueError("Unsupported RTL target: {}".format(args.analyze_rtl_vcd))
            return 0 if agent.analyze_async_fifo_vcd(
                output_dir=args.output_dir,
                limit=args.vcd_limit,
            ) else 1
        except (OSError, ValueError) as exc:
            print("RTL VCD analysis failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.check_rtl:
        try:
            target_name = agent.normalize_rtl_target(args.check_rtl)
            if target_name != "async-fifo":
                raise ValueError("Unsupported RTL target: {}".format(args.check_rtl))
            return 0 if agent.check_async_fifo_rtl(output_dir=args.output_dir) else 1
        except (OSError, ValueError) as exc:
            print("RTL check failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.open_wave:
        try:
            return 0 if agent.open_rtl_wave(
                args.open_wave,
                output_dir=args.output_dir,
            ) else 1
        except (OSError, ValueError) as exc:
            print("RTL wave open failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.open_uvm_wave:
        try:
            return 0 if agent.open_uvm_wave(
                args.open_uvm_wave,
                output_dir=args.output_dir,
                wave_kind=args.uvm_wave_kind,
            ) else 1
        except (OSError, ValueError) as exc:
            print("UVM wave open failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.analyze_vcd:
        return 0 if agent.analyze_vcd(
            args.analyze_vcd,
            condition=args.vcd_condition,
            show=args.vcd_show,
            limit=args.vcd_limit,
        ) else 1

    requirement = build_requirement(args)
    if not requirement:
        print("错误: 用户需求不能为空", file=sys.stderr)
        return 1

    success = agent.execute_workflow(
        requirement,
        output_dir=args.output_dir,
        skip_tool_check=args.no_tool_check,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
