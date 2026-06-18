# Digital IC Agent Minimal Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Digital IC Agent prototype into a runnable, tested CLI that can diagnose the environment, list skills, and generate a Markdown design-spec template from a user requirement.

**Architecture:** Keep the implementation centered in `.trae/agent/agent.py` because the project is still small, but split responsibilities into clear methods on `DigitalICAgent` plus a thin `argparse` CLI layer. Configuration stays in JSON; generated artifacts go under `outputs/<project-slug>/design_spec.md` or the user-provided `--output-dir`.

**Tech Stack:** Python standard library, JSON configuration, Markdown docs, pytest for development tests.

---

## Scope Check

The approved spec covers one coherent subsystem: the Digital IC Agent CLI and its first artifact-generation loop. It does not require separate plans for RTL generation, UVM generation, Vivado automation, or LLM integration because those are explicitly non-goals.

## File Structure

Files to modify or create:

- Modify `.trae/agent/agent.py`
  - Owns CLI parsing, config loading, skill matching, diagnostics, workflow orchestration, and Markdown template generation.
- Modify `.trae/agent/agent.json`
  - Uses portable `uvx` command and array-form CLI check commands.
- Modify `.trae/config.json`
  - Uses portable `uvx` command for SynthPilot.
- Create `tests/test_agent.py`
  - Tests skill matching, config portability, CLI modes, and template generation.
- Create `requirements-dev.txt`
  - Declares pytest as the only development dependency.
- Create `.gitignore`
  - Ignores `.claude/worktrees/` only; does not remove or untrack `.claude/settings.local.json`.
- Modify `README.md`
  - Documents current capabilities, non-goals, CLI usage, and minimal loop.
- Modify `.trae/agent/README.md`
  - Documents Agent-specific CLI behavior and test instructions.

Generated during testing or manual runs, but not committed by tasks:

- `outputs/<project-slug>/design_spec.md`
- temporary pytest output directories

---

### Task 1: Add Initial Tests and Development Dependency

**Files:**
- Create: `tests/test_agent.py`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Create the pytest suite**

Create `tests/test_agent.py` with this exact content:

```python
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / ".trae" / "agent" / "agent.py"
AGENT_CONFIG_PATH = ROOT / ".trae" / "agent" / "agent.json"
TRAE_CONFIG_PATH = ROOT / ".trae" / "config.json"


def load_agent_module():
    spec = importlib.util.spec_from_file_location("digital_ic_agent", AGENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_agent(*args):
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_config_uses_portable_synthpilot_command():
    agent_config = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
    trae_config = json.loads(TRAE_CONFIG_PATH.read_text(encoding="utf-8"))

    assert agent_config["mcpServers"]["synthpilot"]["command"] == "uvx"
    assert trae_config["mcpServers"]["synthpilot"]["command"] == "uvx"


def test_cli_check_commands_are_arrays():
    agent_config = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))

    for tool in agent_config["cliTools"]:
        assert isinstance(tool["checkCommand"], list)
        assert all(isinstance(part, str) for part in tool["checkCommand"])
        assert tool["checkCommand"]


def test_analyze_requirement_matches_design_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("请生成这个模块的设计文档") == ["digital-ic-designer"]


def test_analyze_requirement_matches_rtl_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("实现 UART 的 Verilog RTL 代码") == ["digital-ic-rtl-designer"]


def test_analyze_requirement_matches_uvm_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert "digital-ic-verifier" in agent.analyze_requirement("使用 UVM 做前仿和覆盖率验证")


def test_analyze_requirement_defaults_to_rtl_skill():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert agent.analyze_requirement("做一个计数器") == ["digital-ic-rtl-designer"]
```

- [ ] **Step 2: Add development dependency file**

Create `requirements-dev.txt` with this exact content:

```text
pytest
```

- [ ] **Step 3: Run the new tests and verify expected failures**

Run:

```bash
python -m pytest tests/test_agent.py -v
```

Expected result before implementation:

- `test_config_uses_portable_synthpilot_command` fails because config still uses `C:\Users\Dell\.local\bin\uvx.exe`.
- `test_cli_check_commands_are_arrays` fails because `checkCommand` is still a string.
- Matching tests may pass because the old matcher already covers those inputs.

