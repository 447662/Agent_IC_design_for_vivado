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
| P5.3 | 第三个 RTL 目标 `round-robin-arbiter` | 已完成最小闭环 | 验证非 FIFO 设计族、fairness、VCD/WDB 和报告抽象 |
| P5.4 | 通用规格文档生成 | 已完成 | 从目标配置和用户需求生成 `design_spec.md/html` |
| P5.5 | 通用验证计划 | 已完成 | 从 scenario catalog 生成 `verification_plan.md/html` |
| P5.6 | P4 能力挂载点 | 已完成 | 统一 target schema、`coverage_metrics`、`artifact_manifest` 和 PASS/SKIP/N/A 状态 |
| P5.7 | 目标脚手架生成器 | 已完成 | `--create-target` 生成可校验候选 JSON、RTL/TB/report 占位、README 和 TODO，且默认禁止覆盖 |
| P5.8 | Artifact manifest | 已完成 | 每次 flow 追加运行时 `artifacts.json`，记录命令、工具、时间、状态、错误和产物存在性 |
| P5.9 | Adapter 拆分 | 已完成 | 拆出 Vivado/RWave/Report adapter，并保持 CLI、测试和旧方法入口兼容 |
| P5.10 | 环境预检报告 | 已完成 | 中文 Markdown/HTML 覆盖 Vivado、RWave fallback、Python、Git、权限和 GUI，并记录项目级 manifest |
| P5.11 | 多目标报告总览 | 已完成 | 顶层 index 聚合注册目标、target/environment manifest、最近运行、失败入口和统一报告 surface |
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

## P5.6/P5.9 执行结果

P5.6 将 target registry 从“加载基础描述”升级为严格的通用能力契约：

- 必填字段：`parameters`、`interfaces`、`checks`、`scenario_catalog`、`coverage_metrics`、`artifact_manifest`。
- 状态枚举：`PASS`、`SKIP`、`N/A`。
- 校验范围：字段类型、必填子字段、重复 ID、接口方向、非法状态和非空 checks。
- 三个 target JSON 已完成迁移；规格和验证计划直接读取配置，不再维护 Python fallback catalog。

P5.9 建立了三个 adapter 边界：

- `.trae/agent/adapters/report.py`：target catalog、规格、验证计划与报告写入。
- `.trae/agent/adapters/waveform.py`：RWave、batch JSON、VCD_ANALYZER 与自动降级。
- `.trae/agent/adapters/vivado.py`：Vivado 命令发现、batch 执行与 GUI 启动。
- `DigitalICAgent` 保留既有方法名，通过函数绑定维持 CLI、测试和 monkeypatch 兼容。

验收结果：

- 定向测试：`6 passed, 110 deselected`。
- 完整回归：`116 passed`。
- Ruff：通过。
- Mypy：`Success: no issues found in 11 source files`。
- 覆盖率：`72.63%`，高于项目 `68%` 门槛。
- TDD 证据：`docs/testing/p5_6_p5_9_metadata_and_adapters.tdd.md`。

## P5.7 执行结果

P5.7 新增 `.trae/agent/target_scaffolder.py` 与 CLI `--create-target <name>`：

- 将 `packet_router` 等名称规范为 `packet-router` target 和 `packet_router` Verilog module。
- 生成通过 P5.6 registry 校验的候选 target JSON。
- 生成最小 RTL、testbench、设计规格/验证计划/仿真报告占位、README 和 TODO。
- 拒绝路径穿越等非法名称、已注册 target 和已存在的输出目录。
- 候选配置不会自动安装到正式 registry，避免缺少 `TargetHandler` 时破坏启动。

验收结果：

- RED：`3 failed, 112 deselected`，失败原因是模块、方法和 CLI 尚不存在。
- GREEN：`3 passed, 112 deselected`。
- 完整回归：`119 passed in 11.88s`。
- Ruff：通过。
- Mypy：`Success: no issues found in 12 source files`。
- 整体覆盖率：`73.14%`；`target_scaffolder.py`：`100.0%`。
- TDD 证据：`docs/testing/p5_7_target_scaffolder.tdd.md`。

## P5.8 执行结果

P5.8 新增 `.trae/agent/artifact_manifest.py`，将 P5.6 静态预期产物声明落实为运行时执行证据：

- `run_target_flow()` 对成功、返回失败和异常三种路径写入 manifest。
- 规格、验证计划和 target 脚手架生成会追加独立 run。
- manifest 保存 schema 版本、target、run ID、UTC 时间、命令、options 和工具信息。
- 每条 run 按 P5.6 声明检查产物路径，记录 `PASS/SKIP/N/A`、exists 和 size。
- 非法状态、项目目录外 artifact 和损坏 JSON 会被明确拒绝。

验收结果：

- RED：`5 failed, 119 deselected`。
- GREEN：`5 passed, 119 deselected`；防护补强后 `6 passed, 119 deselected`。
- 完整回归：`125 passed in 10.23s`。
- Ruff：通过。
- Mypy：`Success: no issues found in 13 source files`。
- 整体覆盖率：`73.83%`；`artifact_manifest.py`：`82.6%`。
- TDD 证据：`docs/testing/p5_8_runtime_artifact_manifest.tdd.md`。

