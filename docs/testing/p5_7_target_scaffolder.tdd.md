# P5.7 Target 脚手架生成器 TDD 记录

## 来源计划

本阶段承接 `docs/roadmap/project_followup_backlog.md` 的 P5.7：

- 新增 `--create-target <name>`。
- 生成符合 P5.6 schema 的候选 target JSON。
- 生成 RTL/TB/report 占位和 TODO 检查清单。
- 默认不覆盖已有文件。

## 用户旅程

- 作为数字 IC 设计者，我希望用一个命令创建新 target 的最小工程结构，减少复制旧 target 带来的硬编码和遗漏。
- 作为项目维护者，我希望生成的 JSON 能立即通过 P5.6 registry 校验，但在 handler 尚未实现时不要自动污染正式 registry。
- 作为开发者，我希望非法名称、重复 target 和已有输出目录被明确拒绝，避免路径穿越和误覆盖。

## RED 证据

命令：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-7-red-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests/test_agent.py -k "p5_7" -q --basetemp $base
```

结果：

```text
3 failed, 112 deselected
```

有效 RED 信号：

- `.trae/agent/target_scaffolder.py` 不存在。
- `DigitalICAgent.create_target_scaffold()` 不存在。
- CLI 不识别 `--create-target`。

RED checkpoint：

```text
ff29977 test: define P5.7 target scaffolder contracts
```

## GREEN 证据

定向测试：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-7-green-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests/test_agent.py -k "p5_7" -q --basetemp $base
```

结果：

```text
3 passed, 112 deselected in 0.63s
```

GREEN checkpoint：

```text
8ec5780 feat: implement P5.7 target scaffolder
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
Success: no issues found in 12 source files
```

完整回归：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-7-full-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests -q --basetemp $base
```

结果：

```text
119 passed in 11.88s
```

覆盖率：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-7-cov-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests --cov=.trae/agent --cov-report=term-missing --cov-fail-under=68 -q --basetemp $base
```

结果：

```text
119 passed in 13.28s
TOTAL 73.14%
target_scaffolder.py 100.0%
```

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 | 证据 |
|---|---|---|---|---|---|
| 1 | 脚手架生成可通过 P5.6 registry 校验的候选配置 | `tests/test_agent.py::test_p5_7_target_scaffolder_generates_valid_candidate_project` | unit/integration | PASS | `3 passed, 112 deselected` |
| 2 | 脚手架包含 RTL、TB、三份报告占位、README 与 TODO | 同上 | integration | PASS | 所有预期路径存在 |
| 3 | target 使用 kebab-case，Verilog module 使用 snake_case | 同上 | unit | PASS | `packet_router` -> `packet-router` / `packet_router` |
| 4 | 非法名称和已注册 target 被拒绝 | `tests/test_agent.py::test_p5_7_target_scaffolder_rejects_invalid_duplicate_and_overwrite` | security/unit | PASS | `ValueError` |
| 5 | 已存在输出目录不会被覆盖 | 同上 | safety/unit | PASS | `FileExistsError` |
| 6 | CLI `--create-target` 生成脚手架并输出关键路径 | `tests/test_agent.py::test_p5_7_cli_create_target_generates_scaffold` | CLI integration | PASS | `returncode == 0` |
| 7 | 既有 target、Vivado、UVM、报告和 adapter 流程保持兼容 | `python -X utf8 -m pytest tests -q` | regression | PASS | `119 passed` |

## 实现范围

- 新增 `.trae/agent/target_scaffolder.py`。
- 新增 CLI `--create-target TARGET`。
- 支持使用尾部自然语言文本作为 target description。
- 新增候选 P5.6 metadata、最小 Verilog RTL/TB 和报告占位渲染。
- 新模块纳入 Mypy 与 coverage。

## 设计边界

- 脚手架生成到 `--output-dir/<target>/`，不直接写入 `.trae/agent/targets/`。
- 正式安装前必须补齐 `TargetHandler` 和已实现 flows，否则现有严格 handler 校验会拒绝启动。
- P5.7 只生成静态预期 `artifact_manifest`；每次 flow 的运行时 `artifacts.json` 属于 P5.8。
- 当前未生成 Vivado Tcl，因为不同 target 的源文件、顶层模块、时钟和仿真参数需要在 TODO 阶段明确。

## 合并证据

- RED commit：`ff29977 test: define P5.7 target scaffolder contracts`。
- GREEN commit：`8ec5780 feat: implement P5.7 target scaffolder`。
- RED 与 GREEN checkpoint 均保留在当前分支，未重写历史。
