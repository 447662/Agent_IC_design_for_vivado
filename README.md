# Agent IC Design for Vivado

面向 Vivado 的数字 IC 前端设计 Agent。项目把需求分析、目标配置、RTL/TB 生成、Vivado/xsim 仿真、波形分析、覆盖率汇总和可审查报告组织为可重复的本地流程。

当前内置目标为 `async-fifo`、`sync-fifo` 和 `round-robin-arbiter`。默认产物写入 `outputs/<target>/`，每次目标流程都会更新 `artifacts.json`，记录命令、状态、工具信息和产物新鲜度。

## 安装

要求：

- Windows 或 Linux；Vivado 集成与 GUI 流程主要在 Windows 验证。
- Python 3.11 或 3.13。
- `uv`，用于按 `uv.lock` 创建可复现环境。
- Git。

在仓库根目录执行：

```powershell
uv sync --frozen --group dev
uv run digital-ic-agent --list-targets
```

也可以直接运行源码入口：

```powershell
uv run python .trae/agent/agent.py --list-targets
```

安装验证：

```powershell
uv run digital-ic-agent --diagnostic
uv run digital-ic-agent --environment-report --output-dir outputs
```

`--diagnostic` 输出当前能力检查；`--environment-report` 生成 `outputs/environment-report/environment_report.md`、HTML 报告和独立 manifest。

## 快速开始

不依赖 Vivado 的基础流程：

```powershell
uv run digital-ic-agent --list-skills
uv run digital-ic-agent --list-targets
uv run digital-ic-agent --generate-rtl async-fifo --output-dir outputs
uv run digital-ic-agent --check-rtl async-fifo --output-dir outputs
```

生成的 async FIFO 工程包含 RTL、testbench、Vivado Tcl、报告目录和运行清单：

```text
outputs/async-fifo/
  rtl/async_fifo.v
  tb/tb_async_fifo.v
  sim/
  uvm/
  vivado_project/
  reports/
  artifacts.json
  README.md
```

检测到 Vivado 后，可运行真实仿真：

```powershell
uv run digital-ic-agent --sim-rtl async-fifo --no-wave-gui --output-dir outputs
uv run digital-ic-agent --analyze-rtl-vcd async-fifo --output-dir outputs
uv run digital-ic-agent --generate-overview --output-dir outputs
```

批量或 CI 环境建议始终加 `--no-wave-gui`。需要人工查看波形时，再执行 `--open-wave` 或 `--open-uvm-wave`。

## 能力矩阵

| 能力 | async-fifo | sync-fifo | round-robin-arbiter | 主要证据 |
| --- | --- | --- | --- | --- |
| 目标配置与规格生成 | 支持 | 支持 | 支持 | `targets/*.json`、`reports/design_spec.*` |
| RTL/TB/Vivado Tcl 生成 | 支持 | 支持 | 支持 | `rtl/`、`tb/`、`sim/` |
| Vivado/xsim 仿真 | 支持 | 支持 | 支持 | VCD、WDB、XPR、仿真报告 |
| VCD 自动分析 | 支持 | 支持 | 支持 | 握手、边界或公平性摘要 |
| RTL 自检与报告 | 支持 | 支持 | 支持 | `reports/`、`artifacts.json` |
| 参数回归 | 支持 | 不适用 | 不适用 | `regression_summary.md/html` |
| UVM smoke 与覆盖率 | 支持 | 不适用 | 不适用 | UVM 日志、WDB、coverage DB |
| GUI 波形入口 | 支持 | 支持 | 支持 | WDB、WCFG、Vivado GUI Tcl |
| 多目标总览 | 支持 | 支持 | 支持 | `outputs/index.md/html` |

通用能力：

- `--generate-spec TARGET`：从目标元数据和需求生成设计规格 Markdown/HTML。
- `--generate-verification-plan TARGET`：生成场景、检查点、覆盖率和退出准则。
- `--coverage-closure`：聚合目标覆盖率、阈值、差距和建议场景。
- `--verify-waveform-samples`：验证 VCD/FST/GHW 样例矩阵。
- `--create-target NAME`：生成候选 target 配置、RTL/TB、报告占位和 TODO；不会覆盖现有目录。
- `--generate-overview`：聚合环境与各目标 manifest，生成统一入口。

## Vivado 要求

项目不会依赖硬编码的本机 Vivado 路径。命令发现顺序为：

