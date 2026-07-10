# 波形测试夹具

本目录固定保存 P5.12 的 VCD/FST/GHW 最小真实样例，用于验证 RWaveAnalyzer
作为三种格式的统一波形后端。

| 文件 | 格式 | 来源 | 许可或说明 |
|---|---|---|---|
| `handshake_trace.vcd` | VCD | `VCD_ANALYZER-main/.../verify/fixtures/handshake_trace.vcd` | 项目内既有测试夹具 |
| `handshake_trace.fst` | FST | `docs/tools_archive/RWaveAnalyzer-main/.../verify/fixtures/handshake_trace.fst` | 项目内 RWaveAnalyzer 归档夹具 |
| `time_test.ghw` | GHW | `ekiwi/wellen`, `wellen/inputs/ghdl/time_test.ghw` | 上游仓库为 BSD-3-Clause |

已用项目内构建的 `rwave.exe` 真实解析：

- VCD：3 个信号，`1ns` timescale，`0s - 30ns`
- FST：3 个信号，`1ns` timescale，`0s - 30ns`
- GHW：3 个信号，`1fs` timescale，`0s - 10ns`
