# 数字 IC 前端设计 Agent

这是 `.trae/agent/agent.py` 的本地 CLI 说明。当前版本已从文档模板扩展到 VCD 分析、Vivado/xsim smoke 仿真，以及第一个可落地 RTL 工程 `async-fifo`。

## CLI

```powershell
python .trae/agent/agent.py --diagnostic
python .trae/agent/agent.py --list-skills
python .trae/agent/agent.py --list-targets
python .trae/agent/agent.py --analyze-vcd path/to/wave.vcd
python .trae/agent/agent.py --analyze-vcd path/to/wave.vcd --wave-backend rwave
python .trae/agent/agent.py --analyze-vcd path/to/wave.vcd --wave-backend vcd-analyzer
python .trae/agent/agent.py --smoke-loop --output-dir .tmp-agent-output
python .trae/agent/agent.py --sim-smoke --output-dir .tmp-agent-output
python .trae/agent/agent.py --sim-smoke --no-wave-gui --output-dir .tmp-agent-output
python .trae/agent/agent.py --generate-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --sim-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --sim-rtl async-fifo --no-wave-gui --output-dir outputs
python .trae/agent/agent.py --regress-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --uvm-smoke async-fifo --no-wave-gui --output-dir outputs
python .trae/agent/agent.py --uvm-coverage async-fifo --output-dir outputs
python .trae/agent/agent.py --analyze-rtl-vcd async-fifo --output-dir outputs
python .trae/agent/agent.py --check-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs
```

## 参数

| 参数 | 说明 |
| --- | --- |
| `--diagnostic` | 检查 Vivado、`uv`、SynthPilot MCP 和技能文件 |
| `--list-skills` | 列出当前 Agent 技能配置 |
| `--list-targets` | 列出当前可用 RTL 设计目标、别名和支持 flow |
| `--analyze-vcd <file>` | 分析 VCD，可配合 `--vcd-condition`、`--vcd-show`、`--vcd-limit` |
| `--smoke-loop` | 生成内置握手 VCD 并运行 VCD 分析 |
| `--sim-smoke` | 使用可用仿真器运行握手 RTL smoke，优先 Vivado |
| `--no-wave-gui` | Vivado/xsim 仿真后不打开 GUI 波形 |
| `--generate-rtl async-fifo` | 生成异步 FIFO RTL/TB/Vivado 脚本工程 |
| `--sim-rtl async-fifo` | 运行异步 FIFO Vivado/xsim 仿真，并默认打开 Vivado 工程与最新 WDB |
| `--regress-rtl async-fifo` | 运行异步 FIFO 多参数 Vivado/xsim 回归，并生成回归摘要 |
| `--uvm-smoke async-fifo` | 生成并运行 async FIFO 最小 UVM smoke，输出 UVM 日志、WDB 和中文报告 |
| `--uvm-coverage async-fifo` | 运行 async FIFO UVM smoke 并启用 Vivado/xsim code coverage |
| `--analyze-rtl-vcd async-fifo` | 分析 async FIFO VCD 中的写/读 handshake 事件 |
| `--check-rtl async-fifo` | 检查 async FIFO 工程产物、报告、WCFG，并生成波形可见性验收报告 |
| `--open-wave async-fifo` | 不重新仿真，打开 async FIFO 工程和最新 WDB 波形 |
| `--wave-backend auto|rwave|vcd-analyzer` | 选择波形分析后端；默认 auto 优先 RWaveAnalyzer，失败时降级到 VCD_ANALYZER |
| `--output-dir <path>` | 指定输出根目录 |
| `--no-tool-check` | 普通需求文档流程中跳过外部工具检查 |

## Vivado 流程

`--sim-smoke` 会写入握手 RTL 与 testbench，调用 Vivado/xsim 生成 `handshake_trace.vcd`，再用统一波形分析后端查找 `tb.valid=1,tb.ready=1` 的传输事件。GUI 波形打开使用 `handshake_smoke.wdb`，不要把 `.vcd` 传给 `open_wave_database`。

## RWaveAnalyzer / VCD_ANALYZER

- 默认 `--wave-backend auto`：优先使用 RWaveAnalyzer 的 `rwave`，不可用或运行失败时降级到 `VCD_ANALYZER-main`。
- `RWAVE_BIN` 可指定本机 `rwave.exe` 绝对路径；如果未设置，Agent 会查找 PATH 和已构建的 RWaveAnalyzer `target/release/rwave.exe`。
- `--wave-backend rwave` 用于强制验证 RWaveAnalyzer；`--wave-backend vcd-analyzer` 用于强制旧 Python 分析器兼容路径。
- `--analyze-rtl-vcd async-fifo` 在 RWaveAnalyzer 可用时优先走 batch 模式：一次加载 `async_fifo_trace.vcd`，连续执行 `info`、写计数变化搜索、读计数变化搜索，减少重复解析 VCD 的开销。
- 当前已经用最新 `RWaveAnalyzer-main.zip` 临时解压并 `cargo build --release` 验证，`rwave 0.1.4` 可以读取现有 `handshake_trace.vcd`。

