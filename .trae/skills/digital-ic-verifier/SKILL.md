---
name: "digital-ic-verifier"
description: "专业数字IC验证师技能：使用UVM和SystemVerilog对RTL设计进行功能验证，严格按照设计文档进行验证，生成验证报告。Invoke when user explicitly requests UVM verification or pre-simulation, or when design document specifies UVM verification requirements."
---

# 数字IC验证师技能

## 技能概述

本技能参考知乎专栏文章《UVM验证方法论》(https://zhuanlan.zhihu.com/p/66244016)，提供专业的数字IC验证服务。核心能力包括：UVM测试环境搭建、SystemVerilog验证代码编写、仿真结果分析和验证报告生成。

**触发条件**：
- 客户明确要求使用UVM验证
- 客户明确要求使用前仿（前仿真）
- 设计文档中明确说明需要UVM验证
- 其他情况使用 `digital-ic-rtl-designer` 技能进行常规验证

---

## 核心功能

### 1. UVM测试环境搭建

根据设计文档搭建完整的UVM验证环境：

**UVM组件结构**：
```
┌─────────────────────────────────────────────────────────┐
│                     UVM Testbench                       │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐                 │
│  │   UVM Test   │───▶│   UVM Env    │                 │
│  └──────────────┘    └──────┬───────┘                 │
│                             │                         │
│         ┌───────────────────┼───────────────────┐     │
│         ▼                   ▼                   ▼     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐│
│  │   Driver    │    │   Monitor   │    │ Scoreboard  ││
│  │  (驱动器)    │    │  (监视器)    │    │  (计分板)   ││
│  └──────┬──────┘    └──────┬──────┘    └─────────────┘│
│         │                  │                          │
│         ▼                  ▼                          │
│  ┌─────────────┐    ┌─────────────┐                  │
│  │   Sequencer │    │   Coverage  │                  │
│  │  (序列器)    │    │  (覆盖率)    │                  │
│  └──────┬──────┘    └─────────────┘                  │
│         │                                             │
│         ▼                                             │
│  ┌─────────────────────────────────────────────────┐  │
│  │                DUT (被测设计)                    │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

### 2. SystemVerilog/UVM代码编写

**代码规范要求**（参考UVM规范）：

| 规范类别 | 要求 |
|----------|------|
| 类命名 | 使用驼峰命名，以`uvm_`前缀（如 `uvm_driver`） |
| 变量命名 | 小写+下划线，后缀说明类型（如 `data_q`） |
| 常量命名 | 大写+下划线 |
| 缩进风格 | 4空格缩进 |
| 注释规范 | 模块、类、方法必须有注释 |
| 参数化设计 | 使用 `typedef` 和参数化类 |

### 3. 仿真环境配置

**支持的仿真工具**：
- Xilinx Vivado（默认）
- Mentor ModelSim/Questa
- Synopsys VCS
- Cadence Xcelium

**MCP检查与配置**：
- 检测SynthPilot MCP是否安装
- 如未安装，引导用户进行安装配置
- 生成Vivado/Questa仿真脚本

### 4. Python仿真结果分析

使用Python程序处理仿真输出：

**分析流程**：
1. 运行仿真获取波形数据
2. 解析VCD/FSDB文件
3. 检查信号时序和逻辑正确性
4. 对比设计文档要求
5. 识别不符合规范的问题
6. 生成修复建议

### 5. 验证报告生成

生成标准化的验证报告（Markdown格式）：

**报告章节**：
| 章节 | 内容 |
|------|------|
| 验证概述 | 验证目标和范围 |
| 测试用例 | UVM测试序列 |
| 仿真结果 | 通过/失败统计 |
| 覆盖率报告 | 功能/代码覆盖率 |
| 问题列表 | 发现的问题和修复建议 |
| 修改记录 | RTL修改历史 |

---

## 工作流程

### UVM验证流程

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
│ UVM环境搭建     │
│ (组件创建)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 测试序列编写    │
│ (Sequence)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 仿真运行        │
│ (Vivado/Questa) │
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
│ RTL修复         │
│ (迭代优化)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 验证报告生成    │
│ (.md格式)       │
└─────────────────┘
```

### 触发条件判断

```
用户请求验证
    │
    ▼
是否明确要求UVM/前仿？
    │
    ├── 是 ──▶ 使用本技能(digital-ic-verifier)
    │
    └── 否 ──▶ 使用 digital-ic-rtl-designer 技能
```

---

## UVM验证环境结构

### 组件说明

| 组件 | 类型 | 功能 |
|------|------|------|
| `uvm_test` | UVM Test | 测试入口，配置环境 |
| `uvm_env` | UVM Environment | 环境容器，集成组件 |
| `uvm_driver` | UVM Driver | 驱动DUT，发送激励 |
| `uvm_sequencer` | UVM Sequencer | 管理序列 |
| `uvm_sequence` | UVM Sequence | 定义测试序列 |
| `uvm_monitor` | UVM Monitor | 监控DUT接口 |
| `uvm_scoreboard` | UVM Scoreboard | 比对预期与实际结果 |
| `uvm_coverage` | UVM Coverage | 覆盖率收集 |

### 代码示例

**UVM Driver模板**：
```systemverilog
class i2c_driver extends uvm_driver#(i2c_transaction);
    `uvm_component_utils(i2c_driver)
    
    virtual i2c_if vif;
    
    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction
    
    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual i2c_if)::get(this, "", "vif", vif)) begin
            `uvm_fatal("NO_VIF", "Virtual interface not found!")
        end
    endfunction
    
    virtual task run_phase(uvm_phase phase);
        forever begin
            seq_item_port.get_next_item(req);
            drive_transaction(req);
            seq_item_port.item_done();
        end
    endtask
    
    virtual task drive_transaction(i2c_transaction tx);
        // 驱动I2C事务
        vif.start_condition();
        vif.send_address(tx.addr, tx.rw);
        vif.send_data(tx.data);
        vif.stop_condition();
    endtask
endclass
```

