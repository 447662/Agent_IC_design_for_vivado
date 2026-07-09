# P3.0 async FIFO 最小 UVM smoke TDD 证据

## 来源计划

用户要求先进行 P3.0；本阶段目标是先完成 async FIFO 最小 UVM smoke 环境，不启用覆盖率统计。

## 用户旅程

- 作为验证开发者，我希望一条命令生成并运行 async FIFO 最小 UVM smoke，以便先确认 UVM 基础环境可编译、可仿真、可产生 WDB。
- 作为项目维护者，我希望 smoke 报告中文可读，并明确记录覆盖率未启用，以便后续恢复上下文时不会误判 P3.0 范围。
- 作为 CLI 使用者，我希望 `--uvm-smoke async-fifo --no-wave-gui` 能批处理运行，以便回归时不强制打开 Vivado GUI。

## RED 证据

命令：

```powershell
python -m pytest tests/test_agent.py -k "uvm_smoke" -v --basetemp .tmp-pytest
```

结果摘要：

```text
3 failed
DigitalICAgent 没有 write_async_fifo_uvm_smoke_project
DigitalICAgent 没有 run_async_fifo_uvm_smoke
DigitalICAgent 没有 run_uvm_smoke
CLI 没有 --uvm-smoke
```

## GREEN 证据

命令：

```powershell
python -m pytest tests/test_agent.py -k "uvm_smoke" -v --basetemp .tmp-pytest
```

结果摘要：

```text
3 passed, 45 deselected
```

完整回归：

```powershell
python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest
```

结果摘要：

```text
48 passed
```

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 生成最小 UVM 环境文件和 Vivado Tcl，包含 driver、monitor、scoreboard、env、basic test | `tests/test_agent.py::test_generate_async_fifo_uvm_smoke_creates_minimal_environment` | 单元/生成器 | PASS |
| 2 | UVM smoke runner 可跳过 GUI，能写 Markdown/HTML 报告，并检测 scoreboard/test done 标记 | `tests/test_agent.py::test_run_async_fifo_uvm_smoke_writes_report_and_can_skip_gui` | 单元/集成边界 | PASS |
| 3 | CLI 支持 `--uvm-smoke async-fifo --no-wave-gui --output-dir ...` 并调用 runner | `tests/test_agent.py::test_cli_uvm_smoke_async_fifo_invokes_runner` | CLI | PASS |
| 4 | P3.0 接入不破坏既有 P0-P2 功能 | `python -m pytest tests/test_agent.py -v --basetemp .tmp-pytest` | 回归 | PASS |

## 覆盖率和已知缺口

- 本阶段没有运行 coverage 工具；P3.0 明确不启用覆盖率统计。
- 后续 P3.1 建议单独接入 Vivado/xsim 覆盖率开关、覆盖率报告解析、覆盖率 HTML/Markdown 汇总和失败阈值。
- GUI 打开 UVM WDB 可以在 P3.1 或 P3.2 做成独立命令；P3.0 先保证批处理 smoke 和 WDB 生成。
