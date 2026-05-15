---
name: "digital-ic-rtl-designer"
description: "专业数字IC设计师技能：将设计文档转化为符合Verilog代码规范的RTL实现，自动生成可综合代码、testbench和验证报告。Invoke when user needs to convert design documentation to RTL code, or needs Verilog implementation following industry standards."
---

# 数字IC设计师技能

## 技能概述

本技能参考菜鸟教程《Verilog代码规范》(https://www.runoob.com/w3cnote/verilog2-codeguide.html)，将数字IC设计文档自动转化为符合行业规范的Verilog RTL代码。核心能力包括：RTL代码生成、testbench编写、仿真验证和报告生成。

---

## 核心功能

### 1. RTL代码自动生成

根据设计文档生成符合规范的Verilog代码：

**代码规范要求：**
- 模块命名：使用下划线分隔，小写字母（如 `i2c_top`）
- 信号命名：使用下划线分隔，小写字母（如 `sda_in`）
- 端口顺序：input -> output -> inout
- 缩进风格：4空格缩进
- 注释规范：模块、端口、关键逻辑必须有注释
- 参数化设计：使用 `parameter` 定义可变参数

**生成的文件类型：**
| 文件类型 | 说明 |
|----------|------|
| `*.v` | RTL源文件 |
| `*_tb.v` | 测试平台文件 |
| `*.sv` | SystemVerilog验证文件（可选） |

### 2. 仿真环境配置

自动检测并配置仿真环境：

**支持的仿真工具：**
- Xilinx Vivado（默认）
- Mentor ModelSim
- Synopsys VCS
- Cadence Xcelium

**MCP检查与配置：**
- 检测SynthPilot MCP是否安装
- 如未安装，引导用户进行安装配置
- 生成Vivado仿真脚本

### 3. Testbench编写

根据设计文档自动生成testbench：

**测试验证内容：**
- 模块接口连接
- 时钟和复位信号生成
- 测试向量注入
- 预期结果检查
- 覆盖率收集

**Testbench结构：**
```
┌─────────────────┐
│  Clock Generator│
└────────┬────────┘
         │
┌────────▼────────┐     ┌─────────────────┐
│   Driver        │────▶│  DUT (RTL)      │
│  (测试激励)      │◀────│  (被测模块)      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   Monitor       │     │   Coverage     │
│  (信号监控)      │     │  (覆盖率收集)    │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Scoreboard     │
│  (结果比对)      │
└─────────────────┘
```

### 4. Python仿真结果分析

使用Python程序处理仿真输出：

**分析流程：**
1. 运行仿真获取波形数据
2. 解析VCD或FSDB文件
3. 检查信号时序和逻辑正确性
4. 生成分析报告
5. 识别不符合规范的问题

**Python分析脚本功能：**
- 信号状态检查
- 时序违例检测
- 覆盖率统计
- 自动修复建议

### 5. 设计验证报告生成

生成标准化的验证报告（Markdown格式）：

**报告章节：**
| 章节 | 内容 |
|------|------|
| 验证概述 | 验证目标和范围 |
| 测试用例 | 测试覆盖情况 |
| 仿真结果 | 通过/失败统计 |
| 覆盖率报告 | 语句/分支/条件覆盖 |
| 问题列表 | 发现的问题和修复建议 |

---

## 工作流程

### 完整设计流程

```
设计文档输入
    │
    ▼
┌─────────────────┐
│ 需求分析        │
│ (解析设计文档)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RTL代码生成     │
│ (Verilog规范)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Testbench编写   │
│ (测试向量生成)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 仿真环境配置    │
│ (检测MCP/工具)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 运行仿真        │
│ (Vivado/SynthPilot)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Python分析      │
│ (结果处理)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 问题修复        │
│ (迭代优化)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 验证报告生成    │
│ (.md格式)       │
└─────────────────┘
```

### 输入输出示例

**输入：**
```
设计文档: docs/I2C_Module_Design_Spec.md

文档内容包含:
- 模块接口定义
- 寄存器映射
- 状态机描述
- 时序要求
```

**输出：**
```
src/
├── i2c_top.v          # 顶层模块
├── apb_slave.v        # APB接口模块
├── i2c_core.v         # I2C核心模块
├── control_logic.v    # 控制逻辑模块
├── config_regs.v      # 配置寄存器
├── interrupt_ctrl.v   # 中断控制模块

tb/
├── i2c_tb.v           # 顶层测试平台
├── i2c_driver.v       # 驱动模块
├── i2c_monitor.v      # 监控模块
├── i2c_bus_model.v    # I2C总线模型

docs/
├── verification_report.md  # 验证报告
```

---

## Verilog代码规范

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块名 | 小写+下划线 | `i2c_top` |
| 信号名 | 小写+下划线 | `sda_in`, `pclk` |
| 参数名 | 大写+下划线 | `DATA_WIDTH`, `ADDR_WIDTH` |
| 常量名 | 大写+下划线 | `MAX_COUNT` |
| 状态机状态 | 大写 | `IDLE`, `START`, `DATA_TX` |

### 代码结构

```verilog
// 模块头部注释
// -----------------------------------------------------------------------------
// Module Name: i2c_core
// Description: I2C协议核心引擎，支持主/从模式
// Author: Digital IC Designer
// Date: 2026-05-15
// -----------------------------------------------------------------------------
module i2c_core(
    // 时钟和复位
    input        PCLK,              // 系统时钟
    input        PRESETn,           // 复位信号(低有效)
    
    // APB接口
    input  [31:0] PADDR,           // 地址总线
    input         PSEL,             // 片选信号
    input         PENABLE,          // 使能信号
    input         PWRITE,           // 写使能
    input  [31:0] PWDATA,           // 写数据
    output [31:0] PRDATA,           // 读数据
    output        PREADY,           // 准备就绪
    
    // I2C总线接口
    input        SDA_IN,            // SDA输入
    output       SDA_OUT,           // SDA输出
    output       SDA_OE,            // SDA输出使能
    input        SCL_IN,            // SCL输入
    output       SCL_OUT,           // SCL输出
    output       SCL_OE             // SCL输出使能
);

// 参数定义
parameter DATA_WIDTH = 8;
parameter ADDR_WIDTH = 7;
parameter CLK_DIV    = 125;

// 内部信号声明
reg  [DATA_WIDTH-1:0] shift_reg;   // 移位寄存器
reg  [ADDR_WIDTH-1:0] addr_reg;    // 地址寄存器
reg                   tx_ready;     // 发送就绪
wire                  rx_ready;     // 接收就绪

// 组合逻辑
assign rx_ready = (state == IDLE);

// 时序逻辑
always @(posedge PCLK or negedge PRESETn) begin
    if (!PRESETn) begin
        // 复位初始化
        shift_reg <= 'b0;
        tx_ready  <= 1'b0;
    end else begin
        // 正常逻辑
        case(state)
            IDLE: begin
                // 空闲状态处理
            end
            START: begin
                // 起始条件处理
            end
            // ... 其他状态
        endcase
    end
end

endmodule
```

### 注释规范

1. **模块头部注释**：必须包含模块名称、描述、作者、日期
2. **端口注释**：每个端口必须有注释说明用途
3. **信号注释**：关键信号必须有注释
4. **逻辑注释**：复杂逻辑必须有注释说明
5. **状态机注释**：每个状态必须有注释

---

## 仿真验证流程

### 步骤1：检查仿真环境

```python
# 检查SynthPilot MCP
import subprocess

def check_synthpilot():
    try:
        result = subprocess.run(['uvx', 'synthpilot', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            return False
    except FileNotFoundError:
        return False

# 检查Vivado
def check_vivado():
    try:
        result = subprocess.run(['vivado', '-version'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False
```

### 步骤2：生成仿真脚本

**Vivado仿真脚本示例：**
```tcl
# create_project.tcl
create_project i2c_sim ./sim -part xc7k325tffg900-2
set_property "part" "xc7k325tffg900-2" [current_project]

# 添加源文件
add_files ./src/i2c_top.v
add_files ./src/apb_slave.v
add_files ./src/i2c_core.v

# 添加测试文件
add_files -fileset sim_1 ./tb/i2c_tb.v
add_files -fileset sim_1 ./tb/i2c_driver.v

# 设置顶层
set_property top i2c_tb [current_fileset]

# 运行仿真
launch_simulation
run 1ms
```

### 步骤3：波形自动显示（新增规则）

**自动波形显示规则：**
当客户需要查看波形图时，技能将执行以下流程：
1. **自动调试**: 自动检测并修复仿真错误（如语法错误、连接错误等）
2. **批量运行**: 在后台批量运行仿真，确保波形数据正确生成
3. **自动打开**: 直接打开Vivado波形查看器，无需客户手动操作
4. **预设信号**: 自动添加关键信号到波形窗口（如时钟、复位、数据总线、控制信号等）
5. **自动运行**: 自动执行仿真并显示波形结果

**自动波形脚本示例：**
```tcl
# auto_waveform.tcl
launch_simulation
run 100us

# 自动添加关键信号到波形
add_wave /i2c_tb/PCLK
add_wave /i2c_tb/PRESETn
add_wave /i2c_tb/SDA
add_wave /i2c_tb/SCL
add_wave /i2c_tb/u_i2c_top/u_i2c_core/state
add_wave /i2c_tb/u_i2c_top/u_i2c_core/shift_reg
add_wave /i2c_tb/u_i2c_top/u_config_regs/ctrl_reg
add_wave /i2c_tb/u_i2c_top/u_config_regs/status_reg

# 自动打开波形窗口
update_wave
zoom full
```

### 步骤4：Python结果分析

```python
# analysis.py
import vcd

def analyze_waveform(vcd_file):
    with open(vcd_file, 'r') as f:
        wave = vcd.read(f)
    
    # 检查信号
    signals = wave.signals
    errors = []
    
    # 检查SDA/SCL时序
    sda = wave['SDA']
    scl = wave['SCL']
    
    for i in range(len(sda) - 1):
        # 检查建立时间
        if sda[i] != sda[i+1] and scl[i] == 1:
            errors.append(f"SDA变化时SCL为高电平，时序违例 @ {wave.times[i]}")
    
    return errors

def generate_report(errors, coverage):
    report = f"""# 验证报告

## 测试结果

### 错误统计
共发现 {len(errors)} 个问题

### 覆盖率
- 语句覆盖率: {coverage['statement']}%
- 分支覆盖率: {coverage['branch']}%
- 条件覆盖率: {coverage['condition']}%

## 问题列表
"""
    for i, error in enumerate(errors, 1):
        report += f"- **问题{i}**: {error}\n"
    
    return report
```

---

## 验证报告模板

### 验证报告结构

```markdown
# 设计验证报告

**项目名称**: I2C Controller  
**模块名称**: i2c_top  
**验证日期**: 2026-05-15  
**工具**: Xilinx Vivado 2023.1

---

## 1. 验证概述

### 1.1 验证目标
验证I2C控制器的功能正确性，包括：
- 主模式读写操作
- 从模式地址匹配和数据收发
- 中断功能
- 时序约束满足

### 1.2 验证范围
| 模块 | 验证状态 |
|------|----------|
| i2c_top | ✅ |
| apb_slave | ✅ |
| i2c_core | ✅ |
| control_logic | ✅ |
| config_regs | ✅ |

---

## 2. 测试用例

### 2.1 测试用例清单

| 测试ID | 测试名称 | 目标 | 结果 |
|--------|----------|------|------|
| TC001 | 主模式单字节写 | 验证基本写操作 | ✅ 通过 |
| TC002 | 主模式单字节读 | 验证基本读操作 | ✅ 通过 |
| TC003 | 主模式多字节写 | 验证连续写操作 | ✅ 通过 |
| TC004 | 主模式多字节读 | 验证连续读操作 | ✅ 通过 |
| TC005 | 从模式地址匹配 | 验证地址识别 | ✅ 通过 |
| TC006 | 从模式数据收发 | 验证从模式通信 | ✅ 通过 |
| TC007 | 仲裁丢失处理 | 验证多主设备仲裁 | ✅ 通过 |
| TC008 | 时钟拉伸 | 验证时钟拉伸功能 | ✅ 通过 |

### 2.2 测试覆盖率

| 覆盖率类型 | 目标值 | 实际值 | 状态 |
|-----------|--------|--------|------|
| 语句覆盖率 | 95% | 98% | ✅ |
| 分支覆盖率 | 90% | 92% | ✅ |
| 条件覆盖率 | 85% | 88% | ✅ |
| FSM覆盖率 | 100% | 100% | ✅ |

---

## 3. 问题列表

### 3.1 已修复问题

| 问题ID | 描述 | 严重程度 | 修复方式 |
|--------|------|----------|----------|
| BUG001 | SDA输出使能时序错误 | 高 | 调整状态机转换条件 |
| BUG002 | 地址寄存器复位未初始化 | 中 | 添加复位赋值 |

### 3.2 待处理问题

| 问题ID | 描述 | 严重程度 | 建议 |
|--------|------|----------|------|
| ISS001 | 快速模式下时序余量较小 | 低 | 优化时钟分频逻辑 |

---

## 4. 结论

**验证状态**: ✅ 通过  

所有测试用例通过，覆盖率达到目标要求。设计可以进入下一阶段（综合/实现）。

---

**审核人**:  
**日期**:
```

---

## 技术参考

### Verilog代码规范来源
- https://www.runoob.com/w3cnote/verilog2-codeguide.html

### 工具链
- **仿真**: Xilinx Vivado, ModelSim, VCS
- **综合**: Synopsys DC, Xilinx Vivado
- **验证**: SystemVerilog, Python

### 参考文档
- IEEE Std 1364-2005 (Verilog HDL)
- IEEE Std 1800-2017 (SystemVerilog)
- Xilinx Vivado Design Suite User Guide

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.0 | 2026-05-15 | 初始版本，基础RTL生成能力 |
| v1.1 | 2026-05-15 | 添加testbench生成和仿真分析 |
| v1.2 | 2026-05-15 | 添加Python结果分析和报告生成 |
| v1.3 | 2026-05-15 | 添加波形自动显示功能：持续调试直到顺利生成波形，自动打开Vivado并显示波形图，无需客户操作 |

---

*本技能遵循Verilog代码规范，为用户提供专业的RTL设计和验证服务。*