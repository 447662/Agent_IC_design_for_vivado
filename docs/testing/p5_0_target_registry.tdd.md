# P5.0 Target Registry TDD 证据

## 范围

P5.0 的目标是先把 async FIFO 从单点硬编码流程抽象成最小目标注册表，并提供 `--list-targets` CLI。此阶段不新增第二个 RTL 目标，不改变 async FIFO 既有生成、仿真、UVM 和 coverage 行为。

## 用户故事

- 作为项目维护者，我希望 Agent 能列出当前支持的数字 IC 设计目标，以便后续扩展 sync FIFO、arbiter 等目标时有统一入口。
- 作为验证使用者，我希望 async FIFO 的旧命令继续可用，以便 P5.0 通用化不会破坏 P0-P3.14 已跑通的流程。

## RED 证据

新增测试后先运行：

```powershell
python -m pytest tests/test_agent.py -q -k "target_registry or list_targets" --basetemp .tmp-agent-output\pytest-p5-0-red
```

失败原因：

```text
AttributeError: 'DigitalICAgent' object has no attribute 'list_targets'
error: unrecognized arguments: --list-targets
```

## GREEN 证据

实现最小 registry 和 CLI 后运行：

```powershell
python -m pytest tests/test_agent.py -q -k "target_registry or list_targets" --basetemp .tmp-agent-output\pytest-p5-0-green
```

结果：

```text
2 passed, 66 deselected
```

完整回归：

```powershell
python .trae/agent/agent.py --list-targets
python -m pytest tests/test_agent.py -q --basetemp .tmp-agent-output\pytest-full-p5-0
```

结果：

```text
async-fifo (Asynchronous FIFO)
flows: generate-rtl, sim-rtl, regress-rtl, uvm-smoke, uvm-coverage, uvm-random-regress, analyze-rtl-vcd, check-rtl, open-wave, open-uvm-wave
68 passed in 6.77s
```

## 保证项

| # | 保证项 | 测试或命令 | 结果 |
|---|---|---|---|
| 1 | `DigitalICAgent.list_targets()` 返回注册目标，当前包含 `async-fifo` | `tests/test_agent.py::test_p5_target_registry_lists_async_fifo_metadata` | PASS |
| 2 | `get_target("async_fifo")` 能通过别名解析为 `async-fifo` | `tests/test_agent.py::test_p5_target_registry_lists_async_fifo_metadata` | PASS |
| 3 | `--list-targets` 能输出目标、设计族、别名和 flow | `tests/test_agent.py::test_cli_list_targets_outputs_registered_targets` | PASS |
| 4 | P5.0 不破坏既有 async FIFO 主流程 | `python -m pytest tests/test_agent.py -q --basetemp .tmp-agent-output\pytest-full-p5-0` | PASS |

## 后续

- P5.1：将目标元信息搬到配置文件，例如 `.trae/agent/targets/async_fifo.yaml`。
- P5.2：新增第二个目标 `sync-fifo`，验证 target registry 真正支持多目标。