- [ ] **Step 4: Commit this test scaffold**

```bash
git add tests/test_agent.py requirements-dev.txt
git commit -m "test: add agent CLI baseline tests"
```

---

### Task 2: Make Configuration Portable and Ignore Claude Worktrees

**Files:**
- Modify: `.trae/agent/agent.json`
- Modify: `.trae/config.json`
- Create: `.gitignore`
- Test: `tests/test_agent.py`

- [ ] **Step 1: Update `.trae/agent/agent.json`**

Replace the SynthPilot MCP and CLI tool sections in `.trae/agent/agent.json` so those sections exactly match this content:

```json
  "mcpServers": {
    "synthpilot": {
      "command": "uvx",
      "args": ["synthpilot"],
      "description": "SynthPilot MCP：FPGA/ASIC设计工具集成",
      "required": true,
      "installGuide": "https://synthpilot.dev/install"
    }
  },
  "cliTools": [
    {
      "name": "vivado",
      "description": "Xilinx Vivado：FPGA设计与仿真工具",
      "required": true,
      "checkCommand": ["vivado", "-version"],
      "installGuide": "https://www.xilinx.com/support/download.html"
    },
    {
      "name": "uv",
      "description": "Python包管理器",
      "required": true,
      "checkCommand": ["uv", "--version"],
      "installGuide": "https://astral.sh/uv"
    }
  ],
```

Keep the rest of the JSON file unchanged and valid.

- [ ] **Step 2: Update `.trae/config.json`**

Replace `.trae/config.json` with this exact content:

```json
{
  "mcpServers": {
    "synthpilot": {
      "command": "uvx",
      "args": ["synthpilot"]
    }
  }
}
```

- [ ] **Step 3: Create `.gitignore`**

Create `.gitignore` with this exact content:

```gitignore
.claude/worktrees/
```

Do not remove, delete, or untrack `.claude/settings.local.json` in this task.

- [ ] **Step 4: Run the config tests**

Run:

```bash
python -m pytest tests/test_agent.py::test_config_uses_portable_synthpilot_command tests/test_agent.py::test_cli_check_commands_are_arrays -v
```

Expected result:

```text
2 passed
```

- [ ] **Step 5: Commit the config and ignore changes**

```bash
git add .trae/agent/agent.json .trae/config.json .gitignore
git commit -m "chore: make agent configuration portable"
```

---

### Task 3: Add CLI and Template Generation Tests

**Files:**
- Modify: `tests/test_agent.py`

- [ ] **Step 1: Append CLI tests to `tests/test_agent.py`**

Append this exact content to the end of `tests/test_agent.py`:

```python


def test_cli_list_skills_succeeds():
    result = run_agent("--list-skills")

    assert result.returncode == 0, result.stderr
    assert "digital-ic-designer" in result.stdout
    assert "digital-ic-rtl-designer" in result.stdout
    assert "digital-ic-verifier" in result.stdout


def test_cli_diagnostic_runs_as_independent_mode():
    result = run_agent("--diagnostic")

    assert result.returncode in (0, 1)
    assert "环境诊断" in result.stdout
    assert "CLI工具检查" in result.stdout
    assert "MCP服务器检查" in result.stdout


def test_cli_rejects_conflicting_modes():
    result = run_agent("--diagnostic", "--list-skills")

    assert result.returncode != 0
    assert "not allowed with argument" in result.stderr or "不能" in result.stderr or "conflict" in result.stderr.lower()


def test_cli_no_tool_check_generates_design_spec(tmp_path):
    result = run_agent(
        "--no-tool-check",
        "--output-dir",
        str(tmp_path),
        "设计一个UART控制器",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    spec_files = list(tmp_path.glob("*/design_spec.md"))
    assert len(spec_files) == 1

    content = spec_files[0].read_text(encoding="utf-8")
    assert "设计一个UART控制器" in content
    assert "digital-ic-rtl-designer" in content
    assert "初始设计说明模板" in content
    assert "后续人工确认项" in content


def test_cli_no_tool_check_is_invalid_for_diagnostic():
    result = run_agent("--diagnostic", "--no-tool-check")

    assert result.returncode != 0
    assert "not allowed with argument" in result.stderr or "tool" in result.stderr.lower() or "冲突" in result.stderr
```

