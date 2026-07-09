# Vivado async FIFO 仿真问题复盘

本文沉淀 async FIFO 从 RTL 生成、Vivado/xsim 仿真、WDB 波形打开、VCD 自动分析到报告汇总过程中遇到的问题。后续扩展 P2/P3 时优先参考这里，避免重复踩坑。

## 当前基线

- RTL 目标：`async-fifo`
- RTL：`outputs/async-fifo/rtl/async_fifo.v`
- Testbench：`outputs/async-fifo/tb/tb_async_fifo.v`
- 仿真脚本：`outputs/async-fifo/sim/run_vivado_async_fifo.tcl`
- Vivado 工程脚本：`outputs/async-fifo/sim/create_async_fifo_project.tcl`
- Vivado GUI 脚本：`outputs/async-fifo/sim/open_async_fifo_project_gui.tcl`
- 波形配置：`outputs/async-fifo/sim/async_fifo_debug.wcfg`
- 报告目录：`outputs/async-fifo/reports/`

推荐命令：

```powershell
python .trae/agent/agent.py --generate-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --sim-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --regress-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --analyze-rtl-vcd async-fifo --output-dir outputs
python .trae/agent/agent.py --check-rtl async-fifo --output-dir outputs
python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs
```

## 问题 1：Vivado 不能把 VCD 当作 waveform database 打开

现象：

```text
[Wavedata 42-25] The waveform database 'handshake_trace.vcd' could not be opened for the following reason:
The simulation file has the wrong file extension.
```

原因：`open_wave_database` 需要打开 Vivado/xsim 生成的 `.wdb`，不能直接打开 `.vcd`。VCD 适合给外部分析器使用，不适合作为 Vivado GUI 波形数据库入口。

处理方式：

- xsim 仿真时使用 `-wdb` 生成 `.wdb`。
- Vivado GUI 只打开 `.wdb`。
- `.vcd` 保留给 `VCD_ANALYZER-main` 做自动统计。

## 问题 2：只打开了 Vivado GUI，没有进入项目

现象：Vivado 出现空界面，没有自动打开 `async_fifo_project.xpr`，也没有加载波形。

原因：只启动 GUI 不等于打开工程，必须在 Tcl 脚本里显式执行：

```tcl
open_project $xpr_path
start_gui
open_wave_database $wave_db
```

处理方式：固定使用 `open_async_fifo_project_gui.tcl`，由脚本解析工程路径、读取 `latest_async_fifo_wdb.txt`、打开最新 WDB。

## 问题 3：WDB 打开了，但波形窗口没有历史波形

现象：Scope/Objects 面板能看到信号，但波形窗口里没有完整时间轴数据。

原因：xsim 运行前没有执行 `log_wave -r /`，WDB 没有完整记录仿真期间的信号变化。

处理方式：仿真脚本生成临时 Tcl：

```tcl
log_wave -r /
run all
```

然后通过：

```tcl
exec xsim $snapshot -wdb $wave_db -tclbatch run_async_fifo_wave.tcl
```

保证 WDB 包含完整历史波形。

## 问题 4：GUI 右侧波形窗口为空白

现象：Vivado 已打开 WDB，Scope/Objects 能看到 `tb_async_fifo`、`dut`、`wr_clk`、`rd_clk`、`scenario_id`，但右侧 `async_fifo_debug.wcfg` 没有任何信号行。

根因：旧脚本使用了当前 Vivado 2025.2 下不稳定的 `add_wave -group ...` 写法，并且被 `catch` 静默吞掉，最终保存了空 `.wcfg`。空配置的典型标志是：

```xml
<WVObjectSize size="0" />
```

处理方式：

- 每次打开 WDB 后重新创建波形配置。
- 使用 `add_wave_divider` 加分组标题。
- 使用 `add_wave {{/tb_async_fifo/...}}` 逐个加入信号。
- 保存后校验 `.wcfg`，确认 `WVObjectSize > 0` 且关键对象存在。

P2.6 已把该经验固化为自动检查：`parse_async_fifo_wcfg_summary()` 会验证 `scenario_id`、写/读时钟、scoreboard 计数器、`full_reg`、`empty_reg` 等关键信号。

## 问题 5：旧 WDB 或固定文件名被占用

