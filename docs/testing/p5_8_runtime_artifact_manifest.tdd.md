# P5.8 运行时 Artifact Manifest TDD 记录

## 来源计划

本阶段承接 `docs/roadmap/project_followup_backlog.md` 的 P5.8：

- 每次 target flow 生成或更新 `artifacts.json`。
- 记录产物路径、工具信息、命令、时间戳和状态。
- 将 P5.6 静态 `artifact_manifest` 映射为实际运行证据。

## 用户旅程

- 作为数字 IC 设计者，我希望每次 flow 都留下可重跑命令和产物状态，便于复现仿真、分析与报告生成过程。
- 作为验证工程师，我希望失败 flow 也能写入错误证据，而不是只在成功时生成报告。
- 作为项目维护者，我希望 manifest 采用稳定 schema 并追加历史，避免后续 dashboard 只能依赖散落文件推断状态。
- 作为安全维护者，我希望越界路径、非法状态和损坏 manifest 被拒绝，避免错误证据静默污染。

## RED 证据

命令：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-8-red-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests/test_agent.py tests/test_quality_config.py -k "p5_8" -q --basetemp $base
```

结果：

```text
5 failed, 119 deselected
```

有效 RED 信号：

- `.trae/agent/artifact_manifest.py` 不存在。
- generate RTL、规格、验证计划和 create-target 均未写 `artifacts.json`。
- target flow 异常没有运行时失败记录。
- 新模块未纳入 Mypy。

RED checkpoint：

```text
7add485 test: define P5.8 runtime artifact manifest contracts
```

## GREEN 证据

定向测试：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-8-green-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests/test_agent.py tests/test_quality_config.py -k "p5_8" -q --basetemp $base
```

结果：

```text
5 passed, 119 deselected in 0.62s
```

GREEN checkpoint：

```text
a0dcb22 feat: implement P5.8 runtime artifact manifests
```

防护补强：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-8-guard-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests/test_agent.py tests/test_quality_config.py -k "p5_8" -q --basetemp $base
```

结果：

```text
6 passed, 119 deselected in 0.74s
```

补强提交：

```text
5ec9f30 test: cover P5.8 manifest validation guards
```

静态质量门：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
python -m ruff check .trae/agent tests
python -m mypy
```

结果：

```text
All checks passed!
Success: no issues found in 13 source files
```

完整回归：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-8-final-full-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests -q --basetemp $base
```

结果：

```text
125 passed in 10.23s
```

覆盖率：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-8-final-cov-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests --cov=.trae/agent --cov-report=term-missing --cov-fail-under=68 -q --basetemp $base
```

结果：

```text
125 passed in 10.81s
TOTAL 73.83%
artifact_manifest.py 82.6%
```

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 | 证据 |
|---|---|---|---|---|---|
| 1 | generate-rtl 写入 schema v1 manifest、重跑命令、Python 版本和实际产物状态 | `tests/test_agent.py::test_p5_8_generate_rtl_writes_runtime_artifact_manifest` | integration | PASS | `6 passed, 119 deselected` |
| 2 | 规格与验证计划追加历史而不是覆盖前一条 run | `tests/test_agent.py::test_p5_8_report_generation_appends_manifest_history` | integration | PASS | flow 顺序完整 |
| 3 | target flow 异常写入 FAIL 和 error 后重新抛出原异常 | `tests/test_agent.py::test_p5_8_failed_target_flow_records_failure` | error path | PASS | FAIL run 存在 |
| 4 | create-target 脚手架包含自身 manifest 和候选配置 artifact | `tests/test_agent.py::test_p5_8_create_target_scaffold_writes_runtime_manifest` | integration | PASS | `target_config` PASS |
| 5 | 非法状态、项目外 artifact 和损坏 JSON 被拒绝 | `tests/test_agent.py::test_p5_8_manifest_rejects_invalid_status_external_path_and_corrupt_json` | security/unit | PASS | 明确 `ValueError` |
| 6 | manifest 模块纳入 Mypy | `tests/test_quality_config.py::test_p5_8_artifact_manifest_is_in_mypy_scope` | quality gate | PASS | 13 source files |
| 7 | 全部既有 target、Vivado、UVM、报告、adapter 和脚手架保持兼容 | `python -X utf8 -m pytest tests -q` | regression | PASS | `125 passed` |

## Schema 与状态语义

顶层字段：

- `schema_version`：当前为 `1`。
- `target`：规范化 target 名称。
- `updated_at`：最后写入 UTC 时间。
- `runs`：按执行顺序追加的运行记录。

run 字段：

- `run_id`、`flow`、`status`、`recorded_at`。
- `command`、`options`、`tools`。
- `artifacts`：P5.6 声明产物和额外运行产物。
- `error`：成功为 `null`，失败保存错误文本。

状态：

- run：`PASS` 或 `FAIL`。
- artifact：文件存在为 `PASS`；声明为不适用时为 `N/A`；尚未生成时为 `SKIP`。

## 实现范围

- 新增 `.trae/agent/artifact_manifest.py`。
- `DigitalICAgent.run_target_flow()` 统一记录成功、false result 和异常。
- Report adapter 接入 `generate-spec` 与 `generate-verification-plan`。
- P5.7 scaffolder 接入 `create-target`。
- manifest 保存 Python 版本，并按 flow 保存 Vivado 命令/路径版本或 waveform backend。

## 已知边界

- 历史当前持续追加，尚未限制 run 数量或自动归档。
- Vivado 版本优先从可执行路径提取，未额外启动 Vivado 进程查询版本，避免每次 flow 增加明显延迟。
- manifest 记录 P5.6 声明的关键产物，不递归扫描整个 Vivado 工程，避免大型项目目录造成性能和体积问题。
- 项目整体覆盖率受既有大型 `agent.py` 影响仍低于通用 80% 建议，但高于当前 `68%` 门槛；P5.8 新模块覆盖率为 `82.6%`。

## 合并证据

- RED commit：`7add485 test: define P5.8 runtime artifact manifest contracts`。
- GREEN commit：`a0dcb22 feat: implement P5.8 runtime artifact manifests`。
- 防护补强：`5ec9f30 test: cover P5.8 manifest validation guards`。
- checkpoint 均保留在当前分支，未重写历史。
