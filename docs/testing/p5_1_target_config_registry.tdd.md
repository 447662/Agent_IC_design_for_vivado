# P5.1 Target Config Registry TDD 证据

## 范围

P5.1 的目标是把 P5.0 中的目标注册表从 Python 硬编码迁移到配置文件，方便后续新增 `sync-fifo`、`round-robin-arbiter`、`register-file` 等数字 IC 设计目标。

当前实现采用 JSON 配置，路径为：

```text
.trae/agent/targets/async_fifo.json
```

暂不使用 YAML，避免为单一配置格式引入额外依赖。

## 用户故事

- 作为项目维护者，我希望新增 RTL target 时优先新增配置文件，而不是修改 Agent 主逻辑。
- 作为验证使用者，我希望 async FIFO 原有命令和别名继续可用，P5.1 不破坏 P0-P5.0 已跑通流程。
- 作为后续扩展者，我希望 target 配置缺字段时能被测试及时发现，而不是在仿真阶段才失败。

## RED 证据

新增测试后，在实现 `load_target_registry()` 前运行：

```powershell
python -m pytest tests/test_agent.py -q -k "target_registry or list_targets" --basetemp .tmp-agent-output\pytest-p5-1-targets
```

预期失败点：

```text
AttributeError: 'DigitalICAgent' object has no attribute 'load_target_registry'
```

## GREEN 证据

实现配置文件加载和字段校验后运行：

```powershell
python -m pytest tests/test_agent.py -q -k "target_registry or list_targets" --basetemp .tmp-agent-output\pytest-p5-1-targets
```

结果：

```text
3 passed, 66 deselected
```

## 保证项

| # | 保证项 | 测试或命令 | 结果 |
|---|---|---|---|
| 1 | async FIFO 元信息来自 `.trae/agent/targets/async_fifo.json` | `test_p5_target_registry_lists_async_fifo_metadata` | PASS |
| 2 | `get_target("async_fifo")` 仍能解析到 `async-fifo` | `test_p5_target_registry_lists_async_fifo_metadata` | PASS |
| 3 | 缺少必填字段的 target 配置会报错 | `test_p5_target_registry_rejects_invalid_target_config` | PASS |
| 4 | `--list-targets` 仍能输出目标、设计族和 flow | `test_cli_list_targets_outputs_registered_targets` | PASS |

## 后续

- P5.2：新增第二个 RTL target，建议从 `sync-fifo` 开始。
- P5.3：新增非 FIFO 类 target，建议 `round-robin-arbiter`，验证 registry 对不同设计族是否通用。
- P5.4：把 target 配置扩展为 spec/scenario/report/coverage 的统一入口。
