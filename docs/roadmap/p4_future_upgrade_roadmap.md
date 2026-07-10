# P4 后续升级路线图

P5 通用数字 IC Agent 主流程已经跑通，P4 从升级池转入实施阶段。本文件用于维护 coverage、GUI、回归和报告增强的交付顺序与当前状态。

## 定位

- 当前优先级：P4.0-P4.7 已全部完成，下一步进入 P4 收尾复核。
- 当前基线：P0-P3.14 已打通 async FIFO 的 RTL 生成、Vivado/xsim 仿真、VCD/WDB、UVM smoke、coverage、xcrg 报告和总览页刷新。
- P4 目标：把“能跑通并生成报告”升级为“能定位低覆盖、推荐补测、追踪趋势、服务多个设计目标”。
- P5 兼容要求：P4 的任何能力都不应只绑定 async FIFO；新增报告、数据结构和 CLI 参数要能复用于 CDC、FIFO、arbiter、register file、protocol bridge 等后续目标。

## P4.0：Coverage Closure 总览

目标：把当前 `uvm_coverage_summary.md/html` 扩展成 coverage closure 看板。

建议能力：

- 汇总 Total、Line/Statement、Branch、Condition、Toggle、Functional coverage。
- 标记当前阈值、目标阈值、差距和主要低覆盖类别。
- 链接官方 xcrg code/functional HTML、原始 log、coverage percent 文本和 WDB。
- 输出“下一步补测建议”，但不直接修改 UVM sequence。

P5 兼容点：

- 使用通用字段：`target_name`、`design_family`、`coverage_metrics`、`low_coverage_items`、`recommended_scenarios`。
- 避免写死 async FIFO 信号名；设计特有建议应来自目标配置或目标插件。

当前状态：已完成。

- `--coverage-closure --coverage-target 80 --output-dir outputs` 生成 `outputs/coverage-closure/index.md/html`。
- 聚合注册 target 的 Total、Statement/Line、Branch、Condition、Toggle、Functional coverage。
- 数值目标显示当前值、目标值和 gap；缺失值保持 `-`，不会伪造为 `0.0%`。
- Target 状态支持 `PASS/GAP/MISSING/NOT_RUN/SKIP/INVALID`，项目状态支持 `PASS/WARN/FAIL`。
- async-fifo 真实 xcrg 数据汇总为 Total `27.6%`、Statement `60.2%`、Branch `23.5%`、Condition `22.0%`、Toggle `4.8%`，相对 80% 目标总差距 `52.4%`。
- sync-fifo 与 round-robin-arbiter 保留 target 元数据声明的 `SKIP/N/A`，不误报失败。
- 看板链接 coverage summary、官方 xcrg code/functional HTML、原始 log、percent 文本和 WDB。
- `recommended_scenarios` 字段已预留为空列表，由 P4.2 基于 P4.1 低覆盖明细生成。

## P4.1：低覆盖项提取

目标：从 xcrg 产物中提取可读的低覆盖模块、实例、文件和覆盖类型。

建议能力：

- 解析 xcrg HTML 或可导出的文本摘要。
- 汇总低覆盖文件、实例和 coverage type。
- 对无法解析的 xcrg 版本保留原始链接和明确诊断。
- 增加稳定测试夹具，避免依赖真实 Vivado 产物格式漂移。

P5 兼容点：

- 定义 `CoverageItem` 数据结构，字段包含 `source_file`、`instance`、`metric`、`score`、`details`、`source_report`。
- 所有设计目标共享解析器，目标插件只提供“如何解释这些低覆盖项”的规则。

当前状态：已完成。

- 新增 `.trae/agent/xcrg_coverage.py`，使用标准库结构化解析 xcrg HTML，不依赖 Vivado 运行时或第三方 HTML 包。
- 解析 `codeCoverageReport/files.html`、`modules.html`、`functionalCoverageReport/groups.html` 和 `grp*.html`。
- 输出文件级、模块实例级、functional group、cover point 和 cross 低覆盖项，统一使用 `CoverageItem` 字段。
- 只保留当前 target 工程目录内的 HDL 源文件，自动排除 Vivado 自带 `xlnx_uvm_package.sv` 等外部库。
- 无法识别、缺失或损坏的 xcrg 页面返回 `MISSING/INVALID` 诊断，并保留原始报告链接，不伪造 `0.0%`。
- `coverage-closure/index.md/html` 已展示具体低覆盖项和解析诊断，并新增 `coverage-closure/low_coverage_items.json` 供 P4.2 使用。
- async-fifo 真实 xcrg 产物解析出 36 个低覆盖项、0 条诊断，包含 `cp_full`、`cross_write_full`、`cross_read_empty` 和 57.1% functional group。
- xcrg 的制表符实例名已规范为稳定的 `this.async_fifo_cg`；P4.1 只提供低覆盖证据，由 P4.2 填充推荐场景。