如果只需要批处理结果：

```powershell
python .trae/agent/agent.py --sim-smoke --no-wave-gui --output-dir .tmp-agent-output
```

## 异步 FIFO

第一个 RTL 目标是异步 FIFO：

```powershell
python .trae/agent/agent.py --generate-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --sim-rtl async-fifo --output-dir outputs
```

生成目录：

```text
outputs/async-fifo/
  rtl/async_fifo.v
  tb/tb_async_fifo.v
  uvm/async_fifo_if.sv
  uvm/async_fifo_uvm_pkg.sv
  uvm/tb_async_fifo_uvm.sv
  sim/run_vivado_async_fifo.tcl
  sim/run_vivado_async_fifo_uvm.tcl
  sim/run_vivado_async_fifo_uvm_coverage.tcl
  sim/create_async_fifo_project.tcl
  sim/open_async_fifo_project_gui.tcl
  vivado_project/async_fifo_project.xpr
  reports/
  README.md
```

`async_fifo.v` 包含 `DATA_WIDTH`、`ADDR_WIDTH` 参数、Gray 指针转换、两级 `(* async_reg = "true" *)` 同步器、寄存化 `full`/`empty` 判断。`tb_async_fifo.v` 会产生 `async_fifo_trace.vcd`，并覆盖 `basic_ordered`、`full_boundary`、`empty_boundary`、`reset_recovery`、`mixed_stress`。

`--sim-rtl async-fifo` 会先运行 `run_vivado_async_fifo.tcl`，再用 `create_async_fifo_project.tcl` 生成或更新 Vivado 工程，最后通过 `open_async_fifo_project_gui.tcl` 打开工程和最新 `async_fifo_smoke_*.wdb` 波形。流程也保留 `async_fifo_smoke.wdb` 作为历史固定名兼容路径。

## P2.6-P2.12

- P2.6：`parse_async_fifo_wcfg_summary()` 验证 `async_fifo_debug.wcfg`，检查 `WVObjectSize` 和关键信号。
- P2.7：`write_async_fifo_regression_matrix()` 输出 `reports/regression_matrix.md`，记录 `DATA_WIDTH` / `ADDR_WIDTH` 回归组合。
- P2.8：`write_async_fifo_summary_report()` 输出 `reports/sim_summary.md` 和 `reports/sim_summary.html`，汇总 VCD、WDB、WCFG、场景、统计和命令。
- P2.9：`run_async_fifo_regression()` 驱动真实参数矩阵，`--regress-rtl async-fifo` 输出 `reports/regression_summary.md` 和 `reports/regression_summary.html`。
- P2.10：`write_async_fifo_wave_visibility_report()` 输出 `reports/wave_visibility.md` 和 `reports/wave_visibility.html`，验收 Vivado 工程、最新 WDB、GUI Tcl、`open_project`、`open_wave_database` 和 WCFG 关键对象。
- P2.11：`write_async_fifo_wave_screenshot_report()` 输出 `reports/wave_screenshot.md`、`reports/wave_screenshot.html` 和 `reports/capture_wave_screenshot.ps1`，用于沉淀人工可见的 Vivado GUI 波形截图。
- P2.12：`write_async_fifo_reports_index()` 输出 `reports/index.md` 和 `reports/index.html`，集中链接仿真摘要、回归摘要、波形可见性、截图验收和问题复盘。

## P3.0

- P3.0：`write_async_fifo_uvm_smoke_project()` 生成最小 UVM 环境，包括 interface、sequence、driver、monitor、scoreboard、env 和 `async_fifo_basic_test`。
- `--uvm-smoke async-fifo --no-wave-gui --output-dir outputs` 会批量运行 Vivado/xsim UVM smoke，生成 `sim/async_fifo_uvm_smoke.log`、`sim/async_fifo_uvm_smoke.wdb`、`reports/uvm_smoke_report.md` 和 `reports/uvm_smoke_report.html`。
- 当前验收标记是 `ASYNC_FIFO_UVM_SCOREBOARD_PASS` 和 `ASYNC_FIFO_UVM_TEST_DONE`；P3.0 不做覆盖率统计，覆盖率建议作为 P3.1 单独接入。
- 如果需要看波形，先批量跑通 smoke，再用 Vivado GUI 打开对应 WDB，避免把回归批处理和人工 GUI 查看混在一起。

## P3.1

- P3.1：`write_async_fifo_uvm_coverage_project()` 复用 P3.0 UVM 环境，并额外生成 `sim/run_vivado_async_fifo_uvm_coverage.tcl`。
- `--uvm-coverage async-fifo --output-dir outputs` 会启用 `-cc_type sbct`，将 Vivado/xsim code coverage 写入 `sim/coverage/xsim.codeCov/async_fifo_uvm_cov/xsim.CCInfo`。
- 覆盖率报告输出到 `reports/uvm_coverage_report.md` 和 `reports/uvm_coverage_report.html`，中文记录 UVM 标记、WDB、覆盖率目录和 code coverage DB。
- 本阶段覆盖率先做产物级验收：确认 scoreboard/test done 通过，且 `xsim.codeCov` 数据库存在；覆盖率百分比解析和阈值 gate 可作为 P3.2。

