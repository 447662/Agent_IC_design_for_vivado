# P5 通用数字 IC Agent 设计

P5 的目标是把当前 async FIFO 单点闭环升级为可普遍应用到数字 IC 前端设计的 Agent 框架。重点不是立刻追求更高覆盖率，而是把“需求 -> 规格 -> RTL -> 仿真 -> 分析 -> 报告 -> GUI 波形”的流程抽象成可扩展架构。

## 目标

- 支持多个数字 IC 设计目标，而不只依赖 async FIFO。
- 保留 Vivado/xsim 作为当前首选仿真器，并继续要求需要看波形时打开 Vivado GUI。
- 把 VCD 分析、WDB 打开、UVM、coverage、报告沉淀变成通用能力。
- 让每个新设计目标只需要补目标描述、模板、场景和验收规则。
- P4 coverage closure 能作为后续增强模块接入，而不是阻塞 P5 主流程。

## 非目标

- P5 初期不追求自动完成 coverage closure。
- 不一次性实现复杂协议的完整商用级 UVM VIP。
- 不引入除 Vivado/xsim 外的强依赖仿真器。
- 不让 Agent 自动删除、覆盖用户工程文件；生成内容应进入独立输出目录。

## 总体流程

```text
需求输入
  -> 目标识别 / target registry
  -> 规格文档 / design spec
  -> RTL/TB/UVM 生成
  -> Vivado/xsim 仿真
  -> VCD/WDB/coverage 分析
  -> 中文 Markdown/HTML 报告
  -> Vivado GUI 波形入口
  -> 问题复盘与后续建议
```

## 核心抽象

### 1. DesignTarget

每个可生成/验证的设计目标应有统一描述：

```text
target_name: async-fifo
design_family: fifo
rtl_templates:
tb_templates:
uvm_templates:
simulation_flows:
coverage_profile:
wave_signals:
scenario_catalog:
report_sections:
```

用途：

- 让 CLI 可以列出目标。
- 让生成器知道需要写哪些文件。
- 让检查器知道应验收哪些产物。
- 让报告生成器知道如何组织目标特有信息。

### 2. Flow

流程从硬编码函数升级为通用 flow：

```text
generate-rtl
sim-rtl
regress-rtl
uvm-smoke
uvm-coverage
uvm-random-regress
analyze-waveform
open-wave
check-target
```

每个 flow 需要声明：

- 输入参数。
- 依赖产物。
- 生成产物。
- 成功标记。
- 失败诊断。
- 报告更新点。

### 3. ToolAdapter

当前优先保留 Vivado/xsim：

```text
VivadoAdapter
  - resolve tool path
  - render Tcl
  - run batch simulation
  - open GUI WDB
  - export xcrg coverage
```

后续可扩展：

```text
VcdAnalyzerAdapter
RWaveAdapter
ReportAdapter
CoverageAdapter
```

原则：工具差异由 adapter 处理，设计目标不直接拼工具命令。

### 4. ReportSurface

所有目标共享顶层报告模型：

```text
reports/index.md
reports/index.html
reports/<flow>_summary.md
reports/<flow>_summary.html
reports/lessons_learned.md
```

必须继承 P3.14 经验：

- 每个 flow 成功或失败后都刷新总览页。
- 顶层入口必须链接日志、WDB、HTML 报告、复盘文档和重跑命令。
- 中文报告以用户阅读为主，测试断言优先使用路径、状态、数值和稳定 ASCII 片段。

## P5 分阶段计划

### P5.0：目标注册表

目标：把 async FIFO 从硬编码目标抽象到 registry。

交付：

- `DesignTarget` 数据结构。
- `async-fifo` 注册项。
- `--list-targets` CLI。
- 现有 async FIFO 流程保持全部可用。

验收：

- `--list-targets` 显示 async FIFO。
- 原有 `--generate-rtl async-fifo`、`--sim-rtl async-fifo`、`--uvm-coverage async-fifo` 测试全绿。

当前状态：已完成。`DigitalICAgent` 已提供 `load_target_registry()`、`build_target_registry()`、`list_targets()`、`get_target()` 和 `print_targets()`，CLI 已新增 `--list-targets`。当前注册目标为 `async-fifo`，别名包括 `async_fifo` 和 `asyncfifo`，现有 async FIFO flow 保持兼容。

### P5.1：目标配置文件

目标：允许目标通过配置描述，而不是散落在 Python 函数里。

建议路径：

```text
.trae/agent/targets/async_fifo.json
```

建议内容：

当前状态：已完成。`async-fifo` 的目标元信息已经迁移到 `.trae/agent/targets/async_fifo.json`，Agent 启动时从 `.trae/agent/targets/*.json` 加载 registry，并校验 `name`、`display_name`、`design_family`、`aliases`、`flows`、`description` 必填字段。P5.1 暂不引入 YAML 依赖，避免为一个配置格式增加额外运行时依赖。

- 设计族。
- 默认参数。
- 文件布局。
- 波形信号组。
- 场景列表。
- coverage profile。
- 报告卡片。

验收：

- Agent 能读取配置并生成报告中的目标说明。
- 缺失配置时给出明确诊断。

### P5.2：第二个 RTL 目标

建议选择：`sync-fifo`。

原因：

- 与 async FIFO 接近，便于复用 FIFO 报告和场景。
- 没有跨时钟复杂性，适合验证 target registry 是否通用。
- 可快速验证参数、仿真、VCD、WDB 和报告通路。

