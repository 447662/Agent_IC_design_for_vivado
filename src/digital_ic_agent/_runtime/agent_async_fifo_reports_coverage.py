# -*- coding: utf-8 -*-
import html
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from digital_ic_agent._runtime.artifact_manifest import extract_tool_version
from digital_ic_agent._runtime.coverage_gates import (
    COVERAGE_METRIC_LABELS,
    COVERAGE_METRIC_ORDER,
    evaluate_coverage_gates,
)
from digital_ic_agent._runtime.coverage_history import append_coverage_history


class AsyncFifoCoverageReportMixin:
    if TYPE_CHECKING:
        async_fifo_required_wcfg_objects: Any
        collect_async_fifo_vcd_analysis: Any
        project_root: Any
        render_async_fifo_open_project_gui_script: Any
        render_async_fifo_project_script: Any
        render_async_fifo_readme: Any
        render_async_fifo_rtl: Any
        render_async_fifo_sva: Any
        render_async_fifo_tb: Any
        render_async_fifo_uvm_coverage_script: Any
        render_async_fifo_uvm_interface: Any
        render_async_fifo_uvm_pkg: Any
        render_async_fifo_uvm_top: Any
        render_async_fifo_uvm_vivado_script: Any
        render_async_fifo_vivado_script: Any
        resolve_async_fifo_wave_db: Any
        write_target_dashboard: Any

    def parse_async_fifo_coverage_summary(self, code_cov_info: Any) -> Any:
        code_cov_info = Path(code_cov_info)
        if not code_cov_info.exists():
            return {
                "available": False,
                "coverage_types": [],
                "database_name": "",
                "source_files": [],
                "instances": [],
                "coverage_items": [],
                "raw_tokens": [],
            }

        raw = code_cov_info.read_bytes()
        text = raw.decode("utf-8", errors="ignore")
        tokens = []
        for token in re.split(r"[\x00-\x1f\x7f]+", text):
            token = token.strip()
            if len(token) >= 2 and token not in tokens:
                tokens.append(token)

        coverage_types = []
        if any(token == "sbct" or "sbct" in token.split() for token in tokens):
            coverage_types = ["statement", "branch", "condition", "toggle"]

        database_name = ""
        for token in tokens:
            if token == "async_fifo_uvm_cov" or token.endswith("_uvm_cov"):
                database_name = token
                break

        source_files = [
            token for token in tokens
            if token.endswith((".v", ".sv", ".vh", ".svh"))
        ]
        instances = [
            token for token in tokens
            if "tb_async_fifo_uvm" in token or token.endswith(".dut")
        ]
        coverage_items = [
            token for token in tokens
            if token not in source_files
            and token not in instances
            and token not in {"xsim.codeCov", database_name, "sbct"}
            and (
                "async_fifo" in token
                or "&&" in token
                or "||" in token
                or "!" in token
            )
        ]

        return {
            "available": True,
            "coverage_types": coverage_types,
            "database_name": database_name,
            "source_files": source_files,
            "instances": instances,
            "coverage_items": coverage_items[:20],
            "raw_tokens": tokens[:80],
        }

    def extract_async_fifo_coverage_percent(self, report_path: Any) -> Any:
        report_path = Path(report_path)
        if not report_path.exists():
            return {"available": False, "total_percent": None, "metrics": {}}

        text = report_path.read_text(encoding="utf-8", errors="replace")
        patterns = {
            "statement": r"(?:Statement|Line)\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
            "branch": r"Branch\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
            "condition": r"Condition\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
            "toggle": r"Toggle\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
            "functional": r"Functional\s+Coverage(?:\s+Score|\s*:)\s*([0-9]+(?:\.[0-9]+)?)%?",
        }
        metrics = {}
        for name, pattern in patterns.items():
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                metrics[name] = float(match.group(1))

        total_match = re.search(r"Total\s+Coverage\s*:\s*([0-9]+(?:\.[0-9]+)?)%", text, flags=re.IGNORECASE)
        total_percent = float(total_match.group(1)) if total_match else None
        code_metrics = [
            metrics[name]
            for name in ("statement", "branch", "condition", "toggle")
            if name in metrics
        ]
        if total_percent is None and code_metrics:
            total_percent = round(sum(code_metrics) / len(code_metrics), 2)
        return {
            "available": bool(metrics or total_percent is not None),
            "total_percent": total_percent,
            "metrics": metrics,
        }

    def write_async_fifo_uvm_functional_coverage_report(self, project_dir: Any) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_functional_coverage.md"
        html_path = reports_dir / "uvm_functional_coverage.html"
        log_path = sim_dir / "async_fifo_uvm_coverage.log"
        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")

        checks = [
            ("full_boundary", "full=1" in log_text),
            ("empty_boundary", "empty=1" in log_text),
            ("reset_recovery", "reset=1" in log_text),
            ("mixed_traffic", "mixed=1" in log_text),
            ("functional_coverage_pass", "ASYNC_FIFO_UVM_FCOV_PASS" in log_text),
            ("assertion_pass", "ASYNC_FIFO_UVM_ASSERT_PASS" in log_text and "ASYNC_FIFO_SVA_FAIL" not in log_text),
        ]
        passed = all(ok for _name, ok in checks)
        status = "PASS" if passed else "FAIL"

        lines = [
            "# async-fifo UVM 功能覆盖率摘要",
            "",
            "- 总体状态：{}".format(status),
            "- UVM 日志：`{}`".format(log_path),
            "",
            "## 功能覆盖点",
            "",
        ]
        for name, ok in checks:
            lines.append("- {}：{}".format(name, "FOUND" if ok else "MISSING"))
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for name, ok in checks:
            cards.append(
                '<article class="functional-card {klass}"><h2>{name}</h2><strong>{status}</strong></article>'.format(
                    klass="pass" if ok else "fail",
                    name=html.escape(name),
                    status="FOUND" if ok else "MISSING",
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM 功能覆盖率摘要</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1080px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;background:#17324d;color:#fff}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:18px}",
            ".functional-card{padding:16px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".functional-card.pass{border-left:6px solid #0f8a5f}",
            ".functional-card.fail{border-left:6px solid #b42318}",
            "@media(max-width:900px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM 功能覆盖率摘要</h1><p>总体状态：{}</p></section>'.format(status),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {"passed": passed, "markdown_path": md_path, "html_path": html_path, "log_path": log_path}

    def write_async_fifo_uvm_coverage_summary_report(
        self,
        project_dir: Any,
        sim_result: Any=None,
        coverage_threshold: Any=None,
        coverage_percent: Any=None,
        coverage_thresholds: Any=None,
    ) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_coverage_summary.md"
        html_path = reports_dir / "uvm_coverage_summary.html"
        log_path = sim_dir / "async_fifo_uvm_coverage.log"
        wdb_path = sim_dir / "async_fifo_uvm_coverage.wdb"
        coverage_dir = sim_dir / "coverage"
        code_cov_dir = coverage_dir / "xsim.codeCov" / "async_fifo_uvm_cov"
        code_cov_info = code_cov_dir / "xsim.CCInfo"
        coverage_percent_report_path = reports_dir / "uvm_coverage_percent.txt"
        xcrg_code_report_path = reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html"
        xcrg_functional_report_path = reports_dir / "uvm_coverage_xcrg" / "functionalCoverageReport" / "dashboard.html"
        xcrg_log_path = reports_dir / "xcrg_coverage.log"

        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        tool_text = ""
        if sim_result is not None:
            tool_text = "\n".join(part for part in [sim_result.stdout, sim_result.stderr] if part)
        combined = "\n".join(part for part in [log_text, tool_text] if part)
        smoke_passed = "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined and "ASYNC_FIFO_UVM_TEST_DONE" in combined
        coverage_summary = self.parse_async_fifo_coverage_summary(code_cov_info)
        coverage_percent_summary = self.extract_async_fifo_coverage_percent(coverage_percent_report_path)
        coverage_ready = coverage_summary["available"]

        coverage_thresholds = dict(coverage_thresholds or {})
        coverage_scores = {
            "total": None if coverage_percent is None else float(coverage_percent),
            **coverage_percent_summary["metrics"],
        }
        configured_thresholds = {
            "total": coverage_threshold,
            **coverage_thresholds,
        }
        coverage_gates, coverage_gate_passed = evaluate_coverage_gates(
            coverage_scores,
            configured_thresholds,
        )
        configured_gate_results = [
            gate["result"]
            for gate in coverage_gates.values()
            if gate["threshold"] is not None
        ]
        if not configured_gate_results:
            gate_result = "SKIP"
        elif "FAIL" in configured_gate_results:
            gate_result = "FAIL"
        elif "MISSING" in configured_gate_results:
            gate_result = "MISSING"
        else:
            gate_result = "PASS"

        total_gate = coverage_gates["total"]
        coverage_gap = total_gate["gap"]
        if coverage_thresholds:
            failed_labels = [
                gate["label"]
                for gate in coverage_gates.values()
                if gate["result"] == "FAIL"
            ]
            missing_labels = [
                gate["label"]
                for gate in coverage_gates.values()
                if gate["result"] == "MISSING"
            ]
            if failed_labels:
                gate_diagnostic = "分项 gate 未达标：{}。".format(
                    "、".join(failed_labels)
                )
            elif missing_labels:
                gate_diagnostic = "分项 gate 数据源缺失：{}。".format(
                    "、".join(missing_labels)
                )
            else:
                gate_diagnostic = "所有已配置的分项 coverage gate 均通过。"
        else:
            gate_diagnostic = "未设置覆盖率阈值，coverage gate 跳过。"
            if coverage_threshold is not None and coverage_percent is None:
                gate_diagnostic = "已设置覆盖率阈值 {:.1f}%，但未提供可比较的覆盖率百分比。".format(
                    float(coverage_threshold)
                )
            elif coverage_threshold is not None:
                current_percent = float(coverage_percent)
                threshold_percent = float(coverage_threshold)
                assert coverage_gap is not None
                if current_percent >= threshold_percent:
                    gate_diagnostic = "当前覆盖率 {:.1f}% 达到阈值 {:.1f}%，余量 {:.1f}%。".format(
                        current_percent,
                        threshold_percent,
                        abs(coverage_gap),
                    )
                else:
                    gate_diagnostic = "当前覆盖率 {:.1f}% 低于阈值 {:.1f}%，差距 {:.1f}%。".format(
                        current_percent,
                        threshold_percent,
                        coverage_gap,
                    )

        passed = smoke_passed and coverage_ready and coverage_gate_passed
        status = "PASS" if passed else "FAIL"
        coverage_types_text = " / ".join(coverage_summary["coverage_types"]) or "未识别"
        current_coverage_text = "N/A" if coverage_percent is None else "{:.1f}%".format(float(coverage_percent))
        metric_labels = [
            ("statement", "Statement/Line"),
            ("branch", "Branch"),
            ("condition", "Condition"),
            ("toggle", "Toggle"),
            ("functional", "Functional"),
        ]
        coverage_metric_lines = []
        coverage_metric_cards = []
        for metric_key, metric_label in metric_labels:
            metric_value = coverage_percent_summary["metrics"].get(metric_key)
            metric_text = "N/A" if metric_value is None else "{:.1f}%".format(metric_value)
            coverage_metric_lines.append("- {} Coverage: {}".format(metric_label, metric_text))
            coverage_metric_cards.append(
                '<div class="metric"><span>{} Coverage</span><strong>{}</strong></div>'.format(
                    html.escape(metric_label),
                    html.escape(metric_text),
                )
            )
        total_metric_text = (
            "N/A"
            if coverage_percent_summary["total_percent"] is None
            else "{:.1f}%".format(float(coverage_percent_summary["total_percent"]))
        )
        xcrg_links = [
            ("Vivado Code Coverage", "uvm_coverage_xcrg/codeCoverageReport/dashboard.html", xcrg_code_report_path),
            ("Vivado Functional Coverage", "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html", xcrg_functional_report_path),
            ("XCRG Log", "xcrg_coverage.log", xcrg_log_path),
            ("Coverage Percent Text", "uvm_coverage_percent.txt", coverage_percent_report_path),
        ]
        threshold_text = "未设置" if coverage_threshold is None else "{:.1f}%".format(float(coverage_threshold))
        coverage_gate_table_lines = [
            "| 分项 | 当前值 | 阈值 | Gap | 结果 | 诊断 |",
            "|---|---:|---:|---:|---|---|",
        ]
        coverage_gate_cards = []
        for metric_key in COVERAGE_METRIC_ORDER:
            gate = coverage_gates[metric_key]
            current_text = (
                "N/A"
                if gate["current"] is None
                else "{:.1f}%".format(gate["current"])
            )
            component_threshold_text = (
                "未设置"
                if gate["threshold"] is None
                else "{:.1f}%".format(gate["threshold"])
            )
            gap_text = (
                "N/A"
                if gate["gap"] is None
                else "{:.1f}%".format(gate["gap"])
            )
            coverage_gate_table_lines.append(
                "| {} | {} | {} | {} | {} | {} |".format(
                    gate["label"],
                    current_text,
                    component_threshold_text,
                    gap_text,
                    gate["result"],
                    gate["diagnostic"],
                )
            )
            gate_class = gate["result"].lower()
            coverage_gate_cards.append(
                '<article class="component-gate {gate_class}" data-metric="{metric}">'
                "<h3>{label}</h3>"
                "<p>当前值：<strong>{current}</strong></p>"
                "<p>阈值：<strong>{threshold}</strong></p>"
                "<p>Gap：<strong>{gap}</strong></p>"
                "<p>结果：<strong>{result}</strong></p>"
                "<p>{diagnostic}</p>"
                "</article>".format(
                    gate_class=html.escape(gate_class),
                    metric=html.escape(metric_key),
                    label=html.escape(COVERAGE_METRIC_LABELS[metric_key]),
                    current=html.escape(current_text),
                    threshold=html.escape(component_threshold_text),
                    gap=html.escape(gap_text),
                    result=html.escape(gate["result"]),
                    diagnostic=html.escape(gate["diagnostic"]),
                )
            )

        lines = [
            "# async-fifo UVM 覆盖率摘要",
            "",
            "- 总体状态：{}".format(status),
            "- 目标：`async-fifo`",
            "- 仿真器：Vivado/xsim",
            "- 覆盖率数据库：{}".format("FOUND" if coverage_ready else "MISSING"),
            "- 覆盖率类型：{}".format(coverage_types_text),
            "- 当前覆盖率：{}".format(current_coverage_text),
            "- 覆盖率阈值：{}".format(threshold_text),
            "- Gate 结果：{}".format(gate_result),
            "- Gate 诊断：{}".format(gate_diagnostic),
            "- UVM 日志：`{}`".format(log_path),
            "- 波形数据库：`{}`".format(wdb_path),
            "- Code coverage info：`{}`".format(code_cov_info),
            "",
            "## P3.10 Gate 诊断",
            "",
            "- 诊断结论：{}".format(gate_diagnostic),
            "- 建议动作：优先查看 `uvm_coverage_report.html`、`uvm_functional_coverage.html` 和 `xsim.CCInfo`，确认低覆盖项或缺失百分比来源。",
            "",
            "## P4.3 分项 Coverage Gate",
            "",
            *coverage_gate_table_lines,
            "",
            "## 验收标记",
            "",
            "- `ASYNC_FIFO_UVM_SCOREBOARD_PASS`：{}".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "- `ASYNC_FIFO_UVM_TEST_DONE`：{}".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
            "- `xsim.CCInfo`：{}".format("FOUND" if coverage_ready else "MISSING"),
            "",
            "## 覆盖率数据库元信息",
            "",
            "- 数据库名称：{}".format(coverage_summary["database_name"] or "未识别"),
            "- 源文件：{}".format(", ".join("`{}`".format(item) for item in coverage_summary["source_files"]) or "未识别"),
            "- 实例：{}".format(", ".join("`{}`".format(item) for item in coverage_summary["instances"]) or "未识别"),
            "- 覆盖项片段：{}".format(", ".join("`{}`".format(item) for item in coverage_summary["coverage_items"]) or "未识别"),
        ]
        if sim_result is not None:
            lines.extend([
                "",
                "## 工具返回码",
                "",
                "- Vivado batch return code：{}".format(sim_result.returncode),
            ])
        lines.extend([
            "",
            "## P3.13 xcrg Coverage Scores",
            "",
            "- Total Coverage: {}".format(total_metric_text),
            *coverage_metric_lines,
            "",
            "## P3.13 xcrg Report Links",
            "",
        ])
        lines.extend(
            "- {}: `{}` ({})".format(title, rel_path, "FOUND" if path.exists() else "MISSING")
            for title, rel_path, path in xcrg_links
        )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        dashboard_class = "pass" if passed else "fail"
        type_badges = "".join(
            '<span class="badge">{}</span>'.format(html.escape(item))
            for item in coverage_summary["coverage_types"]
        ) or '<span class="badge muted">未识别</span>'
        source_items = "".join(
            "<li>{}</li>".format(html.escape(item))
            for item in coverage_summary["source_files"]
        ) or "<li>未识别</li>"
        instance_items = "".join(
            "<li>{}</li>".format(html.escape(item))
            for item in coverage_summary["instances"]
        ) or "<li>未识别</li>"
        coverage_item_list = "".join(
            "<li>{}</li>".format(html.escape(item))
            for item in coverage_summary["coverage_items"]
        ) or "<li>未识别</li>"
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM 覆盖率摘要</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f3f6fb;color:#172033}",
            ".page{max-width:1120px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:30px;border-radius:8px;color:#fff;background:linear-gradient(135deg,#17324d,#28665b)}",
            ".hero h1{margin:0 0 10px;font-size:32px}",
            ".coverage-dashboard{margin-top:18px;padding:20px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 10px 26px rgba(31,45,61,.07)}",
            ".coverage-dashboard.pass{border-left:7px solid #0f8a5f}",
            ".coverage-dashboard.fail{border-left:7px solid #b42318}",
            ".metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0}",
            ".metric{padding:14px;border-radius:8px;background:#f7f9fc;border:1px solid #e2e8f0}",
            ".metric span{display:block;color:#637083;font-size:13px}.metric strong{display:block;margin-top:6px;font-size:24px}",
            ".links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:18px 0}",
            ".link-card{padding:14px;border-radius:8px;background:#f8fbff;border:1px solid #dbe7f5}",
            ".link-card a{color:#175cd3;word-break:break-all}",
            ".link-card strong{display:block;margin-bottom:6px}",
            ".diagnostic{padding:14px 16px;margin:14px 0;border-radius:8px;background:#fff7ed;border:1px solid #fed7aa;color:#7c2d12}",
            ".component-gates{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0}",
            ".component-gate{padding:14px;border-radius:8px;background:#f8fafc;border:1px solid #dbe3ee}",
            ".component-gate h3{margin:0 0 10px}.component-gate p{margin:7px 0}",
            ".component-gate.pass{border-left:6px solid #0f8a5f}.component-gate.fail{border-left:6px solid #b42318}",
            ".component-gate.missing{border-left:6px solid #b7791f}.component-gate.skip{border-left:6px solid #94a3b8}",
            ".badge{display:inline-block;margin:3px 6px 3px 0;padding:5px 9px;border-radius:999px;background:#e7f0f8;color:#17324d;font-weight:600}",
            ".muted{background:#eef1f5;color:#637083}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}",
            ".panel{padding:16px;border-radius:8px;background:#fbfcfe;border:1px solid #e2e8f0}",
            ".panel h2{margin:0 0 10px;font-size:18px}li{margin:6px 0;word-break:break-all}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:900px){.metrics,.grid,.component-gates{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM 覆盖率摘要</h1><p>Vivado/xsim code coverage 元信息与阈值 gate</p></section>',
            '<section class="coverage-dashboard {}">'.format(dashboard_class),
            "<h2>总体状态：{}</h2>".format(status),
            '<div class="metrics">',
            '<div class="metric"><span>当前覆盖率</span><strong>{}</strong></div>'.format(html.escape(current_coverage_text)),
            '<div class="metric"><span>覆盖率阈值</span><strong>{}</strong></div>'.format(html.escape(threshold_text)),
            '<div class="metric"><span>Gate 结果</span><strong>{}</strong></div>'.format(gate_result),
            "</div>",
            '<div class="diagnostic"><strong>P3.10 Gate 诊断：</strong>{}</div>'.format(html.escape(gate_diagnostic)),
            "<p><strong>覆盖率类型</strong></p><p>{}</p>".format(type_badges),
            '<section class="grid">',
            '<article class="panel"><h2>源文件</h2><ul>{}</ul></article>'.format(source_items),
            '<article class="panel"><h2>实例</h2><ul>{}</ul></article>'.format(instance_items),
            '<article class="panel"><h2>覆盖项片段</h2><ul>{}</ul></article>'.format(coverage_item_list),
            "</section>",
            "<p><strong>Code coverage info</strong></p><code>{}</code>".format(html.escape(str(code_cov_info))),
            "<p><strong>UVM 日志</strong></p><code>{}</code>".format(html.escape(str(log_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        xcrg_html_block = [
            "<h2>P4.3 Component Coverage Gates</h2>",
            '<div class="component-gates">',
            "\n".join(coverage_gate_cards),
            "</div>",
            "<h2>P3.13 xcrg Coverage Scores</h2>",
            '<div class="metrics">',
            '<div class="metric"><span>Total Coverage</span><strong>{}</strong></div>'.format(html.escape(total_metric_text)),
            "\n".join(coverage_metric_cards),
            "</div>",
            "<h2>P3.13 xcrg Report Links</h2>",
            '<div class="links">',
            "\n".join(
                '<article class="link-card"><strong>{}</strong><a href="{}">{}</a><p>{}</p></article>'.format(
                    html.escape(title),
                    html.escape(rel_path),
                    html.escape(rel_path),
                    "FOUND" if path.exists() else "MISSING",
                )
                for title, rel_path, path in xcrg_links
            ),
            "</div>",
        ]
        html_lines[-5:-5] = xcrg_html_block
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "passed": passed,
            "coverage_gate_passed": coverage_gate_passed,
            "coverage_percent": coverage_percent,
            "coverage_threshold": coverage_threshold,
            "coverage_thresholds": coverage_thresholds,
            "coverage_gates": coverage_gates,
            "coverage_gap": coverage_gap,
            "gate_diagnostic": gate_diagnostic,
            "coverage_summary": coverage_summary,
            "coverage_percent_summary": coverage_percent_summary,
            "markdown_path": md_path,
            "html_path": html_path,
            "log_path": log_path,
            "xcrg_code_report_path": xcrg_code_report_path,
            "xcrg_functional_report_path": xcrg_functional_report_path,
            "xcrg_log_path": xcrg_log_path,
            "coverage_percent_report_path": coverage_percent_report_path,
            "wdb_path": wdb_path,
            "coverage_dir": coverage_dir,
            "code_cov_dir": code_cov_dir,
            "code_cov_info": code_cov_info,
        }

    def write_async_fifo_coverage_history(
        self,
        project_dir: Any,
        summary_report: Any,
        status: Any,
        vivado_command: Any,
        seed: Any=None,
    ) -> Any:
        percent_summary = summary_report["coverage_percent_summary"]
        coverage_metrics = {
            metric: percent_summary["metrics"].get(metric)
            for metric in COVERAGE_METRIC_ORDER
        }
        coverage_metrics["total"] = summary_report["coverage_percent"]
        if coverage_metrics["total"] is None:
            coverage_metrics["total"] = percent_summary["total_percent"]
        return append_coverage_history(
            Path(project_dir) / "reports",
            target_name="async-fifo",
            flow_name="uvm-coverage",
            toolchain={
                "vivado": {
                    "version": extract_tool_version(vivado_command),
                    "command": vivado_command,
                },
                "simulator": {
                    "name": "xsim",
                },
            },
            seed_set=[] if seed is None else [int(seed)],
            coverage_metrics=coverage_metrics,
            coverage_gates=summary_report["coverage_gates"],
            status=status,
            sources={
                "summary_markdown": summary_report["markdown_path"],
                "summary_html": summary_report["html_path"],
                "coverage_percent": summary_report["coverage_percent_report_path"],
                "xcrg_code": summary_report["xcrg_code_report_path"],
                "xcrg_functional": summary_report["xcrg_functional_report_path"],
            },
        )
