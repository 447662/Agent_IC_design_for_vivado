# P5.4/P5.5 通用规格与验证计划执行记录

## 阶段目标

P5.4/P5.5 的目标是把当前 agent 从“能生成/仿真几个 RTL target”推进到“能为任意数字 IC target 生成前置设计文档与验证计划”。

本阶段完成两类通用产物：

- P5.4：`design_spec.md/html`
- P5.5：`verification_plan.md/html`

## 已实现能力

### P5.4 通用规格文档生成

新增命令：

```powershell
python .trae/agent/agent.py --generate-spec round-robin-arbiter --output-dir outputs "生成一个 4 requester round-robin arbiter"
```

默认生成：

```text
outputs/round-robin-arbiter/reports/design_spec.md
outputs/round-robin-arbiter/reports/design_spec.html
```

文档内容包括：

- target 名称、显示名、设计族、描述
- 自然语言需求
- 参数定义
- 接口定义
- 功能场景
- 关键检查点
- 预期产物
- 备注

### P5.5 通用验证计划生成

新增命令：

```powershell
python .trae/agent/agent.py --generate-verification-plan round-robin-arbiter --output-dir outputs
```

默认生成：

```text
outputs/round-robin-arbiter/reports/verification_plan.md
outputs/round-robin-arbiter/reports/verification_plan.html
```

验证计划内容包括：

- target 概览
- scenario catalog
- 检查点与断言建议
- 验证执行顺序
- 出口准则

## 当前覆盖的 target

本阶段 fallback catalog 覆盖三个已注册目标：

| Target | 设计族 | 文档能力 |
|---|---|---|
| `async-fifo` | FIFO | 规格文档、验证计划 |
| `sync-fifo` | FIFO | 规格文档、验证计划 |
| `round-robin-arbiter` | Arbiter | 规格文档、验证计划 |

## 验证结果

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

## 设计决策

- 目标配置优先：如果 target JSON 后续补充 `parameters/interfaces/scenarios/checks/artifacts/notes`，生成器会优先读取配置。
- fallback catalog 保底：当前三个已知目标即使没有扩展 metadata，也能生成规格和验证计划。
- Markdown 与 HTML 同步输出：Markdown 便于版本管理，HTML 便于浏览和评审。
- 文档生成不启动 Vivado：P5.4/P5.5 是前置规划能力，不依赖仿真环境，适合在新 target 设计启动时先运行。

## 对 P5 后续的意义

P5 后续目标是让 agent 普遍用于数字 IC 设计。P5.4/P5.5 让新增 target 的标准流程变为：

1. 新增 target 配置。
2. 生成 `design_spec.md/html`。
3. 生成 `verification_plan.md/html`。
4. 生成 RTL/TB/Vivado Tcl。
5. 运行 Vivado/xsim 仿真。
6. 打开 Vivado GUI 查看 WDB 波形。
7. 生成 VCD/RWave 分析报告与总览报告。

## 后续建议

- 将 fallback catalog 逐步迁移到 target JSON，形成完全配置驱动的 P5 target registry。
- 为 `round-robin-arbiter` 增加参数化 requester 数量，并让 scenario catalog 随参数变化。
- 给 `verification_plan` 增加覆盖率目标字段，为后续 UVM、SVA、functional coverage 做准备。
- 增加 `--generate-all-docs TARGET`，一次生成规格、验证计划和报告索引。
- 在 reports index 中自动链接 `design_spec.html` 与 `verification_plan.html`。
