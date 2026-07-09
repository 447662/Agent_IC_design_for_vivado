# P3.x async FIFO UVM 完整收尾 TDD 证据

## 来源计划

用户要求“完成 P3.x 的所有任务”。本阶段承接 P3.0-P3.2，补齐 P3.3-P3.7：覆盖率百分比文本解析降级路径、functional coverage、随机 seed 回归、SVA 断言包、UVM WDB GUI 专用入口。

## 用户旅程

- 作为验证开发者，我希望 UVM coverage 流程能解析外部覆盖率文本报告，以便后续接入 Vivado 官方百分比导出后自动 gate。
- 作为验证开发者，我希望 async FIFO UVM 环境包含功能覆盖点和 SVA 断言，以便覆盖 full/empty/reset/mixed traffic 与基本非法操作。
- 作为回归使用者，我希望能用多个 seed 跑 UVM 随机回归并生成中文摘要，以便定位失败 seed 和日志。
- 作为波形调试者，我希望能直接打开 UVM smoke/coverage WDB，而不是误打开 RTL WDB 或 VCD。

## RED 证据

命令：

```powershell
python -m pytest tests/test_agent.py -k "coverage_percent or functional_coverage or random_regression or open_async_fifo_uvm_wave or uvm_random_regress" -v --basetemp .tmp-pytest
```

结果摘要：

```text
6 failed, 55 deselected
DigitalICAgent 没有 extract_async_fifo_coverage_percent
没有生成 async_fifo_sva.sv
DigitalICAgent 没有 write_async_fifo_uvm_functional_coverage_report
DigitalICAgent 没有 run_async_fifo_uvm_random_regression
DigitalICAgent 没有 open_async_fifo_uvm_wave_gui
CLI 没有 --uvm-random-regress / --open-uvm-wave
```

## GREEN 证据

定向测试：

```powershell
python -m pytest tests/test_agent.py -k "coverage_percent or functional_coverage or random_regression or open_async_fifo_uvm_wave or uvm_random_regress or uvm_coverage" -v --basetemp .tmp-pytest
```

结果摘要：

```text
12 passed, 49 deselected
```

完整回归：

```powershell
python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest
```

结果摘要：

```text
61 passed
```

真实 Vivado/xsim smoke：

```powershell
python .trae/agent/agent.py --uvm-smoke async-fifo --no-wave-gui --output-dir outputs
```

结果摘要：

```text
Async FIFO UVM smoke completed
UVM log: outputs\async-fifo\sim\async_fifo_uvm_smoke.log
Generated WDB: outputs\async-fifo\sim\async_fifo_uvm_smoke.wdb
UVM smoke report: outputs\async-fifo\reports\uvm_smoke_report.md
```

真实 Vivado/xsim coverage：

```powershell
python .trae/agent/agent.py --uvm-coverage async-fifo --output-dir outputs
```

结果摘要：

```text
Async FIFO UVM coverage completed
Coverage DB: outputs\async-fifo\sim\coverage\xsim.codeCov\async_fifo_uvm_cov
UVM coverage report: outputs\async-fifo\reports\uvm_coverage_report.md
UVM coverage summary: outputs\async-fifo\reports\uvm_coverage_summary.md
UVM functional coverage report: outputs\async-fifo\reports\uvm_functional_coverage.md
```

真实 Vivado/xsim 随机 seed 回归：

```powershell
python .trae/agent/agent.py --uvm-random-regress async-fifo --uvm-seeds 11,22,33 --output-dir outputs
```

结果摘要：

```text
3 个 seed 均完成 UVM coverage 流程
outputs\async-fifo\reports\uvm_random_regression.md 显示 3/3 PASS
```

## 生成产物

- SVA 断言包：`outputs/async-fifo/uvm/async_fifo_sva.sv`
- 功能覆盖率报告：`outputs/async-fifo/reports/uvm_functional_coverage.md`
- 功能覆盖率 HTML：`outputs/async-fifo/reports/uvm_functional_coverage.html`
- 随机回归报告：`outputs/async-fifo/reports/uvm_random_regression.md`
- 随机回归 HTML：`outputs/async-fifo/reports/uvm_random_regression.html`
- UVM smoke WDB：`outputs/async-fifo/sim/async_fifo_uvm_smoke.wdb`
- UVM coverage WDB：`outputs/async-fifo/sim/async_fifo_uvm_coverage.wdb`

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 能解析覆盖率文本中的 statement/branch/condition/toggle/total 百分比 | `tests/test_agent.py::test_extract_async_fifo_coverage_percent_parses_text_report` | 单元 | PASS |
| 2 | UVM 环境生成 functional covergroup 和 `async_fifo_sva.sv`，并在 Tcl 中编译 SVA | `tests/test_agent.py::test_generate_async_fifo_uvm_environment_includes_functional_coverage_and_sva` | 生成器 | PASS |
| 3 | 能从 UVM 日志生成中文 functional coverage 报告 | `tests/test_agent.py::test_write_async_fifo_uvm_functional_coverage_report` | 报告 | PASS |
| 4 | UVM 随机回归按 seed 执行并生成 seed 摘要 | `tests/test_agent.py::test_run_async_fifo_uvm_random_regression_writes_seed_report` | 集成边界 | PASS |
| 5 | UVM WDB GUI 入口直接打开 smoke/coverage WDB | `tests/test_agent.py::test_open_async_fifo_uvm_wave_gui_uses_uvm_wdb` | GUI 入口 | PASS |
| 6 | CLI 支持 `--uvm-random-regress` 和 `--open-uvm-wave` | `tests/test_agent.py::test_cli_uvm_random_regress_and_open_uvm_wave` | CLI | PASS |
| 7 | P3.x 接入不破坏既有 P0-P3.2 功能 | `python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest` | 回归 | PASS |
| 8 | 真实 Vivado/xsim smoke、coverage、随机 seed 回归均可运行 | 真实命令见 GREEN 证据 | 工具集成 | PASS |

## 已知缺口

- 覆盖率百分比自动导出仍依赖后续确认 Vivado 官方文本报告命令；P3.x 已提供 `extract_async_fifo_coverage_percent()` 和 `--coverage-percent`/`--coverage-threshold` 接口。
- 当前 random regression 复用同一输出目录和日志，报告能记录 seed 状态，但不会为每个 seed 单独保留 WDB/log 快照；如需调试失败 seed，后续建议扩展为 seed 独立输出目录。
- functional coverage 目前以关键日志标记和 covergroup 摘要为主，后续可把 coverpoint/bin 百分比接入更细粒度 HTML 看板。
