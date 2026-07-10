# P4.1 低覆盖项提取 TDD 证据

## 来源与用户旅程

本阶段依据 `docs/roadmap/p4_future_upgrade_roadmap.md` 的 P4.1 定义实施，未使用外部计划文件。

1. 作为验证负责人，我希望看到低覆盖的具体文件、实例和指标，而不是只有类别级 gap，以便直接定位补测对象。
2. 作为 UVM 维护者，我希望看到 functional group、cover point 和 cross 的未覆盖明细，以便识别缺失场景。
3. 作为多 target 维护者，我希望解析器排除 Vivado 自带 UVM 库，并在报告格式漂移时保留原始链接和明确诊断。
4. 作为 P4.2 实现者，我希望获得稳定的 `CoverageItem` JSON 契约，以便映射 `scenario_catalog`。

## 契约

每个低覆盖项包含：

```text
source_file
instance
metric
score
details
source_report
```

解析范围：

- `codeCoverageReport/files.html`
- `codeCoverageReport/modules.html`
- `functionalCoverageReport/groups.html`
- `functionalCoverageReport/grp*.html`

## RED

检查点提交：

```text
e856b32 test: define P4.1 low coverage item contract
3680e0c test: reproduce Vivado functional group header
f3d68ea test: reject xcrg navigation links as sources
c730b5f test: normalize xcrg functional instance names
```

初始契约命令：

```powershell
python -m pytest tests/test_agent.py -k "p4_1" -q --basetemp .tmp-p4-1-red-20260710-a
```

结果：

```text
4 failed, 148 deselected
```

失败点：

- 尚无 `.trae/agent/xcrg_coverage.py`。
- 看板尚无 `coverage_gaps`、具体 `low_coverage_items`、解析诊断和 JSON 索引。
- 新模块尚未进入 Mypy 范围。

真实 xcrg 格式回归：

```text
groups.html 使用 Name 表头时：2 failed, 2 passed
grp0.html 含 Dashboard/Groups 导航链接时：1 failed, 3 passed
实例名含制表符转义时：2 failed, 2 passed
```

这些失败分别证明测试能够捕获：

- functional group 行被静默跳过；
- 导航文字被误识别为 HDL 源文件；
- `\t` 导致的 `his .async_fifo_cg` 不稳定实例名。

## GREEN

实现检查点：

```text
ab5625d feat: add P4.1 low coverage item extraction
692d601 fix: harden P4.1 functional xcrg parsing
```

最终定向验证：

```powershell
python -m pytest tests/test_agent.py -k "p4_0 or p4_1" -q --basetemp .tmp-p4-final-regression-20260710-a
python -m ruff check .trae/agent/xcrg_coverage.py .trae/agent/coverage_closure.py tests/test_agent.py
python -m mypy --config-file pyproject.toml
```

结果：

```text
11 passed, 141 deselected
All checks passed!
Success: no issues found in 18 source files
```

全量验证：

```powershell
python -m pytest -q --basetemp .tmp-p4-final-full-20260710-a
```

结果：

```text
159 passed in 15.73s
```

## 保证矩阵

| # | 保证项 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 文件、模块、functional group、cover point 和 cross 转换为统一 `CoverageItem` | `test_p4_1_extracts_project_low_coverage_items_from_xcrg` | 单元/集成 | PASS |
| 2 | 当前 target 之外的 Vivado/UVM 源文件被过滤 | `test_p4_1_extracts_project_low_coverage_items_from_xcrg` | 边界 | PASS |
| 3 | 低覆盖项按分数排序，只保留低于目标阈值的条目 | `test_p4_1_extracts_project_low_coverage_items_from_xcrg` | 单元 | PASS |
| 4 | 缺失或无法识别的页面返回 `MISSING/INVALID`，不生成伪造的 0 分项 | `test_p4_1_reports_missing_and_invalid_xcrg_pages_without_zero_defaults` | 错误路径 | PASS |
| 5 | 看板展示具体低覆盖项、原始报告链接和解析诊断 | `test_p4_1_dashboard_renders_concrete_items_and_writes_json` | 集成 | PASS |
| 6 | `low_coverage_items.json` 保留多 target 通用契约，`recommended_scenarios` 仍为空 | `test_p4_1_dashboard_renders_concrete_items_and_writes_json` | 集成 | PASS |
| 7 | Vivado `Name` 表头、导航链接和制表符实例名均被稳定处理 | P4.1 真实格式夹具 | 回归 | PASS |
| 8 | 新解析器进入 Mypy 范围 | `test_p4_1_xcrg_coverage_module_is_in_mypy_scope` | 配置 | PASS |

## 真实产物验收

命令：

```powershell
python .trae/agent/agent.py --coverage-closure --coverage-target 80 --output-dir outputs
```

产物：

```text
outputs/coverage-closure/index.md
outputs/coverage-closure/index.html
outputs/coverage-closure/low_coverage_items.json
```

async-fifo 真实解析结果：

```text
低覆盖项：36
解析诊断：0
```

分布：

| Metric | Count |
|---|---:|
| Statement | 6 |
| Branch | 8 |
| Condition | 8 |
| Toggle | 10 |
| Functional group | 1 |
| Cover point | 1 |
| Cross | 2 |

功能覆盖明细：

| Item | Score | Source | Instance |
|---|---:|---|---|
| `async_fifo_uvm_pkg::async_fifo_monitor::async_fifo_cg` | 57.1% | `uvm/async_fifo_uvm_pkg.sv` | `this.async_fifo_cg` |
| `cp_full` | 0.0% | `uvm/async_fifo_uvm_pkg.sv` | `this.async_fifo_cg` |
| `cross_write_full` | 0.0% | `uvm/async_fifo_uvm_pkg.sv` | `this.async_fifo_cg` |
| `cross_read_empty` | 0.0% | `uvm/async_fifo_uvm_pkg.sv` | `this.async_fifo_cg` |

Vivado 自带 `xlnx_uvm_package.sv` 未进入结果。

## 覆盖率

命令：

```powershell
$env:PYTHONPATH = (Resolve-Path ".tmp-p5-cov-deps").Path
$env:COVERAGE_FILE = ".tmp-p4-1-coverage-20260710-b"
python -m coverage run -m pytest tests/test_agent.py -k "p4_0 or p4_1" -q --basetemp .tmp-p4-final-coverage-tests-20260710-a
python -m coverage report .trae/agent/xcrg_coverage.py .trae/agent/coverage_closure.py
```

结果：

```text
.trae/agent/coverage_closure.py  92.1%
.trae/agent/xcrg_coverage.py     86.4%
TOTAL                            88.9%
```

## 已知后续

- `recommended_scenarios` 仍为空列表；P4.2 将根据 `metric`、`details.name` 和 target `scenario_catalog` 生成建议。
- P4.1 只读取和诊断覆盖率，不自动修改 UVM sequence 或 RTL。
- 解析器优先兼容当前 Vivado 2025.2 xcrg 结构；其它版本无法识别时保留 `MISSING/INVALID` 与原始链接。
