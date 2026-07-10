# P4.7 工程报告 Dashboard TDD 证据

## Source Plan

- `docs/roadmap/p4_future_upgrade_roadmap.md` 的 P4.7。
- 本轮按 ECC TDD 与验证闭环执行 RED、GREEN、断链回归、全量测试、静态检查和 dashboard 静态验收。

## User Journeys

1. 作为数字 IC 工程师，我希望从单个 target 的报告首页快速看到 Spec、RTL、Simulation、UVM、Coverage、Wave、Lessons 七个阶段的状态和入口。
2. 作为回归维护者，我希望报告展示最近运行、最近失败、重跑命令和失败归档，不需要翻阅多层日志目录。
3. 作为多 target 使用者，我希望在各 target 之间切换；目标 dashboard 尚未生成时，也不会进入不存在的页面。
4. 作为报告阅读者，我希望工程资源列表保留官方 coverage dashboard，但不展开大量 xcrg 内部明细页。
5. 作为中文环境使用者，我希望 Markdown/HTML 保持 UTF-8，并能区分文件编码问题与终端代码页显示问题。

## RED Evidence

提交：

```text
bae92992 test: define P4.7 report dashboard behavior
```

初始结果：

```text
3 failed, 173 deselected
```

预期失败：

- `write_target_dashboard()` 尚不存在。
- 报告首页尚未提供七阶段卡片、目标选择、最近运行和失败入口。
- 未运行 target 尚无明确的 NOT_RUN 降级状态。

目标导航断链回归：

```text
1 failed, 2 passed
```

失败原因：其他 target 的 `reports/index.html` 尚未生成时，目标选择器仍直接链接到不存在的页面。

## GREEN Evidence

提交：

```text
830fd3f6 feat: add P4.7 engineering report dashboard
41b2772c fix: harden P4.7 dashboard navigation
```

最终定向结果：

```text
3 passed, 173 deselected
```

文档收尾定向复核：

```text
4 passed, 172 deselected
```

静态检查：

```text
Ruff: All checks passed!
Mypy: Success, 23 source files
```

## Task Report

| Task | Execution summary | Validation | Guarantee |
|---|---|---|---|
| 通用 target dashboard | `project_overview.py` 新增 `write_target_dashboard()` | P4.7 定向测试与真实输出 | 报告逻辑不绑定 async FIFO |
| 七阶段状态 | 固定聚合 Spec、RTL、Simulation、UVM、Coverage、Wave、Lessons | 阶段卡片断言 | 每个 target 使用一致的信息架构 |
| 最近运行与最近失败 | 从 `artifacts.json` 读取最近记录、错误和命令 | manifest fixture 与 HTML/Markdown 断言 | 可从首页定位当前状态和失败原因 |
| 失败归档入口 | 自动定位最新 `failure_archive.json` | 失败 seed fixture | 失败证据与重跑入口可直接访问 |
| 未运行降级 | 无 manifest 时输出 NOT_RUN、尚无运行和尚无失败 | 空 target 回归测试 | 新 target 不会生成误导性 PASS |
| 多 target 导航 | dashboard 存在时直达目标，不存在时回退顶层锚点 | 断链回归与链接扫描 | 导航不会指向不存在的目标页面 |
| 工程资源收敛 | 仅收录顶层报告与官方嵌套 `dashboard.html` | xcrg dashboard/detail fixture | 保留正式入口，不展开内部明细页 |
| async FIFO 兼容 | `write_async_fifo_reports_index()` 委托通用实现并保留 lessons | 既有报告回归 | 升级不丢失问题复盘入口 |

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result |
|---|---|---|---|---|
| 1 | dashboard 聚合七阶段、最近运行、最近失败和归档 | `test_p4_7_target_dashboard_groups_stages_recent_run_and_failure_entry` | unit/integration | PASS |
| 2 | 未运行 target 输出 NOT_RUN 且不伪造失败归档 | `test_p4_7_target_dashboard_handles_not_run_without_failure_archive` | regression | PASS |
| 3 | 目标 dashboard 缺失时回退顶层 target 锚点 | P4.7 目标导航断链回归 | regression | PASS |
| 4 | xcrg 官方 dashboard 保留且内部明细页不进入资源列表 | P4.7 工程资源断言 | unit | PASS |
| 5 | async FIFO 报告索引继续保留问题复盘入口 | `tests/test_agent.py -k "p4_7 or reports_index"` | integration | PASS |

## Static Dashboard Acceptance

对真实生成的 dashboard 执行本地 DOM、CSS、文件链接和响应式规则验收：

```text
TargetLinks: 4
StageCards: 7
ReadyCards: 6
ResourceRows: 42
BrokenLinks: []
HasNestedDetailSpam: false
Mojibake: false
```

同时确认：

- 存在响应式断点。
- 阶段卡片采用弹性网格。
- 目标导航支持换行。
- 页面未收录 xcrg 模块内部明细页。
- 所有本地报告链接均存在。

浏览器直接访问本地 `file://` 页面被安全策略拦截，因此本轮未生成浏览器截图；验收改用本地 DOM、CSS、链接存在性和响应式规则检查，未绕过安全限制。

## Full Validation

全量测试与覆盖率：

```text
183 passed in 15.82s
TOTAL 80.19%
project_overview.py 90.7%
```

静态检查：

```text
Ruff: All checks passed!
Mypy: Success, 23 source files
```

真实 Agent 验收：

```text
--check-rtl async-fifo
所有检查项均为 [OK]
```

## Coverage and Known Gaps

- `project_overview.py` 覆盖率为 `90.7%`，全量覆盖率为 `80.19%`。
- 本地 `file://` 浏览器访问受安全策略限制，本轮未提供浏览器像素截图；DOM、CSS、断链和响应式规则已通过静态验收。
- dashboard 当前聚合现有文件和 manifest；外部工具若不更新 manifest，需要先运行对应 Agent flow 或 `--generate-overview` 刷新状态。
- P4.0-P4.7 已全部完成，后续收尾复核发现并修复了顶层项目总览对缺失 manifest 生成断链的问题。

## P4 Closure Regression

初次真实输出扫描：

```text
Dashboard pages: 3
Relative links: 119
Broken links: 3
```

断链均来自顶层 `outputs/index.html`：

- `environment-report/artifacts.json`
- `round-robin-arbiter/artifacts.json`
- `sync-fifo/artifacts.json`

TDD 检查点：

```text
c0cb3355 test: reject missing manifest links in project overview
87a89592 fix: avoid broken manifest links in project overview
f501fa35 test: require missing manifest status for overview targets
320db6a0 fix: render missing target manifests as status text
```

关键 RED/GREEN：

```text
RED: 1 failed
GREEN: 1 passed
Related overview/dashboard tests: 5 passed, 171 deselected
```

最终验证：

```text
Ruff: All checks passed!
Mypy: Success, 23 source files
183 passed in 25.62s
TOTAL 80.22%
project_overview.py 90.9%
Dashboard pages: 3
Relative links: 116
Broken links: 0
```

P4 收尾复核已完成，详细结论见 `docs/testing/p4_closure_audit.md`。
