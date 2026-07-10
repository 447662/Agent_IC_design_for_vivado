# Artifact/History Rotation TDD 证据

## Source Plan

- 来源于 `docs/testing/p4_closure_audit.md` 的首项高价值修复。
- 目标是限制长期运行产生的活动历史体积，同时不删除任何旧记录。

## User Journeys

1. 作为长期回归维护者，我希望活动 manifest/history 只保留最近记录，避免文件无限增长。
2. 作为审计人员，我希望溢出记录按原顺序进入压缩归档，历史信息不会丢失。
3. 作为环境维护者，我希望 target、environment 和 coverage 使用同一套 rotation 规则。
4. 作为调试人员，我希望可以传入 `None` 关闭未来轮转，临时完整保留活动历史。
5. 作为报告使用者，我希望 coverage 趋势页能看到活动数量、归档数量和归档入口。

## Rotation Contract

- 默认活动记录限制：`200`。
- `None`：关闭未来轮转，不删除已有文件。
- 非正整数或布尔值：拒绝并抛出 `ValueError`。
- target/environment 活动文件：`artifacts.json`。
- target/environment 压缩归档：`artifacts.archive.jsonl.gz`。
- coverage 活动文件：`coverage_history.jsonl`。
- coverage 压缩归档：`coverage_history.archive.jsonl.gz`。
- coverage rotation metadata：`coverage_history.meta.json`。
- gzip JSONL 归档按时间顺序追加，活动窗口保留最新 N 条。

## RED Evidence

提交：

```text
446c717b test: define artifact and history rotation behavior
```

结果：

```text
3 failed, 176 deselected
```

预期失败：

- `record_artifact_run()` 尚不接受 `max_active_runs`。
- `write_environment_manifest()` 尚不接受 `max_active_runs`。
- `append_coverage_history()` 尚不接受 `max_active_records`。

## GREEN Evidence

提交：

```text
ef265ad2 feat: add compressed artifact and history rotation
```

定向结果：

```text
3 passed, 176 deselected
```

相关回归：

```text
13 passed, 166 deselected
```

## Task Report

| Task | Execution summary | Validation | Guarantee |
|---|---|---|---|
| 共享轮转内核 | 新增 `history_rotation.py`，统一限制校验、归档路径和 gzip JSONL 追加 | 三条 rotation 集成测试 | 三类历史使用一致规则 |
| Target manifest | `artifacts.json` 保留最新 N 条并记录 `history` metadata | target manifest rotation 测试 | 溢出 run 顺序归档且活动窗口有界 |
| Environment manifest | 环境预检复用相同 manifest rotation | environment manifest rotation 测试 | 项目级环境历史不再无限增长 |
| Coverage history | JSONL 活动窗口重写，溢出记录压缩归档 | coverage rotation 测试 | 最新 delta 只基于活动窗口最后两条 |
| 趋势报告 | Markdown/HTML 展示活动数量、归档数量和入口 | 报告文本断言 | 使用者可发现压缩归档 |
| 关闭轮转 | `None` 保留全部活动记录且不创建归档 | target manifest disable 测试 | 调试场景可手动关闭未来轮转 |
| 非法限制 | `0` 等非法值抛出准确错误 | ValueError 断言 | 不允许静默丢弃全部活动记录 |

## Test Specification

| # | What is guaranteed | Test | Type | Result |
|---|---|---|---|---|
| 1 | Environment manifest 保留最新两条并归档前两条 | `test_history_rotation_archives_environment_manifest_runs` | integration | PASS |
| 2 | Target manifest 支持压缩归档、关闭轮转和非法限制拒绝 | `test_history_rotation_archives_target_manifest_runs_and_can_be_disabled` | integration | PASS |
| 3 | Coverage history 归档旧记录且保持最新 delta | `test_history_rotation_archives_coverage_records_and_keeps_latest_deltas` | integration/report | PASS |

## Full Validation

```text
Ruff: All checks passed!
Mypy: Success, 24 source files
186 passed in 18.80s
TOTAL 80.55%
history_rotation.py 90.9%
artifact_manifest.py 85.5%
coverage_history.py 90.2%
environment_report.py 78.9%
```

## Coverage and Known Gaps

- 新共享模块覆盖率为 `90.9%`，项目总覆盖率为 `80.55%`。
- gzip 归档采用单文件追加，尚未按大小或日期分卷。
- 当前提供归档写入和发现能力，尚未提供把归档记录恢复回活动窗口的 CLI。
- 为避免数据丢失，归档写入先于活动文件重写；极端写入失败重试可能产生重复归档记录，后续可基于 `run_id` 或记录哈希增加去重工具。
- 下一优先项是 Windows/Vivado 自动验收和 dashboard 链接 CI。