1. Agent 显式配置的命令。
2. `DIGITAL_IC_AGENT_VIVADO`。
3. `VIVADO_PATH`。
4. `PATH` 中的 `vivado`。

PowerShell 示例：

```powershell
$env:DIGITAL_IC_AGENT_VIVADO = "D:\vivado\2025.2\Vivado\bin\vivado.bat"
uv run digital-ic-agent --environment-report --output-dir outputs
uv run digital-ic-agent --sim-rtl sync-fifo --no-wave-gui --output-dir outputs
```

Vivado/xsim 验收关注以下真实证据：

- 命令输出包含可识别的 `Vivado vYYYY.N` 版本横幅。
- 仿真日志包含目标对应的 PASS 标志。
- VCD、WDB 和 XPR 文件存在且非空。
- `artifacts.json` 中本次运行状态为 `PASS`，产物未标记为 stale。

Vivado GUI 通过 WDB 打开波形；VCD 保留给自动分析器。GUI 打开但波形为空时，应检查生成的 WCFG 是否包含关键信号，而不是尝试用 `open_wave_database` 直接打开 VCD。

## 常用流程

### 诊断与目标发现

```powershell
uv run digital-ic-agent --diagnostic
uv run digital-ic-agent --environment-report --output-dir outputs
uv run digital-ic-agent --list-targets
uv run digital-ic-agent --list-skills
```

### 规格与验证计划

```powershell
uv run digital-ic-agent --generate-spec round-robin-arbiter --output-dir outputs "4 requester round-robin arbiter"
uv run digital-ic-agent --generate-verification-plan round-robin-arbiter --output-dir outputs
```

### RTL 闭环

```powershell
uv run digital-ic-agent --generate-rtl sync-fifo --output-dir outputs
uv run digital-ic-agent --sim-rtl sync-fifo --no-wave-gui --output-dir outputs
uv run digital-ic-agent --analyze-rtl-vcd sync-fifo --output-dir outputs
uv run digital-ic-agent --check-rtl sync-fifo --output-dir outputs
```

### async FIFO 回归与 UVM

```powershell
uv run digital-ic-agent --regress-rtl async-fifo --output-dir outputs
uv run digital-ic-agent --uvm-smoke async-fifo --no-wave-gui --output-dir outputs
uv run digital-ic-agent --uvm-coverage async-fifo --no-wave-gui --output-dir outputs
uv run digital-ic-agent --uvm-random-regress async-fifo --uvm-seeds 11,22,33 --no-wave-gui --output-dir outputs
```

可选覆盖率门槛：

```powershell
uv run digital-ic-agent --uvm-coverage async-fifo --coverage-threshold 80 --output-dir outputs
uv run digital-ic-agent --coverage-closure --coverage-target 80 --output-dir outputs
```

### 波形分析

```powershell
uv run digital-ic-agent --analyze-waveform tests/fixtures/waveforms/handshake_trace.vcd
uv run digital-ic-agent --analyze-waveform tests/fixtures/waveforms/handshake_trace.fst --wave-backend rwave
uv run digital-ic-agent --analyze-vcd path/to/wave.vcd --vcd-condition "tb.valid=1,tb.ready=1" --vcd-show "tb.data"
uv run digital-ic-agent --verify-waveform-samples --output-dir outputs
```

`--wave-backend auto` 优先使用 RWaveAnalyzer；VCD 可降级到 VCD_ANALYZER。FST/GHW 不能降级为 VCD 解析器。

### 创建新目标候选

```powershell
uv run digital-ic-agent --create-target packet_router --output-dir outputs "Configurable packet router target"
```

生成器只创建候选目录。完成目标配置、handler、RTL、testbench 和验收清单后，才能把它接入正式注册表。

## 质量证据

本地完整门禁：

```powershell
$env:UV_CACHE_DIR = ".tmp\uv-cache"
$env:PYTHONDONTWRITEBYTECODE = "1"
uv run --frozen ruff check .trae/agent tests src/digital_ic_agent scripts
uv run --frozen mypy
uv run --frozen pytest tests --junitxml .tmp/pytest-results.xml --cov=src/digital_ic_agent --cov-report=term-missing --cov-report=xml:coverage.xml --basetemp .tmp-pytest -p no:cacheprovider
```

质量证据由以下脚本从 JUnit XML、coverage XML 和测试目录生成：