- [ ] **Step 2: Run the CLI tests and verify expected failures**

Run:

```bash
python -m pytest tests/test_agent.py::test_cli_list_skills_succeeds tests/test_agent.py::test_cli_diagnostic_runs_as_independent_mode tests/test_agent.py::test_cli_rejects_conflicting_modes tests/test_agent.py::test_cli_no_tool_check_generates_design_spec tests/test_agent.py::test_cli_no_tool_check_is_invalid_for_diagnostic -v
```

Expected result before implementation:

- `--list-skills` fails because the CLI does not implement this option.
- conflicting mode tests fail because there is no `argparse` conflict handling.
- template generation fails because `--no-tool-check` and `--output-dir` are not implemented.
- `--diagnostic` may fail because it is treated as a user requirement in the old code.

- [ ] **Step 3: Commit the failing CLI tests**

```bash
git add tests/test_agent.py
git commit -m "test: cover agent CLI modes and template output"
```

---

### Task 4: Implement CLI, Diagnostics, and Design Spec Generation

**Files:**
- Replace: `.trae/agent/agent.py`
- Test: `tests/test_agent.py`

- [ ] **Step 1: Replace `.trae/agent/agent.py`**

Replace the entire contents of `.trae/agent/agent.py` with this exact code:

```python
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


try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


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
```

- [ ] **Step 2: Run the full test suite**

Run:

```bash
python -m pytest tests/test_agent.py -v
```

Expected result:

```text
10 passed
```

If the diagnostic test returns `1` because Vivado or SynthPilot is missing, that is still expected because the test accepts return code `0` or `1`.

- [ ] **Step 3: Run manual CLI smoke tests**

Run:

```bash
python .trae/agent/agent.py --list-skills
```

Expected output includes:

```text
digital-ic-designer
digital-ic-rtl-designer
digital-ic-verifier
```

Run:

```bash
python .trae/agent/agent.py --no-tool-check --output-dir outputs "设计一个UART控制器"
```

Expected output includes:

```text
设计文档模板已生成:
工作流执行完成
```

- [ ] **Step 4: Inspect the generated design document**

Open the generated file under `outputs/uart/design_spec.md` or the printed path and verify it includes:

```markdown
# 数字 IC 设计说明模板
```

and:

```text
设计一个UART控制器
```

Do not delete the generated file without user confirmation if it was created in the repository worktree. If cleanup is desired, ask the user before deleting because the user's global instruction requires confirmation before deletion.

- [ ] **Step 5: Commit the implementation**

```bash
git add .trae/agent/agent.py
git commit -m "feat: add agent CLI and design spec generation"
```

---

### Task 5: Update Project Documentation

**Files:**
- Replace: `README.md`
- Replace: `.trae/agent/README.md`

- [ ] **Step 1: Replace root `README.md`**

Replace `README.md` with this exact content:

