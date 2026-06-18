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
import hashlib
import json
import re
import shlex
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
    mode_group.add_argument("--diagnostic", action="store_true", help="只运行环境诊断")
    mode_group.add_argument("--list-skills", action="store_true", help="列出技能配置")
    parser.add_argument("--output-dir", default="outputs", help="设计文档模板输出目录，默认 outputs")
    parser.add_argument("--no-tool-check", action="store_true", help="跳过 Vivado、SynthPilot 等外部工具检查")
    parser.add_argument("requirement", nargs="*", help="用户自然语言设计需求")

    args = parser.parse_args(argv)
    if args.no_tool_check and (args.diagnostic or args.list_skills):
        parser.error("--no-tool-check 只能用于普通工作流模式")
    return args


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
