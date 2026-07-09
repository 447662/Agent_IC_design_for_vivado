# P5.4/P5.5 通用规格与验证计划 TDD 记录

## 来源计划

本阶段承接 P5 通用数字 IC Agent 规划：

- P5.4：从自然语言需求或 target 配置生成 `design_spec.md` 与 `design_spec.html`。
- P5.5：从 scenario catalog 生成 `verification_plan.md` 与 `verification_plan.html`。

目标是把前面 `async-fifo`、`sync-fifo`、`round-robin-arbiter` 的单点流程进一步抽象为可复用的文档生成能力，使后续新增任意 RTL target 时，都能先生成中文规格和验证计划，再进入 RTL/TB/Vivado 仿真。

## 用户旅程

- 作为数字 IC 设计者，我希望 agent 能根据 target 配置和自然语言目标生成中文规格文档，便于设计评审前统一接口、参数、场景和检查点。
- 作为验证工程师，我希望 agent 能根据 scenario catalog 生成验证计划，便于确认 smoke test、边界场景、scoreboard 和后续覆盖率工作的范围。
- 作为项目维护者，我希望该能力不只服务于 `round-robin-arbiter`，也能复用到 FIFO 类目标，证明 P5 的通用化方向成立。

## RED 证据

新增 P5.4/P5.5 测试后，首次运行：

```powershell
python -m pytest tests/test_agent.py -k "p5_4 or p5_5" -q --basetemp .tmp-pytest
```

结果：

```text
5 failed, 86 deselected
```

有效 RED 信号：

- `DigitalICAgent` 尚未实现 `write_target_design_spec()`。
- `DigitalICAgent` 尚未实现 `write_target_verification_plan()`。
- CLI 尚未支持 `--generate-spec`。
- CLI 尚未支持 `--generate-verification-plan`。

## GREEN 证据

定向测试：

```powershell
python -m pytest tests/test_agent.py -k "p5_4 or p5_5" -q --basetemp .tmp-pytest
```

结果：

```text
5 passed, 86 deselected in 0.64s
```

完整回归：

```powershell
python -m pytest tests/test_agent.py -q --basetemp .tmp-pytest
```

结果：

```text
91 passed in 9.52s
```

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 | 证据 |
|---|---|---|---|---|---|
| 1 | `round-robin-arbiter` 可生成 target 级中文 `design_spec.md/html` | `tests/test_agent.py::test_p5_4_generate_design_spec_from_round_robin_target_config` | unit | PASS | `5 passed, 86 deselected` |
| 2 | CLI `--generate-spec round-robin-arbiter` 可生成 Markdown 与 HTML | `tests/test_agent.py::test_p5_4_cli_generate_spec_creates_markdown_and_html` | integration | PASS | `5 passed, 86 deselected` |
| 3 | `round-robin-arbiter` 可从 scenario catalog 生成 `verification_plan.md/html` | `tests/test_agent.py::test_p5_5_generate_verification_plan_from_scenario_catalog` | unit | PASS | `5 passed, 86 deselected` |
| 4 | CLI `--generate-verification-plan round-robin-arbiter` 可生成 Markdown 与 HTML | `tests/test_agent.py::test_p5_5_cli_generate_verification_plan_creates_markdown_and_html` | integration | PASS | `5 passed, 86 deselected` |
| 5 | 规格与验证计划生成逻辑可复用于 `sync-fifo` | `tests/test_agent.py::test_p5_4_p5_5_sync_fifo_spec_and_plan_are_target_generic` | unit | PASS | `5 passed, 86 deselected` |
| 6 | 本次新增能力未破坏既有 P0-P5.3 流程 | `python -m pytest tests/test_agent.py -q --basetemp .tmp-pytest` | regression | PASS | `91 passed in 9.52s` |

## 实现范围

- 新增 target 规格 catalog fallback，覆盖：
  - `async-fifo`
  - `sync-fifo`
  - `round-robin-arbiter`
- 新增 scenario catalog 规范化入口，用于把 target 的场景转换为验证计划。
- 新增 `render_target_design_spec()` 与 `write_target_design_spec()`。
- 新增 `render_target_verification_plan()` 与 `write_target_verification_plan()`。
- 新增轻量 Markdown 到 HTML 渲染函数，输出中文为主、美观可读的 HTML 页面。
- 新增 CLI：
  - `--generate-spec TARGET`
  - `--generate-verification-plan TARGET`

## 产物路径

默认输出目录为 `outputs/<target>/reports/`：

```text
design_spec.md
design_spec.html
verification_plan.md
verification_plan.html
```

示例命令：

```powershell
python .trae/agent/agent.py --generate-spec round-robin-arbiter --output-dir outputs "生成一个 4 requester round-robin arbiter"
python .trae/agent/agent.py --generate-verification-plan round-robin-arbiter --output-dir outputs
```

## 经验沉淀

- target 级文档生成应优先读取 target 配置，缺字段时使用内置 fallback catalog，避免新目标一开始必须补齐全部元数据。
- 规格文档和验证计划要和 scenario catalog 绑定，防止文档写一套、testbench 场景跑另一套。
- HTML 报告继续保持中文为主，并提供清晰表格、卡片、响应式布局，方便直接评审。
- CLI 文档生成不需要启动 Vivado，也不依赖真实仿真，因此适合作为新 target 的第一步入口。
- Windows 环境下测试继续统一使用 `--basetemp .tmp-pytest`，避免本机 Temp 权限影响结果。

## 已知边界

- 当前 catalog fallback 写在 agent 内，后续可迁移到 `.trae/agent/targets/*.json` 的 `parameters/interfaces/scenarios/checks/artifacts/notes` 字段。
- 当前 HTML 渲染器是轻量实现，足够用于项目报告；若后续报告复杂度继续上升，可引入模板文件或统一 report renderer。
- P5.5 目前生成验证计划，不执行 UVM 或覆盖率闭环；覆盖率、SVA、约束随机仍属于后续 P5/P4 升级项。
