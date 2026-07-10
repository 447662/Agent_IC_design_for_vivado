# P5.10 环境预检报告 TDD 记录

## 目标

为数字 IC Agent 增加独立中文环境预检入口，在运行 Vivado、波形分析或 GUI flow 前集中暴露工具、权限和桌面条件：

- Python 版本与解释器。
- Git 命令与版本。
- Vivado 命令与版本横幅。
- RWave 命令或 VCD_ANALYZER fallback。
- 输出目录创建/写入权限。
- Windows 交互会话或 Linux GUI 显示环境。

输出固定为 `outputs/environment-report/environment_report.md`、`environment_report.html` 和项目级 `artifacts.json`。

## RED

先新增 5 个失败测试：

1. 全部环境项可用时生成中文 Markdown、HTML 和 environment manifest。
2. Vivado、RWave 和 GUI 缺失时输出 WARN 与中文修复建议，但不崩溃。
3. 输出根路径是文件、无法创建目录时抛出 `OSError`。
4. CLI 捕获输出错误，返回 1 且不打印 traceback。
5. `environment_report.py` 纳入 Mypy 范围。

执行结果：

```text
5 failed, 125 deselected
```

失败原因符合预期：模块、CLI 参数和 Mypy 配置尚不存在。

RED 检查点提交：

```text
9273ac5 test: define P5.10 environment report contract
```

## GREEN

新增 `.trae/agent/environment_report.py`，并通过方法绑定接入 `DigitalICAgent`：

- `collect_environment_checks()` 统一收集六类检查项。
- `render_environment_markdown()` 输出中文状态表和修复建议。
- 复用通用 Markdown HTML renderer 生成 UTF-8 HTML。
- `write_environment_manifest()` 使用 `scope: environment` 记录运行历史。
- `--environment-report` 对 PASS/WARN 返回 0，对 FAIL 或写入错误返回 1。
- 输出权限检查前置，避免目录不可写时继续调用外部工具。

初始 GREEN：

```text
5 passed, 125 deselected
```

真实 CLI 冒烟发现 Vivado 2025.2 会输出有效版本横幅，但 `-version` 返回码可能非零。新增回归测试，先复现：

```text
1 failed, 124 deselected
```

随后改为识别 `Vivado vYYYY.N` 版本横幅，保留无有效输出时的 WARN：

```text
6 passed, 125 deselected
```

GREEN 实现提交：

```text
9f3cd36 feat: add P5.10 environment preflight reports
```

## 设计决策

- 环境预检不属于任何 RTL target，因此不复用带 `target` 强约束的 P5.8 manifest。
- 项目级 manifest 放在 `outputs/environment-report/artifacts.json`，使用 `scope: environment`，避免伪造 target。
- Vivado、RWave 和 GUI 缺失允许降级为 WARN；Python 或 Git 基础条件不满足为 FAIL。
- RWave 缺失但仓库内 VCD_ANALYZER fallback 存在时判定 PASS。
- 所有 Markdown、HTML 和 JSON 使用 UTF-8，JSON 使用 `ensure_ascii=False`。

## 最终验证

```text
Ruff: All checks passed!
Mypy: Success: no issues found in 14 source files
Pytest: 131 passed in 14.61s
Coverage total: 73.61%
environment_report.py: 73.7%
```

真实 CLI：

```powershell
python -X utf8 .trae/agent/agent.py --environment-report --output-dir .tmp-p5-10-smoke-output
```

当前机器结果为 WARN：Python、Git、Vivado、VCD_ANALYZER fallback 和输出权限均 PASS，仅运行进程未暴露交互式 Windows 会话标记，因此 GUI 前置条件为 WARN。Markdown、HTML 和 environment manifest 均成功生成，中文无乱码。