现象：重复仿真时，旧的 `async_fifo_smoke.wdb` 可能被 Vivado GUI 占用，导致生成或覆盖失败。

处理方式：

- 每次仿真生成带时间戳的 `async_fifo_smoke_*.wdb`。
- `latest_async_fifo_wdb.txt` 记录最新 WDB。
- 保留 `async_fifo_smoke.wdb` 作为兼容路径，但 GUI 优先读取最新文件。

## 问题 6：工程生成脚本中的保存/关闭时机

现象：批处理生成工程时，个别 Vivado 命令在无 GUI 或工程状态未稳定时容易报错。

处理方式：

- `create_async_fifo_project.tcl` 只负责创建或更新工程、加入 RTL/TB、设置 top、刷新 compile order。
- 关闭工程前避免多余保存动作造成干扰。
- GUI 打开与工程创建分离，分别由两个脚本负责。

## 问题 7：TclStore / xsim package 警告

现象：某些环境会提示 TclStore 路径或 `::tclapp::xilinx::xsim` 加载异常。

处理方式：

- 脚本里保留 Vivado TclStore bootstrap。
- 流程不依赖额外手动环境变量。
- 真正执行 xsim 时仍以 Vivado 自带命令链为准。

## 问题 8：VCD 分析容易误判握手事件

现象：只看 `wr_en` 或 `rd_en` 会把 FIFO full/empty 边界上的无效请求误算成成功传输。

处理方式：

- 写握手条件：`tb_async_fifo.wr_en=1,tb_async_fifo.full=0`
- 读握手条件：`tb_async_fifo.rd_en=1,tb_async_fifo.empty=0,tb_async_fifo.error_count=0`
- 统计时同时显示 `write_count`、`read_count` 和数据。

## 问题 9：异步 FIFO full/empty 的组合路径不利于观察

现象：组合 `full/empty` 在边界状态附近不够直观，也不利于 GUI 里稳定定位状态变化。

处理方式：

- 改为寄存化 `full_reg` / `empty_reg`。
- 对外 `assign full = full_reg; assign empty = empty_reg;`。
- 波形配置里加入 `dut/full_reg`、`dut/empty_reg`，直接观察状态寄存器。

## 问题 10：报告分散，不利于继续工作

现象：仿真日志、VCD 分析、WDB 路径、GUI 波形配置、参数矩阵分别散落在不同文件里，恢复上下文成本高。

处理方式：

- P2.7 新增 `reports/regression_matrix.md`，记录 `DATA_WIDTH` / `ADDR_WIDTH` 参数矩阵。
- P2.8 新增 `reports/sim_summary.md` 和 `reports/sim_summary.html`，汇总 VCD/WDB/WCFG、场景状态、VCD 统计、命令清单。
- P2.9 新增 `reports/regression_summary.md` 和 `reports/regression_summary.html`，把参数矩阵从规划表推进为真实 Vivado/xsim 回归结果。
- P2.10 新增 `reports/wave_visibility.md` 和 `reports/wave_visibility.html`，把“GUI 是否真的能看到波形”拆成工程、WDB、GUI Tcl、打开工程命令、打开 WDB 命令、WCFG 对象数和关键对象验收。
- P2.11 新增 `reports/wave_screenshot.md`、`reports/wave_screenshot.html` 和 `reports/capture_wave_screenshot.ps1`，在打开 Vivado GUI 后沉淀实际波形截图。
- P2.12 新增 `reports/index.md` 和 `reports/index.html`，把仿真摘要、回归摘要、波形可见性、截图验收和问题复盘串成统一入口。
- P3.0 新增 `reports/uvm_smoke_report.md` 和 `reports/uvm_smoke_report.html`，把最小 UVM smoke 的 scoreboard 标记、test done 标记、日志和 WDB 路径沉淀下来。
- P3.1 新增 `reports/uvm_coverage_report.md` 和 `reports/uvm_coverage_report.html`，把 UVM smoke 覆盖率开关、code coverage 数据库、WDB 和日志路径沉淀下来。
- `--check-rtl async-fifo` 会自动补齐 summary / regression matrix / wave visibility，并在已有 WCFG 时检查其有效性。

## 问题 13：接入 UVM 时先做最小 smoke，不急着加覆盖率

