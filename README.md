# Agent IC Design for Vivado

## P5.4/P5.5 通用规格与验证计划

P5.4/P5.5 已完成 target 级通用文档生成：`--generate-spec` 可从自然语言需求和目标配置生成 `design_spec.md/html`，`--generate-verification-plan` 可从 scenario catalog 生成 `verification_plan.md/html`。当前已覆盖 `async-fifo`、`sync-fifo` 和 `round-robin-arbiter`，用于把新数字 IC target 的设计规格、接口、场景、检查点和验证出口准则先沉淀下来，再进入 RTL/TB/Vivado 仿真闭环。

```powershell
python .trae/agent/agent.py --generate-spec round-robin-arbiter --output-dir outputs "生成一个 4 requester round-robin arbiter"
python .trae/agent/agent.py --generate-verification-plan round-robin-arbiter --output-dir outputs
python .trae/agent/agent.py --generate-spec sync-fifo --output-dir outputs
python .trae/agent/agent.py --generate-verification-plan sync-fifo --output-dir outputs
```

默认产物位于 `outputs/<target>/reports/design_spec.md`、`outputs/<target>/reports/design_spec.html`、`outputs/<target>/reports/verification_plan.md` 和 `outputs/<target>/reports/verification_plan.html`。TDD 证据见 `docs/testing/p5_4_p5_5_spec_and_verification_plan.tdd.md`，执行记录见 `docs/roadmap/p5_4_p5_5_execution_record.md`。

## P5.3 round-robin-arbiter

P5.3 已完成第三个 RTL 目标 `round-robin-arbiter` 的最小闭环，用于验证非 FIFO 控制逻辑设计族。当前支持 target 配置、RTL/TB/Vivado Tcl 生成、真实 Vivado/xsim 仿真、VCD grant/fairness 分析、WDB GUI 打开和中文仿真报告。

```powershell
python .trae/agent/agent.py --generate-rtl round-robin-arbiter --output-dir outputs
python .trae/agent/agent.py --sim-rtl round-robin-arbiter --no-wave-gui --output-dir outputs
python .trae/agent/agent.py --analyze-rtl-vcd round-robin-arbiter --output-dir outputs
python .trae/agent/agent.py --open-wave round-robin-arbiter --output-dir outputs
```

真实验收产物包括 `outputs/round-robin-arbiter/sim/round_robin_arbiter_trace.vcd`、`outputs/round-robin-arbiter/sim/round_robin_arbiter_smoke_20260709_230319.wdb`、`outputs/round-robin-arbiter/vivado_project/round_robin_arbiter_project.xpr` 和 `outputs/round-robin-arbiter/reports/sim_report.md/html`。TDD 证据见 `docs/testing/p5_3_round_robin_arbiter_target.tdd.md`。

这是一个面向 Vivado 的数字 IC 前端设计 Agent 原型。当前重点是把“需求分析 -> RTL 生成 -> Vivado/xsim 仿真 -> VCD 分析 -> GUI 波形查看 -> 报告沉淀”串成可重复流程。

## 当前能力

- 需求分析：根据自然语言需求匹配设计文档、RTL、验证相关技能。
- 环境诊断：检查 Vivado、`uv`、SynthPilot MCP 等外部工具。
- VCD/波形分析：`--analyze-vcd` 支持条件搜索与信号观察，默认 `--wave-backend auto` 会优先使用 RWaveAnalyzer 的 `rwave`，不可用时自动降级到 `VCD_ANALYZER-main`。
- 内置闭环：`--smoke-loop` 生成握手示例 VCD 并调用分析器。
- Vivado smoke 仿真：`--sim-smoke` 调用 Vivado/xsim，生成 `handshake_trace.vcd` 和 `handshake_smoke.wdb`。
- async FIFO RTL：`--generate-rtl async-fifo` 生成 RTL/TB/Vivado 脚本工程。
- async FIFO 仿真：`--sim-rtl async-fifo` 运行 Vivado/xsim，生成 VCD、带时间戳的 WDB，并兼容固定名 `async_fifo_smoke.wdb`。
- GUI 波形：`--open-wave async-fifo` 打开 Vivado 工程和最新 WDB，并加载 `async_fifo_debug.wcfg`。
- 自检报告：`--check-rtl async-fifo` 检查 RTL/TB/脚本/仿真产物/报告，并在已有 WCFG 时验证波形配置。
- 参数回归：`--regress-rtl async-fifo` 运行 async FIFO 多参数 Vivado/xsim 回归，并输出中文回归摘要。
- 最小 UVM smoke：`--uvm-smoke async-fifo` 生成 async FIFO 最小 UVM 环境，运行 Vivado/xsim smoke，并输出中文 UVM smoke 报告。
- UVM 覆盖率：`--uvm-coverage async-fifo` 在 UVM smoke 基础上启用 Vivado/xsim code coverage，并输出中文覆盖率报告。
- 波形可见性验收：`--check-rtl async-fifo` 会自动生成 `wave_visibility.md/html`，用于确认 GUI 打开工程、WDB 和 WCFG 的关键条件。
- GUI 截图验收：`--check-rtl async-fifo` 会生成 `wave_screenshot.md/html` 和截图捕获脚本，打开 Vivado GUI 后可沉淀实际波形截图。
- 报告总览页：`--check-rtl async-fifo` 会生成 `outputs/async-fifo/reports/index.html`，集中链接仿真摘要、回归摘要、波形验收、截图验收和问题复盘。

