# P4.5 失败 Seed 自动归档 TDD 证据

## Source Plan

- `docs/roadmap/p4_future_upgrade_roadmap.md` 的 P4.5。
- 本轮按 ECC `tdd-workflow` 执行 RED、GREEN、覆盖率和证据记录。

## User Journeys

1. 作为长回归使用者，我希望失败 seed 自动保存最小复现材料，以便后续输出清理后仍能定位失败。
2. 作为验证工程师，我希望归档包含重跑命令和 WDB 打开命令，以便快速复现和查看波形。
3. 作为报告使用者，我希望随机回归摘要直接链接失败归档，以便从总览进入调试材料。
4. 作为 Agent 维护者，我希望归档 schema 不绑定 async FIFO 或 UVM coverage，以便后续复用于仿真、lint 和 formal smoke。

## RED Evidence

提交：

```text
e8d71ec1 test: define P4.5 failed seed archive behavior
```

命令：

```powershell
pytest -q tests/test_agent.py -k p4_5 --basetemp .tmp/pytest-p4-5-red-20260710-b
```

结果：

```text
3 failed, 165 deselected in 0.48s
```

预期失败：

- `.trae/agent/failure_archive.py` 尚不存在。
- 随机回归失败 seed 尚未生成 `failure_archive.json`。
- 新模块尚未进入 Mypy 范围。

## GREEN Evidence

提交：

```text
a3912b4c feat: add P4.5 failed seed archives
4d18c2a7 chore: ignore local test scratch directory
```

定向命令：

```powershell
pytest -q tests/test_agent.py -k "p4_5 or random_regression_writes_seed_report" --basetemp .tmp/pytest-p4-5-green-20260710-a
```

结果：

```text
4 passed, 164 deselected in 0.95s
```

模块覆盖率命令：

```powershell
$env:PYTHONPATH=(Resolve-Path '.tmp/test-deps-p4-5-cov').Path
python -m pytest -q tests/test_agent.py -k "p4_5 or random_regression_writes_seed_report" --cov=failure_archive --cov-report=term-missing --basetemp .tmp/pytest-p4-5-module-cov-20260710-a
```

结果：

```text
failure_archive.py: 89.0%
4 passed, 164 deselected
```

## Task Report

| Task | Execution summary | Validation | Guarantee |
|---|---|---|---|
| 通用归档内核 | 新增 `archive_failed_run()`，按 flow/run ID 创建固定目录并复制 role 化材料 | `test_p4_5_archives_failed_run_materials_with_generic_manifest` | schema 可用于 `sync-fifo` / `formal-smoke`，没有写死 async FIFO 或 UVM coverage |
| 最小复现材料 | 保存 log、WDB、coverage DB、Tcl 和目标配置 | 同上及夹具产物抽查 | 五类材料位于 `artifacts/<role>/`，manifest 记录可用状态和归档路径 |
| 重跑与波形命令 | 生成 `reproduce.ps1`、`open_wave.ps1` 和 README | 同上 | 失败 seed 可从归档直接获得重跑和波形入口 |
| 随机回归集成 | 仅失败 seed 调用归档，成功 seed 不创建归档 | `test_p4_5_random_regression_archives_only_failed_seed_and_links_report` | `seed_22` 归档、`seed_11` 不归档 |
| 报告链接 | Markdown/HTML 新增 Failure Archive、Reproduce、Open WDB | 同上 | 报告可直接定位归档目录和命令脚本 |
| 类型检查 | `failure_archive.py` 加入 `pyproject.toml` | `test_p4_5_failure_archive_module_is_in_mypy_scope` / `mypy` | 新模块进入持续类型检查 |

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result |
|---|---|---|---|---|
| 1 | 通用 manifest 包含 target、flow、run ID、状态、seed、材料和命令 | `tests/test_agent.py::test_p4_5_archives_failed_run_materials_with_generic_manifest` | unit | PASS |
| 2 | log、WDB、coverage DB、Tcl、目标配置均复制到固定归档目录 | 同上 | unit | PASS |
| 3 | 归档生成 `reproduce.ps1`、`open_wave.ps1` 和 README | 同上及夹具抽查 | unit/integration | PASS |
| 4 | 失败 seed 被归档，成功 seed 不误归档 | `tests/test_agent.py::test_p4_5_random_regression_archives_only_failed_seed_and_links_report` | integration | PASS |
| 5 | Markdown/HTML 摘要链接归档与命令 | 同上 | integration | PASS |
| 6 | 新模块进入 Mypy 配置 | `tests/test_agent.py::test_p4_5_failure_archive_module_is_in_mypy_scope` | config | PASS |

## Full Validation

全量测试与覆盖率：

```powershell
$env:PYTHONPATH=(Resolve-Path '.tmp/test-deps-p4-5-cov').Path
$env:COVERAGE_FILE='.tmp/.coverage-p4-5-full'
python -m pytest -q tests --cov=.trae/agent --cov-report=term-missing --cov-fail-under=68 --basetemp .tmp/pytest-p4-5-full-cov-20260710-a
```

结果：

```text
175 passed in 21.57s
TOTAL 79.07%
failure_archive.py 89.0%
```

静态检查：

```powershell
ruff check .
mypy
```

结果：

```text
All checks passed!
Success: no issues found in 22 source files
```

## Fixture Acceptance

集成夹具生成：

```text
async-fifo/failure_archives/uvm-coverage/seed_22/
├── failure_archive.json
├── reproduce.ps1
├── open_wave.ps1
├── README.md
└── artifacts/
    ├── log/async_fifo_uvm_coverage.log
    ├── waveform/async_fifo_uvm_coverage.wdb
    ├── coverage_db/async_fifo_uvm_cov/xsim.CCInfo
    ├── tcl/run_vivado_async_fifo_uvm_coverage.tcl
    └── target_config/async_fifo.json
```

`uvm_random_regression.md` 的失败行同时包含 Failure Archive、Reproduce 和 Open WDB 路径。

## Coverage and Known Gaps

- `failure_archive.py` 定向覆盖率为 `89.0%`，超过 80% 要求。
- 全量覆盖率为 `79.07%`，超过项目 `68%` 门槛。
- 本轮使用夹具制造失败 seed，未额外运行一次故意失败的真实 Vivado 长回归；真实 Vivado coverage 主链已在 P4.3/P4.4 验收。
- P4.6 将继续增强 GUI 自动验收，判断 WDB、Scope/Objects 和 wave config 是否真实非空。
