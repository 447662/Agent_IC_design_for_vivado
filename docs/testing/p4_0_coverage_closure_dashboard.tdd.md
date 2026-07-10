# P4.0 多 Target Coverage Closure 看板 TDD 证据

## 用户旅程

1. 作为验证负责人，我希望在一个看板中看到所有 target 的 coverage 当前值、目标值和差距，以便确定 closure 优先级。
2. 作为 target 维护者，我希望未启用 coverage 的目标显示 `SKIP/N/A`，已声明但没有运行的目标显示 `NOT_RUN`，避免缺失数据被误写成 0。
3. 作为调试工程师，我希望从看板直接进入 coverage summary、官方 xcrg code/functional HTML、原始日志、percent 文本和 WDB。
4. 作为项目维护者，我希望单个 target 的损坏报告标记为 `INVALID`，但其它 target 仍能正常展示。

## RED

检查点提交：

```text
4b103ac test: define P4.0 coverage closure dashboard contract
```

命令：

```powershell
python -m pytest tests/test_agent.py -q -k "p4_0" --basetemp .tmp-agent-output/pytest-p4-0-red
```

结果：

```text
7 failed, 141 deselected
```

失败点：

- 尚无 `.trae/agent/coverage_closure.py`。
- CLI 尚无 `--coverage-closure` 和 `--coverage-target`。
- 尚无多 target 状态、差距、链接和错误隔离逻辑。
- 新模块尚未进入 Mypy 范围。

## GREEN

检查点提交：

```text
bb6fc08 feat: add P4.0 coverage closure dashboard
```

命令：

```powershell
python -m pytest tests/test_agent.py -q -k "p4_0" --basetemp .tmp-agent-output/pytest-p4-0-green-2
python -m ruff check .trae/agent tests/test_agent.py
python -m mypy
```

结果：

```text
7 passed, 141 deselected
All checks passed!
Success: no issues found in 17 source files
```

## 保证矩阵

| # | 保证项 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | xcrg Line/Branch/Condition/Toggle 与现有 gate 阈值可稳定解析 | `test_p4_0_parses_xcrg_scores_and_existing_gate_threshold` | 单元 | PASS |
| 2 | 多 target 看板正确聚合真实 gap、SKIP/N/A、链接和空 `recommended_scenarios` | `test_p4_0_coverage_dashboard_aggregates_gaps_and_skipped_targets` | 集成 | PASS |
| 3 | 已启用但无数据的 target 显示 `NOT_RUN`，当前值和 gap 保持 `-` | `test_p4_0_coverage_dashboard_marks_enabled_target_without_data_not_run` | 边界 | PASS |
| 4 | 单个损坏 score 报告标记 `INVALID`，其它 target 保持可用 | `test_p4_0_coverage_dashboard_isolates_invalid_target_report` | 错误路径 | PASS |
| 5 | CLI 接受 `--coverage-closure --coverage-target 85` | `test_p4_0_cli_accepts_coverage_closure_target` | 单元 | PASS |
| 6 | 空输出目录仍能生成 WARN 看板，async-fifo 为 `NOT_RUN`，其它目标为 `SKIP` | `test_p4_0_cli_generates_empty_coverage_dashboard` | CLI 集成 | PASS |
| 7 | 新模块纳入 Mypy | `test_p4_0_coverage_closure_module_is_in_mypy_scope` | 配置 | PASS |

## 真实产物验收

命令：

```powershell
python .trae/agent/agent.py --coverage-closure --coverage-target 80 --output-dir outputs
```

产物：

```text
outputs/coverage-closure/index.md
outputs/coverage-closure/index.html
```

真实结果：

| Target | 状态 | Current Total | Target | Gap |
|---|---|---:|---:|---:|
| async-fifo | GAP | 27.6% | 80.0% | 52.4% |
| round-robin-arbiter | SKIP | - | 80.0% | - |
| sync-fifo | SKIP | - | 80.0% | - |

async-fifo 分项：

| Metric | Current | Target | Gap |
|---|---:|---:|---:|
| Statement/Line | 60.2% | 80.0% | 19.8% |
| Branch | 23.5% | 80.0% | 56.5% |
| Condition | 22.0% | 80.0% | 58.0% |
| Toggle | 4.8% | 80.0% | 75.2% |
| Functional | MISSING | 80.0% | - |

## 覆盖率

P4.0 定向测试覆盖：

```text
.trae/agent/coverage_closure.py  91.0%
```

全量命令：

```powershell
$env:PYTHONPATH = (Resolve-Path ".tmp-p5-cov-deps").Path
python -X utf8 -m pytest tests --cov=.trae/agent --cov-report=term-missing --cov-fail-under=68 --basetemp .tmp-agent-output/pytest-p4-0-full-cov
```

结果：

```text
155 passed in 17.60s
TOTAL 3076 statements, 75.87% coverage
Required test coverage of 68% reached
```

## 已知后续

- P4.0 只定位低覆盖类别和 gap，不解析具体源文件、实例或未命中 bin；该能力属于 P4.1。
- `recommended_scenarios` 已作为通用字段预留为空列表，P4.2 将使用 P4.1 结果映射 target `scenario_catalog`。
- Functional coverage 当前缺少独立数值，因此明确显示 `MISSING`，不从 code coverage 推测或填 0。
