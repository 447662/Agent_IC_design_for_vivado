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
