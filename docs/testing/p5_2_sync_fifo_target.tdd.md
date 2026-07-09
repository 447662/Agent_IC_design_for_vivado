# P5.2 sync-fifo 目标 TDD 证据

## 来源计划

- P5 总体设计：`docs/roadmap/p5_general_digital_ic_agent_design.md`
- P5 系列执行记录：`docs/roadmap/p5_series_execution_record.md`

## 用户旅程

- 作为数字 IC 设计者，我希望在 `async-fifo` 之外注册第二个目标 `sync-fifo`，从而验证 target registry 不再只服务单一目标。
- 作为验证使用者，我希望运行 `--generate-rtl sync-fifo` 后得到 RTL、testbench 和 Vivado Tcl，从而快速建立可仿真的同步 FIFO 工程。
- 作为调试使用者，我希望 `--sim-rtl sync-fifo` 和 `--analyze-rtl-vcd sync-fifo` 能接入现有 Vivado/xsim 与 VCD/RWave 分析流程，从而形成 P5 的第二目标闭环。

## RED / GREEN 记录

### RED 1：目标注册与生成器缺失

命令：

```powershell
python -m pytest tests/test_agent.py -q -k "p5_2" --basetemp .tmp-agent-output\pytest-p5-2-red
```

结果摘录：

```text
3 failed, 74 deselected
FileNotFoundError: .trae\agent\targets\sync_fifo.json
ValueError: Unsupported RTL target: sync-fifo
```

### GREEN 1：注册、生成、CLI 生成通过

命令：

```powershell
python -m pytest tests/test_agent.py -q -k "p5_2" --basetemp .tmp-agent-output\pytest-p5-2-green-2
```

结果：

```text
3 passed, 74 deselected
```

### RED 2：仿真与 VCD 分析入口缺失

命令：

```powershell
python -m pytest tests/test_agent.py -q -k "p5_2" --basetemp .tmp-agent-output\pytest-p5-2-red-2
```

结果摘录：

```text
3 failed, 3 passed, 74 deselected
AttributeError: DigitalICAgent has no attribute 'open_sync_fifo_project_gui'
AttributeError: DigitalICAgent object has no attribute 'analyze_sync_fifo_vcd'
```

### GREEN 2：P5.2 最小闭环通过

命令：

```powershell
python -m pytest tests/test_agent.py -q -k "p5_2" --basetemp .tmp-agent-output\pytest-p5-2-green-4
```

结果：

```text
6 passed, 74 deselected
```

### 相关回归

命令：

```powershell
python -m pytest tests/test_agent.py -q -k "p5 or sync_fifo or analyze_rtl_vcd or sim_rtl" --basetemp .tmp-agent-output\pytest-p5-2-target-2
```

结果：

```text
47 passed, 33 deselected
```

### 真实 Vivado 2025.2 验收

命令：

```powershell
python .trae/agent/agent.py --sim-rtl sync-fifo --no-wave-gui --output-dir outputs
```

结果摘录：

```text
Sync FIFO simulation completed
Generated VCD: outputs\sync-fifo\sim\sync_fifo_trace.vcd
Generated WDB: outputs\sync-fifo\sim\sync_fifo_smoke_20260709_224327.wdb
Vivado project: outputs\sync-fifo\vivado_project\sync_fifo_project.xpr
Simulation report: outputs\sync-fifo\reports\sim_report.md
```

VCD 分析命令：

```powershell
python .trae/agent/agent.py --analyze-rtl-vcd sync-fifo --output-dir outputs --vcd-limit 5 --wave-backend auto
```

结果摘录：

```text
Sync FIFO VCD analysis
Signals: 26
Backend: vcd_analyzer
Duration: 915ns
Write handshakes: 6
Read handshakes: 6
```

GUI 波形命令：

```powershell
python .trae/agent/agent.py --open-wave sync-fifo --output-dir outputs
```

结果摘录：

```text
Vivado project GUI launched: outputs\sync-fifo\vivado_project\sync_fifo_project.xpr
Vivado waveform database: outputs\sync-fifo\sim\sync_fifo_smoke_20260709_224327.wdb
```

真实 Vivado 修复记录：

- `run_vivado_sync_fifo.tcl` 起初裸调用 `xvlog/xelab/xsim`，Vivado Tcl 报 `invalid command name "xvlog"`；已改为与 async FIFO 一致的 `exec xvlog` / `exec xelab` / `exec xsim`。
- `create_sync_fifo_project.tcl` 起初未套用 TclStore bootstrap，遇到本机 TclStore 初始化异常；已复用 async FIFO 的 `render_vivado_tclstore_bootstrap()`。
- Vivado 2025.2 下 `save_project` 被解析成缺少 `name` 的保存命令；已对齐 async FIFO 的做法，工程创建脚本使用 `close_project` + `exit 0`。

## 保证项

| # | 保证项 | 测试或命令 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | registry 可加载 `sync-fifo` 元信息和别名 | `test_p5_2_target_registry_lists_sync_fifo_metadata` | 单元 | PASS |
| 2 | `sync-fifo` 可生成 RTL/TB/Vivado Tcl/README/reports 目录 | `test_p5_2_generate_sync_fifo_project_creates_rtl_tb_sim_reports` | 单元 | PASS |
| 3 | CLI `--generate-rtl sync-fifo` 输出目标相关文件路径 | `test_p5_2_cli_generate_rtl_sync_fifo_creates_project` | 集成 | PASS |
| 4 | `run_sync_fifo_vivado_sim()` 能运行 Vivado batch、生成 VCD/WDB/工程和报告 | `test_p5_2_run_sync_fifo_vivado_sim_creates_project_and_can_skip_gui` | 集成 | PASS |
| 5 | `analyze_sync_fifo_vcd()` 能报告写/读 handshake | `test_p5_2_analyze_sync_fifo_vcd_reports_write_and_read_handshakes` | 单元 | PASS |
| 6 | CLI `--analyze-rtl-vcd sync-fifo` 能分发到 sync FIFO 分析器 | `test_p5_2_cli_analyze_rtl_vcd_sync_fifo_invokes_analyzer` | 集成 | PASS |
| 7 | 真实 Vivado 2025.2 可完成 sync FIFO batch 仿真并生成 VCD/WDB/工程 | `--sim-rtl sync-fifo --no-wave-gui` | 真实工具 | PASS |
| 8 | 真实 sync FIFO VCD 可被统一分析入口解析出读写事件 | `--analyze-rtl-vcd sync-fifo` | 真实工具 | PASS |
| 9 | Vivado GUI 可打开 sync FIFO 工程和 WDB 波形 | `--open-wave sync-fifo` | 真实工具 | PASS |

## 已知缺口

- P5.2 当前先完成 RTL/TB/Vivado/VCD/report 最小闭环，暂不包含 UVM、coverage closure、多 seed 回归。
- GUI 波形已经能打开工程和 WDB；自动截图/像素级非空验收仍属于后续 P4 GUI 自动验收增强。
