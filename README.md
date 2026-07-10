# Agent IC Design for Vivado

## P5.11 多 Target 顶层报告总览

P5.11 新增 `--generate-overview`，聚合注册表、每个 target 的运行时 `artifacts.json` 和 P5.10 environment manifest，在输出根目录生成统一入口：

```powershell
python .trae/agent/agent.py --generate-overview --output-dir outputs
```

```text
outputs/
  index.md
  index.html
  environment-report/
  async-fifo/
  sync-fifo/
  round-robin-arbiter/
```

总览按 target 展示当前状态、最近 flow、最近状态、时间、错误和重跑命令，并链接统一的 Spec、RTL、Simulation、UVM、Coverage、Wave、Lessons surface。未运行 target 显示 `NOT_RUN`；损坏 manifest 显示 `INVALID`，但不会阻止其他目标展示。target manifest 或环境预检更新后会自动刷新顶层总览，也可以随时手动运行 `--generate-overview`。

TDD 证据见 `docs/testing/p5_11_project_overview.tdd.md`。

## P5.10 中文环境预检报告

P5.10 新增独立 CLI `--environment-report`，在进入 Vivado、波形分析或 GUI flow 前集中检查 Python、Git、Vivado、RWave/VCD_ANALYZER fallback、输出目录权限和 GUI 前置条件。

```powershell
python .trae/agent/agent.py --environment-report --output-dir outputs
```

默认生成：

```text
outputs/environment-report/
  environment_report.md
  environment_report.html
  artifacts.json
```

每项检查使用 `PASS/WARN/FAIL`，并提供中文详情和修复建议。报告生成成功且只有可降级告警时 CLI 返回 0；Python、Git 等基础阻断项为 `FAIL` 时返回 1；输出目录不可写或 manifest 损坏时明确报错且不输出 traceback。环境报告使用独立 `scope: environment` 运行清单，不伪装成某个 RTL target。

TDD 证据见 `docs/testing/p5_10_environment_report.tdd.md`。

## P5.8 运行时 Artifact Manifest

P5.8 新增每个 target 的运行时 `artifacts.json`。所有注册 target flow，以及 `--generate-spec`、`--generate-verification-plan` 和 `--create-target`，都会追加一条运行记录；异常和返回失败同样会写入 `FAIL` 证据后再交还原有错误处理。

```text
outputs/<target>/artifacts.json
```

每条记录包含：

- flow、`PASS/FAIL`、UTC 时间与唯一 run ID。
- 可重跑命令和本次 options。
- Python 版本；适用时记录 Vivado 命令/路径版本和 waveform backend。
- P5.6 声明产物的实际存在状态、相对路径和文件大小。
- 失败错误文本；artifact 状态继续使用 `PASS/SKIP/N/A`。

```json
{
  "schema_version": 1,
  "target": "sync-fifo",
  "runs": [
    {
      "flow": "generate-rtl",
      "status": "PASS",
      "command": ["python", ".trae/agent/agent.py", "--generate-rtl", "sync-fifo"],
      "artifacts": [
        {"id": "rtl", "path": "rtl/sync_fifo.v", "status": "PASS", "exists": true}
      ]
    }
  ]
}
```

历史记录采用追加模式，不会覆盖前一次 flow 证据。TDD 证据见 `docs/testing/p5_8_runtime_artifact_manifest.tdd.md`。

## P5.7 Target 脚手架生成器

P5.7 新增 `--create-target <name>`，用于生成符合 P5.6 schema 的候选 target 配置、最小 RTL/TB、报告占位和 TODO 验收清单。脚手架不会自动写入正式 `.trae/agent/targets/`，因为正式 registry 要求每个 target 同时存在匹配的 `TargetHandler`；完成 TODO 并补齐 handler 后，再按生成的 README 安装候选配置。

```powershell
python .trae/agent/agent.py --create-target packet_router --output-dir outputs "Configurable packet router target"
```

