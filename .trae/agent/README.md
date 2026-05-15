# 数字IC前端设计Agent

## 简介

数字IC前端设计Agent是一个智能设计助手，整合了数字IC设计的全流程技能，能够：
- 智能分析用户需求
- 自动匹配合适的设计技能
- 检查工具环境并引导安装
- 执行完整的设计流程

## 架构

```
┌─────────────────────────────────────────────────────────┐
│              Digital IC Frontend Agent                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐     ┌─────────────┐     ┌───────────┐  │
│  │ 需求分析    │────▶│ 技能匹配    │────▶│ 工具检查  │  │
│  └─────────────┘     └─────────────┘     └─────┬─────┘  │
│                                               │        │
│                                               ▼        │
│                    ┌──────────────────────────────┐     │
│                    │      技能执行引擎            │     │
│                    └─────────────┬──────────────┘     │
│                                  │                    │
│         ┌────────────────────────┼────────────────┐    │
│         ▼                        ▼                ▼    │
│  ┌─────────────┐        ┌─────────────┐   ┌─────────┐ │
│  │ Designer    │        │ RTL Designer│   │ Verifier│ │
│  │ (设计文档)   │        │ (代码实现)   │   │ (UVM)   │ │
│  └─────────────┘        └─────────────┘   └─────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 技能列表

| 技能名称 | 功能 | 触发关键词 |
|----------|------|------------|
| digital-ic-designer | 生成设计文档 | 设计文档、架构设计、需求分析 |
| digital-ic-rtl-designer | RTL代码实现与常规验证 | RTL、Verilog、仿真、波形 |
| digital-ic-verifier | UVM验证与前仿 | UVM、SystemVerilog、前仿 |

## 依赖工具

### 必须安装
- **Xilinx Vivado** - FPGA设计与仿真工具
- **SynthPilot MCP** - FPGA/ASIC设计集成工具
- **Python** - 脚本运行环境
- **uv** - Python包管理器

### 可选安装
- Mentor Questa - 高级验证工具
- Synopsys VCS - 高性能仿真工具

## 使用方法

### 方法1: 命令行启动

```bash
# Windows
.\.trae\agent\start_agent.bat "我需要设计一个I2C控制器"

# 或直接运行Python
python .trae/agent/agent.py "设计一个UART接口"
```

### 方法2: 交互式模式

```bash
.\.trae\agent\start_agent.bat
```

然后按照提示输入设计需求。

### 方法3: 诊断模式

```bash
python .trae/agent/agent.py --diagnostic
```

## 智能匹配规则

### 技能匹配优先级

1. **设计文档生成** - 检测到"设计文档"、"架构设计"等关键词
2. **UVM验证** - 检测到"UVM"、"前仿"、"功能验证"等关键词
3. **RTL实现** - 默认匹配，检测到"RTL"、"Verilog"、"仿真"等关键词

### 示例

| 用户需求 | 匹配技能 |
|----------|----------|
| "设计一个I2C控制器" | digital-ic-designer |
| "实现UART的Verilog代码" | digital-ic-rtl-designer |
| "用UVM验证SPI模块" | digital-ic-verifier |
| "进行前仿真" | digital-ic-verifier |

## 工作流

```
用户输入需求
    │
    ▼
┌─────────────┐
│ 需求分析    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 工具检查    │
│ (MCP/CLI)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 技能匹配    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 执行任务    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 结果验证    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 生成报告    │
└─────────────┘
```

## 配置文件

### agent.json

```json
{
  "name": "digital-ic-frontend-agent",
  "version": "1.0.0",
  "skills": [...],
  "mcpServers": {...},
  "cliTools": [...],
  "workflow": {...}
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| name | Agent名称 |
| version | 版本号 |
| skills | 技能列表 |
| mcpServers | MCP服务器配置 |
| cliTools | CLI工具配置 |
| workflow | 工作流配置 |

## 安装指南

### 1. 安装依赖工具

1. **安装Xilinx Vivado**
   - 下载地址: https://www.xilinx.com/support/download.html
   - 安装完成后添加到系统PATH

2. **安装SynthPilot**
   ```bash
   uv tool install synthpilot
   ```

3. **安装Python依赖**
   ```bash
   pip install -r requirements.txt
   ```

### 2. 配置Agent

无需额外配置，Agent会自动检测环境。

## 故障排除

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| Vivado未找到 | 安装Vivado并添加到PATH |
| SynthPilot不可用 | 运行 `uv tool install synthpilot` |
| 技能文件缺失 | 检查 `.trae/skills` 目录 |

### 诊断命令

```bash
python .trae/agent/agent.py --diagnostic
```

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.0 | 2026-05-15 | 初始版本 |

## 许可证

MIT License

---

*数字IC前端设计Agent - 让IC设计更智能*
