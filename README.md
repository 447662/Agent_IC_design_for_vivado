# Agent_IC_design_for_vivado

数字IC前端设计Agent - 智能IC设计助手

## 简介

本项目是一个专业的数字IC前端设计Agent，整合了设计、实现、验证全流程，能够智能分析用户需求并自动匹配合适的技能。

## 功能特性

- **智能需求分析** - 根据用户输入自动识别设计需求
- **技能自动匹配** - 根据需求自动选择合适的设计技能
- **工具环境检查** - 自动检测Vivado、SynthPilot等工具
- **完整设计流程** - 支持从需求分析到验证报告的全流程

## 项目结构

```
├── .trae/
│   ├── agent/           # Agent核心组件
│   │   ├── agent.py     # Agent入口脚本
│   │   ├── agent.json   # Agent配置文件
│   │   ├── start_agent.bat  # Windows启动脚本
│   │   └── README.md    # Agent说明文档
│   ├── skills/          # 技能目录
│   │   ├── digital-ic-designer/    # 设计文档生成
│   │   ├── digital-ic-rtl-designer/ # RTL代码实现
│   │   └── digital-ic-verifier/    # UVM验证
│   └── config.json      # MCP配置
└── README.md            # 项目说明
```

## 技能列表

| 技能名称 | 功能 | 触发关键词 |
|----------|------|------------|
| digital-ic-designer | 生成设计文档 | 设计文档、架构设计、需求分析 |
| digital-ic-rtl-designer | RTL代码实现与常规验证 | RTL、Verilog、仿真、波形 |
| digital-ic-verifier | UVM验证与前仿 | UVM、SystemVerilog、前仿 |

## 使用方法

### 启动Agent

```bash
# Windows
.\.trae\agent\start_agent.bat

# 或直接运行Python
python .trae/agent/agent.py "我需要设计一个I2C控制器"
```

### 交互式模式

```bash
python .trae/agent/agent.py
```

## 工作流

```
用户输入需求
    │
    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 需求分析    │───▶│ 工具检查    │───▶│ 技能匹配    │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                              │
                                              ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 执行任务    │───▶│ 结果验证    │───▶│ 生成报告    │
└─────────────┘    └─────────────┘    └─────────────┘
```

## 依赖工具

- **Xilinx Vivado** - FPGA设计与仿真工具
- **SynthPilot MCP** - FPGA/ASIC设计集成工具
- **Python** - 脚本运行环境

## 许可证

MIT License

---

*数字IC前端设计Agent - 让IC设计更智能*