## P3.2-P3.13

- P3.2：`write_async_fifo_uvm_coverage_summary_report()` 生成 `reports/uvm_coverage_summary.md/html`，解析 `xsim.CCInfo` 中的可读元信息，并支持 `--coverage-threshold` / `--coverage-percent` gate。
- P3.3：`extract_async_fifo_coverage_percent()` 支持从文本报告解析 statement、branch、condition、toggle 和 total 百分比，并兼容 Vivado `xcrg` 的 Line / Branch / Condition / Toggle Coverage Score 输出。
- P3.4：UVM package 中加入 `covergroup async_fifo_cg`，`write_async_fifo_uvm_functional_coverage_report()` 输出 `reports/uvm_functional_coverage.md/html`。
- P3.5：`--uvm-random-regress async-fifo --uvm-seeds 11,22,33` 运行多 seed UVM 回归，并生成 `reports/uvm_random_regression.md/html`。
- P3.6：`write_async_fifo_uvm_smoke_project()` 额外生成 `uvm/async_fifo_sva.sv`，并在 UVM top 中绑定基础 SVA。
- P3.7：`--open-uvm-wave async-fifo --uvm-wave-kind smoke|coverage` 直接打开 UVM WDB，避免混用 RTL WDB 或 VCD。
- P3.8：`run_async_fifo_uvm_random_regression()` 为每个 seed 使用独立 `uvm_regression/seed_<N>/async-fifo` 输出目录，并在 `uvm_random_regression.md/html` 中记录每个 seed 的 log、WDB 和工程路径。
- P3.9：`write_async_fifo_uvm_wave_screenshot_report()` 生成 `reports/uvm_wave_screenshot.md`、`reports/uvm_wave_screenshot.html` 和 `reports/capture_uvm_wave_screenshot.ps1`，用于 UVM WDB GUI 人工截图验收。
- P3.10：`write_async_fifo_uvm_coverage_summary_report()` 增强 coverage gate 诊断，返回 `coverage_gap` / `gate_diagnostic`，并在 Markdown/HTML 中说明覆盖率达标、低于阈值或缺少可比较百分比的原因。
- P3.11：`run_vivado_async_fifo_uvm_coverage.tcl` 会生成 `reports/uvm_coverage_percent.txt`；`run_async_fifo_uvm_coverage()` 会自动解析该文件中的覆盖率百分比，不再必须手动传入 `--coverage-percent` 才能触发 gate。
- P3.12：真实 Vivado 2025.2 验证确认 `report_coverage` 不是可用 Tcl 命令，覆盖率导出改用 `xcrg`，生成 `reports/uvm_coverage_xcrg/codeCoverageReport/`、`reports/uvm_coverage_xcrg/functionalCoverageReport/` 和 `reports/xcrg_coverage.log`。
- P3.13：`write_async_fifo_reports_index()` 新增 coverage summary、官方 `xcrg` code/functional HTML、`xcrg_coverage.log` 和 `uvm_coverage_percent.txt` 入口；`write_async_fifo_uvm_coverage_summary_report()` 展示 Total、Statement/Line、Branch、Condition、Toggle 分项覆盖率。
- P3.14：`run_async_fifo_uvm_coverage()` 在成功和失败路径都会刷新 `reports/index.md/html`，真实 coverage runner 结束后总览页不再停留在旧状态；已用真实 Vivado coverage 和 `--open-uvm-wave async-fifo --uvm-wave-kind coverage` 验收。

## P4-P5 路线

- P4 暂不作为当前必须实现项，coverage closure、低覆盖项定位、分项 gate、趋势记录和 GUI 自动验收已整理到 `docs/roadmap/p4_future_upgrade_roadmap.md`。
- P5 进入通用化设计阶段，目标是把 async FIFO 单点流程抽象为 target registry、通用 flow、工具 adapter 和报告 surface，设计见 `docs/roadmap/p5_general_digital_ic_agent_design.md`。
- P5.0 已完成最小 target registry：`DigitalICAgent.list_targets()` / `get_target()` 统一管理 `async-fifo` 元信息，`--list-targets` 可列出目标、别名、设计族和支持 flow。
- P5.1 已完成目标配置文件化：`DigitalICAgent.load_target_registry()` 从 `.trae/agent/targets/*.json` 加载目标元信息，当前 async FIFO 配置为 `.trae/agent/targets/async_fifo.json`。

## 问题复盘

Vivado/async FIFO 仿真过程中遇到的问题已沉淀到：

```text
docs/vivado_async_fifo_lessons_learned.md
```

后续如果出现“GUI 打开但没有波形”，先检查三件事：WDB 是否打开、Scope/Objects 是否有对象、`async_fifo_debug.wcfg` 的 `WVObjectSize` 是否大于 0。