现象：UVM、覆盖率、GUI 波形和参数回归如果一次性全部接入，失败面会变大，很难判断是 UVM 编译、scoreboard、xsim 库、覆盖率开关还是 GUI 打开链路出了问题。

处理方式：

- P3.0 只接入 async FIFO 最小 UVM smoke：interface、sequence、driver、monitor、scoreboard、env 和 basic test。
- 验收标记先保持简单明确：`ASYNC_FIFO_UVM_SCOREBOARD_PASS` 和 `ASYNC_FIFO_UVM_TEST_DONE`。
- 报告明确写“覆盖率统计：未启用”，避免误以为已经完成 coverage closure。
- 先用 `--uvm-smoke async-fifo --no-wave-gui` 批处理跑通，再按需打开 Vivado GUI 看 `async_fifo_uvm_smoke.wdb`。
- P3.1 再单独处理覆盖率统计，避免把 UVM smoke 的编译/功能问题和覆盖率工具链问题混在一起。

## 问题 14：Vivado UVM 库 timescale 与设计文件不一致

现象：P3.0 真实 Vivado/xsim smoke 中，RTL/top 带有 `timescale`，但 Vivado 预编译 UVM 包没有显式 timescale，`xelab` 报错：UVM package 没有 timescale，但设计里至少一个 module 有 timescale。

处理方式：

- 不删除 async FIFO RTL/testbench 的 `timescale`，避免影响既有 RTL smoke 和 VCD 时间单位。
- 在 UVM smoke Tcl 的 `xelab` 命令中加入 `-timescale 1ns/1ps`，给未声明 timescale 的库/单元设置默认值。
- 回归测试检查 `run_vivado_async_fifo_uvm.tcl` 必须包含 `-timescale 1ns/1ps`，防止后续改脚本时复发。

## 问题 15：UVM monitor 采样时序必须匹配 RTL 读数据延迟

现象：P3.0 真实 Vivado/xsim smoke 能完成 elaboration 和 UVM run phase，但 scoreboard 报 `expected=0x40 actual=0x00`、后续读数整体偏移一拍。

原因：当前 async FIFO RTL 在 `rd_fire` 后用非阻塞赋值更新 `rd_data`，读数据在读握手后的下一个 `rd_clk` 采样点稳定。第一版 UVM monitor 在 `rd_en && !empty` 同拍采样 `rd_data`，拿到的是上一拍旧值。

处理方式：

- UVM monitor 对读通道加入 `read_pending`，先记录 `rd_en && !empty`，下一拍再采样 `rd_data` 并发送给 scoreboard。
- 回归测试检查 UVM package 中保留 `read_pending = vif.rd_en && !vif.empty`，防止后续又回退成同拍采样。
- 这类问题不能只看 UVM 结构是否完整，必须用真实 xsim 跑到 scoreboard 才能暴露。

## 问题 16：Vivado/xsim 覆盖率参数不能沿用通用 `-coverage all`

现象：P3.1 探测覆盖率时，使用 `xelab ... -coverage all` 会直接失败并打印帮助信息；Vivado 2025.2 的 xelab 覆盖率参数不是这个形式。

处理方式：

- 用本机最小 DUT/testbench 探针确认真实可用参数，再固化到脚本。
- 当前使用 `xelab ... -cc_type sbct -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov`，其中 `sbct` 分别对应 statement、branch、condition、toggle。
- 覆盖率数据库验收路径为 `sim/coverage/xsim.codeCov/async_fifo_uvm_cov/xsim.CCInfo`。
- P3.1 先做“覆盖率数据库生成”验收，不强行解析百分比或设阈值；后续 P3.2 再加覆盖率摘要解析和 gate。

## 问题 17：`xsim.CCInfo` 不能直接当作百分比文本报告读取

现象：P3.2 读取 `xsim.CCInfo` 时，可以搜到 `sbct`、数据库名、源文件、实例名和部分条件表达式，但它本质是 binary-ish 覆盖率数据库，不是直接可读的百分比报告。`xcrg.exe` 使用 `-help`、`--help`、`-h` 或无参数运行时也没有输出可用帮助，不能凭猜测接入百分比解析。

处理方式：

