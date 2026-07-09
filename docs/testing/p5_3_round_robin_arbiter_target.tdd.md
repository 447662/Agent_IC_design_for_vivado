# P5.3 Round-Robin Arbiter TDD 验收记录

## 来源计划

P5.3 来源于 `docs/roadmap/p5_series_execution_record.md` 中的第三个 RTL 目标规划：在 `async-fifo` 和 `sync-fifo` 之后，引入一个非 FIFO 控制类模块，验证 target registry、RTL/TB 生成、Vivado/xsim 仿真、VCD 分析、WDB GUI 和报告链路是否可以扩展到新的设计族。

## 用户旅程

- 作为数字 IC 设计者，我希望 agent 能生成 4 路 round-robin arbiter RTL 工程，以便快速启动非 FIFO 控制逻辑验证。
- 作为验证工程师，我希望 testbench 覆盖单请求、多请求、轮转、复位恢复和公平性窗口，以便确认仲裁器行为正确。
- 作为使用者，我希望 `--sim-rtl`、`--analyze-rtl-vcd` 和 `--open-wave` 能和 FIFO 目标保持一致，以便用同一套命令完成仿真、分析和 GUI 波形查看。

## RED 证据

新增 P5.3 测试后，首次运行：

```powershell
python -m pytest tests/test_agent.py -k "p5_3" -q
```

结果：

```text
1 failed, 80 deselected, 5 errors
```

有效 RED 信号：

- `round_robin_arbiter.json` 不存在。
- `DigitalICAgent` 尚未实现 `round-robin-arbiter` 的生成、仿真、VCD 分析和 CLI 分发。
- 本机默认 pytest 临时目录 `C:\Users\ycy123\AppData\Local\Temp\pytest-of-ycy123` 权限异常，后续统一使用仓库内 `--basetemp .tmp-pytest`，避免环境噪声干扰测试结论。

## GREEN 证据

P5.3 定向测试：

```powershell
python -m pytest tests/test_agent.py -k "p5_3" -q --basetemp .tmp-pytest
```

结果：

```text
6 passed, 80 deselected
```

完整回归：

```powershell
python -m pytest tests/test_agent.py -q --basetemp .tmp-pytest
```

结果：

```text
86 passed in 9.21s
```

真实 Vivado 2025.2 仿真：

```powershell
python .trae/agent/agent.py --sim-rtl round-robin-arbiter --no-wave-gui --output-dir outputs
```

结果：

```text
Round-Robin Arbiter simulation completed
Generated VCD: outputs\round-robin-arbiter\sim\round_robin_arbiter_trace.vcd
Generated WDB: outputs\round-robin-arbiter\sim\round_robin_arbiter_smoke_20260709_230319.wdb
Vivado project: outputs\round-robin-arbiter\vivado_project\round_robin_arbiter_project.xpr
Simulation report: outputs\round-robin-arbiter\reports\sim_report.md
```

VCD 分析：

```powershell
python .trae/agent/agent.py --analyze-rtl-vcd round-robin-arbiter --output-dir outputs --vcd-limit 5
```

结果摘要：

```text
Round-Robin Arbiter VCD analysis
Signals: 19
Backend: vcd_analyzer
Duration: 235ns
Grant events: 6
Fairness checkpoints: 6
```

Vivado GUI 波形：

```powershell
python .trae/agent/agent.py --open-wave round-robin-arbiter --output-dir outputs
```

结果：

