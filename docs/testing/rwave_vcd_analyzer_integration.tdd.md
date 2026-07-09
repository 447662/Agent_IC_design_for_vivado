# RWaveAnalyzer / VCD_ANALYZER 深度整合 TDD 证据

## 范围

本阶段目标是把项目从单一 `VCD_ANALYZER-main` 调用升级为统一波形分析后端：

- 默认优先使用 RWaveAnalyzer 的 `rwave`。
- `rwave` 不存在或自动模式失败时降级到现有 `VCD_ANALYZER-main`。
- CLI 支持 `--wave-backend auto|rwave|vcd-analyzer`，便于调试、对照和回归。
- 现有 `--analyze-vcd`、`--smoke-loop`、`--sim-smoke`、`--analyze-rtl-vcd async-fifo` 均保持兼容。

## 工具盘点

| 工具 | 当前定位 | 关键能力 |
|---|---|---|
| RWaveAnalyzer / `rwave` | 新默认优先后端 | VCD/FST/GHW，JSON 输出，`info/list/dump/summary/snapshot/compare/search`，支持 batch |
| VCD_ANALYZER-main | 兼容降级后端 | VCD，JSON 输出，现有 async FIFO/握手分析路径稳定 |

最新 `RWaveAnalyzer-main.zip` 已在临时目录解压验证，`cargo build --release` 成功生成 `rwave.exe`，版本输出为：

```text
rwave 0.1.4
```

## RED 证据

新增后端选择测试后，在实现 `run_waveform_analyzer_json(..., backend=...)` 前，相关测试预期失败：

```powershell
python -m pytest tests/test_agent.py -q -k "waveform_analyzer or analyze_vcd or analyze_async_fifo_vcd or analyze_rtl_vcd or sim_smoke or smoke_loop" --basetemp .tmp-agent-output\pytest-wave-backend-cli
```

预期失败点：

```text
TypeError: run_waveform_analyzer_json() got an unexpected keyword argument 'backend'
```

## GREEN 证据

实现统一后端选择和 CLI 透传后运行：

```powershell
python -m pytest tests/test_agent.py -q -k "waveform_analyzer or analyze_vcd or analyze_async_fifo_vcd or analyze_rtl_vcd or sim_smoke or smoke_loop" --basetemp .tmp-agent-output\pytest-wave-backend-cli
```

结果：

```text
16 passed, 57 deselected
```

## 真实后端验证

使用最新 RWaveAnalyzer zip 临时构建出的 `rwave.exe` 执行：

```powershell
$env:RWAVE_BIN = "<临时构建目录>\target\release\rwave.exe"
python .trae/agent/agent.py --analyze-vcd VCD_ANALYZER-main\VCD_ANALYZER-main\verify\fixtures\handshake_trace.vcd --vcd-condition "valid=1,ready=1" --vcd-show data --vcd-limit 5
```

关键输出：

```text
Backend: rwave
命中数量: 2
0xaa
0x55
```

## 保证项

| # | 保证项 | 测试或命令 | 结果 |
|---|---|---|---|
| 1 | auto 模式优先调用 `rwave --json ...` | `test_waveform_analyzer_prefers_rwave_when_available` | PASS |
| 2 | auto 模式在无 `rwave` 时降级到 `vcd_analyzer.py --json ...` | `test_waveform_analyzer_falls_back_to_vcd_analyzer` | PASS |
| 3 | `--wave-backend vcd-analyzer` 可强制旧后端 | `test_waveform_analyzer_can_force_vcd_analyzer` | PASS |
| 4 | `--wave-backend rwave` 在缺少 rwave 时不会静默降级 | `test_waveform_analyzer_can_require_rwave` | PASS |
| 5 | async FIFO VCD 分析走统一后端入口 | `test_analyze_async_fifo_vcd_reports_write_and_read_handshakes` | PASS |
| 6 | CLI `--analyze-rtl-vcd` 能透传指定后端 | `test_cli_analyze_rtl_vcd_async_fifo_invokes_analyzer` | PASS |

## 后续

- 增加 `--wave-format` 或自动识别 FST/GHW 的端到端样例。
- 为 RWaveAnalyzer batch 模式增加一次加载、多查询的 async FIFO 分析路径。
- 将波形后端信息写入 `sim_summary.html` 和报告总览页，便于回溯每次仿真使用的分析器。
