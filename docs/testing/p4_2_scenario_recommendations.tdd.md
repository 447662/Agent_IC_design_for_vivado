# P4.2 Coverage 场景补齐建议 TDD 证据

## 来源与用户旅程

本阶段依据 `docs/roadmap/p4_future_upgrade_roadmap.md` 的 P4.2 定义实施，未使用外部计划文件。

1. 作为验证负责人，我希望低覆盖项能映射到可执行的场景 ID，以便直接安排补测。
2. 作为 target 维护者，我希望匹配规则位于 `scenario_catalog`，避免通用代码写死 async FIFO 语义。
3. 作为评审者，我希望每条建议包含优先级、命中项、指标和原因，以便审计推荐依据。
4. 作为多 target 维护者，我希望 `SKIP/N/A` 场景不会被误报为可执行建议，无低覆盖项时保持空列表。

## 契约

`recommended_scenarios` 保持场景 ID 列表：

```json
[
  "full_boundary",
  "empty_boundary"
]
```

详细建议写入 `scenario_recommendations`：

```text
scenario_id
scenario_type
purpose
priority
evidence_count
matched_items
matched_metrics
source_reports
reason
```

场景可选匹配规则：

```text
coverage_match.tokens
coverage_match.source_patterns
coverage_match.metrics
coverage_match.fallback
coverage_match.priority
```

## RED

检查点提交：

```text
cefaefc test: define P4.2 coverage scenario recommendations
```

命令：

```powershell
python -m pytest tests/test_agent.py -k "p4_2" -q --basetemp .tmp-p4-2-red-20260710-a
```

结果：

```text
4 failed, 152 deselected
```

失败点：

- 尚无 `.trae/agent/coverage_recommendations.py`。
- coverage closure 的 `recommended_scenarios` 仍为空。
- async-fifo 场景目录尚无 `coverage_match` 和 `clock_ratio_sweep`。
- 新推荐器尚未进入 Mypy 范围。

## GREEN

实现检查点：

```text
821404b feat: add P4.2 coverage scenario recommendations
```

定向验证：

```powershell
python -m pytest tests/test_agent.py -k "p4_0 or p4_1 or p4_2" -q --basetemp .tmp-p4-2-regression-20260710-a
python -m ruff check .trae/agent/coverage_recommendations.py .trae/agent/coverage_closure.py tests/test_agent.py
python -m mypy --config-file pyproject.toml
```

结果：

```text
15 passed, 141 deselected
All checks passed!
Success: no issues found in 19 source files
```

全量验证：

```powershell
python -m pytest -q --basetemp .tmp-p4-2-full-20260710-a
```

结果：

```text
163 passed in 13.10s
```

## 保证矩阵

| # | 保证项 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 低覆盖项映射为按优先级排序的场景 ID 与详细证据 | `test_p4_2_maps_low_coverage_items_to_scenario_ids_and_evidence` | 单元 | PASS |
| 2 | `SKIP/N/A` 场景不进入建议，无低覆盖项时返回空结果 | `test_p4_2_maps_low_coverage_items_to_scenario_ids_and_evidence` | 边界 | PASS |
| 3 | 看板 Markdown/HTML 展示场景 ID、用途、优先级、证据和原因 | `test_p4_2_dashboard_renders_recommendations_and_json` | 集成 | PASS |
| 4 | `low_coverage_items.json` 同时保存场景 ID 和详细推荐 | `test_p4_2_dashboard_renders_recommendations_and_json` | 集成 | PASS |
| 5 | async-fifo 场景目录包含五类 coverage 匹配规则和 `clock_ratio_sweep` | `test_p4_2_async_fifo_catalog_defines_coverage_matching_rules` | 配置 | PASS |
| 6 | 推荐器进入 Mypy 范围 | `test_p4_2_recommendations_module_is_in_mypy_scope` | 配置 | PASS |
| 7 | P4.1 夹具同时保留 `cross_write_full` 和 `cross_read_empty` | P4.1/P4.2 定向回归 | 回归 | PASS |

## 真实产物验收

命令：

```powershell
python .trae/agent/agent.py --coverage-closure --coverage-target 80 --output-dir outputs
```

async-fifo 推荐结果：

| Priority | Scenario ID | Evidence Count | 关键证据 |
|---|---|---:|---|
| HIGH | `full_boundary` | 2 | `cp_full`、`cross_write_full` |
| HIGH | `empty_boundary` | 1 | `cross_read_empty` |
| MEDIUM | `reset_recovery` | 8 | `uvm/async_fifo_sva.sv`、statement/branch/condition/toggle |
| MEDIUM | `clock_ratio_sweep` | 2 | `rtl/async_fifo.v` 的 toggle |
| LOW | `mixed_stress` | 33 | 未被边界规则覆盖的广泛代码/功能覆盖缺口 |

产物：

```text
outputs/coverage-closure/index.md
outputs/coverage-closure/index.html
outputs/coverage-closure/low_coverage_items.json
```

## 覆盖率

命令：

```powershell
$env:PYTHONPATH = (Resolve-Path ".tmp-p5-cov-deps").Path
$env:COVERAGE_FILE = ".tmp-p4-2-full-20260710-a/.coverage-p4-2"
python -m coverage run -m pytest tests/test_agent.py -k "p4_0 or p4_1 or p4_2" -q --basetemp .tmp-p4-2-coverage-tests-20260710-a
python -m coverage report .trae/agent/coverage_recommendations.py .trae/agent/xcrg_coverage.py .trae/agent/coverage_closure.py
```

结果：

```text
.trae/agent/coverage_closure.py          92.7%
.trae/agent/coverage_recommendations.py  93.2%
.trae/agent/xcrg_coverage.py             86.4%
TOTAL                                    89.7%
```

## 已知后续

- P4.2 只生成补测建议，不自动修改 UVM sequence、RTL 或 target 状态。
- `mixed_stress` 是低优先级 fallback，用于承接未被边界/复位/时钟规则直接解释的覆盖缺口。
- 下一步 P4.3 将为 Total、Statement/Line、Branch、Condition、Toggle 和 Functional coverage 增加独立 gate。
