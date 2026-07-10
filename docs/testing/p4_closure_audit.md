# P4 收尾发布审计

## Audit Result

P4 发布审计：`84/100`，可发布但有保留项。P4.0-P4.7 的本地测试、覆盖率、静态检查、UTF-8、文档证据和真实报告入口均通过；本轮按用户要求未观测 GitHub Actions，且真实 Vivado GUI 自动验收仍依赖可交互 Windows 桌面，因此评分封顶为 `84`。

## Blockers

- 无发布阻塞项。

## Fixed During Audit

真实 `outputs/index.html` 链接扫描发现 `3` 个断链：

- `environment-report/artifacts.json`
- `round-robin-arbiter/artifacts.json`
- `sync-fifo/artifacts.json`

根因是 `project_overview.py` 在 target/environment manifest 不存在时仍预填 href，Markdown/HTML 渲染层又无条件输出链接。

修复后的契约：

- manifest 存在时提供链接，包括 JSON 无效时的诊断入口。
- manifest 不存在时显示“manifest 尚未生成”，不生成 href。
- environment report 与 environment manifest 分别判断，不再用不存在的 manifest 作为报告回退链接。

## TDD Evidence

用户旅程：

1. 作为报告使用者，我希望尚未运行的 target 显示 NOT_RUN 和明确的缺失状态，而不是打开不存在的 manifest。
2. 作为环境预检使用者，我希望报告与 manifest 分别显示真实可用入口。
3. 作为维护者，我希望缺失、有效和无效 manifest 三种状态都被回归测试覆盖。

提交：

```text
c0cb3355 test: reject missing manifest links in project overview
87a89592 fix: avoid broken manifest links in project overview
f501fa35 test: require missing manifest status for overview targets
320db6a0 fix: render missing target manifests as status text
```

RED/GREEN：

```text
RED: 1 failed
GREEN: 1 passed
Related overview/dashboard tests: 5 passed, 171 deselected
```

## Evidence Checked

- `git status --short --branch`
- `git log --oneline --decorate -20`
- `.github/workflows/python-quality.yml`
- `requirements-dev.txt`
- `.trae/agent/README.md`
- `.trae/agent/project_overview.py`
- `docs/roadmap/p4_future_upgrade_roadmap.md`
- `docs/roadmap/project_followup_backlog.md`
- `docs/roadmap/p5_general_digital_ic_agent_design.md`
- `docs/testing/p4_0_coverage_closure_dashboard.tdd.md` 至 `docs/testing/p4_7_report_dashboard.tdd.md`
- `tests/test_agent.py`
- `outputs/index.html`
- `outputs/coverage-closure/index.html`
- 已生成的 target `reports/index.html`

## Validation

P4 测试与文档：

```text
P4.0-P4.7 TDD evidence count: 1 each
Total explicitly named P4 tests: 31
Markdown relative links checked: 13 files; broken=0
Strict UTF-8 decode: PASS
```

代码质量：

```text
Ruff: All checks passed!
Mypy: Success, 23 source files
183 passed in 25.62s
TOTAL 80.22%
project_overview.py 90.9%
```

真实报告入口：

```text
Dashboard pages: 3
Relative links: 116
Broken links: 0
```

## High-Value Fixes

1. 增加具备桌面会话的 Windows runner，自动执行 Vivado Tcl、WDB 打开和 GUI 可见性验收。
2. 将 dashboard 相对链接扫描固化为自动测试或 CI 检查，避免生成物入口回归。
3. 为 gzip JSONL 归档增加按大小/日期分卷、恢复和合并工具。

## Evidence Missing

- 本轮按要求未观测 GitHub Actions 运行结果。
- 本轮未重新启动 Vivado GUI；真实 WDB/GUI 证据沿用 P4.6 已记录的 Vivado 2025.2 验收。
- 浏览器直接访问本地 `file://` 页面受安全策略限制，因此未生成浏览器截图。

## Next Action

P4 基线已冻结，artifact/history rotation 已按 TDD 完成。下一项建议实现 Windows/Vivado 自动验收，并将 dashboard 相对链接扫描固化到 CI。

## Post-Audit Follow-Up

Artifact/history rotation 已完成：

```text
446c717b test: define artifact and history rotation behavior
ef265ad2 feat: add compressed artifact and history rotation
3 passed, 176 deselected
13 passed, 166 deselected
186 passed in 18.80s
TOTAL 80.55%
history_rotation.py 90.9%
Ruff: All checks passed!
Mypy: Success, 24 source files
```

详细证据见 `docs/testing/artifact_history_rotation.tdd.md`。
