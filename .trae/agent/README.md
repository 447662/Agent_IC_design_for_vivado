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
| uv 未找到 | 安装 uv，参考 [uv 安装文档](https://astral.sh/uv) |
| SynthPilot 不可用 | 确认 `uvx synthpilot --version` 可运行 |
| 技能文件缺失 | 检查 `.trae/skills` 目录 |

## 版本历史

| 版本 | 日期 | 更新内容 |
| --- | --- | --- |
| v1.1 | 2026-06-18 | 增加 CLI 参数、诊断模式、技能列表和设计说明模板生成 |
| v1.0 | 2026-05-15 | 初始版本 |