## P4.2：场景补齐建议

目标：根据低覆盖项和目标设计特性，生成补测建议。

async FIFO 可覆盖：

- full boundary：写到 full 后继续写、解除 full 后恢复。
- empty boundary：读到 empty 后继续读、写入后恢复。
- reset recovery：写域/读域分别 reset、traffic 中 reset。
- clock ratio sweep：写快读慢、读快写慢、近似同频、相位错开。
- mixed traffic：随机 burst、backpressure、near-full/near-empty 抖动。

P5 兼容点：

- 每类设计定义 `scenario_catalog`，例如 arbiter 的 fairness/starvation，register file 的 RAW/WAW，CDC sync 的 metastability-safe reset。
- Agent 输出建议时引用场景 ID，而不是散落自然语言。

当前状态：已完成。

- 新增 `.trae/agent/coverage_recommendations.py`，将通用 `CoverageItem` 映射到 target `scenario_catalog`。
- 场景可通过可选 `coverage_match` 配置 `tokens`、`source_patterns`、`metrics`、`fallback` 和 `priority`。
- 只推荐 `status=PASS` 的可执行场景；`SKIP/N/A` 场景不会进入补测清单。
- `recommended_scenarios` 保持稳定的场景 ID 列表，同时新增 `scenario_recommendations` 保存优先级、用途、命中项、指标、原始报告和解释。
- async-fifo 新增 `clock_ratio_sweep`，并为 `full_boundary`、`empty_boundary`、`reset_recovery`、`clock_ratio_sweep`、`mixed_stress` 配置 coverage 匹配规则。
- 真实 async-fifo 结果依次推荐 `full_boundary`、`empty_boundary`、`reset_recovery`、`clock_ratio_sweep`、`mixed_stress`。
- 看板 Markdown/HTML 和 `low_coverage_items.json` 均展示推荐场景与证据，但不会自动修改 UVM sequence。

## P4.3：分项 Coverage Gate

目标：从单一总覆盖率 gate 升级为分项 gate。

建议 CLI：

```powershell
python .trae/agent/agent.py --uvm-coverage async-fifo --coverage-threshold 60 --coverage-line-threshold 80 --coverage-branch-threshold 50 --output-dir outputs
```

建议规则：

- 总覆盖率阈值仍保留。
- line/branch/condition/toggle 支持独立阈值。
- 缺失某个分项时，报告应说明是“数据源缺失”，不是默认 FAIL 或默认 0。
- 失败时仍刷新 `reports/index.md/html`。

P5 兼容点：

- 每个设计目标可提供默认阈值 profile：`smoke`、`nightly`、`release`。
- 目标无关 gate 逻辑只处理数值和状态，目标相关阈值来自配置。

当前状态：已完成。

- 新增 `.trae/agent/coverage_gates.py`，统一计算 Total、Statement/Line、Branch、Condition、Toggle、Functional 的当前值、阈值、gap、结果和诊断。
- 分项状态支持 `PASS/FAIL/MISSING/SKIP`；设置阈值但数据源缺失时明确输出 `MISSING` 和“数据源缺失”，不会伪造为 `0.0%`。
- CLI 新增 `--coverage-line-threshold`、`--coverage-branch-threshold`、`--coverage-condition-threshold`、`--coverage-toggle-threshold`、`--coverage-functional-threshold`，并保留 `--coverage-threshold` 总覆盖率 gate。
- `agent_cli.py`、`DigitalICAgent.run_uvm_coverage()`、`target_flows.py` 和 async-fifo runner 已贯通 `coverage_thresholds` 参数。
- Markdown/HTML 摘要新增 P4.3 分项 gate 表格与状态卡片；任一分项 `FAIL/MISSING` 时 runner 返回失败，失败路径仍刷新 `reports/index.md/html`。
- Functional 百分比可以从 `Functional Coverage Score` 解析；缺省 Total 仍只由 statement/branch/condition/toggle 四项计算，不把 Functional 重复计入。
- 真实 async-fifo xcrg 数据为 Total `27.64%`、Statement `60.2041%`、Branch `23.5294%`、Condition `22.0%`、Toggle `4.84%`；当前 xcrg 文本没有 Functional 数值，配置 Functional 阈值时正确标记 `MISSING`。
- P4.3 定向回归 `8 passed`，全量回归 `168 passed`，Ruff 通过，Mypy `20 source files` 通过；`coverage_gates.py` 定向覆盖率 `93.2%`。

