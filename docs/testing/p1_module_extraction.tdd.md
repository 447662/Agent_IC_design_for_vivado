# P1 Agent 模块拆分 TDD 证据

## 来源与目标

本轮任务由代码审查后的 P1 优化建议直接产生，没有单独的外部计划文件。

用户旅程：

- 作为 Agent 维护者，我希望低耦合基础设施从 `agent.py` 中独立出来，以便后续修改命令执行、目标注册、配置或 CLI 时减少回归范围。
- 作为现有调用方，我希望 `agent.py` 继续导出原有类、函数和方法，以便已有脚本与测试无需迁移。

## 第一轮：运行时与目标注册表

RED 命令：

```powershell
python -X utf8 -m pytest tests/test_agent.py -q --basetemp .tmp-p1-red -k "runtime_components_live_in_dedicated_module or target_registry_module_preserves_sorting_aliases_and_validation"
```

RED 结果：`2 failed, 98 deselected`。失败原因是 `agent_runtime.py` 与 `target_registry.py` 尚不存在。

GREEN 验证：

```powershell
python -X utf8 -m pytest tests/test_agent.py -q --basetemp .tmp-p1-green -k "runtime_components_live_in_dedicated_module or target_registry_module_preserves_sorting_aliases_and_validation or command_runner or target_registry or target_handler_registry"
```

GREEN 结果：`9 passed, 91 deselected`。

完整回归结果：`100 passed`。

检查点提交：

- RED：`2976211 test: define P1 module extraction boundaries`
- GREEN：`155a066 refactor: extract agent runtime and target registry`

## 第二轮：CLI 与配置

RED 命令：

```powershell
python -X utf8 -m pytest tests/test_agent.py -q --basetemp .tmp-p1-cli-red -k "cli_helpers_live_in_dedicated_module or config_helpers_live_in_dedicated_module"
```

RED 结果：`2 failed, 100 deselected`。失败原因是 `agent_cli.py` 与 `agent_config.py` 尚不存在。

GREEN 验证：

```powershell
python -X utf8 -m pytest tests/test_agent.py -q --basetemp .tmp-p1-cli-green-2 -k "cli_helpers_live_in_dedicated_module or config_helpers_live_in_dedicated_module or cli_ or command or main"
```

GREEN 结果：`36 passed, 66 deselected`。

完整回归结果：`102 passed`。

检查点提交：

- RED：`042dc4a test: define CLI and config extraction boundaries`
- GREEN：由本轮最终模块化提交保存。

## 测试规格

| # | 保证 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | `CommandRunner` 和 `TargetHandler` 来自独立运行时模块，`agent.py` 保持兼容导出 | `test_runtime_components_live_in_dedicated_module` | 单元 | PASS |
| 2 | target JSON 仍按名称排序、支持下划线别名并拒绝缺失字段 | `test_target_registry_module_preserves_sorting_aliases_and_validation` | 单元 | PASS |
| 3 | CLI 参数、seed 解析和需求拼装来自独立模块，主入口仍使用同一函数对象 | `test_cli_helpers_live_in_dedicated_module` | 单元 | PASS |
| 4 | Agent 配置读取结果与源 JSON 一致，字符串和数组命令保持兼容 | `test_config_helpers_live_in_dedicated_module` | 单元 | PASS |
| 5 | 全部现有设计生成、仿真、分析、报告和 CLI 行为未回归 | `python -X utf8 -m pytest tests/test_agent.py -q` | 回归 | PASS，102 项 |

## 额外验证

- `python -X utf8 -m compileall -q .trae/agent tests`：PASS。
- `python -X utf8 .trae/agent/agent.py --list-targets`：PASS。
- 项目文本严格 UTF-8 扫描：PASS，63 个文件。
- `git diff --check`：无空白错误，仅有 Windows 行尾转换提示。

## 覆盖率与后续边界

本轮未启用覆盖率采集，因此不声明新的覆盖率百分比。现有测试覆盖模块导入、兼容导出、命令执行、目标注册和主要 CLI 路径。

后续批次继续处理：

- waveform analyzer 与 VCD/WDB 路径解析；
- Markdown/HTML 报告生成；
- async FIFO、sync FIFO 和 round-robin arbiter 的 RTL/Vivado runner。