## P5.10 执行结果

P5.10 新增 `.trae/agent/environment_report.py` 与 CLI `--environment-report`：

- 检查 Python 版本/解释器、Git 命令、Vivado 命令和版本横幅。
- 检查 RWave，并在不可用时确认 `VCD_ANALYZER` fallback。
- 在工具探测前验证输出目录可创建、可写。
- 检查 Windows 交互会话或 Linux `DISPLAY/WAYLAND_DISPLAY` GUI 前置条件。
- 生成中文 `environment_report.md/html`，每项包含 `PASS/WARN/FAIL`、详情和修复建议。
- 生成 `outputs/environment-report/artifacts.json`，使用 `scope: environment` 追加预检历史。
- CLI 对可降级 `WARN` 返回 0，对基础 `FAIL`、不可写目录或损坏 manifest 返回 1。

验收结果：

- RED：`5 failed, 125 deselected`。
- GREEN：初始 `5 passed, 125 deselected`；Vivado 非零返回码兼容回归补强后 `6 passed, 125 deselected`。
- 完整回归：`131 passed in 14.61s`。
- Ruff：通过。
- Mypy：`Success: no issues found in 14 source files`。
- 整体覆盖率：`73.61%`；`environment_report.py`：`73.7%`。
- 真实 CLI：Python、Git、Vivado、VCD_ANALYZER fallback 和输出权限为 PASS；无交互桌面标记为 WARN，报告和 manifest 正常生成。
- TDD 证据：`docs/testing/p5_10_environment_report.tdd.md`。

## P5.11 执行结果

P5.11 新增 `.trae/agent/project_overview.py` 与 CLI `--generate-overview`：

- 注册表提供预期 target，即使没有任何输出也能显示 `NOT_RUN`。
- 自动发现输出目录中的额外 target manifest，避免遗漏候选或已移除注册项。
- 按每个 flow 的最新状态计算 target 总体 PASS/FAIL，并展示最近 flow、时间、错误和重跑命令。
- 固定聚合 Spec、RTL、Simulation、UVM、Coverage、Wave、Lessons 七类 surface。
- 环境卡片读取 P5.10 environment manifest，并链接环境报告。
- 单个 manifest 损坏时标记 `INVALID`，其他 target 继续展示。
- target manifest 和 environment manifest 写入后自动刷新 `outputs/index.md/html`。

验收结果：

- 初始 RED：`6 failed, 131 deselected`。
- 初始 GREEN：`6 passed, 131 deselected`。
- 自动刷新 RED：`2 failed, 6 passed, 131 deselected`。
- 自动刷新 GREEN：`8 passed, 131 deselected`。
- 完整回归：`139 passed in 17.92s`。
- Ruff：通过。
- Mypy：`Success: no issues found in 15 source files`。
- 整体覆盖率：`74.39%`；`project_overview.py`：`85.8%`。
- 真实 CLI：环境预检 + `sync-fifo` RTL + `round-robin-arbiter` 规格被聚合为 3 个目标，其中 2 个 PASS、`async-fifo` 为 NOT_RUN，项目状态 WARN。
- TDD 证据：`docs/testing/p5_11_project_overview.tdd.md`。

## 执行原则

- 测试先行：先补失败测试，再实现最小功能。
- 复用优先：复用 async FIFO 已沉淀的 Vivado/WDB/VCD/RWave 经验，但不把第二个目标硬塞进 async FIFO 的专用函数。
- 报告中文为主：用户阅读报告必须是中文，测试断言优先使用稳定路径、状态和 ASCII 标记。
- 不自动删除用户文件：所有新产物写入独立输出目录。

## 2026-07-10 状态快照

P5.0-P5.11 已完成：

- P5.0：最小 target registry 与 `--list-targets`。
- P5.1：target 配置文件化，使用 `.trae/agent/targets/*.json`。
- P5.2：第二个 RTL target `sync-fifo` 最小闭环。
- P5.3：第三个 RTL target `round-robin-arbiter` 最小闭环。
- P5.4：通用 `design_spec.md/html` 生成。
- P5.5：通用 `verification_plan.md/html` 生成。
- P5.6：通用 target 元数据契约与严格校验。
- P5.7：候选 target 脚手架生成器。
- P5.8：运行时 `artifacts.json` 与 flow 历史。
- P5.9：Report、Waveform、Vivado adapter 拆分。
- P5.10：中文环境预检 Markdown/HTML 与项目级 environment manifest。
- P5.11：多 target 顶层 Markdown/HTML、统一 surface 和自动刷新。

后续建议推进 P5.12。未完成规划集中记录在 `docs/roadmap/project_followup_backlog.md`，后续继续设计时以该 backlog 作为入口，再结合 `p4_future_upgrade_roadmap.md` 和 `p5_general_digital_ic_agent_design.md` 细化任务。
