# P5.12 RWave FST/GHW 统一波形样例 TDD 证据

## 范围

P5.12 用三个最小真实波形样例验证统一后端：

| 格式 | 文件 | 来源 |
|---|---|---|
| VCD | `tests/fixtures/waveforms/handshake_trace.vcd` | 项目内 VCD_ANALYZER 测试夹具 |
| FST | `tests/fixtures/waveforms/handshake_trace.fst` | 项目内 RWaveAnalyzer 归档夹具 |
| GHW | `tests/fixtures/waveforms/time_test.ghw` | `ekiwi/wellen` BSD-3-Clause 测试夹具 |

## RED

先提交失败测试 `441bb05 test: define P5.12 unified waveform contract`。

```powershell
python -m pytest tests/test_agent.py -q -k "p5_12" --basetemp .tmp-agent-output/pytest-p5-12-red-clean
```

预期结果：

```text
9 failed, 132 deselected
```

失败点覆盖：

- CLI 尚无 `--analyze-waveform`。
- CLI 尚无 `--verify-waveform-samples`。
- FST/GHW 的 `auto` 模式错误降级到 VCD_ANALYZER。
- `DigitalICAgent` 尚无通用 `analyze_waveform()`。
- 尚无格式矩阵报告模块和 Mypy 配置。

## GREEN

实现提交：`fbd00a9 feat: add P5.12 unified waveform samples`。

```powershell
python -m pytest tests/test_agent.py -q -k "p5_12" --basetemp .tmp-agent-output/pytest-p5-12-green
```

结果：

```text
9 passed, 132 deselected
```

波形相关兼容回归：

```powershell
python -m pytest tests/test_agent.py -q -k "p5_12 or waveform_analyzer or analyze_vcd or rwave_batch or smoke_loop" --basetemp .tmp-agent-output/pytest-p5-12-wave-regression
```

结果：

```text
17 passed, 124 deselected
```

## 后端规则

| 输入格式 | `auto` | `rwave` | `vcd-analyzer` |
|---|---|---|---|
| VCD | 优先 RWave，失败可降级 | 强制 RWave | 强制旧 VCD 分析器 |
| FST | 强制 RWave，失败明确报错 | 强制 RWave | 拒绝，旧后端仅支持 VCD |
| GHW | 强制 RWave，失败明确报错 | 强制 RWave | 拒绝，旧后端仅支持 VCD |

## 真实 RWave 验收

```powershell
$env:RWAVE_BIN = (Resolve-Path "docs/tools_archive/RWaveAnalyzer-main/RWaveAnalyzer-main/target/release/rwave.exe").Path
python .trae/agent/agent.py --analyze-waveform tests/fixtures/waveforms/handshake_trace.fst
python .trae/agent/agent.py --analyze-waveform tests/fixtures/waveforms/time_test.ghw
python .trae/agent/agent.py --verify-waveform-samples --output-dir .tmp-agent-output/p5-12-real
```

结果：

| 格式 | 状态 | 后端 | 信号数 | Timescale | 时间范围 |
|---|---|---|---:|---|---|
| VCD | PASS | rwave | 3 | 1ns | 0s - 30ns |
| FST | PASS | rwave | 3 | 1ns | 0s - 30ns |
| GHW | PASS | rwave | 3 | 1fs | 0s - 10ns |

报告：

```text
.tmp-agent-output/p5-12-real/waveform-samples/format_matrix.md
.tmp-agent-output/p5-12-real/waveform-samples/format_matrix.html
```

## 静态检查

```powershell
python -m ruff check .trae/agent tests/test_agent.py
python -m mypy
```

结果：Ruff 与 Mypy 均通过，Mypy 检查 16 个源文件。

## 全量回归

```powershell
$env:PYTHONPATH = (Resolve-Path ".tmp-p5-cov-deps").Path
python -X utf8 -m pytest tests --cov=.trae/agent --cov-report=term-missing --cov-fail-under=68 --basetemp .tmp-agent-output/pytest-p5-12-full-cov
```

结果：

```text
148 passed in 18.83s
TOTAL 2870 statements, 74.91% coverage
Required test coverage of 68% reached
```
