# P5 系列执行记录

本文用于记录 P5 通用数字 IC Agent 阶段的执行计划、验收口径和阶段状态。P5 的核心目标是把当前 async FIFO 单点闭环抽象为可复用于多个数字 IC 设计目标的通用流程。

## 总目标

- 支持多个设计目标，而不是只服务 `async-fifo`。
- 保留 Vivado/xsim 作为当前主仿真器；需要人工看波形时继续打开 Vivado GUI。
- 将 RTL/TB 生成、仿真、VCD/RWave 分析、WDB GUI、中文报告和经验沉淀抽象成通用能力。
- P4 coverage closure 暂作为后续升级池，只在 P5 中预留通用数据结构和挂载点。

## 阶段规划

| 阶段 | 目标 | 当前状态 | 验收重点 |
|---|---|---|---|
| P5.0 | 目标注册表 | 已完成 | `--list-targets` 可列出已注册目标，async FIFO 原流程保持兼容 |
| P5.1 | 目标配置文件化 | 已完成 | `.trae/agent/targets/*.json` 可加载目标元信息并校验必填字段 |
| P5.2 | 第二个 RTL 目标 `sync-fifo` | 已完成最小闭环 | 新增目标配置、RTL/TB/Vivado Tcl、仿真入口、VCD 分析和中文报告 |
| P5.3 | 第三个 RTL 目标 `round-robin-arbiter` | 未开始 | 验证非 FIFO 设计族、fairness、SVA 和报告抽象 |
| P5.4 | 通用规格文档生成 | 未开始 | 从目标配置和用户需求生成 `design_spec.md/html` |
| P5.5 | 通用验证计划 | 未开始 | 从 scenario catalog 生成 `verification_plan.md/html` |
| P5.6 | P4 能力挂载点 | 未开始 | 统一 `coverage_metrics`、SKIP/N/A 状态和 closure 报告入口 |
| P5.7 | 目标脚手架生成器 | 建议新增 | `--create-target` 能生成 target JSON 和模板占位 |
| P5.8 | Artifact manifest | 建议新增 | 每次 flow 输出 `artifacts.json`，统一记录产物和重跑命令 |
| P5.9 | Adapter 拆分 | 建议新增 | 拆出 Vivado/RWave/Report adapter，降低主文件膨胀风险 |
| P5.10 | 环境预检报告 | 建议新增 | 记录 Vivado、RWave、Python、Git、权限和 GUI 前置条件 |
| P5.11 | 多目标报告总览 | 建议新增 | 顶层 index 聚合多个 target 的状态和入口 |
| P5.12 | RWave FST/GHW 样例 | 建议新增 | 验证 RWaveAnalyzer 不只是 VCD 替代，而是统一波形后端 |

## P5.2 执行口径

`sync-fifo` 是 P5 通用化的第一块试金石。它与 `async-fifo` 同属 FIFO 设计族，但没有跨时钟同步逻辑，适合快速验证 target registry、生成器、仿真器、波形分析和报告是否能扩展到第二个目标。

P5.2 最小交付：

- `.trae/agent/targets/sync_fifo.json`
- `outputs/sync-fifo/rtl/sync_fifo.v`
- `outputs/sync-fifo/tb/tb_sync_fifo.v`
- `outputs/sync-fifo/sim/run_vivado_sync_fifo.tcl`
- `outputs/sync-fifo/sim/create_sync_fifo_project.tcl`
- `outputs/sync-fifo/sim/open_sync_fifo_project_gui.tcl`
- `outputs/sync-fifo/reports/sim_report.md/html`
- `--generate-rtl sync-fifo`
- `--sim-rtl sync-fifo --no-wave-gui`
- `--analyze-rtl-vcd sync-fifo`

当前已实现：

- `.trae/agent/targets/sync_fifo.json`
- `DigitalICAgent.write_sync_fifo_project()`
- `DigitalICAgent.run_sync_fifo_vivado_sim()`
- `DigitalICAgent.analyze_sync_fifo_vcd()`
- `DigitalICAgent.write_sync_fifo_sim_report()`
- CLI `--generate-rtl sync-fifo`
- CLI `--sim-rtl sync-fifo`
- CLI `--analyze-rtl-vcd sync-fifo`

已验证：

- P5.2 目标测试：`6 passed, 74 deselected`
- P5/P5.2 相关回归：`47 passed, 33 deselected`
- 完整回归：`80 passed`
- 真实 Vivado 2025.2：`--sim-rtl sync-fifo --no-wave-gui` 已生成 VCD/WDB/工程/报告。
- VCD 分析：`--analyze-rtl-vcd sync-fifo` 已解析 26 个信号、6 个写事件、6 个读事件。
- GUI 波形：`--open-wave sync-fifo` 已打开 `sync_fifo_project.xpr` 和 `sync_fifo_smoke_20260709_224327.wdb`。

P5.2 暂不要求：

- UVM 环境。
- coverage closure。
- 多 seed 回归。
- 自动修改测试以提升覆盖率。

## 执行原则

- 测试先行：先补失败测试，再实现最小功能。
- 复用优先：复用 async FIFO 已沉淀的 Vivado/WDB/VCD/RWave 经验，但不把第二个目标硬塞进 async FIFO 的专用函数。
- 报告中文为主：用户阅读报告必须是中文，测试断言优先使用稳定路径、状态和 ASCII 标记。
- 不自动删除用户文件：所有新产物写入独立输出目录。