- P3.2 先做稳定的“覆盖率数据库元信息摘要”，解析 `xsim.CCInfo` 中可读 token，生成中文 `uvm_coverage_summary.md/html`。
- 覆盖率类型从已验证的 `sbct` 映射为 statement、branch、condition、toggle。
- 阈值 gate 设计成可选参数：未设置阈值时 `Gate 结果：SKIP`；设置阈值但没有可靠百分比时 FAIL；设置阈值和百分比时按数值判断 PASS/FAIL。
- 后续只有在确认 Vivado 2025.2 官方覆盖率导出命令后，再把 `--coverage-percent` 从手动输入升级为自动提取。

## 问题 20：Vivado 2025.2 覆盖率百分比导出不能用 Tcl `report_coverage`

现象：P3.12 真实运行 `python .trae/agent/agent.py --uvm-coverage async-fifo --coverage-threshold 1 --output-dir outputs` 时，code coverage 数据库和 UVM 标记都存在，但 coverage gate 仍失败。查看 `reports/uvm_coverage_percent.txt` 后发现 Tcl 内调用 `report_coverage` 返回 `invalid command name "report_coverage"`，导致当前覆盖率为 N/A。

原因：Vivado 2025.2 的覆盖率报告生成器是独立命令 `xcrg`，不是 xsim Tcl 会话里的 `report_coverage` 命令。实测可用命令为 `xcrg -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov -report_dir <reports>/uvm_coverage_xcrg -report_format html -log <reports>/xcrg_coverage.log`，其中 `-cov_db_dir` 要指向包含 `xsim.codeCov` 和 `xsim.covdb` 的父目录 `coverage`。

修复：

- `run_vivado_async_fifo_uvm_coverage.tcl` 改为通过 `auto_execok xcrg` / `xcrg.bat` 查找 Vivado 自带 `xcrg`。
- `xcrg` 输出追加到 `reports/uvm_coverage_percent.txt`，同时生成 `reports/uvm_coverage_xcrg/codeCoverageReport/`、`reports/uvm_coverage_xcrg/functionalCoverageReport/` 和 `reports/xcrg_coverage.log`。
- `extract_async_fifo_coverage_percent()` 兼容 `Line Coverage Score`、`Branch Coverage Score`、`Condition Coverage Score`、`Toggle Coverage Score`；若没有 `Total Coverage`，用四项平均值作为 gate 百分比。
- 真实验收结果：Line 60.2041、Branch 23.5294、Condition 22、Toggle 4.84，自动解析总覆盖率 27.6%，`--coverage-threshold 1` gate PASS。

经验：

- 不要把 Vivado Tcl 命令和 Vivado 独立可执行工具混用；coverage 百分比导出必须用真实工具探针确认。
- `xcrg` 的 `-cov_db_dir` 要传 coverage 父目录，不要传 `coverage/xsim.codeCov` 或 `coverage/xsim.covdb` 子目录，否则可能只打印 options、不生成报告。
- 百分比 gate 必须同时保留自动解析和手动 `--coverage-percent` 覆盖入口，方便不同 Vivado 版本或报告格式变化时继续验证。

## 问题 21：P3.13 报告入口必须把官方 xcrg 产物连起来

现象：P3.12 已经能生成 `uvm_coverage_xcrg/`、`xcrg_coverage.log` 和 `uvm_coverage_percent.txt`，但恢复项目状态时仍需要分别打开多个路径，`reports/index.html` 和 `uvm_coverage_summary.html` 没有直接呈现这些官方报告入口。

原因：原报告总览只覆盖 smoke/regression/wave/lessons，coverage summary 也只展示 gate 和 `xsim.CCInfo` 元信息，没有把 `xcrg` 的 code/functional HTML 及分项 score 汇总到一个可读入口。

修复：

- `reports/index.md/html` 新增 `uvm_coverage_summary.html`、`uvm_coverage_xcrg/codeCoverageReport/dashboard.html`、`uvm_coverage_xcrg/functionalCoverageReport/dashboard.html`、`xcrg_coverage.log` 和 `uvm_coverage_percent.txt`。
- `uvm_coverage_summary.md/html` 新增 Total、Statement/Line、Branch、Condition、Toggle 覆盖率展示，并标记官方 `xcrg` 报告路径是否 FOUND。
- 测试使用稳定路径和数值断言，避免 Windows 终端中文编码显示差异影响验收。

经验：

