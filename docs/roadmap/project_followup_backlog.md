# 项目后续规划 Backlog

本文用于集中记录当前项目未完成、可后续升级的设计任务。目标是让后续继续设计时，不需要从聊天记录、README 和多个阶段文档里反复拼接上下文。

## 当前基线

截至 2026-07-10，项目已经完成从单点 async FIFO 到通用数字 IC Agent 的主流程雏形：

- `async-fifo`：RTL/TB/Vivado/xsim/VCD/WDB/UVM smoke/UVM coverage/报告总览已经跑通。
- `sync-fifo`：作为第二个 RTL target，已跑通 RTL/TB/Vivado/xsim/VCD/RWave/GUI/中文报告最小闭环。
- `round-robin-arbiter`：作为第三个 RTL target，已验证非 FIFO 控制逻辑设计族，覆盖 grant/fairness/VCD 分析/WDB GUI。
- P5.4/P5.5：已支持 target 级 `design_spec.md/html` 与 `verification_plan.md/html` 生成。
- P5.6：三个 target 已迁移到统一元数据契约，场景、覆盖率和产物状态统一为 `PASS/SKIP/N/A`。
- P5.7：已支持 `--create-target` 生成候选配置、RTL/TB、报告占位、README 和 TODO 清单。
- P5.8：注册 target flow、规格/验证计划与脚手架均会追加运行时 `artifacts.json`。
- P5.9：Report、Waveform、Vivado 逻辑已拆到 adapter，现有 CLI 与 `DigitalICAgent` 方法入口保持兼容。
- P5.10：`--environment-report` 已生成中文 Markdown/HTML，覆盖 Python、Git、Vivado、RWave fallback、权限和 GUI 条件。
- P5.11：顶层 `index.md/html` 已聚合注册目标、target manifest、environment manifest 和统一报告 surface。
- P5.12：`--analyze-waveform` 与真实 VCD/FST/GHW 样例矩阵已证明 RWaveAnalyzer 的统一后端能力。
- P4.0：`--coverage-closure` 已生成多 target Markdown/HTML 看板，汇总真实 xcrg 数值、80% 目标、gap、状态和产物入口。
- P4.1：已解析 xcrg 文件、模块、functional group、cover point 和 cross，输出通用低覆盖项与 JSON 索引。
- P4.2：已将低覆盖项映射到 target `scenario_catalog`，输出有优先级和证据的可执行补测场景。
- RWaveAnalyzer/VCD_ANALYZER：VCD 的 `auto` 策略允许 RWave 失败后兼容降级；FST/GHW 禁止降级到旧 VCD 分析器。

## P5 后续主线

P5 的目标仍然是“让这个 agent 普遍适用于数字 IC 设计”，后续优先级建议如下：

| 阶段 | 状态 | 建议优先级 | 目标 | 验收口径 |
|---|---|---:|---|---|
| P5.6 | 已完成 | - | P4 能力挂载点 | 已定义通用 `parameters`、`interfaces`、`checks`、`scenario_catalog`、`coverage_metrics`、`artifact_manifest`，并严格校验 PASS/SKIP/N/A |
| P5.7 | 已完成 | - | 目标脚手架生成器 | `--create-target <name>` 生成 P5.6 候选 JSON、RTL/TB/report 占位、README 和 TODO，并拒绝非法名称、重复 target 与覆盖 |
| P5.8 | 已完成 | - | Artifact manifest | 每次 flow 追加 `artifacts.json`，记录命令、options、工具信息、UTC 时间、PASS/FAIL、产物存在性和错误 |
| P5.9 | 已完成 | - | Adapter 拆分 | Vivado、RWave/VCD、Report 逻辑已拆为 adapter，主类通过方法绑定保持兼容 |
| P5.10 | 已完成 | - | 环境预检报告 | `--environment-report` 输出中文 `environment_report.md/html` 与项目级 `artifacts.json`，包含 PASS/WARN/FAIL、详情和修复建议 |
| P5.11 | 已完成 | - | 多目标报告总览 | 顶层 `outputs/index.md/html` 展示最近 flow、PASS/FAIL/NOT_RUN/INVALID、错误、重跑命令和 Spec/RTL/Simulation/UVM/Coverage/Wave/Lessons 入口 |
| P5.12 | 已完成 | - | RWave FST/GHW 样例 | `--analyze-waveform` 支持 VCD/FST/GHW，`--verify-waveform-samples` 输出三格式 PASS 矩阵，FST/GHW 缺少 RWave 时明确失败 |