```markdown
# Agent_IC_design_for_vivado

数字 IC 前端设计 Agent - 智能 IC 设计助手原型。

## 简介

本项目是一个数字 IC 前端设计 Agent 原型，当前聚焦于需求分析、技能匹配、工具环境诊断和设计文档模板生成。它为后续扩展到 RTL 生成、UVM 验证和 Vivado/SynthPilot 自动化提供基础结构。

## 当前已实现

- **智能需求分析**：根据用户输入中的关键词匹配设计阶段。
- **技能自动匹配**：从配置文件中选择设计文档、RTL 或 UVM 验证技能。
- **工具环境检查**：检测 Vivado、uv 和 SynthPilot MCP 是否可用。
- **CLI 控制**：支持诊断、技能列表、输出目录和跳过工具检查参数。
- **最小闭环**：根据用户需求生成 Markdown 设计说明模板。
- **自动化测试**：使用 pytest 覆盖核心匹配、配置和 CLI 行为。

## 当前未实现

- 自动生成完整可综合 RTL。
- 自动生成完整 UVM 验证环境。
- 自动调用 Vivado 完成仿真闭环。
- 自动综合、时序分析、波形解析或覆盖率统计。
- 接入真实 LLM 或 Trae skill 运行时进行智能内容生成。

## 项目结构

```text
├── .trae/
│   ├── agent/                 # Agent 核心组件
│   │   ├── agent.py           # Agent 入口脚本
│   │   ├── agent.json         # Agent 配置文件
│   │   ├── start_agent.bat    # Windows 启动脚本
│   │   └── README.md          # Agent 说明文档
│   ├── skills/                # 技能目录
│   │   ├── digital-ic-designer/
│   │   ├── digital-ic-rtl-designer/
│   │   └── digital-ic-verifier/
│   └── config.json            # MCP 配置
├── docs/                      # 项目文档
├── tests/                     # 自动化测试
├── requirements-dev.txt       # 开发测试依赖
└── README.md                  # 项目说明
```

## 技能列表

| 技能名称 | 功能 | 触发关键词 |
| --- | --- | --- |
| `digital-ic-designer` | 生成设计文档 | 设计文档、架构设计、需求分析 |
| `digital-ic-rtl-designer` | RTL 代码实现与常规验证 | RTL、Verilog、仿真、波形 |
| `digital-ic-verifier` | UVM 验证与前仿 | UVM、SystemVerilog、前仿 |

## 依赖工具

### 运行 Agent

- Python 3

### 完整环境诊断所需工具

- Xilinx Vivado
- uv
- SynthPilot MCP，可通过 `uvx synthpilot` 调用

如果只是体验设计文档模板生成，可以使用 `--no-tool-check` 跳过外部 EDA 工具检查。

## 使用方法

### 列出技能

```bash
python .trae/agent/agent.py --list-skills
```

### 运行环境诊断

```bash
python .trae/agent/agent.py --diagnostic
```

诊断全部通过时返回成功；缺少 Vivado、uv 或 SynthPilot MCP 时返回非零状态码并显示安装指南。

### 生成设计文档模板

```bash
python .trae/agent/agent.py --no-tool-check --output-dir outputs "设计一个UART控制器"
```

生成路径类似：

```text
outputs/uart/design_spec.md
```

### 交互式模式

```bash
python .trae/agent/agent.py --no-tool-check
```

随后根据提示输入设计需求。

## 开发与测试

安装测试依赖：

```bash
python -m pip install -r requirements-dev.txt
```

运行测试：

```bash
python -m pytest tests/test_agent.py -v
```

## 工作流

```text
用户输入需求
    │
    ▼
需求分析与技能匹配
    │
    ▼
工具检查（可用 --no-tool-check 跳过）
    │
    ▼
生成设计说明模板
    │
    ▼
人工补充约束并进入后续 RTL/UVM 阶段
```

## 许可证

MIT License
```

- [ ] **Step 2: Replace `.trae/agent/README.md`**

Replace `.trae/agent/README.md` with this exact content:

```markdown
# 数字 IC 前端设计 Agent

## 简介

数字 IC 前端设计 Agent 是一个智能设计助手原型，当前实现以下能力：

- 分析用户自然语言需求。
- 根据关键词匹配设计文档、RTL 或 UVM 验证技能。
- 检查 Vivado、uv 和 SynthPilot MCP 环境。
- 生成 Markdown 设计说明模板，作为后续设计讨论起点。

当前版本不会自动生成完整 RTL、UVM 验证环境或 Vivado 仿真结果。

## 架构

```text
┌─────────────────────────────────────────────────────────┐
│              Digital IC Frontend Agent                  │
├─────────────────────────────────────────────────────────┤
│  CLI 参数解析                                           │
│        │                                                │
│        ▼                                                │
│  需求分析 ──▶ 技能匹配 ──▶ 工具检查（可跳过）           │
│        │                                                │
│        ▼                                                │
│  Markdown 设计说明模板生成                              │
└─────────────────────────────────────────────────────────┘
```

## 技能列表

| 技能名称 | 功能 | 触发关键词 |
| --- | --- | --- |
| `digital-ic-designer` | 生成设计文档 | 设计文档、架构设计、需求分析 |
| `digital-ic-rtl-designer` | RTL 代码实现与常规验证 | RTL、Verilog、仿真、波形 |
| `digital-ic-verifier` | UVM 验证与前仿 | UVM、SystemVerilog、前仿 |

## 依赖工具

### 必需

- Python 3

### 环境诊断检查项

- Xilinx Vivado
- uv
- SynthPilot MCP

如果本机没有完整 EDA 环境，可以使用 `--no-tool-check` 仅生成设计说明模板。

## CLI 使用

### 列出技能

```bash
python .trae/agent/agent.py --list-skills
```

### 运行诊断

```bash
python .trae/agent/agent.py --diagnostic
```

### 生成设计说明模板

```bash
python .trae/agent/agent.py --no-tool-check --output-dir outputs "设计一个UART控制器"
```

### 交互式输入

```bash
python .trae/agent/agent.py --no-tool-check
```

## 参数说明

| 参数 | 说明 |
| --- | --- |
| `--diagnostic` | 只运行环境诊断 |
| `--list-skills` | 列出技能配置 |
| `--output-dir <path>` | 指定产物根目录，默认 `outputs` |
| `--no-tool-check` | 跳过 Vivado、SynthPilot 等外部工具检查 |
| `requirement` | 用户自然语言设计需求 |

`--diagnostic`、`--list-skills` 和普通工作流互斥。`--no-tool-check` 只适用于普通工作流。

## 输出文档

普通工作流会生成：

```text
outputs/<project-slug>/design_spec.md
```

文档包含：

1. 需求摘要。
2. Agent 匹配结果。
3. 初步设计目标。
4. 建议模块划分。
5. 初步接口定义。
6. 验证计划占位。
7. 后续人工确认项。

## 开发测试

安装测试依赖：

```bash
python -m pip install -r requirements-dev.txt
```

运行测试：

```bash
python -m pytest tests/test_agent.py -v
```

## 故障排除

| 问题 | 解决方案 |
| --- | --- |
| Vivado 未找到 | 安装 Vivado 并添加到 PATH，或使用 `--no-tool-check` 仅生成模板 |
| uv 未找到 | 安装 uv，参考 https://astral.sh/uv |
| SynthPilot 不可用 | 确认 `uvx synthpilot --version` 可运行 |
| 技能文件缺失 | 检查 `.trae/skills` 目录 |

## 版本历史

| 版本 | 日期 | 更新内容 |
| --- | --- | --- |
| v1.1 | 2026-06-18 | 增加 CLI 参数、诊断模式、技能列表和设计说明模板生成 |
| v1.0 | 2026-05-15 | 初始版本 |
```

- [ ] **Step 3: Run markdown-related smoke checks by reading key headings**

Run:

```bash
python - <<'PY'
from pathlib import Path
for path in [Path('README.md'), Path('.trae/agent/README.md')]:
    text = path.read_text(encoding='utf-8')
    assert '--diagnostic' in text
    assert '--list-skills' in text
    assert '--no-tool-check' in text
    assert 'design_spec.md' in text
print('docs smoke check passed')
PY
```

Expected output:

```text
docs smoke check passed
```

- [ ] **Step 4: Run tests after docs update**

Run:

```bash
python -m pytest tests/test_agent.py -v
```

Expected result:

```text
10 passed
```

- [ ] **Step 5: Commit documentation updates**

```bash
git add README.md .trae/agent/README.md
git commit -m "docs: document agent minimal loop"
```

---

### Task 6: Final Verification and Status Report

