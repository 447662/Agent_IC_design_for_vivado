# P3.1 async FIFO UVM 覆盖率 TDD 证据

## 来源计划

用户要求继续 P3.1；本阶段目标是在 P3.0 最小 UVM smoke 基础上接入 Vivado/xsim code coverage，并生成中文覆盖率报告。

## 用户旅程

- 作为验证开发者，我希望一条命令运行 async FIFO UVM smoke 并启用 code coverage，以便确认覆盖率数据库能由真实 Vivado/xsim 生成。
- 作为项目维护者，我希望覆盖率报告中文可读，并明确记录 WDB、日志和 coverage DB 路径，以便恢复上下文时可以直接定位产物。
- 作为 CLI 使用者，我希望 `--uvm-coverage async-fifo` 独立于 `--uvm-smoke`，以便批处理覆盖率验证不强制打开 GUI。

## RED 证据

命令：

```powershell
python -m pytest tests/test_agent.py -k "uvm_coverage" -v --basetemp .tmp-pytest
```

结果摘要：

```text
3 failed
DigitalICAgent 没有 write_async_fifo_uvm_coverage_project
DigitalICAgent 没有 run_async_fifo_uvm_coverage
DigitalICAgent 没有 run_uvm_coverage
CLI 没有 --uvm-coverage
```

## GREEN 证据

定向测试：

```powershell
python -m pytest tests/test_agent.py -k "uvm_coverage" -v --basetemp .tmp-pytest
```

结果摘要：

```text
3 passed, 48 deselected
```

完整回归：

```powershell
python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest
```

结果摘要：

```text
51 passed
```

真实 Vivado/xsim 覆盖率：

```powershell
python .trae/agent/agent.py --uvm-coverage async-fifo --output-dir outputs
```

结果摘要：

```text
Async FIFO UVM coverage completed
Coverage DB: outputs\async-fifo\sim\coverage\xsim.codeCov\async_fifo_uvm_cov
UVM coverage report: outputs\async-fifo\reports\uvm_coverage_report.md
```

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 覆盖率 Tcl 使用 Vivado 2025.2 可用参数 `-cc_type sbct -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov` | `tests/test_agent.py::test_generate_async_fifo_uvm_coverage_script_enables_xsim_code_coverage` | 单元/生成器 | PASS |
| 2 | 覆盖率 runner 可写 Markdown/HTML 报告，并验收 scoreboard/test done/code coverage DB | `tests/test_agent.py::test_run_async_fifo_uvm_coverage_writes_report` | 单元/集成边界 | PASS |
| 3 | CLI 支持 `--uvm-coverage async-fifo --output-dir ...` 并调用 runner | `tests/test_agent.py::test_cli_uvm_coverage_async_fifo_invokes_runner` | CLI | PASS |
| 4 | P3.1 接入不破坏既有 P0-P3.0 功能 | `python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest` | 回归 | PASS |
| 5 | 真实 Vivado/xsim 生成 code coverage 数据库 | `python .trae/agent/agent.py --uvm-coverage async-fifo --output-dir outputs` | 工具集成 | PASS |

## 覆盖率和已知缺口

- P3.1 已生成 code coverage 数据库：`outputs/async-fifo/sim/coverage/xsim.codeCov/async_fifo_uvm_cov/xsim.CCInfo`。
- P3.1 只验收覆盖率数据库存在和 UVM smoke 通过，不解析覆盖率百分比。
- 后续 P3.2 建议解析覆盖率摘要、生成更美观的 coverage HTML 看板，并加入最低覆盖率阈值 gate。