```text
outputs/packet-router/
  target/packet_router.json
  rtl/packet_router.v
  tb/tb_packet_router.v
  reports/design_spec.md
  reports/verification_plan.md
  reports/sim_report.md
  artifacts.json
  TODO.md
  README.md
```

名称会统一规范为 kebab-case target 与 snake_case Verilog module；非法路径、已注册 target 和已有输出目录会被拒绝，默认不会覆盖任何文件。TDD 证据见 `docs/testing/p5_7_target_scaffolder.tdd.md`。

## P5.6/P5.9 通用元数据契约与 Adapter 拆分

P5.6 已将 target 配置升级为严格、可校验的通用元数据契约。每个 `.trae/agent/targets/*.json` 必须提供 `parameters`、`interfaces`、`checks`、`scenario_catalog`、`coverage_metrics` 和 `artifact_manifest`；能力状态统一使用 `PASS`、`SKIP`、`N/A`。注册表会拒绝缺失字段、重复 ID、非法接口方向、非法状态和错误字段类型，规格与验证计划直接消费 target JSON，不再依赖 Python 内置 fallback catalog。

```json
{
  "scenario_catalog": [
    {"id": "reset_recovery", "type": "recovery", "purpose": "复位恢复", "status": "PASS"}
  ],
  "coverage_metrics": [
    {"id": "branch", "label": "Branch coverage", "source": "xcrg", "status": "PASS"}
  ],
  "artifact_manifest": [
    {"id": "sim_report", "path": "reports/sim_report.md", "status": "PASS"}
  ]
}
```

P5.9 已将报告渲染、波形分析和 Vivado 调度从 `agent.py` 拆到 `.trae/agent/adapters/`。`DigitalICAgent` 保留原有方法名并绑定 adapter 函数，因此 CLI、现有测试和 monkeypatch 入口保持兼容。

```text
.trae/agent/adapters/
  report.py       # 规格、验证计划与 HTML/Markdown 报告
  waveform.py     # RWave、VCD_ANALYZER 与自动降级调度
  vivado.py       # Vivado 命令发现、batch 执行与 GUI 启动
```

TDD 证据见 `docs/testing/p5_6_p5_9_metadata_and_adapters.tdd.md`。

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
- 环境预检报告：`--environment-report` 生成中文 Markdown/HTML，覆盖 Python、Git、Vivado、RWave fallback、权限和 GUI 条件。
- 多 target 总览：`--generate-overview` 聚合 target/environment manifest，生成顶层 `index.md/html`，并在 manifest 更新后自动刷新。
- Target 元数据：三个 target 均使用统一 schema，场景、覆盖率和产物状态统一为 `PASS/SKIP/N/A`。
- Target 脚手架：`--create-target` 生成候选配置、RTL/TB、报告占位、README 和 TODO 清单，且默认禁止覆盖。
- 运行时 manifest：每个 target 的 `artifacts.json` 追加 flow 状态、命令、工具信息、产物存在性和失败证据。
- Adapter 边界：报告、波形和 Vivado 外部工具逻辑位于 `.trae/agent/adapters/`，主类保留兼容方法绑定。
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
python .trae/agent/agent.py --environment-report --output-dir outputs
python .trae/agent/agent.py --generate-overview --output-dir outputs
python .trae/agent/agent.py --list-skills
python .trae/agent/agent.py --list-targets
python .trae/agent/agent.py --create-target packet_router --output-dir outputs "Configurable packet router target"
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
- P5.3-P5.5：已完成 `round-robin-arbiter` 最小闭环、通用规格文档和通用验证计划生成。
- P5.6：已完成 target 元数据契约，统一 `scenario_catalog`、`coverage_metrics`、`artifact_manifest` 与 `PASS/SKIP/N/A` 状态。
- P5.7：已完成候选 target 脚手架生成器，提供配置、RTL/TB、报告占位和 TODO 清单，并保护已有文件。
- P5.8：已完成运行时 `artifacts.json`，统一记录 target flow、规格/验证计划与脚手架执行历史。
- P5.9：已拆出 Report、Waveform、Vivado adapter，并保持现有 CLI 与测试兼容。
- P5.10：已完成中文环境预检报告、项目级环境 manifest、修复建议和 CLI 退出码。
- P5.11：已完成多 target 顶层 `index.md/html`、状态聚合、统一 surface 链接和 manifest 更新后自动刷新。