```powershell
uv run --frozen python scripts/generate_quality_summary.py --junitxml .tmp/pytest-results.xml --coverage-xml coverage.xml --readme README.md --output-dir docs/generated --write-readme
uv run --frozen python scripts/generate_agent_eval_report.py --eval-cases tests/fixtures/agent_eval_cases.json --output-dir docs/generated
uv run --frozen python scripts/generate_test_module_report.py --tests-dir tests --line-limit 1000 --output-dir docs/generated
```

详细产物：

- `docs/generated/quality_summary.md`
- `docs/generated/capability_matrix.md`
- `docs/generated/agent_eval_report.md/json`
- `docs/generated/test_module_report.md/json`

<!-- digital-ic-agent:quality:start -->
## 自动质量摘要

此区块由生成器维护；本地样例运行仅用于验证格式，正式数值以最新 CI 全量产物为准。

Generated by `python scripts/generate_quality_summary.py` from JUnit XML and coverage XML artifacts.

| Metric | Value |
| --- | ---: |
| Data scope | CI full quality artifact |
| Test result | PASS |
| Pytest total | 501 |
| Line coverage | 90.3% |
| Branch coverage | 80.3% |
| Routing evaluation cases | 60 |
| Additional agent evaluation cases | 10 |
| Capability synthpilot | WARN (optional; degraded-only; source FAIL; captured 2026-07-13T10:27:10Z) |
<!-- digital-ic-agent:quality:end -->

## 故障排查

### `uv sync --frozen` 报锁文件不一致

不要直接忽略 `--frozen`。先确认 `pyproject.toml` 与 `uv.lock` 是否来自同一变更集；依赖确需变更时，重新生成锁文件并审查差异。

### 找不到 Vivado

```powershell
$env:DIGITAL_IC_AGENT_VIVADO = "D:\vivado\2025.2\Vivado\bin\vivado.bat"
uv run digital-ic-agent --environment-report --output-dir outputs
```

不要把个人安装路径写入源代码。CI 的 Vivado job 需要带 `Windows` 和 `vivado` 标签的受控 self-hosted runner。

### 批量任务停在 GUI

对 `--sim-smoke`、`--sim-rtl`、`--uvm-smoke`、`--uvm-coverage` 和随机回归使用 `--no-wave-gui`。GUI 仅用于人工波形检查。

### FST/GHW 分析失败

确认已配置 `RWAVE_BIN` 或已构建 RWaveAnalyzer。FST/GHW 不会回退到只支持 VCD 的分析器。

### 产物显示 `STALE` 或 `INVALID`

重新运行对应 target flow，并检查 `outputs/<target>/artifacts.json` 中的输入摘要、工具版本和错误字段。损坏 manifest 会被明确标记，不应手工伪造为 PASS。

### Windows 测试临时目录或缓存权限错误

使用仓库内临时目录，并关闭字节码与 pytest cache provider：

```powershell
$env:UV_CACHE_DIR = ".tmp\uv-cache"
$env:PYTHONDONTWRITEBYTECODE = "1"
uv run --frozen pytest tests --basetemp .tmp-pytest -p no:cacheprovider
```

## 项目结构

```text
src/digital_ic_agent/       # 可安装公共包与核心运行时
src/digital_ic_agent/_runtime/ # 目标插件、adapter、内置元数据与 CLI 实现
.trae/agent/                # 兼容薄入口、配置元数据与启动脚本
.trae/skills/               # 数字 IC 设计与验证技能
tests/                      # 拆分后的单元、集成、架构与安全测试
scripts/                    # 质量证据生成器
docs/generated/             # 可再生质量报告
docs/testing/               # 已执行的 TDD 证据
outputs/                    # 本地运行产物，不作为源码入口
```

公共包和 `.trae/agent/agent.py` 兼容入口都直接导入 `digital_ic_agent._runtime`；运行时不再使用 legacy loader，也不会为加载内置模块修改 `sys.path`。外部 target 插件必须通过 manifest 显式声明为 `trusted-local`，并在独立子进程中运行，受 allowlist、输出根目录、读取边界、最小环境变量和命令拒绝策略约束。插件 metadata 将隔离方式标记为 `python-guarded-subprocess`、沙箱能力标记为 `none`；这些 Python 级防护仅用于降低可信本地插件的误用风险，不构成可运行不可信代码的操作系统安全沙箱。