## P4 后续升级池

P4 不是当前阻塞主流程的必需项，但需要保留为后续能力池。P4 所有能力都应兼容 P5 的多 target 模型，避免只写死 async FIFO。

| 阶段 | 状态 | 建议优先级 | 目标 | 说明 |
|---|---|---:|---|---|
| P4.0 | 已完成 | - | Coverage closure 看板 | `coverage-closure/index.md/html` 聚合多 target 当前值、目标值、gap、PASS/GAP/MISSING/NOT_RUN/SKIP/INVALID 和官方 coverage/WDB 入口 |
| P4.1 | 已完成 | - | 低覆盖项提取 | `CoverageItem` 聚合文件、实例、指标、分数、明细和来源报告；真实 async-fifo 提取 36 项、0 条诊断 |
| P4.2 | 已完成 | - | 场景补齐建议 | `recommended_scenarios` 输出场景 ID，`scenario_recommendations` 保留优先级、命中项、指标和原因 |
| P4.3 | 已完成 | - | 分项 coverage gate | Total/line/branch/condition/toggle/functional 独立阈值；状态支持 PASS/FAIL/MISSING/SKIP |
| P4.4 | 已完成 | - | coverage 趋势记录 | JSONL 追加真实运行，趋势报告展示分项值、delta、seed、工具链和 gate 状态 |
| P4.5 | 未完成 | P2 | 失败 seed 自动归档 | 长回归失败时保存最小复现材料和重跑命令 |
| P4.6 | 未完成 | P2 | GUI 可见性自动化增强 | 从“打开 Vivado GUI”升级为“自动判断波形区非空并保留截图证据” |
| P4.7 | 未完成 | P2 | 报告体验升级 | 把报告升级为工程 dashboard，统一 spec/RTL/sim/UVM/coverage/wave/lessons 卡片 |

## 已知技术债

- `agent.py` 仍承载较多 target 专用 RTL/TB/UVM flow；后续扩展时应继续按清晰边界迁移，但不为拆分而拆分。
- 运行时 `artifacts.json` 当前持续追加全部历史，尚未设置保留数量、归档或压缩策略；长周期回归可在后续增加 rotation。
- 环境预检的项目级 `artifacts.json` 同样采用追加模式；后续可与 P5.11 顶层总览一起设计统一 rotation。
- P5.11 会在 Agent 写入 target/environment manifest 后自动刷新；外部工具直接修改输出文件但不写 manifest 时，需要手动运行 `--generate-overview`。
- P5.7 只生成候选 target，不自动安装到正式 registry；这是为了避免缺少 `TargetHandler` 时破坏 Agent 启动，安装动作应在 TODO 完成后人工执行。
- Adapter 目前通过方法绑定兼容旧入口；后续新增外部工具能力应优先进入 adapter，避免逻辑重新回流到主类。
- README 和部分旧文档存在历史编码显示问题；后续改文档时应使用 UTF-8，并优先新增清晰中文文档，不建议大面积重写旧记录。
- `outputs/` 当前用于本地真实 Vivado 验收，不应提交到仓库；如需要保留关键证据，应转写到 `docs/testing/` 或 `docs/roadmap/`。
- `.claude/settings.local.json` 是本地配置，不应提交。

## 推荐下一步

建议后续按依赖顺序推进：

1. **P4.5**：归档失败 seed、日志、WDB、coverage DB 和可复现命令。
2. **P4.6**：增强 GUI 波形可见性自动化并保留截图证据。
3. **P4.7**：统一工程 dashboard，整合 spec、RTL、sim、UVM、coverage、wave 和 lessons。

## 清理原则

后续清理仓库时遵守：

- 删除前必须先列出清单并获得明确确认。
- 优先删除 `.pytest_cache/`、`.tmp-pytest/`、`.tmp-agent-output/`、重复仿真输出、旧 zip 包等可再生成文件。
- 不删除 `docs/tools_archive/`、`.trae/agent/targets/`、`tests/`、`VCD_ANALYZER-main/` 等项目正常运行依赖。
- `outputs/` 若要删除，需要确认不再需要本地 Vivado 波形和报告证据；其内容可由命令重新生成，但真实仿真耗时较长。
