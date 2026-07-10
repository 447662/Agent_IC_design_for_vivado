# P4.3 分项 Coverage Gate TDD 证据

## 来源

- 路线图：`docs/roadmap/p4_future_upgrade_roadmap.md`
- 阶段：P4.3
- 目标：从单一 Total gate 升级为 Total、Statement/Line、Branch、Condition、Toggle、Functional 独立 gate。

## 用户旅程

- 作为验证负责人，我希望每个 coverage 分项可以设置独立阈值，以便避免 Total 达标掩盖 Branch、Toggle 等薄弱项。
- 作为报告使用者，我希望缺失分项显示 `MISSING` 和“数据源缺失”，以便区分数据不可用与真实低覆盖。
- 作为 CLI 使用者，我希望分项阈值可以贯穿通用 target flow 和 async-fifo runner，以便在自动化回归中直接作为退出条件。
- 作为维护者，我希望 gate 计算与目标专用报告解耦，并进入 Ruff、Mypy 和覆盖率检查范围。

## 交付接口

```powershell
python .trae/agent/agent.py `
  --uvm-coverage async-fifo `
  --coverage-threshold 25 `
  --coverage-line-threshold 60 `
  --coverage-branch-threshold 20 `
  --coverage-condition-threshold 20 `
  --coverage-toggle-threshold 4 `
  --coverage-functional-threshold 80 `
  --output-dir outputs
```

分项参数：

- `--coverage-line-threshold`
- `--coverage-branch-threshold`
- `--coverage-condition-threshold`
- `--coverage-toggle-threshold`
- `--coverage-functional-threshold`

## RED

初始测试检查点：

```text
4349fdc test: define P4.3 component coverage gates
```

命令：

```powershell
python -m pytest tests/test_agent.py -q `
  -k "component_thresholds or missing_component_data or component_gate_not_met or forwards_component_thresholds or cli_uvm_coverage_async_fifo_invokes_runner or cli_uvm_coverage_async_fifo_keeps_threshold_optional" `
  --basetemp .tmp-p4-3-red-20260710-a
```

结果：

```text
6 failed, 154 deselected
```

预期失败原因：

- `write_async_fifo_uvm_coverage_summary_report()` 尚不接受 `coverage_thresholds`。
- `run_async_fifo_uvm_coverage()` 尚不接受分项阈值。
- CLI 尚不识别五个分项参数。
- 旧 CLI 调用没有传递空的分项阈值字典。

Functional/Total 兼容性 RED：

```text
test_extract_async_fifo_coverage_percent_parses_xcrg_scores
Expected Total: 27.64
Actual Total:   39.71
```

该失败证明 Functional 新指标被错误计入缺省 Total 平均值；修复后 Total 只平均四个 code coverage 指标。

Mypy 范围 RED 检查点：

```text
62b15ad5 test: require P4.3 gates in mypy scope
```

失败原因：

```text
assert '".trae/agent/coverage_gates.py"' in pyproject
```

## GREEN

实现检查点：

```text
86eeda8 feat: add P4.3 component coverage gates
86c0175 chore: include P4.3 gates in mypy checks
```

主要实现：

- 新增 `.trae/agent/coverage_gates.py`，以目标无关方式计算六个 coverage gate。
- 每个 gate 返回 `current`、`threshold`、`gap`、`result`、`diagnostic`。
- 分项状态支持 `PASS/FAIL/MISSING/SKIP`。
- `extract_async_fifo_coverage_percent()` 新增 Functional 解析，同时保持 Total 仅由四项 code coverage 计算。
- Markdown 摘要新增 `P4.3 分项 Coverage Gate` 表格。
- HTML 摘要新增 `P4.3 Component Coverage Gates` 状态卡片。
- CLI、通用 flow、async-fifo runner 和失败报告路径均传递 `coverage_thresholds`。
- 分项 gate 失败或缺失时 runner 返回失败，并继续刷新报告总览。

定向回归：

```powershell
python -m pytest tests/test_agent.py -q `
  -k "component_thresholds or missing_component_data or component_gate_not_met or forwards_component_thresholds or cli_uvm_coverage_async_fifo_invokes_runner or cli_uvm_coverage_async_fifo_keeps_threshold_optional or extract_async_fifo_coverage_percent_parses_xcrg_scores or p4_3_coverage_gates_module_is_in_mypy_scope" `
  --basetemp .tmp-p4-3-final-targeted-20260710-a
```

结果：

```text
8 passed, 153 deselected in 0.55s
```