**Files:**
- No planned source changes.

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
python -m pytest tests/test_agent.py -v
```

Expected result:

```text
10 passed
```

- [ ] **Step 2: Verify the skill list command**

Run:

```bash
python .trae/agent/agent.py --list-skills
```

Expected output includes all three skills:

```text
digital-ic-designer
digital-ic-rtl-designer
digital-ic-verifier
```

- [ ] **Step 3: Verify diagnostic mode**

Run:

```bash
python .trae/agent/agent.py --diagnostic
```

Expected output includes:

```text
数字IC前端设计Agent - 环境诊断
【CLI工具检查】
【MCP服务器检查】
【技能文件检查】
```

Expected exit code is `0` if all tools exist or `1` if Vivado/SynthPilot/uv is missing.

- [ ] **Step 4: Verify minimal loop in a temporary output directory**

Run:

```bash
python .trae/agent/agent.py --no-tool-check --output-dir .tmp-agent-output "设计一个UART控制器"
```

Expected output includes:

```text
设计文档模板已生成:
工作流执行完成
```

Expected generated file:

```text
.tmp-agent-output/uart/design_spec.md
```

Open the file and verify it contains:

```text
设计一个UART控制器
```

Because this step creates `.tmp-agent-output/`, ask the user before deleting it. Do not delete it automatically.

- [ ] **Step 5: Check git status**

Run:

```bash
git status --short
```

Expected tracked changes should include only intentional files if commits were not made during execution:

```text
 M .trae/agent/README.md
 M .trae/agent/agent.json
 M .trae/agent/agent.py
 M .trae/config.json
 M README.md
?? .gitignore
?? requirements-dev.txt
?? tests/
?? docs/superpowers/
```

The actual status may also show pre-existing local changes to `.claude/settings.local.json`; do not revert, delete, or untrack that file without explicit user confirmation.

- [ ] **Step 6: Provide final report**

Report these items to the user:

```markdown
已完成：
- 实现 `--diagnostic`、`--list-skills`、`--output-dir`、`--no-tool-check`。
- 移除 SynthPilot 的个人路径硬编码，改为 `uvx synthpilot`。
- 将 CLI 检查命令改为数组格式。
- 实现 `outputs/<project-slug>/design_spec.md` 设计文档模板生成。
- 新增 pytest 测试和 `requirements-dev.txt`。
- 更新 README 和 Agent README。
- 新增 `.gitignore` 忽略 `.claude/worktrees/`。

验证：
- `python -m pytest tests/test_agent.py -v`：通过。
- `python .trae/agent/agent.py --list-skills`：通过。
- `python .trae/agent/agent.py --diagnostic`：已运行，按本机工具安装情况返回结果。
- `python .trae/agent/agent.py --no-tool-check --output-dir .tmp-agent-output "设计一个UART控制器"`：已生成设计文档模板。

注意：
- 未删除或取消跟踪 `.claude/settings.local.json`。
- 如需清理 `.tmp-agent-output/` 或 `outputs/`，需用户确认后再删除。
```

- [ ] **Step 7: Commit final verification notes only if files changed**

If Task 6 only ran commands and did not change files, do not create a commit. If a final tracked documentation adjustment was made during verification, commit only that adjustment:

```bash
git add <changed-doc-file>
git commit -m "docs: clarify agent verification notes"
```

---

## Self-Review

Spec coverage:

- CLI flags are covered in Tasks 3 and 4.
- `--diagnostic` independent mode is covered in Tasks 3, 4, and 6.
- `--list-skills` is covered in Tasks 3, 4, and 6.
- `--output-dir` and `--no-tool-check` are covered in Tasks 3, 4, and 6.
- Portable SynthPilot config and array-form `checkCommand` are covered in Tasks 1 and 2.
- Design document template output is covered in Tasks 3, 4, and 6.
- Tests and `requirements-dev.txt` are covered in Task 1.
- README updates are covered in Task 5.
- `.claude/worktrees/` ignore rule is covered in Task 2.
- `.claude/settings.local.json` is explicitly left untouched in Tasks 2 and 6.

Placeholder scan:

- The plan contains no `TBD`, `TODO`, or incomplete implementation steps.
- All code-writing steps include exact file content or exact code to append.
- All verification steps include commands and expected output.

Type and signature consistency:

- `DigitalICAgent.analyze_requirement(user_input)` remains available for tests.
- `DigitalICAgent.execute_workflow(user_input, output_dir="outputs", skip_tool_check=False)` matches CLI use.
- `main(argv=None)` and `parse_args(argv=None)` are pure enough for future direct unit tests.
- JSON `checkCommand` values are arrays and `normalize_command()` still supports strings for backwards compatibility.