- coverage gate 的数值、官方 HTML、日志和解析源文本必须在同一摘要页闭环，避免下次只看到 gate PASS/FAIL 但找不到依据。
- 修改中文报告时，测试优先断言路径、数值和 ASCII 标题，中文文案只保留少量关键验收，降低编码噪音。

## 问题 18：随机 seed 参数不能传给 Vivado 外层命令

现象：P3.5 首次真实运行 `--uvm-random-regress async-fifo --uvm-seeds 11,22,33` 时，把 `-testplusarg ntb_random_seed=...` 追加到了 `vivado -mode batch ...` 外层命令，Vivado 报错：`Unknown option '-testplusarg'`。

处理方式：

- 不再把 seed 参数传给 Vivado 外层命令。
- Python runner 设置环境变量 `ASYNC_FIFO_UVM_SEED`。
- `run_vivado_async_fifo_uvm_coverage.tcl` 在调用 `xsim` 时读取该环境变量，并把 `-testplusarg ntb_random_seed=<seed>` 加到 xsim 参数列表。
- 真实 Vivado/xsim 随机回归已用 seed `11,22,33` 重新验证通过。

## 问题 19：P3.x 新增覆盖项必须兼容旧 coverage smoke

现象：接入 functional coverage 和 SVA 后，旧的 P3.1 单元测试 fake log 只有 `ASYNC_FIFO_UVM_SCOREBOARD_PASS` 和 `ASYNC_FIFO_UVM_TEST_DONE`，没有 functional coverage 标记，导致基础 `run_async_fifo_uvm_coverage()` 被误判失败。

处理方式：

- `uvm_functional_coverage.md/html` 仍然照常生成，记录标记是否 FOUND。
- 基础 coverage runner 只在出现明确 `ASYNC_FIFO_SVA_FAIL` 时失败，避免把旧日志或部分工具输出误判为功能失败。
- P3.4/P3.6 的强验收由专门的 functional coverage 报告和真实 Vivado/xsim 流程承担。

## 问题 11：报告内容正确，但不够适合人读

现象：第一版 `sim_summary.html` 只是把 Markdown 条目包成简单 HTML，信息虽然完整，但视觉层级弱，不适合快速查看仿真状态。

处理方式：

- Markdown 报告改为中文为主，便于直接阅读和归档。
- HTML 报告改为看板样式，包含顶部状态、指标卡片、场景覆盖、WCFG 验收、产物路径和常用命令。
- 测试中增加中文标题、状态标签、卡片 class 和“场景覆盖”等断言，避免后续回退成裸 HTML。

## 问题 12：终端显示乱码，不一定代表文件损坏

现象：用 PowerShell `Get-Content` 读取中文 Markdown/HTML 时，输出里可能出现“中文被错按另一种编码解释”的乱码，看起来像文件再次损坏。

复核结果：用 Python 按 UTF-8 直接读取后，`sim_summary.html`、`sim_summary.md`、`README.md`、`.trae/agent/README.md` 和本文档都能检测到预期中文，且没有替换字符，说明文件本身是 UTF-8 正常内容，问题主要来自终端输出编码/显示链路。

处理方式：

- 判断文件是否真实乱码时，不只看 PowerShell 控制台显示。
- 优先使用 Python `Path(...).read_text(encoding="utf-8")` 做内容检查。
- 回归测试加入常见 mojibake 片段检查，防止真正乱码写入仓库文档或报告；复盘文档中也不要原样保留这些片段，避免测试把示例当作真实残留。

## 有价值的经验

