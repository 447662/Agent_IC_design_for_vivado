# 项目后续规划 Backlog

本文用于集中记录当前项目未完成、可后续升级的设计任务。目标是让后续继续设计时，不需要从聊天记录、README 和多个阶段文档里反复拼接上下文。

## 当前基线

截至 2026-07-10，项目已经完成从单点 async FIFO 到通用数字 IC Agent 的主流程雏形：

- `async-fifo`：RTL/TB/Vivado/xsim/VCD/WDB/UVM smoke/UVM coverage/报告总览已经跑通。
- `sync-fifo`：作为第二个 RTL target，已跑通 RTL/TB/Vivado/xsim/VCD/RWave/GUI/中文报告最小闭环。
- `round-robin-arbiter`：作为第三个 RTL target，已验证非 FIFO 控制逻辑设计族，覆盖 grant/fairness/VCD 分析/WDB GUI。
- P5.4/P5.5：已支持 target 级 `design_spec.md/html` 与 `verification_plan.md/html` 生成。
- P5.6：三个 target 已迁移到统一元数据契约，场景、覆盖率和产物状态统一为 `PASS/SKIP/N/A`。
- P5.9：Report、Waveform、Vivado 逻辑已拆到 adapter，现有 CLI 与 `DigitalICAgent` 方法入口保持兼容。
- RWaveAnalyzer/VCD_ANALYZER：已形成 `--wave-backend auto` 策略，优先 RWave，失败时降级到 VCD_ANALYZER。

## P5 后续主线

P5 的目标仍然是“让这个 agent 普遍适用于数字 IC 设计”，后续优先级建议如下：

| 阶段 | 状态 | 建议优先级 | 目标 | 验收口径 |
|---|---|---:|---|---|
| P5.6 | 已完成 | - | P4 能力挂载点 | 已定义通用 `parameters`、`interfaces`、`checks`、`scenario_catalog`、`coverage_metrics`、`artifact_manifest`，并严格校验 PASS/SKIP/N/A |
| P5.7 | 未完成 | P0 | 目标脚手架生成器 | `--create-target <name>` 生成 target JSON、RTL/TB/report 占位和 TODO 检查清单 |
| P5.8 | 未完成 | P1 | Artifact manifest | 每次 flow 生成 `artifacts.json`，记录产物路径、工具版本、命令、时间戳、状态 |
| P5.9 | 已完成 | - | Adapter 拆分 | Vivado、RWave/VCD、Report 逻辑已拆为 adapter，主类通过方法绑定保持兼容 |
| P5.10 | 未完成 | P1 | 环境预检报告 | 输出 Vivado、Python、Git、RWave、权限、GUI 条件的中文 `environment_report.md/html` |
| P5.11 | 未完成 | P2 | 多目标报告总览 | 顶层 `outputs/index.html` 汇总多个 target 的规格、仿真、波形、覆盖率、经验文档入口 |
| P5.12 | 未完成 | P2 | RWave FST/GHW 样例 | 增加非 VCD 波形样例，验证 RWaveAnalyzer 作为统一波形后端的扩展价值 |

## P4 后续升级池

P4 不是当前阻塞主流程的必需项，但需要保留为后续能力池。P4 所有能力都应兼容 P5 的多 target 模型，避免只写死 async FIFO。

| 阶段 | 状态 | 建议优先级 | 目标 | 说明 |
|---|---|---:|---|---|
| P4.0 | 未完成 | P1 | Coverage closure 看板 | 从“能显示覆盖率”升级为“能定位缺口并建议补测” |
| P4.1 | 未完成 | P1 | 低覆盖项提取 | 解析 xcrg HTML/log，提取低覆盖文件、实例、指标和来源报告 |
| P4.2 | 未完成 | P1 | 场景补齐建议 | 将低覆盖项映射到 `scenario_catalog`，输出可执行补测建议 |
| P4.3 | 未完成 | P2 | 分项 coverage gate | 支持 line/branch/condition/toggle/functional 独立阈值 |
| P4.4 | 未完成 | P2 | coverage 趋势记录 | 输出 `coverage_history.jsonl`、`coverage_trend.md/html` |
| P4.5 | 未完成 | P2 | 失败 seed 自动归档 | 长回归失败时保存最小复现材料和重跑命令 |
| P4.6 | 未完成 | P2 | GUI 可见性自动化增强 | 从“打开 Vivado GUI”升级为“自动判断波形区非空并保留截图证据” |
| P4.7 | 未完成 | P2 | 报告体验升级 | 把报告升级为工程 dashboard，统一 spec/RTL/sim/UVM/coverage/wave/lessons 卡片 |

## 已知技术债

- `agent.py` 仍承载较多 target 专用 RTL/TB/UVM flow；后续扩展时应继续按清晰边界迁移，但不为拆分而拆分。
- 当前 `artifact_manifest` 是 target 的预期产物声明；P5.8 仍需生成每次真实 flow 的运行时 `artifacts.json`，补充命令、工具版本、时间戳和实际状态。
- Adapter 目前通过方法绑定兼容旧入口；后续新增外部工具能力应优先进入 adapter，避免逻辑重新回流到主类。
- README 和部分旧文档存在历史编码显示问题；后续改文档时应使用 UTF-8，并优先新增清晰中文文档，不建议大面积重写旧记录。
- `outputs/` 当前用于本地真实 Vivado 验收，不应提交到仓库；如需要保留关键证据，应转写到 `docs/testing/` 或 `docs/roadmap/`。
- `.claude/settings.local.json` 是本地配置，不应提交。

## 推荐下一步

建议后续按依赖顺序推进：

1. **P5.7**：实现 `--create-target`，用 P5.6 schema 自动生成合法 target 配置和最小工程占位。
2. **P5.8**：让每次 flow 输出运行时 `artifacts.json`，把 P5.6 的预期 manifest 落到实际执行证据。
3. **P5.10**：生成中文环境预检报告，在进入 Vivado/RWave flow 前集中暴露工具、权限和 GUI 前置条件。

## 清理原则

后续清理仓库时遵守：

- 删除前必须先列出清单并获得明确确认。
- 优先删除 `.pytest_cache/`、`.tmp-pytest/`、`.tmp-agent-output/`、重复仿真输出、旧 zip 包等可再生成文件。
- 不删除 `docs/tools_archive/`、`.trae/agent/targets/`、`tests/`、`VCD_ANALYZER-main/` 等项目正常运行依赖。
- `outputs/` 若要删除，需要确认不再需要本地 Vivado 波形和报告证据；其内容可由命令重新生成，但真实仿真耗时较长。
