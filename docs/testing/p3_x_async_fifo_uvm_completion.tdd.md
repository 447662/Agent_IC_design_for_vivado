# P3.x async FIFO UVM 完整收尾 TDD 证据

## 来源计划

用户要求“完成 P3.x 的所有任务”。本阶段承接 P3.0-P3.2，补齐 P3.3-P3.13：覆盖率百分比文本解析降级路径、functional coverage、随机 seed 回归、SVA 断言包、UVM WDB GUI 专用入口、seed 独立输出目录、UVM GUI 波形截图验收、覆盖率 gate 诊断增强、Vivado 覆盖率百分比自动导出、真实 Vivado 2025.2 coverage 导出验收，以及覆盖率报告总览增强。

## 用户旅程

- 作为验证开发者，我希望 UVM coverage 流程能解析外部覆盖率文本报告，以便后续接入 Vivado 官方百分比导出后自动 gate。
- 作为验证开发者，我希望 async FIFO UVM 环境包含功能覆盖点和 SVA 断言，以便覆盖 full/empty/reset/mixed traffic 与基本非法操作。
- 作为回归使用者，我希望能用多个 seed 跑 UVM 随机回归并生成中文摘要，以便定位失败 seed 和日志。
- 作为波形调试者，我希望能直接打开 UVM smoke/coverage WDB，而不是误打开 RTL WDB 或 VCD。
- 作为验证负责人，我希望 coverage gate 失败时能直接看到阈值、当前覆盖率和差距，以便判断是覆盖率不足还是百分比数据缺失。
- 作为验证负责人，我希望 Vivado coverage 流程能自动生成百分比文本报告并触发 gate，以便减少手动 `--coverage-percent` 输入。
- 作为验证负责人，我希望真实 Vivado 2025.2 coverage 导出命令被验证并沉淀，以便避免继续使用不可用的 Tcl `report_coverage` 假设。

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
| 9 | UVM 随机回归为每个 seed 保留独立工程/log/WDB 路径 | `tests/test_agent.py::test_run_async_fifo_uvm_random_regression_writes_seed_report` | 回归产物隔离 | PASS |
| 10 | UVM GUI 波形截图验收报告和捕获脚本可生成 | `tests/test_agent.py::test_async_fifo_uvm_wave_screenshot_report_embeds_png_and_capture_script` | GUI 验收报告 | PASS |
| 11 | 覆盖率 gate 诊断输出当前覆盖率、阈值、差距和缺失百分比原因 | `tests/test_agent.py::test_write_async_fifo_uvm_coverage_summary_report_gates_threshold` / `tests/test_agent.py::test_write_async_fifo_uvm_coverage_summary_report_requires_percent_when_threshold_set` | 报告 | PASS |
| 12 | Vivado coverage Tcl 自动尝试导出 `uvm_coverage_percent.txt`，runner 自动解析 `Total Coverage` 并驱动 gate | `tests/test_agent.py::test_generate_async_fifo_uvm_coverage_script_enables_xsim_code_coverage` / `tests/test_agent.py::test_run_async_fifo_uvm_coverage_uses_auto_percent_report` | 报告/集成边界 | PASS |
| 13 | Vivado 2025.2 使用 `xcrg` 生成真实 coverage HTML 和 score 文本，runner 自动解析并驱动 gate | `tests/test_agent.py::test_extract_async_fifo_coverage_percent_parses_xcrg_scores` / `python .trae/agent/agent.py --uvm-coverage async-fifo --coverage-threshold 1 --output-dir outputs` | 真实工具集成 | PASS |
| 14 | P3.13 coverage summary 和 reports index 直接链接 `xcrg` 官方 code/functional HTML，并展示 line/branch/condition/toggle 分项覆盖率 | `tests/test_agent.py::test_async_fifo_reports_index_links_core_reports_and_lessons` / `tests/test_agent.py::test_write_async_fifo_uvm_coverage_summary_report_gates_threshold` | 报告 | PASS |

## 已知缺口

- 覆盖率百分比自动导出已接入 `uvm_coverage_percent.txt` 自动解析；P3.12 已确认 Vivado 2025.2 应使用 `xcrg`，而不是 Tcl `report_coverage`。真实输出会生成 `uvm_coverage_xcrg/` HTML 报告、`xcrg_coverage.log` 和 coverage score 文本，仍保留 `xsim.CCInfo` 元信息摘要和手动 `--coverage-percent` 覆盖入口。
- random regression 已改为 seed 独立输出目录，后续真实长回归可在此基础上增加“保留最近 N 次”和失败 seed 自动归档。
- functional coverage 目前以关键日志标记和 covergroup 摘要为主，后续可把 coverpoint/bin 百分比接入更细粒度 HTML 看板。