交付：

- sync FIFO RTL/TB。
- Vivado/xsim 仿真 Tcl。
- VCD 分析条件。
- WDB GUI 打开入口。
- 中文报告和总览页。

### P5.3：第三个 RTL 目标

建议选择：`round-robin-arbiter`。

原因：

- 设计族从 FIFO 扩展到仲裁器，能检验框架是否真的通用。
- 验证重点变为 fairness、grant onehot、no starvation。
- SVA 和场景目录更有代表性。

交付：

- arbiter RTL/TB。
- 场景：单请求、多请求、轮转、公平性、reset recovery。
- SVA：grant onehot、grant implies request、bounded fairness。
- 报告和 WDB 入口。

### P5.4：通用规格文档生成

目标：把自然语言需求变成结构化设计规格。

建议规格字段：

- 功能描述。
- 接口定义。
- 参数。
- 时钟/复位。
- 关键时序。
- 场景和边界条件。
- 验证计划。
- coverage 目标占位。
- 人工确认项。

验收：

- 对 async FIFO、sync FIFO、arbiter 都能生成规格文档。
- 规格文档中的接口和生成 RTL/TB 保持一致。

### P5.5：通用验证计划

目标：把每个 target 的 scenario catalog 输出成验证计划。

建议产物：

```text
reports/verification_plan.md
reports/verification_plan.html
```

验收：

- 每个场景有 ID、目的、刺激、检查点、覆盖目标、对应测试。
- 报告总览页链接验证计划。

### P5.6：P4 能力挂载点

目标：让 P4 coverage closure 能自然接进 P5。

交付：

- 通用 `coverage_metrics` schema。
- 通用 `coverage_closure.md/html` 入口。
- 每个 target 可选 `coverage_profile`。
- P4 低覆盖项和补测建议从 target scenario catalog 获取解释。

验收：

- async FIFO 可继续使用现有 xcrg 数据。
- sync FIFO/arbiter 即使暂时没有 coverage，也能显示 SKIP/N/A，而不是误报失败。

### P5.12：RWave FST/GHW 统一波形样例

目标：用非 VCD 真实样例证明 RWaveAnalyzer 是 VCD/FST/GHW 的统一波形后端，而不是仅作为旧 VCD 分析器的替代入口。

交付：

- 新增通用 `--analyze-waveform <file>`，支持 VCD/FST/GHW。
- 保留 `--analyze-vcd` 和 `DigitalICAgent.analyze_vcd()` 兼容入口。
- VCD 的 `auto` 模式保留 RWave -> VCD_ANALYZER 降级。
- FST/GHW 的 `auto` 模式禁止降级；RWave 缺失或失败时明确报错。
- 跟踪 VCD/FST/GHW 最小真实夹具及来源说明。
- 新增 `--verify-waveform-samples`，输出中文 `format_matrix.md/html`。

验收：

- 三种格式均由 `rwave` 返回 `_waveform_backend: rwave`。
- FST/GHW 不会调用仅支持 VCD 的旧分析器。
- 格式矩阵记录信号数、timescale、时间范围、后端和 PASS/FAIL。
- 旧 `--analyze-vcd`、条件搜索和 target VCD 流程保持兼容。

当前状态：已完成。真实验收结果为 VCD/FST 各 3 个信号、`1ns`、`0s - 30ns`，GHW 为 3 个信号、`1fs`、`0s - 10ns`；三种格式矩阵状态为 `PASS`。

## 优先支持目标建议

| 优先级 | Target | 价值 | 难度 |
|---|---|---|---|
| P5.2 | `sync-fifo` | 复用 FIFO 思路，验证框架通用性 | 低 |
| P5.3 | `round-robin-arbiter` | 验证 fairness/SVA/非 FIFO 设计 | 中 |
| P5.4+ | `register-file` | 常见 IP，适合接口/读写冲突验证 | 中 |
| P5.4+ | `cdc-sync` | 强化 CDC、reset、波形检查经验 | 中 |
| P5.5+ | `axi-stream-fifo` | 接近真实协议，适合 ready/valid 生态 | 高 |
| P5.5+ | `uart-lite` | 端到端状态机和协议测试 | 高 |

## 与 P4 的关系

P4 不取消，只降级为后续升级池。P5 需要预留 P4 接口：

- 每个 target 都能声明 coverage 目标。
- 每个 flow 都能记录历史结果。
- 每个报告都能被 index 聚合。
- 每个失败都能保留重跑命令。
- 每个 target 的 scenario catalog 都能服务 coverage closure 建议。

## 下一步建议

P5.0-P5.12 的通用主流程已经形成，P4 coverage closure 已继续推进：

- P4.0：多 target coverage closure 看板已完成。
- P4.1：xcrg 低覆盖文件、实例、指标和来源提取已完成。
- P4.2：低覆盖项到 target `scenario_catalog` 的可执行补测建议已完成。
- P4.3：Total/Line/Branch/Condition/Toggle/Functional 分项 gate 已完成，目标无关逻辑位于 `coverage_gates.py`。
- P4.4：append-only coverage history 和 Markdown/HTML 趋势报告已完成，schema 已包含 target、flow、toolchain 和 seed。
- 下一步进入 P4.5，自动归档失败 seed 的最小复现材料。
