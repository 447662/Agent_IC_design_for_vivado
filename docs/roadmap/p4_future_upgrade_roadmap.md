# P4 后续升级路线图

P4 先不作为当前必须实现项。本文件用于沉淀 P3.14 之后的 coverage、GUI、回归和报告增强方向，等待 P5 通用数字 IC Agent 主流程跑通后再逐步接入。

## 定位

- 当前优先级：暂停实现，作为后续升级池维护。
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

## P4.4：Coverage 趋势记录

目标：记录每次真实 coverage 的时间、seed、Vivado 版本、分项覆盖率和 gate 结果。

建议产物：

- `reports/coverage_history.jsonl`
- `reports/coverage_trend.md`
- `reports/coverage_trend.html`

P5 兼容点：

- history schema 必须包含 `target_name`、`flow_name`、`toolchain`、`seed_set`。
- 多目标项目可以在同一个 dashboard 中按 target 过滤。

## P4.5：失败 Seed 自动归档

目标：长回归中失败 seed 自动保留最小复现材料。

建议能力：

- 失败 seed 目录固定保留 log、WDB、coverage DB、Tcl、目标配置。
- 自动生成“重跑该 seed”的命令。
- 在总览页标记失败 seed，并链接到对应 WDB 打开命令。

P5 兼容点：

- seed 归档路径不应写死 UVM coverage，后续仿真、lint、formal smoke 都可复用同一归档模型。

## P4.6：GUI 可见性自动化增强

目标：从“打开 GUI 并提供截图脚本”升级为“自动判断波形区域非空”。

建议能力：

- 检查 WDB 已打开、Scope/Objects 非空、wave config 有对象。
- 可选地捕获 Vivado 窗口截图并做像素级非空检查。
- 报告里保留人工截图入口。

P5 兼容点：

- GUI 验收应抽象为 `wave_open_check`，兼容 RTL WDB、UVM WDB 和未来其它目标的 WDB。

## P4.7：报告体验升级

目标：让报告更像工程 dashboard，而不是堆叠日志。

建议能力：

- `reports/index.html` 增加目标选择、阶段状态、最近运行、失败入口。
- 每个目标保留统一报告卡片：Spec、RTL、Simulation、UVM、Coverage、Wave、Lessons。
- 对中文报告继续保持 UTF-8，并避免终端乱码误判。

P5 兼容点：

- index 不应只服务 `outputs/async-fifo`；应能聚合多个 target。

## 暂缓事项

以下内容有价值，但不应阻塞 P5 主流程：

- 自动修改 UVM sequence 以提升覆盖率。
- 覆盖率目标自动闭环到高阈值。
- 像素级 Vivado 波形验证。
- 多工具 coverage 适配，例如 Questa/VCS/Xcelium。
- 从自然语言直接生成复杂协议 UVM agent。

## P5 接入原则

P4 后续升级必须遵守：

- 先做通用数据结构，再做 async FIFO 特例。
- 先扩展报告和诊断，再自动改设计或测试。
- 先保留真实工具产物链接，再做二次摘要解析。
- 所有 P4 能力都要能被 P5 的目标注册表调用。
- 所有失败路径都要刷新顶层报告入口，避免 P3.14 的问题复发。