```text
Vivado project GUI launched: outputs\round-robin-arbiter\vivado_project\round_robin_arbiter_project.xpr
Vivado waveform database: outputs\round-robin-arbiter\sim\round_robin_arbiter_smoke_20260709_230319.wdb
```

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 | 证据 |
|---|---|---|---|---|---|
| 1 | target registry 能加载 `round-robin-arbiter` 元数据、别名和 flow | `tests/test_agent.py::test_p5_3_target_registry_lists_round_robin_arbiter_metadata` | unit | PASS | `6 passed, 80 deselected` |
| 2 | `--generate-rtl round-robin-arbiter` 生成 RTL、TB、Vivado Tcl、GUI Tcl、reports 和 README | `tests/test_agent.py::test_p5_3_generate_round_robin_arbiter_project_creates_rtl_tb_sim_reports` | unit | PASS | `6 passed, 80 deselected` |
| 3 | CLI 生成入口会输出 round-robin RTL/TB/Vivado script 路径 | `tests/test_agent.py::test_p5_3_cli_generate_rtl_round_robin_arbiter_creates_project` | integration | PASS | `6 passed, 80 deselected` |
| 4 | `run_round_robin_arbiter_vivado_sim()` 会运行仿真、创建 Vivado 工程并支持跳过 GUI | `tests/test_agent.py::test_p5_3_run_round_robin_arbiter_vivado_sim_creates_project_and_can_skip_gui` | unit | PASS | `6 passed, 80 deselected` |
| 5 | VCD 分析能报告 grant 事件和 fairness checkpoint | `tests/test_agent.py::test_p5_3_analyze_round_robin_arbiter_vcd_reports_grants_and_fairness` | unit | PASS | `6 passed, 80 deselected` |
| 6 | CLI `--analyze-rtl-vcd round-robin-arbiter` 能分发到 P5.3 分析器 | `tests/test_agent.py::test_p5_3_cli_analyze_rtl_vcd_round_robin_arbiter_invokes_analyzer` | integration | PASS | `6 passed, 80 deselected` |
| 7 | 真实 Vivado/xsim 能生成 VCD、WDB、XPR 和中文报告 | `python .trae/agent/agent.py --sim-rtl round-robin-arbiter --no-wave-gui --output-dir outputs` | system | PASS | 生成 `round_robin_arbiter_trace.vcd`、`round_robin_arbiter_smoke_20260709_230319.wdb`、`round_robin_arbiter_project.xpr` |
| 8 | Vivado GUI 能打开 P5.3 工程和 WDB 波形 | `python .trae/agent/agent.py --open-wave round-robin-arbiter --output-dir outputs` | manual/system | PASS | GUI launch 输出成功 |

## 实现范围

- 新增 `.trae/agent/targets/round_robin_arbiter.json`。
- 新增 `round_robin_arbiter.v` 生成器。
- 新增 `tb_round_robin_arbiter.v` 生成器，覆盖 `single_request`、`multiple_requests`、`rotating_grant`、`reset_recovery`、`fairness_window`。
- 新增 Vivado batch Tcl、xsim Tcl、工程创建 Tcl、GUI 打开 Tcl。
- 新增 `run_round_robin_arbiter_vivado_sim()`、`analyze_round_robin_arbiter_vcd()`、`open_round_robin_arbiter_project_gui()`。
- 更新 `generate_rtl_project()`、`run_rtl_sim()`、`open_rtl_wave()` 和 CLI `--analyze-rtl-vcd` 分发。

## 问题沉淀

- VCD_ANALYZER 的 `--condition` 必须使用 `SIG=VAL`、`SIG==VAL` 或 `SIG!=VAL`，不能只传信号名。P5.3 初版 fairness 查询使用了 `tb_round_robin_arbiter.scenario_id`，真实分析时报错，已改为 `tb_round_robin_arbiter.grant_valid=1`，并在 `--show` 中保留 `scenario_id`。
- Windows 默认 pytest 临时目录可能出现权限拒绝。仓库测试建议使用 `--basetemp .tmp-pytest`，避免本机 Temp 权限影响测试稳定性。
- Vivado GUI 查看仍必须打开 `.wdb`，不要把 `.vcd` 传给 GUI 波形入口；P5.3 继续沿用固定 WDB 和时间戳 WDB 双路径策略。

## 已知边界

- P5.3 当前是 4 路固定实例，RTL 参数保留 `REQUESTERS`，但 testbench 场景按 4 路编写。
- 本阶段未引入 UVM、coverage closure 或 SVA 包；这些适合放入后续 P5/P4 升级池。
- `outputs/` 产物用于本地验收，不提交到仓库。