全量回归：

```powershell
python -m pytest -q --basetemp .tmp-p4-3-final-full-20260710-a
```

结果：

```text
168 passed in 14.05s
```

静态检查：

```powershell
python -m ruff check .trae/agent tests/test_agent.py
python -m mypy --config-file pyproject.toml
```

结果：

```text
All checks passed!
Success: no issues found in 20 source files
```

## 测试规格

| # | 保证项 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | Total 与五个分项可以独立设置阈值 | `test_write_async_fifo_uvm_coverage_summary_report_gates_component_thresholds` | 单元/报告 | PASS |
| 2 | 单个分项低于阈值时只标记该项 FAIL，并使整体 gate 失败 | `test_write_async_fifo_uvm_coverage_summary_report_gates_component_thresholds` | 单元 | PASS |
| 3 | 缺失 Functional 数值时输出 MISSING 和“数据源缺失”，不写 0.0% | `test_write_async_fifo_uvm_coverage_summary_report_marks_missing_component_data` | 边界 | PASS |
| 4 | runner 因 Branch gate 失败返回失败，并保留 summary/index | `test_run_async_fifo_uvm_coverage_fails_when_component_gate_not_met` | 集成 | PASS |
| 5 | 五个 CLI 参数映射为稳定的 metric ID 字典 | `test_cli_uvm_coverage_async_fifo_forwards_component_thresholds` | CLI | PASS |
| 6 | 未配置分项阈值时保持空字典和旧 Total gate 行为 | `test_cli_uvm_coverage_async_fifo_invokes_runner`、`test_cli_uvm_coverage_async_fifo_keeps_threshold_optional` | 兼容 | PASS |
| 7 | Functional 可解析，但不进入缺省 Total 平均值 | `test_extract_async_fifo_coverage_percent_parses_xcrg_scores` | 解析/兼容 | PASS |
| 8 | 新 gate 模块进入项目 Mypy 范围 | `test_p4_3_coverage_gates_module_is_in_mypy_scope` | 配置 | PASS |

## 真实产物验收

数据源：

```text
outputs/async-fifo/reports/uvm_coverage_percent.txt
```

解析结果：

| Metric | Current |
|---|---:|
| Total | 27.64% |
| Statement/Line | 60.2041% |
| Branch | 23.5294% |
| Condition | 22.0% |
| Toggle | 4.84% |
| Functional | N/A |

配置 Functional `80%` 阈值时：

```text
Total PASS
Statement/Line PASS
Branch PASS
Condition PASS
Toggle PASS
Functional MISSING
Overall passed = false
```

最终真实报告使用 Total `25%`、Statement `60%`、Branch `20%`、Condition `20%`、Toggle `4%`：

```text
Total PASS
Statement/Line PASS
Branch PASS
Condition PASS
Toggle PASS
Functional SKIP
Overall passed = true
```

真实报告已刷新：

```text
outputs/async-fifo/reports/uvm_coverage_summary.md
outputs/async-fifo/reports/uvm_coverage_summary.html
```

`outputs/` 为本地真实工具产物，不提交到仓库。

## 覆盖率

命令：

```powershell
$env:PYTHONPATH = (Resolve-Path ".tmp-p5-cov-deps").Path
$env:COVERAGE_FILE = ".tmp-p4-3-full-20260710-a/.coverage-p4-3"
python -m coverage run -m pytest tests/test_agent.py -q `
  -k "uvm_coverage_summary_report or run_async_fifo_uvm_coverage or cli_uvm_coverage or extract_async_fifo_coverage_percent" `
  --basetemp .tmp-p4-3-coverage-tests-20260710-a
python -m coverage report `
  .trae/agent/coverage_gates.py `
  .trae/agent/agent_cli.py `
  .trae/agent/target_flows.py
```

结果：

```text
14 passed, 146 deselected
.trae/agent/coverage_gates.py  93.2%
Selected module total          80.4%
```

## 已知后续

- Vivado 2025.2 当前 `uvm_coverage_percent.txt` 会生成 Functional Coverage Report 路径，但没有直接输出 `Functional Coverage Score`；配置 Functional 阈值时会正确显示 `MISSING`。
- 默认阈值 profile（`smoke/nightly/release`）仍属于后续配置增强，本阶段只交付稳定的目标无关 gate 核心和 CLI 参数。
- 下一步 P4.4 将记录每次 coverage 的时间、seed、工具链、分项数值和 gate 结果，并生成历史趋势报告。
