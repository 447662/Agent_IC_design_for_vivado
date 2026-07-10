# P5.6/P5.9 元数据契约与 Adapter 拆分 TDD 记录

## 来源计划

本阶段承接 P5 通用数字 IC Agent 路线：

- P5.6：为 target 定义统一、严格、可扩展的能力元数据契约。
- P5.9：将 Report、Waveform、Vivado 外部工具逻辑从 `agent.py` 拆到独立 adapter。

没有使用单独的 `*.plan.md`；用户旅程和验收口径来自 `docs/roadmap/project_followup_backlog.md` 与 `docs/roadmap/p5_series_execution_record.md`。

## 用户旅程

- 作为 target 维护者，我希望每个目标都使用同一份 metadata schema，以便规格、验证计划、覆盖率和产物报告可以通用消费。
- 作为验证工程师，我希望能力状态只使用 `PASS/SKIP/N/A`，以便区分已通过、暂未执行和不适用。
- 作为项目维护者，我希望 Report、Waveform、Vivado 逻辑有独立边界，同时保留现有 CLI、测试和 monkeypatch 入口。
- 作为开发者，我希望 adapter 的错误、无效 JSON 和 fallback 路径被自动测试覆盖，避免工具异常被静默吞掉。

## RED 证据

RED checkpoint：

```text
41cf72a test: define P5.6 metadata and P5.9 adapter contracts
```

首次运行 P5.6/P5.9 契约测试时得到：

```text
4 failed
```

有效 RED 信号：

- target registry 尚未要求通用 metadata schema。
- 非法 capability status 尚未被拒绝。
- `.trae/agent/adapters/report.py`、`waveform.py`、`vivado.py` 尚不存在。
- `DigitalICAgent` 的报告、波形与 Vivado 方法尚未绑定到 adapter。

## GREEN 证据

定向测试：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-targeted-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests/test_agent.py tests/test_quality_config.py -k "p5_6 or p5_9" -q --basetemp $base
```

结果：

```text
6 passed, 110 deselected
```

完整回归：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-full-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests -q --basetemp $base
```

结果：

```text
116 passed in 11.34s
```

静态质量门：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
python -m ruff check .trae/agent tests
python -m mypy
```

结果：

```text
Ruff PASS
Success: no issues found in 11 source files
```

覆盖率：

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp-p5-quality-deps').Path
$base = '.tmp-p5-cov-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
python -X utf8 -m pytest tests --cov=.trae/agent --cov-report=term-missing --cov-fail-under=68 -q --basetemp $base
```

结果：

```text
116 passed
TOTAL 72.63%
```

Windows 临时目录说明：未指定 `--basetemp` 的一次复验因系统目录 `C:\Users\ycy123\AppData\Local\Temp\pytest-of-ycy123` 拒绝访问而出现 3 个 fixture setup error；这不是功能测试失败。改用仓库内唯一 `--basetemp` 后，同一组 6 项测试全部通过。

## 测试规格

| # | 保证项 | 测试文件或命令 | 类型 | 结果 | 证据 |
|---|---|---|---|---|---|
| 1 | 三个 target 暴露统一 parameters/interfaces/checks/scenario/coverage/artifact metadata | `tests/test_agent.py::test_p5_6_target_registry_exposes_common_capability_metadata` | unit | PASS | `6 passed, 110 deselected` |
| 2 | 非法 capability status 会在加载 target registry 时失败 | `tests/test_agent.py::test_p5_6_target_registry_rejects_invalid_capability_status` | unit | PASS | `6 passed, 110 deselected` |
| 3 | 规格与验证计划会展示 PASS/SKIP/N/A 能力状态 | `tests/test_agent.py::test_p5_6_spec_and_plan_surface_capability_statuses` | integration | PASS | `6 passed, 110 deselected` |
| 4 | `DigitalICAgent` 的目标方法由三个 adapter 模块提供 | `tests/test_agent.py::test_p5_9_adapter_modules_own_extracted_agent_methods` | architecture | PASS | `6 passed, 110 deselected` |
| 5 | RWave、batch JSON 的进程错误和无效 JSON 会产生明确异常 | `tests/test_agent.py::test_p5_9_waveform_adapter_reports_rwave_and_batch_errors` | unit | PASS | `6 passed, 110 deselected` |
| 6 | VCD_ANALYZER 错误和 auto fallback 失败会保留可诊断信息 | `tests/test_agent.py::test_p5_9_waveform_adapter_handles_vcd_and_fallback_errors` | unit | PASS | `6 passed, 110 deselected` |
| 7 | 三个 adapter 纳入 Mypy 检查范围 | `tests/test_quality_config.py`、`python -m mypy` | quality gate | PASS | `11 source files` |
| 8 | 全部既有 target、Vivado、UVM、报告流程保持回归兼容 | `python -X utf8 -m pytest tests -q` | regression | PASS | `116 passed` |

## 实现范围

P5.6：

- `target_registry.py` 新增对象列表、必填字段、唯一 ID、接口方向和状态枚举校验。
- `async_fifo.json`、`sync_fifo.json`、`round_robin_arbiter.json` 补齐统一 metadata。
- 删除 Python 内置 target fallback catalog，报告直接消费 target 配置。

P5.9：

- 新增 `.trae/agent/adapters/report.py`。
- 新增 `.trae/agent/adapters/waveform.py`。
- 新增 `.trae/agent/adapters/vivado.py`。
- Vivado smoke、target 仿真、UVM smoke/coverage 和 GUI 启动改为调用 adapter。
- `DigitalICAgent` 通过方法绑定保留兼容 API。

## 覆盖率与已知边界

- 项目整体覆盖率为 `72.63%`，满足当前 `68%` 门槛，但未达到通用 TDD 建议的 80%；本阶段新增 adapter 的覆盖率较高，未覆盖部分主要位于既有大型 target/UVM flow。
- `report.py`：`97.8%`。
- `waveform.py`：`97.1%`。
- `vivado.py`：`84.4%`。
- `target_registry.py`：`81.8%`。
- P5.6 的 `artifact_manifest` 是预期产物契约；运行时 manifest 生成属于 P5.8。
- P5.9 未拆分所有 target 专用流程，后续应按真实复用边界继续演进。

## 合并证据

- RED commit：`41cf72a test: define P5.6 metadata and P5.9 adapter contracts`。
- GREEN commit：实现和文档完成、全部质量门通过后创建。
- 不重写或压缩 RED checkpoint，便于后续审计测试先行证据。