## P4.4：Coverage 趋势记录

目标：记录每次真实 coverage 的时间、seed、Vivado 版本、分项覆盖率和 gate 结果。

建议产物：

- `reports/coverage_history.jsonl`
- `reports/coverage_trend.md`
- `reports/coverage_trend.html`

P5 兼容点：

- history schema 必须包含 `target_name`、`flow_name`、`toolchain`、`seed_set`。
- 多目标项目可以在同一个 dashboard 中按 target 过滤。

当前状态：已完成。

- 新增 `.trae/agent/coverage_history.py`，以 append-only JSONL 保存每次 coverage 运行。
- history schema 包含 `schema_version`、`recorded_at`、`target_name`、`flow_name`、`toolchain`、`seed_set`、`coverage_metrics`、`coverage_gates`、`status` 和 `sources`。
- `run_async_fifo_uvm_coverage()` 在真实仿真成功、gate 失败、覆盖产物失败、SVA 失败和 Vivado 返回失败路径各追加一次记录，不由普通报告重写触发历史追加。
- 自动生成 `reports/coverage_trend.md/html`，展示最新分项值、相邻运行 delta、运行状态、gate 结果、seed 和 Vivado 版本。
- `reports/index.md/html` 新增 `coverage_trend.html`、`coverage_trend.md` 和 `coverage_history.jsonl` 入口。
- JSONL 读取会报告具体损坏行号，避免静默跳过错误历史。
- 两次真实 Vivado 2025.2/xsim coverage 运行已追加 2 条 PASS 记录；Total `27.64%`、Statement `60.2041%`、Branch `23.5294%`、Condition `22.0%`、Toggle `4.84%`，第二次相邻 delta 均为 `+0.0%`。
- P4.4 定向回归 `4 passed`，全量回归 `172 passed`，Ruff 通过，Mypy `21 source files` 通过；`coverage_history.py` 定向覆盖率 `90.3%`。

## P4.5：失败 Seed 自动归档

目标：长回归中失败 seed 自动保留最小复现材料。

建议能力：

- 失败 seed 目录固定保留 log、WDB、coverage DB、Tcl、目标配置。
- 自动生成“重跑该 seed”的命令。
- 在总览页标记失败 seed，并链接到对应 WDB 打开命令。

P5 兼容点：

- seed 归档路径不应写死 UVM coverage，后续仿真、lint、formal smoke 都可复用同一归档模型。

当前状态：已完成。

- 新增 `.trae/agent/failure_archive.py`，提供目标和 flow 无关的 `archive_failed_run()`。
- 固定归档路径为 `failure_archives/<flow_name>/<run_id>/`，当前 async-fifo 随机回归使用 `failure_archives/uvm-coverage/seed_<N>/`。
- `failure_archive.json` 记录 `schema_version`、时间、target、flow、run ID、状态、seed、材料清单、重跑命令和波形打开命令。
- 归档按 role 保存 log、WDB、coverage DB、Tcl 和目标配置；缺失材料会在 manifest 中标记 `available=false`，不会伪造文件。
- 自动生成 `README.md`、`reproduce.ps1` 和 `open_wave.ps1`，便于复现失败 seed 和重新打开对应 WDB。
- `run_async_fifo_uvm_random_regression()` 只归档失败 seed，成功 seed 不创建归档目录。
- `uvm_random_regression.md/html` 新增 Failure Archive、Reproduce 和 Open WDB 入口。
- 通用 schema 测试使用 `sync-fifo` / `formal-smoke`，确认实现没有写死 async FIFO 或 UVM coverage。
- P4.5 定向回归 `4 passed`，全量回归 `175 passed`；Ruff 通过，Mypy `22 source files` 通过；总覆盖率 `79.07%`，`failure_archive.py` 定向覆盖率 `89.0%`。

## P4.6：GUI 可见性自动化增强

目标：从“打开 GUI 并提供截图脚本”升级为“自动判断波形区域非空”。

建议能力：

- 检查 WDB 已打开、Scope/Objects 非空、wave config 有对象。
- 可选地捕获 Vivado 窗口截图并做像素级非空检查。
- 报告里保留人工截图入口。

P5 兼容点：

- GUI 验收应抽象为 `wave_open_check`，兼容 RTL WDB、UVM WDB 和未来其它目标的 WDB。

完成情况：

