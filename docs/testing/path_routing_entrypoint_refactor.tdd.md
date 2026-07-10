# 路径、路由与组合入口改造 TDD 证据

## 来源

本次任务直接来自用户请求：

1. 修复运行时产物路径边界。
2. 修复自然语言路由中的否定语义。
3. 拆分 Agent 组合工厂和 CLI 调度入口。

本次实现未读取或引用现有升级规划。

## 用户旅程

- 作为运行流维护者，我希望产物路径不能通过绝对路径、`..` 或符号链接逃出
  target 项目目录，以保证 manifest 只描述本次运行的受控产物。
- 作为自然语言用户，我希望“不需要 UVM”“不要 RTL”等否定表达不会反向触发
  对应技能。
- 作为维护者，我希望 `agent.py` 只负责组装 `DigitalICAgent` 并委托 CLI 入口，
  使实例化错误边界和命令分派可以独立测试。

## RED 证据

命令：

```powershell
python -m pytest `
  tests/test_agent.py::test_cli_entrypoint_and_composition_live_in_dedicated_modules `
  tests/test_agent.py::test_analyze_requirement_respects_negated_skill_keywords `
  tests/test_agent.py::test_artifact_manifest_rejects_relative_path_escape `
  --basetemp .tmp-red-three-fixes -p no:cacheprovider -q
```

结果：`5 failed`。

- `agent_entrypoint.py` 和 `agent_composition.py` 尚不存在。
- 三个否定语义用例均选择了被明确排除的技能。
- `../outside.log` 未触发目录边界异常。

## GREEN 证据

定向命令：

```powershell
python -m pytest `
  tests/test_agent.py::test_cli_entrypoint_and_composition_live_in_dedicated_modules `
  tests/test_agent.py::test_analyze_requirement_respects_negated_skill_keywords `
  tests/test_agent.py::test_artifact_manifest_rejects_relative_path_escape `
  tests/test_agent.py::test_cli_list_skills_succeeds `
  tests/test_agent.py::test_cli_diagnostic_runs_as_independent_mode `
  tests/test_agent.py::test_p5_7_cli_create_target_generates_scaffold `
  --basetemp .tmp-green-three-fixes -p no:cacheprovider -q
```

结果：`8 passed`。

完整验证：

```text
Ruff:    PASS
Mypy:    PASS, 27 source files
Pytest:  PASS, 191 tests
Coverage: 80.72%
CLI smoke: --list-targets and --list-skills PASS
```

## 保证清单

| # | 保证 | 测试或命令 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 绝对路径和 `..` 相对路径都不能逃出 target 项目目录 | `test_artifact_manifest_rejects_relative_path_escape`、既有 absolute path 用例 | 安全/单元 | PASS |
| 2 | “不需要 UVM，只做 RTL”只选择 RTL 技能 | `test_analyze_requirement_respects_negated_skill_keywords` | 行为/单元 | PASS |
| 3 | “不要设计文档，只实现 RTL”不会选择设计文档技能 | 同上 | 行为/单元 | PASS |
| 4 | “只生成设计文档，不要 RTL 和仿真”只选择设计技能 | 同上 | 行为/单元 | PASS |
| 5 | `agent.py` 的 `main` 委托独立 `run_cli`，实例化委托独立 `build_agent` | `test_cli_entrypoint_and_composition_live_in_dedicated_modules` | 架构/单元 | PASS |
| 6 | 原有 CLI 目标、技能、诊断和 target 创建行为保持可用 | 定向 CLI 测试、真实 CLI smoke、完整测试集 | 集成 | PASS |

## 覆盖率与已知边界

- 总覆盖率为 `80.72%`，达到本次 TDD 门槛。
- 新路由模块覆盖率为 `93.1%`，artifact manifest 为 `86.7%`。
- CLI 子进程测试不会自动合并到当前 coverage 数据，因此
  `agent_entrypoint.py` 的独立覆盖率低于其实际行为测试覆盖。
- 本次未启动真实 Vivado GUI 或执行硬件工具链；相关流程继续由现有模拟测试和
  CLI 分派测试保护。

## Git 检查点

- RED：`test: add reproducers for routing boundaries and entrypoint`
- GREEN：`fix: secure artifact routing and split cli entrypoint`
