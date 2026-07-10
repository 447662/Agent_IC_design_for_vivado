# P4.6 GUI 可见性自动化 TDD 证据

## Source Plan

- `docs/roadmap/p4_future_upgrade_roadmap.md` 的 P4.6。
- 本轮按 ECC TDD 与验证闭环执行 RED、GREEN、静态检查、覆盖率和真实 Vivado GUI 验收。

## User Journeys

1. 作为 RTL 验证工程师，我希望 Agent 自动确认 WDB 已打开且 Scope、Object、Wave、Wave Config 非空，避免“GUI 打开但没有有效波形”。
2. 作为报告使用者，我希望保留 Vivado 窗口截图及像素指标，以便不依赖人工描述判断界面是否空白。
3. 作为 UVM 使用者，我希望 RTL WDB 与 UVM WDB 复用同一套探针和截图判定，而不是维护两套目标专用逻辑。
4. 作为 Agent 维护者，我希望失效的 latest WDB 指针不会覆盖仍然可用的 WDB 回退路径。

## RED Evidence

提交：

```text
7356f51a test: define P4.6 automated wave visibility
```

结果：

```text
8 failed, 164 deselected
```

预期失败：

- `.trae/agent/wave_visibility.py` 尚不存在。
- RTL/UVM GUI Tcl 尚未写运行时可见性探针。
- 截图脚本尚未输出窗口像素指标。
- 报告尚未合并运行时与截图状态。

## GREEN Evidence

提交：

```text
bdf2feee feat: add P4.6 automated wave visibility checks
a8d4bacb test: cover stale async fifo wave pointer
2ea2ae64 fix: ignore stale async fifo wave pointer
```

定向结果：

```text
10 passed, 164 deselected
wave_visibility.py 100.0%
```

静态检查：

```text
Ruff: All checks passed
Mypy: Success, 23 source files
```

## Task Report

| Task | Execution summary | Validation | Guarantee |
|---|---|---|---|
| 通用可见性判定 | 新增 `evaluate_wave_open_check()`，读取运行时探针和截图指标 | P4.6 定向单元测试 | 状态支持 `PASS`、`FAIL`、`PENDING`，并提供逐项诊断 |
| Vivado 运行时探针 | 新增 `render_wave_open_probe_tcl()`，统计 WDB、Scope、Object、Wave、Wave Config | RTL/UVM GUI Tcl 测试与真实 Vivado | GUI 打开后自动生成 JSON 证据 |
| 窗口截图指标 | 新增 `render_window_capture_script()`，捕获前台窗口并统计尺寸、采样像素、唯一颜色和非均匀比例 | PowerShell AST、单元测试、真实截图 | 空白或错误窗口可由指标自动拒绝 |
| RTL 报告集成 | `--check-rtl` 合并静态 WCFG、运行时探针和截图状态 | `wave_visibility.md/html` 与 `wave_screenshot.md/html` | 报告区分静态预检、运行时和截图状态 |
| UVM 报告集成 | smoke/coverage WDB 使用同一探针 schema 与截图指标 | UVM 报告单元测试 | 可见性逻辑不绑定 RTL WDB |
| 失效指针保护 | latest WDB 只有在目标文件存在时才覆盖回退路径 | stale pointer 回归测试与真实旧指针复现 | 不再因失效时间戳指针打开不存在的 WDB |

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result |
|---|---|---|---|---|
| 1 | 非空运行时探针和截图指标返回 PASS | `test_p4_6_wave_open_check_evaluates_runtime_and_screenshot_metrics` | unit | PASS |
| 2 | 空 Scope/Wave 或空白截图返回 FAIL | `test_p4_6_wave_open_check_rejects_empty_runtime_and_blank_screenshot` | unit | PASS |
| 3 | 缺失、损坏和非法 JSON 返回可诊断状态 | `test_p4_6_wave_open_check_handles_missing_corrupt_and_invalid_values` | unit | PASS |
| 4 | Tcl 探针和 PowerShell 捕获脚本不绑定具体 flow | `test_p4_6_wave_probe_and_capture_scripts_are_flow_agnostic` | unit | PASS |
| 5 | RTL 与 UVM GUI Tcl 注入运行时探针 | `tests/test_agent.py -k p4_6` | integration | PASS |
| 6 | latest 指针失效时使用存在的 WDB 回退路径 | `test_async_fifo_open_project_gui_ignores_stale_latest_wave_pointer` | regression | PASS |
| 7 | 捕获脚本可通过 PowerShell AST 解析 | PowerShell Parser | static | PASS |
| 8 | RTL/UVM GUI Tcl 可由 Vivado 2025.2 Tcl 解释器完整解析 | Vivado Tcl parse acceptance | integration | PASS |

## Real Vivado GUI Acceptance

真实验收流程：

1. 用 `--sim-rtl async-fifo --no-wave-gui` 生成与当前 RTL/TB 匹配的新 WDB。
2. 用 `--open-wave async-fifo` 打开 Vivado 2025.2 工程和最新 WDB。
3. 等待 `wave_open_check.json` 刷新。
4. 捕获 Vivado 前台窗口，生成 `wave_visibility.png` 和 `wave_screenshot_metrics.json`。
5. 用 `--check-rtl async-fifo` 刷新全部可见性报告并验证 WCFG 关键对象。

真实结果：

```text
WDB: async_fifo_smoke_20260710_221215.wdb
WdbOpened: True
ScopeCount: 35
ObjectCount: 57
WaveCount: 31
WaveConfigCount: 1
Screenshot: 1500x950
UniqueColors: 582
NonUniformRatio: 99.9946%
```

所有 RTL 检查项均为 `[OK]`，包括 WCFG 对象数和 async FIFO 关键对象完整性。

验收过程中还复现了一个真实环境问题：`latest_async_fifo_wdb.txt` 指向已删除的时间戳 WDB，而固定名 `async_fifo_smoke.wdb` 仍存在。实现已增加存在性判断；随后重新运行 RTL 仿真生成当前源码对应的新 WDB，验证关键测试台计数器和 DUT 状态信号可进入 WCFG。

## Full Validation

全量测试与覆盖率：

```powershell
$env:PYTHONPATH=(Resolve-Path '.tmp/test-deps-p4-5-cov').Path
$env:COVERAGE_FILE='.tmp/.coverage-p4-6-full'
python -m pytest -q tests --cov=.trae/agent --cov-report=term-missing --cov-fail-under=68 --basetemp .tmp/pytest-p4-6-full-cov
```

结果：

```text
181 passed in 15.61s
TOTAL 79.64%
wave_visibility.py 100.0%
```

静态检查：

```powershell
ruff check .
mypy
```

结果：

```text
All checks passed!
Success: no issues found in 23 source files
```

## Coverage and Known Gaps

- `wave_visibility.py` 定向覆盖率为 `100.0%`。
- 全量覆盖率为 `79.64%`，超过项目 `68%` 门槛。
- 真实 GUI 验收依赖可交互 Windows 桌面和前台窗口权限；无交互 CI 应保留 Tcl/JSON 单元与集成测试，将窗口截图验收放在具备桌面会话的 Windows runner。
- 截图指标用于判断窗口非空，不替代对具体波形时间区间、光标位置或信号值的语义断言；这些可作为后续精细 GUI 验收扩展。
- P4.7 工程 dashboard 与 P4 收尾复核均已完成；真实 GUI 自动验收仍保留为需要可交互 Windows runner 的持续集成扩展。
