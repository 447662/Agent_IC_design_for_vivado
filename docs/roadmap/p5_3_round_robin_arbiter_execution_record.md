# P5.3 Round-Robin Arbiter 执行记录

## 阶段目标

P5.3 用 `round-robin-arbiter` 作为第三个 RTL 目标，验证当前 agent 不只适用于 FIFO 类数据通路，也能覆盖控制逻辑设计族。

本阶段目标是完成最小闭环：

- target registry 新增 `round-robin-arbiter`
- RTL/TB/Vivado Tcl 自动生成
- Vivado/xsim batch 仿真
- VCD grant/fairness 分析
- WDB GUI 波形打开
- 中文仿真报告与 TDD 证据沉淀

## 设计内容

`round_robin_arbiter` 当前为 4 路请求仲裁器：

- 输入：`clk`、`rst_n`、`req[3:0]`
- 输出：`grant[3:0]`、`grant_valid`
- 行为：grant 后轮转优先级指针；reset 后从 requester 0 开始；无请求时 grant 清零

testbench 覆盖：

- `single_request`
- `multiple_requests`
- `rotating_grant`
- `reset_recovery`
- `fairness_window`

## 已实现文件

- `.trae/agent/targets/round_robin_arbiter.json`
- `.trae/agent/agent.py`
- `tests/test_agent.py`
- `docs/testing/p5_3_round_robin_arbiter_target.tdd.md`
- `README.md`

## 验证结果

P5.3 定向测试：

```powershell
python -m pytest tests/test_agent.py -k "p5_3" -q --basetemp .tmp-pytest
```

结果：

```text
6 passed, 80 deselected
```

完整回归：

```powershell
python -m pytest tests/test_agent.py -q --basetemp .tmp-pytest
```

结果：

```text
86 passed in 9.21s
```

真实 Vivado 2025.2 仿真：

```powershell
python .trae/agent/agent.py --sim-rtl round-robin-arbiter --no-wave-gui --output-dir outputs
```

结果：

```text
Round-Robin Arbiter simulation completed
Generated VCD: outputs\round-robin-arbiter\sim\round_robin_arbiter_trace.vcd
Generated WDB: outputs\round-robin-arbiter\sim\round_robin_arbiter_smoke_20260709_230319.wdb
Vivado project: outputs\round-robin-arbiter\vivado_project\round_robin_arbiter_project.xpr
Simulation report: outputs\round-robin-arbiter\reports\sim_report.md
```

VCD 分析：

```powershell
python .trae/agent/agent.py --analyze-rtl-vcd round-robin-arbiter --output-dir outputs --vcd-limit 5
```

结果：

```text
Signals: 19
Backend: vcd_analyzer
Duration: 235ns
Grant events: 6
Fairness checkpoints: 6
```

GUI 波形：

```powershell
python .trae/agent/agent.py --open-wave round-robin-arbiter --output-dir outputs
```

结果：

```text
Vivado project GUI launched: outputs\round-robin-arbiter\vivado_project\round_robin_arbiter_project.xpr
Vivado waveform database: outputs\round-robin-arbiter\sim\round_robin_arbiter_smoke_20260709_230319.wdb
```

## 问题沉淀

- VCD_ANALYZER 的 condition 不能只写信号名，必须使用 `SIG=VAL`、`SIG==VAL` 或 `SIG!=VAL`。
- P5.3 初版 fairness 查询使用 `tb_round_robin_arbiter.scenario_id` 作为 condition，真实分析失败；已改为 `tb_round_robin_arbiter.grant_valid=1`，并通过 `--show` 保留 `scenario_id`。
- Windows 默认 pytest Temp 目录可能权限异常；本项目建议统一使用 `--basetemp .tmp-pytest`。
- GUI 波形入口继续使用 WDB，不直接打开 VCD。

## 后续建议

- P5.4：通用规格文档生成。
- P5.5：通用验证计划生成。
- P5 后续：把 round-robin arbiter 扩展为参数化 requesters 回归矩阵。
- P4/P5 升级池：为 arbiter 增加 SVA、coverage 和 bounded fairness 统计。
