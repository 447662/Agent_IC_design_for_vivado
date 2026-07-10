# Python 工程质量链路 TDD 证据

## 来源与目标

本轮任务来自 P1 模块化之后的工程质量优化建议，没有单独的外部计划文件。

用户旅程：

- 作为维护者，我希望本地和 CI 使用同一套 Ruff、Mypy、pytest 与覆盖率命令，以便提交前即可发现问题。
- 作为评审者，我希望质量门槛由版本化配置和测试约束，避免 CI 被静默弱化。
- 作为贡献者，我希望缓存、覆盖率文件和临时测试目录不会污染 Git 工作区。

## RED

新增 `tests/test_quality_config.py` 后运行：

```powershell
python -X utf8 -m pytest tests/test_quality_config.py -q --basetemp .tmp-quality-red
```

结果：`4 failed`。

失败原因：

- 缺少 `pyproject.toml`；
- `requirements-dev.txt` 只有 pytest；
- 缺少 `.github/workflows/python-quality.yml`；
- `.gitignore` 缺少 Mypy、Ruff、Coverage 和通用临时目录规则。

RED 检查点：

- `9e840d6 test: define Python quality gate contracts`

## GREEN

实现内容：

- 新增 `pyproject.toml`，集中配置 pytest、Ruff、Mypy 和 Coverage；
- 开发依赖增加 pytest-cov、Ruff 和 Mypy；
- 新增 Python 3.11/3.13 GitHub Actions 质量矩阵；
- 覆盖率门槛根据实测 `70.8%` 设置为 `68%`；
- `.gitignore` 增加静态检查、覆盖率和临时目录产物。

验证命令与结果：

```powershell
python -X utf8 -m pytest tests/test_quality_config.py -q
# 4 passed

python -m ruff check .trae/agent tests
# All checks passed

python -m mypy
# Success: no issues found in 8 source files

python -X utf8 -m pytest tests --cov=.trae/agent --cov-report=term-missing --cov-report=xml --cov-fail-under=68
# 110 passed
# Total coverage: 70.80%
```

GREEN 检查点：

- `adfec47 ci: add Python quality gates`

## 测试规格

| # | 保证 | 证据 | 结果 |
|---|---|---|---|
| 1 | `pyproject.toml` 同时定义 pytest、Ruff、Mypy 和 Coverage 配置 | `test_pyproject_defines_python_quality_gates` | PASS |
| 2 | 开发依赖包含 pytest-cov、Ruff 和 Mypy | `test_development_requirements_include_quality_tools` | PASS |
| 3 | GitHub Actions 执行安装、lint、类型检查、测试和 68% 覆盖率门槛 | `test_github_actions_runs_all_python_quality_gates` | PASS |
| 4 | Python 缓存、静态检查缓存、覆盖率和临时测试目录被忽略 | `test_python_quality_artifacts_are_gitignored` | PASS |
| 5 | 全部测试在覆盖率模式下通过 | `110 passed, total coverage 70.8%` | PASS |

## 覆盖率与已知边界

- Coverage 启用 branch coverage，当前总覆盖率为 `70.8%`。
- CI 门槛设置为 `68%`，为 Python 版本和平台差异保留小幅缓冲。
- Mypy 当前检查 8 个已拆分模块；`agent.py` 仍以动态编排和兼容导出为主，待后续模块化后逐步纳入。
- 本机 Anaconda 隔离了用户级 site-packages，因此本轮本地覆盖率验证通过进程内加入用户 site-packages 完成；GitHub Actions 的全新虚拟环境不需要该兼容步骤。
