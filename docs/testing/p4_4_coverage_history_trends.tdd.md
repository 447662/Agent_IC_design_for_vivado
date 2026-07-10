# P4.4 Coverage 历史与趋势 TDD 证据

## 来源

- 路线图：`docs/roadmap/p4_future_upgrade_roadmap.md`
- 阶段：P4.4
- 目标：记录每次真实 coverage 的时间、seed、Vivado 版本、分项覆盖率和 gate 结果，并生成趋势报告。

## 用户旅程

- 作为验证负责人，我希望每次真实 coverage 自动追加一条不可覆盖的历史记录，以便追踪回归变化。
- 作为报告使用者，我希望看到最新值与上一次运行的 delta，以便快速识别覆盖率提升或回退。
- 作为多 target 维护者，我希望 history schema 显式包含 target、flow、toolchain 和 seed，以便后续聚合过滤。
- 作为故障排查者，我希望损坏 JSONL 能报告准确行号，而不是静默忽略历史错误。

## 产物

```text
reports/coverage_history.jsonl
reports/coverage_trend.md
reports/coverage_trend.html
```

History schema：

```text
schema_version
recorded_at
target_name
flow_name
toolchain
seed_set
coverage_metrics
coverage_gates
status
sources
```

## RED

测试检查点：

```text
7bc6798c test: define P4.4 coverage history trends
```

命令：

```powershell
python -m pytest tests/test_agent.py -q -k "p4_4" `
  --basetemp .tmp-p4-4-red-20260710-b
```

结果：

```text
4 failed, 161 deselected
```

预期失败原因：

- `.trae/agent/coverage_history.py` 尚不存在。
- runner 尚未写入 `coverage_history.jsonl`。
- `coverage_trend.md/html` 和报告索引链接尚未生成。
- 新模块尚未进入 Mypy 文件清单。

## GREEN

实现检查点：

```text
ad5571a3 feat: add P4.4 coverage history trends
```

主要实现：

- `append_coverage_history()` 在追加前校验旧 JSONL，再写入单行 UTF-8 JSON。
- `load_coverage_history()` 对 JSON 错误、非对象记录和 schema 不匹配报告准确行号。
- `calculate_metric_deltas()` 比较最新两次运行，按 Total/Statement/Branch/Condition/Toggle/Functional 输出 delta。
- `write_coverage_trend_report()` 生成 Markdown/HTML 最新值、delta 卡片和完整历史表。
- runner 在每个真实 coverage 结束路径只追加一次记录，并在追加后刷新报告索引。
- 工具链记录 Vivado 命令、Vivado 版本和 xsim；seed 以 `seed_set` 数组保存。

定向验证：

```powershell
python -m pytest tests/test_agent.py -q -k "p4_4" `
  --basetemp .tmp-p4-4-green-20260710-b
python -m ruff check .trae/agent tests/test_agent.py
python -m mypy --config-file pyproject.toml
```

结果：

```text
4 passed, 161 deselected in 0.47s
All checks passed!
Success: no issues found in 21 source files
```

全量验证：

```powershell
python -m pytest -q --basetemp .tmp-p4-4-full-20260710-a
```

结果：

```text
172 passed in 15.92s
```

## 测试规格

| # | 保证项 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 两次记录追加为两行 JSONL，不覆盖首条记录 | `test_p4_4_appends_coverage_history_and_renders_trend_deltas` | 单元/持久化 | PASS |
| 2 | schema 包含 target、flow、toolchain、seed、metrics、gates 和 status | `test_p4_4_appends_coverage_history_and_renders_trend_deltas` | schema | PASS |
| 3 | Markdown/HTML 展示正负 delta 和 target 标记 | `test_p4_4_appends_coverage_history_and_renders_trend_deltas` | 报告 | PASS |
| 4 | 损坏 JSONL 报告准确行号 | `test_p4_4_history_reports_invalid_jsonl_line` | 错误路径 | PASS |
| 5 | runner 同一项目追加 PASS/FAIL、seed 和 Vivado 版本 | `test_p4_4_runner_appends_pass_and_fail_history_and_refreshes_index` | 集成 | PASS |
| 6 | gate 失败后仍生成 history、trend 和报告索引入口 | `test_p4_4_runner_appends_pass_and_fail_history_and_refreshes_index` | 集成 | PASS |
| 7 | 新 history 模块进入项目 Mypy 范围 | `test_p4_4_coverage_history_module_is_in_mypy_scope` | 配置 | PASS |

## 真实产物验收

命令执行两次：

```powershell
python .trae/agent/agent.py `
  --uvm-coverage async-fifo `
  --coverage-threshold 25 `
  --coverage-line-threshold 60 `
  --coverage-branch-threshold 20 `
  --coverage-condition-threshold 20 `
  --coverage-toggle-threshold 4 `
  --output-dir outputs
```

结果：

```text
Async FIFO UVM coverage completed
history_count=2
```

最新两条记录：

| Recorded At | Status | Vivado | Total | Statement | Branch | Condition | Toggle | Functional |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2026-07-10T13:27:47.429Z | PASS | 2025.2 | 27.64% | 60.2041% | 23.5294% | 22.0% | 4.84% | N/A |
| 2026-07-10T13:29:01.499Z | PASS | 2025.2 | 27.64% | 60.2041% | 23.5294% | 22.0% | 4.84% | N/A |

最新 delta：

```text
Total          +0.0%
Statement/Line +0.0%
Branch         +0.0%
Condition      +0.0%
Toggle         +0.0%
Functional     N/A
```

报告索引状态：

```text
Coverage Trend        READY
Coverage History JSONL READY
```

真实产物位于：

```text
outputs/async-fifo/reports/coverage_history.jsonl
outputs/async-fifo/reports/coverage_trend.md
outputs/async-fifo/reports/coverage_trend.html
```

`outputs/` 为本地真实 Vivado 产物，不提交到仓库。

## 覆盖率

命令：

```powershell
$env:PYTHONPATH = (Resolve-Path ".tmp-p5-cov-deps").Path
$env:COVERAGE_FILE = ".tmp-p4-4-full-20260710-a/.coverage-p4-4"
python -m coverage run -m pytest tests/test_agent.py -q -k "p4_4" `
  --basetemp .tmp-p4-4-coverage-tests-20260710-a
python -m coverage report .trae/agent/coverage_history.py
```

结果：

```text
4 passed, 161 deselected
.trae/agent/coverage_history.py  90.3%
```

## 已知后续

- `coverage_history.jsonl` 当前保持 append-only，不做轮转；长期回归的保留和压缩策略仍属于技术债。
- 当前趋势报告展示相邻两次运行 delta；跨 target 聚合过滤可在统一 dashboard 阶段继续增强。
- 下一步 P4.5 将归档失败 seed 的 log、WDB、coverage DB、Tcl、目标配置和可复现命令。
