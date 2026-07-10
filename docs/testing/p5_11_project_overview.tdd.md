# P5.11 多 Target 项目总览 TDD 记录

## 用户旅程

1. 作为首次运行 Agent 的用户，我希望总览列出全部注册 target，即使尚未生成任何产物，也能看到明确的 `NOT_RUN` 状态。
2. 作为项目维护者，我希望在一个顶层页面看到每个 target 的最近 flow、状态、失败原因、重跑命令和常用报告入口。
3. 作为排障人员，我希望一个损坏的 manifest 只把对应 target 标记为 `INVALID`，而不会让整个 dashboard 无法生成。
4. 作为持续运行 flow 的用户，我希望 target 或环境 manifest 更新后自动刷新顶层总览，不需要手动同步。

## 初始 RED

先新增 6 个失败测试：

- 聚合两个 target、environment manifest、失败状态和报告链接。
- 空输出目录展示注册 target 的 `NOT_RUN`。
- 损坏 manifest 不阻断其他 target。
- CLI 生成空项目总览并返回 WARN/0。
- 输出路径不可写时返回 1 且不显示 traceback。
- `project_overview.py` 纳入 Mypy 范围。

执行结果：

```text
6 failed, 131 deselected
```

失败原因均为模块、CLI 和 Mypy 接入尚不存在。

RED 检查点：

```text
ad0bed6 test: define P5.11 project overview contract
```

## 初始 GREEN

新增 `.trae/agent/project_overview.py`：

- 合并注册表 target 与输出目录中发现的 manifest。
- 读取 target 最新 flow 状态与 environment 状态。
- 输出顶层 `index.md/html`。
- 生成 Spec、RTL、Simulation、UVM、Coverage、Wave、Lessons surface。
- 使用 PASS、FAIL、WARN、NOT_RUN、MISSING、INVALID 表达项目状态。

定向结果：

```text
6 passed, 131 deselected
```

完整回归：

```text
137 passed in 16.27s
Coverage total: 74.06%
project_overview.py: 81.2%
```

GREEN 提交：

```text
9e96903 feat: add P5.11 multi-target project overview
```

## 自动刷新补强

对照 P5 通用设计中的“每个 flow 成功或失败后刷新总览页”要求，新增两个集成测试：

- `--generate-rtl sync-fifo` 写入 target manifest 后自动生成顶层 index。
- `--environment-report` 写入 environment manifest 后自动生成顶层 index。

补强 RED：

```text
2 failed, 6 passed, 131 deselected
```

补强 GREEN：

```text
8 passed, 131 deselected
```

实现方式：

- `DigitalICAgent.record_artifact_run()` 在 P5.8 manifest 写入成功后刷新总览。
- `write_environment_report()` 写入 environment manifest 后调用同一刷新入口。
- 总览刷新失败只输出辅助诊断，不覆盖主 flow 的原始成功或失败结果。

补强提交：

```text
a64e1de refactor: refresh P5.11 overview after manifest updates
```

## 真实 CLI 验收

依次执行：

```powershell
python -X utf8 .trae/agent/agent.py --environment-report --output-dir .tmp-p5-11-smoke-output
python -X utf8 .trae/agent/agent.py --generate-rtl sync-fifo --output-dir .tmp-p5-11-smoke-output
python -X utf8 .trae/agent/agent.py --generate-spec round-robin-arbiter --output-dir .tmp-p5-11-smoke-output "生成一个 4 requester round-robin arbiter"
python -X utf8 .trae/agent/agent.py --generate-overview --output-dir .tmp-p5-11-smoke-output
```

结果：

- 总览状态 WARN。
- 注册目标数量 3。
- `sync-fifo`：PASS / `generate-rtl`。
- `round-robin-arbiter`：PASS / `generate-spec`。
- `async-fifo`：NOT_RUN。
- 环境状态 WARN，环境 HTML 与 manifest 链接正常。
- RTL、规格和 target README surface 链接使用输出根目录相对路径。

## 最终验证

```text
Ruff: All checks passed!
Mypy: Success: no issues found in 15 source files
Pytest: 139 passed in 17.92s
Coverage total: 74.39%
project_overview.py: 85.8%
```

## 保证项

| # | 保证 | 测试类型 | 结果 |
|---|---|---|---|
| 1 | 空项目仍列出所有注册 target，并显示 NOT_RUN | unit/integration | PASS |
| 2 | 最近 flow、FAIL 和错误信息进入 Markdown/HTML | unit | PASS |
| 3 | 七类统一报告 surface 使用相对链接 | unit | PASS |
| 4 | 损坏 manifest 只影响单个 target | unit | PASS |
| 5 | CLI 对 WARN 返回 0，对 FAIL 或写入错误返回 1 | integration | PASS |
| 6 | target/environment manifest 更新后自动刷新顶层 index | integration | PASS |
| 7 | 中文 Markdown/HTML 使用 UTF-8，无乱码 | unit/real CLI | PASS |