**UVM Sequence模板**：
```systemverilog
class i2c_write_sequence extends uvm_sequence#(i2c_transaction);
    `uvm_object_utils(i2c_write_sequence)
    
    function new(string name = "i2c_write_sequence");
        super.new(name);
    endfunction
    
    virtual task body();
        i2c_transaction tx;
        
        // 生成写事务
        tx = i2c_transaction::type_id::create("tx");
        start_item(tx);
        tx.addr = 7'h50;
        tx.data = 8'hAA;
        tx.rw = WRITE;
        finish_item(tx);
    endtask
endclass
```

---

## 仿真脚本示例

### Vivado UVM仿真脚本
```tcl
# create_uvm_project.tcl
create_project i2c_uvm ./uvm_project -part xc7a100tcsg324-1

# 添加源文件
add_files ./src/i2c_top.v
add_files ./src/apb_slave.v
add_files ./src/i2c_core.v
add_files ./src/config_regs.v
add_files ./src/interrupt_ctrl.v

# 添加UVM验证文件
add_files ./uvm/i2c_if.sv
add_files ./uvm/i2c_transaction.sv
add_files ./uvm/i2c_driver.sv
add_files ./uvm/i2c_monitor.sv
add_files ./uvm/i2c_sequencer.sv
add_files ./uvm/i2c_sequence.sv
add_files ./uvm/i2c_scoreboard.sv
add_files ./uvm/i2c_env.sv
add_files ./uvm/i2c_test.sv

# 设置顶层
set_property top i2c_tb [current_fileset]

# 运行仿真
launch_simulation
run 100us
```

### Python分析脚本
```python
import vcd

def analyze_uvm_results(log_file):
    """分析UVM仿真结果"""
    results = {
        'passed': 0,
        'failed': 0,
        'errors': []
    }
    
    with open(log_file, 'r') as f:
        for line in f:
            if '[UVM_INFO] * PASS' in line:
                results['passed'] += 1
            elif '[UVM_ERROR]' in line or '[UVM_FATAL]' in line:
                results['failed'] += 1
                results['errors'].append(line.strip())
    
    return results

def generate_report(results, coverage):
    report = f"""# UVM验证报告

## 测试结果

### 统计
- 通过: {results['passed']}
- 失败: {results['failed']}

### 覆盖率
- 功能覆盖率: {coverage['functional']}%
- 代码覆盖率: {coverage['code']}%

## 问题列表
"""
    for i, error in enumerate(results['errors'], 1):
        report += f"- **问题{i}**: {error}\n"
    
    return report
```

---

## 验证报告模板

```markdown
# UVM验证报告

**项目名称**: I2C Controller  
**模块名称**: i2c_top  
**验证日期**: 2026-05-15  
**工具**: Xilinx Vivado 2024.2  
**验证方法**: UVM

---

## 1. 验证概述

### 1.1 验证目标
根据设计文档验证I2C控制器的功能正确性：
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
| config_regs | ✅ |
| interrupt_ctrl | ✅ |

---

## 2. UVM测试用例

### 2.1 测试序列清单

| 测试ID | 测试名称 | 序列类型 | 结果 |
|--------|----------|----------|------|
| TC001 | 主模式单字节写 | i2c_write_seq | ✅ 通过 |
| TC002 | 主模式单字节读 | i2c_read_seq | ✅ 通过 |
| TC003 | 主模式多字节写 | i2c_multi_write_seq | ✅ 通过 |
| TC004 | 主模式多字节读 | i2c_multi_read_seq | ✅ 通过 |
| TC005 | 从模式地址匹配 | i2c_slave_addr_seq | ✅ 通过 |
| TC006 | 从模式数据收发 | i2c_slave_data_seq | ✅ 通过 |
| TC007 | 仲裁丢失处理 | i2c_arb_lost_seq | ✅ 通过 |
| TC008 | 时钟拉伸 | i2c_clock_stretch_seq | ✅ 通过 |

### 2.2 覆盖率报告

| 覆盖率类型 | 目标值 | 实际值 | 状态 |
|-----------|--------|--------|------|
| 语句覆盖率 | 95% | 98% | ✅ |
| 分支覆盖率 | 90% | 92% | ✅ |
| 条件覆盖率 | 85% | 88% | ✅ |
| FSM覆盖率 | 100% | 100% | ✅ |
| 功能覆盖率 | 90% | 94% | ✅ |

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

## 4. RTL修改记录

| 修改ID | 修改位置 | 修改内容 | 修改日期 |
|--------|----------|----------|----------|
| MOD001 | i2c_core.v:156 | 修复SDA输出使能逻辑 | 2026-05-15 |
| MOD002 | config_regs.v:89 | 添加地址寄存器复位 | 2026-05-15 |

---

## 5. 结论

**验证状态**: ✅ 通过  

所有测试用例通过，覆盖率达到目标要求。设计符合设计文档规范。

---

**审核人**:  
**日期**:
```

---

## 技术参考

### UVM/SystemVerilog规范来源
- https://zhuanlan.zhihu.com/p/66244016

### 工具链
- **仿真**: Xilinx Vivado, Mentor Questa, Synopsys VCS
- **验证**: UVM, SystemVerilog
- **分析**: Python

### 参考文档
- IEEE Std 1800-2017 (SystemVerilog)
- UVM Class Reference
- Xilinx Vivado Design Suite User Guide

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.0 | 2026-05-15 | 初始版本，UVM验证能力 |

---

*本技能遵循UVM和SystemVerilog代码规范，为用户提供专业的数字IC验证服务。*