- 新增 `.trae/agent/wave_visibility.py`，统一解析 WDB、Scope、Object、Wave、Wave Config 和截图像素指标，状态支持 `PASS`、`FAIL`、`PENDING`。
- RTL 和 UVM GUI Tcl 会自动写入运行时 JSON 探针；截图脚本捕获前台 Vivado 窗口并生成 PNG 与 `wave_screenshot_metrics.json`。
- `--check-rtl` 会读取运行时探针和截图指标，刷新 `wave_visibility.md/html`、`wave_screenshot.md/html` 及报告索引。
- GUI Tcl 会忽略 `latest_async_fifo_wdb.txt` 中不存在的旧时间戳 WDB，避免失效指针覆盖可用的固定名 WDB。
- 真实 Vivado 2025.2 验收使用新生成的 `async_fifo_smoke_20260710_221215.wdb`：Scope `35`、Object `57`、Wave `31`、Wave Config `1`；截图 `1500x950`、唯一颜色 `582`、非均匀像素比例 `99.99%`。
- P4.6 RED 为 `8 failed, 164 deselected`，GREEN 为 `10 passed, 164 deselected`，`wave_visibility.py` 定向覆盖率 `100.0%`。
- 全量回归 `181 passed`，总覆盖率 `79.64%`；Ruff 通过，Mypy `23 source files` 通过。
- 详细证据见 `docs/testing/p4_6_gui_visibility_automation.tdd.md`。

## P4.7：报告体验升级

目标：让报告更像工程 dashboard，而不是堆叠日志。

状态：已完成。

已交付：

- `project_overview.py` 新增通用 `write_target_dashboard()`，每个 target 的 `reports/index.md/html` 统一展示目标选择、阶段状态、最近运行、最近失败、重跑命令和失败归档入口。
- 阶段卡片固定为 Spec、RTL、Simulation、UVM、Coverage、Wave、Lessons 七类，并根据目标目录、报告和 manifest 自动判定 READY/NOT_RUN。
- 多 target 导航优先链接目标自身 dashboard；目标 dashboard 尚未生成时回退到顶层 `../../index.html#target-<name>`，避免死链。
- 工程资源仅收录顶层报告与嵌套官方 `dashboard.html`，不展开 xcrg 的模块明细页，避免资源列表被内部页面淹没。
- `write_async_fifo_reports_index()` 已委托给通用 dashboard，同时保留 async FIFO 问题复盘文档入口。
- Markdown/HTML 均按 UTF-8 生成；PowerShell 读取无 BOM UTF-8 文档时需显式使用 `-Encoding UTF8`，避免把终端代码页显示问题误判为文件乱码。

验证：

- TDD 初始 RED：`3 failed, 173 deselected`；初始 GREEN：`3 passed, 173 deselected`。
- 目标导航断链回归 RED：`1 failed, 2 passed`；最终 GREEN：`3 passed, 173 deselected`。
- 全量回归 `183 passed in 15.82s`，总覆盖率 `80.19%`，`project_overview.py` 覆盖率 `90.7%`。
- Ruff 输出 `All checks passed!`；Mypy 输出 `Success: no issues found in 23 source files`。
- 真实 `--check-rtl async-fifo` 全部检查为 `[OK]`。
- dashboard 静态验收：目标链接 `4`、阶段卡片 `7`、READY 卡片 `6`、资源行 `42`、断链 `0`、无 xcrg 明细页泛滥、无乱码。
- 浏览器直接打开本地 `file://` 页面受安全策略限制，因此本轮采用 DOM、CSS、链接存在性和响应式规则验收，不绕过安全限制。

提交：

```text
bae92992 test: define P4.7 report dashboard behavior
830fd3f6 feat: add P4.7 engineering report dashboard
41b2772c fix: harden P4.7 dashboard navigation
```

详细证据见 `docs/testing/p4_7_report_dashboard.tdd.md`。

## 暂缓事项

以下内容有价值，但不应阻塞 P5 主流程：

- 自动修改 UVM sequence 以提升覆盖率。
- 覆盖率目标自动闭环到高阈值。
- 多工具 coverage 适配，例如 Questa/VCS/Xcelium。
- 从自然语言直接生成复杂协议 UVM agent。

## P5 接入原则

P4 后续升级必须遵守：

- 先做通用数据结构，再做 async FIFO 特例。
- 先扩展报告和诊断，再自动改设计或测试。
- 先保留真实工具产物链接，再做二次摘要解析。
- 所有 P4 能力都要能被 P5 的目标注册表调用。
- 所有失败路径都要刷新顶层报告入口，避免 P3.14 的问题复发。