## 问题复盘

Vivado/async FIFO 仿真问题已沉淀到：

```text
docs/vivado_async_fifo_lessons_learned.md
```

重点经验包括：VCD 与 WDB 的职责区分、必须显式打开 Vivado 工程、WDB 必须提前 `log_wave -r /`、WCFG 不能只检查文件存在、GUI 脚本中的 `catch` 需要结果验收、WDB 用时间戳避免占用。

## 开发测试

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .trae/agent tests
python -m mypy
python -X utf8 -m pytest tests --cov=.trae/agent --cov-report=term-missing --cov-fail-under=68 --basetemp .tmp-pytest
```

项目文本统一使用无 BOM 的 UTF-8。Windows PowerShell 5.x 直接读取中文文件时，请显式指定编码，例如：

```powershell
Get-Content -Encoding UTF8 README.md
```

当前完整回归：`139 passed`；整体覆盖率为 `74.39%`，CI 门槛为 `68%`。

GitHub Actions 会在 Python 3.11 和 3.13 上运行 Ruff、Mypy、完整 pytest 与覆盖率门槛，配置见 `.github/workflows/python-quality.yml`。

## RWaveAnalyzer / VCD_ANALYZER 整合

- `--wave-backend auto` 是默认模式：优先调用 `RWAVE_BIN`、PATH 中的 `rwave`，或已构建的 RWaveAnalyzer `target/release/rwave.exe`；不可用时降级到 `VCD_ANALYZER-main/VCD_ANALYZER-main/vcd_analyzer.py`。
- `--wave-backend rwave` 强制使用 RWaveAnalyzer，适合验证 VCD/FST/GHW 统一分析路径；如果找不到 `rwave` 会直接失败。
- `--wave-backend vcd-analyzer` 强制使用旧版 Python VCD_ANALYZER，适合做兼容性对照。
- async FIFO 的 `--analyze-rtl-vcd async-fifo` 在 RWaveAnalyzer 可用时会优先使用 `rwave --batch --json`，一次加载 VCD 并完成 `info`、写 handshake、读 handshake 三类查询；`auto` 模式下 batch 不可用时仍保留旧后端降级路径。
- 最新 `RWaveAnalyzer-main.zip` 是本地下载包，不提交到仓库；需要验证时可临时解压并运行 `cargo build --release`，再设置 `RWAVE_BIN=<rwave.exe 路径>`。

## 项目结构

```text
.trae/agent/agent.py          # Agent CLI、target flow 与兼容方法绑定
.trae/agent/artifact_manifest.py # 运行时 artifacts.json 记录与校验
.trae/agent/environment_report.py # 中文环境预检、修复建议与项目级 manifest
.trae/agent/project_overview.py # 多 target 状态聚合与顶层 index.md/html
.trae/agent/target_registry.py # Target schema 加载与严格校验
.trae/agent/target_scaffolder.py # 候选 target 配置与工程占位生成器
.trae/agent/adapters/         # Report、Waveform、Vivado adapter
.trae/agent/targets/          # async FIFO、sync FIFO、round-robin 配置
.trae/agent/agent.json        # 工具与技能配置
.trae/skills/                 # 数字 IC 设计/RTL/验证技能说明
tests/test_agent.py           # 功能与回归测试
tests/test_quality_config.py  # Ruff/Mypy/覆盖率质量门配置测试
docs/testing/                 # TDD 证据
docs/roadmap/                 # P4 后续升级池与 P5 通用化设计
README.md                     # 项目说明
```