## 常用命令

```powershell
python .trae/agent/agent.py --diagnostic
python .trae/agent/agent.py --list-skills
python .trae/agent/agent.py --list-targets
python .trae/agent/agent.py --analyze-vcd path/to/wave.vcd --vcd-condition "tb.valid=1,tb.ready=1" --vcd-show "tb.data"
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

## async FIFO 工程

`--generate-rtl async-fifo` 会生成：

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

`async_fifo.v` 使用双时钟接口、Gray 指针、两级 `(* async_reg = "true" *)` 同步器，以及寄存化 `full_reg` / `empty_reg` 状态判断。`tb_async_fifo.v` 内置 scoreboard，会覆盖：

- `basic_ordered`
- `full_boundary`
- `empty_boundary`
- `reset_recovery`
- `mixed_stress`

仿真通过时会打印 `ASYNC_FIFO_SCOREBOARD_PASS`；失败时打印 `ASYNC_FIFO_SCOREBOARD_FAIL` 并让 xsim 返回失败。

## Vivado 波形说明

Vivado GUI 不能用 `open_wave_database` 直接打开 `.vcd`，当前流程会打开 xsim 生成的 `.wdb`。VCD 保留给自动分析器使用。

P2.5 以后，GUI 脚本会优先打开最新 `async_fifo_smoke_*.wdb`，同时保留 `async_fifo_smoke.wdb` 作为兼容路径；随后自动创建 `async_fifo_debug.wcfg`，按 Scenario、Write Domain、Read Domain、Scoreboard、DUT Pointers、DUT Status、DUT Sync 分组加入关键信号。P2.6 进一步增加 WCFG 验收：如果已有 `.wcfg`，`--check-rtl` 会检查 `WVObjectSize` 和关键对象，避免再次出现“Vivado 打开但波形窗口为空”的问题。

## P2.6-P2.12

- P2.6：WCFG 自动验收，检测空波形配置和缺失关键信号。
- P2.7：参数回归矩阵报告，输出 `outputs/async-fifo/reports/regression_matrix.md`。
- P2.8：仿真摘要报告，输出 `outputs/async-fifo/reports/sim_summary.md` 和 `outputs/async-fifo/reports/sim_summary.html`。
- P2.9：真实参数回归，`--regress-rtl async-fifo` 会依次运行 `dw8_aw4`、`dw16_aw4`、`dw8_aw3`，并输出 `outputs/async-fifo/reports/regression_summary.md` 和 `outputs/async-fifo/reports/regression_summary.html`。
- P2.10：波形可见性验收，`--check-rtl async-fifo` 会自动输出 `outputs/async-fifo/reports/wave_visibility.md` 和 `outputs/async-fifo/reports/wave_visibility.html`，检查 Vivado 工程、最新 WDB、GUI Tcl、`open_project`、`open_wave_database` 和 WCFG 关键对象。
- P2.11：GUI 波形截图验收，输出 `outputs/async-fifo/reports/wave_screenshot.md`、`outputs/async-fifo/reports/wave_screenshot.html` 和 `capture_wave_screenshot.ps1`，用于保存人工可见的 Vivado 波形截图。
- P2.12：报告总览页，输出 `outputs/async-fifo/reports/index.md` 和 `outputs/async-fifo/reports/index.html`，统一入口链接 `sim_summary.html`、`regression_summary.html`、`wave_visibility.html`、`wave_screenshot.html` 和问题复盘文档。

## P3.0

- P3.0：最小 UVM smoke 环境，`--uvm-smoke async-fifo` 会生成 `uvm/async_fifo_if.sv`、`uvm/async_fifo_uvm_pkg.sv`、`uvm/tb_async_fifo_uvm.sv` 和 `sim/run_vivado_async_fifo_uvm.tcl`。
- 当前 UVM smoke 包含 driver、monitor、scoreboard、env、basic test 和 8 笔写入/读出顺序校验，通过时日志包含 `ASYNC_FIFO_UVM_SCOREBOARD_PASS` 和 `ASYNC_FIFO_UVM_TEST_DONE`。
- P3.0 暂不启用覆盖率统计；报告会明确写入“覆盖率统计：未启用”。覆盖率建议放到 P3.1。
- 批量验证建议使用 `--no-wave-gui`；需要人工看波形时，再打开 Vivado GUI 查看生成的 `async_fifo_uvm_smoke.wdb`。

## P3.1

- P3.1：UVM code coverage，`--uvm-coverage async-fifo` 会生成 `sim/run_vivado_async_fifo_uvm_coverage.tcl` 并运行真实 Vivado/xsim 覆盖率仿真。
- 覆盖率启用参数为 `-cc_type sbct -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov`，覆盖 statement / branch / condition / toggle。
- 主要产物包括 `sim/async_fifo_uvm_coverage.log`、`sim/async_fifo_uvm_coverage.wdb`、`sim/coverage/xsim.codeCov/async_fifo_uvm_cov/xsim.CCInfo`、`reports/uvm_coverage_report.md` 和 `reports/uvm_coverage_report.html`。
- 当前验收同时检查 `ASYNC_FIFO_UVM_SCOREBOARD_PASS`、`ASYNC_FIFO_UVM_TEST_DONE` 和 `xsim.codeCov` 数据库存在。

## P3.2-P3.13

- P3.2：覆盖率数据库元信息摘要，`--uvm-coverage async-fifo` 会额外输出 `reports/uvm_coverage_summary.md/html`，记录 `xsim.CCInfo` 中可读的数据库名、源文件、实例和覆盖项片段。
- P3.3：覆盖率百分比文本解析降级路径，支持解析外部文本中的 statement / branch / condition / toggle / total 百分比，并兼容 Vivado `xcrg` 输出的 Line / Branch / Condition / Toggle Coverage Score。
- P3.4：UVM functional coverage，UVM monitor 中加入 `covergroup async_fifo_cg`，并输出 `reports/uvm_functional_coverage.md/html`。
- P3.5：UVM 随机 seed 回归，命令为 `python .trae/agent/agent.py --uvm-random-regress async-fifo --uvm-seeds 11,22,33 --output-dir outputs`，输出 `reports/uvm_random_regression.md/html`。
- P3.6：SVA 断言包，生成 `uvm/async_fifo_sva.sv`，覆盖 full 时禁止写、empty 时禁止读、reset 后 flag 非 X 等基础属性。
- P3.7：UVM WDB GUI 专用入口，命令为 `python .trae/agent/agent.py --open-uvm-wave async-fifo --uvm-wave-kind coverage --output-dir outputs`，可直接打开 `async_fifo_uvm_smoke.wdb` 或 `async_fifo_uvm_coverage.wdb`。
- P3.8：UVM 多 seed 回归改为 seed 独立输出目录，形如 `outputs/async-fifo/uvm_regression/seed_11/async-fifo`，避免 log、WDB 和 coverage DB 相互覆盖。
- P3.9：UVM GUI 波形截图验收，`--open-uvm-wave` 会生成 `reports/uvm_wave_screenshot.md/html` 和 `capture_uvm_wave_screenshot.ps1`，用于沉淀人工可见的 Vivado UVM 波形截图。
- P3.10：覆盖率 gate 诊断增强，`uvm_coverage_summary.md/html` 会输出当前覆盖率、阈值、差距百分比和缺失覆盖率百分比时的明确原因，便于快速判断失败是覆盖率不足还是数据源缺失。
- P3.11：Vivado 覆盖率百分比自动导出，coverage Tcl 会生成 `reports/uvm_coverage_percent.txt`，runner 会自动解析覆盖率百分比并供 coverage gate 使用。
- P3.12：真实 Vivado 2025.2 coverage 验收，确认 Tcl 内 `report_coverage` 不可用，已改用 Vivado 自带 `xcrg -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov` 生成 `reports/uvm_coverage_xcrg/` HTML 报告和 `xcrg_coverage.log`；实测自动解析覆盖率为 27.6%，`--coverage-threshold 1` gate PASS。
- P3.13：报告总览页新增 `uvm_coverage_summary.html`、Vivado `xcrg` code/functional HTML、`xcrg_coverage.log` 和 `uvm_coverage_percent.txt` 入口；`uvm_coverage_summary.md/html` 直接展示 Total、Statement/Line、Branch、Condition、Toggle 分项覆盖率和官方报告链接。
- P3.14：真实 `--uvm-coverage` 流程结束后会同步刷新 `reports/index.md/html`，成功和失败路径都能从总览页进入 coverage summary、官方 `xcrg` code/functional HTML、`xcrg_coverage.log` 和 `uvm_coverage_percent.txt`；已重新运行真实 Vivado coverage 并打开 `async_fifo_uvm_coverage.wdb` GUI 波形。

## P4-P5 路线

- P4：coverage closure、低覆盖项定位、分项 gate、趋势记录和 GUI 自动验收先整理为后续升级池，不阻塞当前主流程；路线图见 `docs/roadmap/p4_future_upgrade_roadmap.md`。
- P5：开始把 async FIFO 单点流程抽象成通用数字 IC Agent 框架，优先做 target registry、通用 flow、目标配置和第二个 RTL 目标；设计见 `docs/roadmap/p5_general_digital_ic_agent_design.md`。
- P5 系列执行记录：`docs/roadmap/p5_series_execution_record.md`，记录 P5.0-P5.12 的阶段目标、状态和验收口径。
- P5.0：已完成最小 target registry 和 `--list-targets` CLI，当前注册目标包括 `async-fifo` 和 `sync-fifo`，且保持 async FIFO 原有入口兼容。
- P5.1：已将 target registry 迁移到 `.trae/agent/targets/*.json`，当前 async FIFO 配置位于 `.trae/agent/targets/async_fifo.json`，后续新增 RTL 目标优先新增配置文件，再补对应 flow 实现。
- P5.2：已完成第二个 RTL 目标 `sync-fifo` 的最小闭环，新增目标配置、RTL/TB/Vivado Tcl 生成、真实 Vivado/xsim 仿真、VCD 分析、WDB GUI 打开和中文仿真报告。

## 问题复盘

Vivado/async FIFO 仿真问题已沉淀到：

```text
docs/vivado_async_fifo_lessons_learned.md
```

重点经验包括：VCD 与 WDB 的职责区分、必须显式打开 Vivado 工程、WDB 必须提前 `log_wave -r /`、WCFG 不能只检查文件存在、GUI 脚本中的 `catch` 需要结果验收、WDB 用时间戳避免占用。

## 开发测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest
```

当前完整回归：`80 passed`；P5.2 目标回归已通过 `47 passed, 33 deselected`。

## RWaveAnalyzer / VCD_ANALYZER 整合

- `--wave-backend auto` 是默认模式：优先调用 `RWAVE_BIN`、PATH 中的 `rwave`，或已构建的 RWaveAnalyzer `target/release/rwave.exe`；不可用时降级到 `VCD_ANALYZER-main/VCD_ANALYZER-main/vcd_analyzer.py`。
- `--wave-backend rwave` 强制使用 RWaveAnalyzer，适合验证 VCD/FST/GHW 统一分析路径；如果找不到 `rwave` 会直接失败。
- `--wave-backend vcd-analyzer` 强制使用旧版 Python VCD_ANALYZER，适合做兼容性对照。
- async FIFO 的 `--analyze-rtl-vcd async-fifo` 在 RWaveAnalyzer 可用时会优先使用 `rwave --batch --json`，一次加载 VCD 并完成 `info`、写 handshake、读 handshake 三类查询；`auto` 模式下 batch 不可用时仍保留旧后端降级路径。
- 最新 `RWaveAnalyzer-main.zip` 是本地下载包，不提交到仓库；需要验证时可临时解压并运行 `cargo build --release`，再设置 `RWAVE_BIN=<rwave.exe 路径>`。

## 项目结构

```text
.trae/agent/agent.py       # Agent CLI 和核心流程
.trae/agent/agent.json     # 工具与技能配置
.trae/skills/              # 数字 IC 设计/RTL/验证技能说明
tests/test_agent.py        # 回归测试
docs/                      # 设计计划、问题复盘和阶段沉淀
docs/roadmap/              # P4 后续升级池与 P5 通用化设计
README.md                  # 项目说明
```
