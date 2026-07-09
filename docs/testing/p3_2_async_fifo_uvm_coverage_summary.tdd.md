# P3.2 async FIFO UVM 覆盖率摘要与 gate TDD 证据

## 来源计划

用户要求继续下一步；本阶段承接 P3.1 的 Vivado/xsim code coverage 数据库生成能力，目标是从 `xsim.CCInfo` 中解析可读元信息，生成中文覆盖率摘要报告，并加入可选覆盖率阈值 gate。

## 用户旅程

- 作为验证开发者，我希望覆盖率运行结束后自动生成中文摘要，以便快速确认 UVM smoke、coverage DB 和核心元信息是否齐全。
- 作为项目维护者，我希望报告中记录源文件、实例和覆盖项片段，以便恢复上下文时能判断覆盖率数据库确实来自当前 async FIFO/UVM 设计。
- 作为 CLI 使用者，我希望能通过可选参数设置覆盖率阈值 gate，以便在拿到百分比数据后把覆盖率纳入自动验收。

## RED 证据

命令：

```powershell
python -m pytest tests/test_agent.py -k "coverage_summary or uvm_coverage" -v --basetemp .tmp-pytest
```

结果摘要：

```text
4 failed, 3 passed, 48 deselected
DigitalICAgent 没有 parse_async_fifo_coverage_summary
DigitalICAgent 没有 write_async_fifo_uvm_coverage_summary_report
run_async_fifo_uvm_coverage 不支持 coverage_threshold
CLI 不识别 --coverage-threshold / --coverage-percent
```

## GREEN 证据

定向测试：

```powershell
python -m pytest tests/test_agent.py -k "coverage_summary or uvm_coverage" -v --basetemp .tmp-pytest
```

结果摘要：

```text
7 passed, 48 deselected
```

完整回归：

```powershell
python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest
```

结果摘要：

```text
55 passed
```

真实 Vivado/xsim 覆盖率摘要：

```powershell
python .trae/agent/agent.py --uvm-coverage async-fifo --output-dir outputs
```

结果摘要：

```text
Async FIFO UVM coverage completed
UVM log: outputs\async-fifo\sim\async_fifo_uvm_coverage.log
Generated WDB: outputs\async-fifo\sim\async_fifo_uvm_coverage.wdb
Coverage DB: outputs\async-fifo\sim\coverage\xsim.codeCov\async_fifo_uvm_cov
UVM coverage report: outputs\async-fifo\reports\uvm_coverage_report.md
UVM coverage summary: outputs\async-fifo\reports\uvm_coverage_summary.md
```

## 生成产物

- Markdown 摘要：`outputs/async-fifo/reports/uvm_coverage_summary.md`
- HTML 摘要：`outputs/async-fifo/reports/uvm_coverage_summary.html`
- 覆盖率数据库：`outputs/async-fifo/sim/coverage/xsim.codeCov/async_fifo_uvm_cov/xsim.CCInfo`

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 能从 binary-ish `xsim.CCInfo` 中解析 `sbct`、数据库名、源文件、实例和覆盖项片段 | `tests/test_agent.py::test_parse_async_fifo_coverage_summary_extracts_xsim_metadata` | 单元 | PASS |
| 2 | 能生成中文 `uvm_coverage_summary.md/html`，并在低于阈值时标记 FAIL | `tests/test_agent.py::test_write_async_fifo_uvm_coverage_summary_report_gates_threshold` | 单元/报告 | PASS |
| 3 | 覆盖率 runner 在 threshold 未满足时返回失败并保留摘要报告 | `tests/test_agent.py::test_run_async_fifo_uvm_coverage_fails_when_threshold_not_met` | 集成边界 | PASS |
| 4 | CLI 支持 `--coverage-threshold` 和 `--coverage-percent` 并传递给 runner | `tests/test_agent.py::test_cli_uvm_coverage_async_fifo_invokes_runner` | CLI | PASS |
| 5 | 不设置阈值时保持 P3.1 默认行为，coverage gate 为 SKIP | `tests/test_agent.py::test_cli_uvm_coverage_async_fifo_keeps_threshold_optional` | CLI | PASS |
| 6 | P3.2 接入不破坏既有 P0-P3.1 功能 | `python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest` | 回归 | PASS |
| 7 | 真实 Vivado/xsim 能生成 P3.2 覆盖率摘要 | `python .trae/agent/agent.py --uvm-coverage async-fifo --output-dir outputs` | 工具集成 | PASS |

## 覆盖率和已知缺口

- P3.2 当前解析的是 `xsim.CCInfo` 中可读字符串元信息，不把二进制数据库强行解释成官方百分比。
- `xcrg.exe` 在本机用 `-help`、`--help`、`-h` 和无参数运行都没有输出可用帮助，暂未接入官方百分比导出。
- `--coverage-threshold` 需要和 `--coverage-percent` 搭配使用；如果只设置阈值但没有百分比，gate 会 FAIL，避免误把未知覆盖率当 PASS。
- 后续可以继续查 Vivado 2025.2 覆盖率报告导出工具，拿到可靠百分比后再把 `coverage_percent` 从手动输入升级为自动解析。