- Vivado GUI 波形入口必须使用 `.wdb`，VCD 只用于外部分析。
- GUI 自动化必须显式打开工程、打开 WDB、创建波形配置，不能只启动 Vivado。
- 对 GUI 脚本中的 `catch` 要保持警惕，关键产物必须做二次验收。
- `.wcfg` 是否有效不能靠“文件存在”判断，要检查 `WVObjectSize` 和关键信号。
- 仿真产物应使用时间戳命名，避免 GUI 占用旧文件。
- async FIFO 验证要覆盖 full、empty、reset recovery、mixed asynchronous traffic，不只跑 happy path。
- VCD 事件统计必须用真实 handshake 条件，不能只看 enable。
- 每个阶段都要沉淀可重复命令和报告文件，便于隔几天后快速恢复状态。
- 中文文档和报告要区分“终端显示乱码”和“文件真实乱码”，必要时用 UTF-8 读取脚本验证。
- 用户可读报告不能只保证信息齐全，也要保证中文、视觉层级和快速定位能力。
- UVM 环境应先建立最小可运行 smoke，再逐步增加覆盖率、随机约束和复杂场景；每一步都要有独立报告和验收标记。
- Vivado/xsim 接入 UVM 时要显式处理 timescale 默认值，优先在 `xelab` 层设置，避免为了 UVM 破坏既有 RTL 文件风格。
- UVM monitor 的采样点必须跟 RTL 时序语义一致；尤其是非阻塞赋值更新的输出，通常要在事件后一拍采样。
- 覆盖率参数必须用真实 Vivado/xsim 命令探针确认；不同仿真器或版本的 coverage 开关差异很大。
- 覆盖率数据库和覆盖率百分比是两层能力：先验收数据库存在和归属元信息，再接入官方百分比导出，避免把二进制数据库误读成文本报告。
- xsim plusarg 必须传给 `xsim`，不能传给 `vivado` 外层命令；需要跨 Python/Vivado Tcl 传参时，环境变量比拼接外层命令更稳。
- 新增验证强度时要兼容已有 smoke 语义：报告可以记录 MISSING，但基础 runner 应只对明确失败标记或关键验收缺失报 FAIL。

## 当前 P2.6-P3.7 状态

- P2.6：已完成 WCFG 自动验收，能检测空波形配置和缺失关键信号。
- P2.7：已完成参数回归矩阵报告，基线为 `DATA_WIDTH=8, ADDR_WIDTH=4`，规划组合包括 `16x4` 和 `8x3`。
- P2.8：已完成仿真摘要 Markdown/HTML，集中记录产物路径、场景结果、VCD 统计、WCFG 验收和常用命令。
- P2.9：已完成真实多参数回归入口，`--regress-rtl async-fifo` 会运行 `dw8_aw4`、`dw16_aw4`、`dw8_aw3` 并生成回归摘要。
- P2.10：已完成波形可见性验收报告，`--check-rtl async-fifo` 会生成 `wave_visibility.md/html`，避免只打开 GUI 但缺少波形对象的旧问题。
- P2.11：已完成 GUI 波形截图验收报告，截图本身需要在 Vivado GUI 打开后运行捕获脚本生成。
- P2.12：已完成报告总览页，`reports/index.html` 是后续恢复项目状态的第一入口。
- P3.0：已完成 async FIFO 最小 UVM smoke 生成、CLI 入口、中文报告和单独验收标记；覆盖率统计未启用，建议放到 P3.1。
- P3.1：已完成 async FIFO UVM code coverage 入口、Vivado/xsim 覆盖率脚本、中文覆盖率报告和真实覆盖率数据库验收。
- P3.2：已完成覆盖率数据库元信息解析、中文覆盖率摘要报告、可选 `--coverage-threshold` / `--coverage-percent` gate 和真实 Vivado/xsim 摘要生成验收。
- P3.3：已完成覆盖率百分比文本解析降级路径，为后续接入 Vivado 官方百分比报告预留自动 gate 入口。
- P3.4：已完成 UVM functional coverage 采样标记和中文 functional coverage 报告。
- P3.5：已完成 UVM 多 seed 随机回归入口、seed 报告和真实 Vivado/xsim seed 回归验收。
- P3.6：已完成 async FIFO SVA 断言包生成、UVM top 绑定和断言结果标记。
- P3.7：已完成 UVM smoke/coverage WDB 的 Vivado GUI 专用打开入口。
- P3.12：已完成真实 Vivado 2025.2 `xcrg` coverage 报告生成、coverage score 自动解析和 gate 验收。
- P3.13：已完成 coverage 报告总览增强，`reports/index.html` 和 `uvm_coverage_summary.html` 直接链接官方 `xcrg` code/functional HTML、日志、百分比文本，并展示 line/branch/condition/toggle 分项。

## 后续建议

- 后续可以把截图捕获升级为自动定位 Vivado 窗口或像素级波形区域自检。
- 后续可以把随机 seed 回归升级为每个 seed 独立输出目录，便于失败 seed 保留单独日志和 WDB。
