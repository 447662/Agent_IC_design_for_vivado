# -*- coding: utf-8 -*-
import html
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from digital_ic_agent._runtime.agent_async_fifo_report_support import (
    AsyncFifoWcfgSummary,
    CompletedProcessLike,
    PathLike,
)
from digital_ic_agent._runtime.wave_visibility import (
    evaluate_wave_open_check,
    render_window_capture_script,
)


class AsyncFifoSimulationReportMixin:
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
        write_async_fifo_summary_report: Any

    def write_async_fifo_sim_report(
        self,
        project_dir: PathLike,
        vcd_path: PathLike,
        wave_db_path: PathLike,
        sim_result: CompletedProcessLike | None = None,
        project_result: CompletedProcessLike | None = None,
        limit: int = 20,
    ) -> Path:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "sim_report.md"

        analysis = None
        analysis_error = None
        try:
            analysis = self.collect_async_fifo_vcd_analysis(output_dir=project_dir.parent, limit=limit)
        except (FileNotFoundError, RuntimeError) as exc:
            analysis_error = str(exc)

        lines = [
            "# async-fifo Simulation Report",
            "",
            "## Summary",
            "",
            "- Target: `async-fifo`",
            "- Simulator: Vivado/xsim",
            "- Status: PASS" if analysis_error is None else "- Status: PASS_WITH_ANALYSIS_WARNING",
            "- VCD: `{}`".format(vcd_path),
            "- WDB: `{}`".format(wave_db_path),
            "- Vivado project: `{}`".format(project_dir / "vivado_project" / "async_fifo_project.xpr"),
            "",
            "## Scoreboard",
            "",
            "- Testbench includes `ASYNC_FIFO_SCOREBOARD_PASS` / `ASYNC_FIFO_SCOREBOARD_FAIL` checks.",
            "- xsim returns failure if `$fatal(1, ...)` is reached.",
            "",
            "## Scenarios",
            "",
            "- `basic_ordered`: ordered write/read smoke path.",
            "- `full_boundary`: fills FIFO to full and confirms overflow writes are blocked.",
            "- `empty_boundary`: drains FIFO to empty and confirms underflow reads are blocked.",
            "- `reset_recovery`: resets mid-test and verifies clean post-reset operation.",
            "- `mixed_stress`: overlaps write/read activity across asynchronous clocks.",
        ]

        if analysis is not None:
            info = analysis["info"]
            write_events = analysis["write_events"]
            read_events = analysis["read_events"]
            lines.extend([
                "",
                "## VCD Analysis",
                "",
                "- Signals: {}".format(info.get("signal_count", "unknown")),
                "- Time range: {} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")),
                "- Duration: {}".format(info.get("duration_h", "unknown")),
                "- Timescale: {}".format(info.get("timescale", "unknown")),
                "- Write events: {}".format(write_events.get("total", write_events.get("shown", "unknown"))),
                "- Read events: {}".format(read_events.get("total", read_events.get("shown", "unknown"))),
                "",
                "## Write Samples",
                "",
            ])
            for row in (write_events.get("events") or [])[: int(limit)]:
                lines.append("- {} {}".format(row.get("time_h", "unknown"), row.get("values") or {}))
            lines.extend(["", "## Read Samples", ""])
            for row in (read_events.get("events") or [])[: int(limit)]:
                lines.append("- {} {}".format(row.get("time_h", "unknown"), row.get("values") or {}))
        else:
            lines.extend(["", "## VCD Analysis", "", "- Analysis warning: {}".format(analysis_error)])

        if sim_result is not None or project_result is not None:
            lines.extend(["", "## Tool Return Codes", ""])
            if sim_result is not None:
                lines.append("- Simulation command return code: {}".format(sim_result.returncode))
            if project_result is not None:
                lines.append("- Project command return code: {}".format(project_result.returncode))

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        regression_path = self.write_async_fifo_regression_matrix(project_dir)
        self.write_async_fifo_summary_report(
            project_dir=project_dir,
            vcd_path=vcd_path,
            wave_db_path=wave_db_path,
            analysis=analysis,
            analysis_error=analysis_error,
            regression_path=regression_path,
        )
        return report_path

    def parse_async_fifo_wcfg_summary(self, project_dir: PathLike) -> AsyncFifoWcfgSummary:
        project_dir = Path(project_dir)
        wcfg_path = project_dir / "sim" / "async_fifo_debug.wcfg"
        required_objects = list(self.async_fifo_required_wcfg_objects())
        summary: AsyncFifoWcfgSummary = {
            "path": wcfg_path,
            "exists": wcfg_path.exists(),
            "object_count": 0,
            "required_objects": required_objects,
            "present_required": [],
            "missing_required": required_objects[:],
            "valid": False,
        }
        if not wcfg_path.exists():
            return summary

        text = wcfg_path.read_text(encoding="utf-8", errors="replace")
        size_match = re.search(r"<WVObjectSize\s+size=\"(\d+)\"", text)
        if size_match:
            summary["object_count"] = int(size_match.group(1))
        else:
            summary["object_count"] = len(re.findall(r"/tb_async_fifo/", text))

        present_required = [name for name in required_objects if name in text]
        summary["present_required"] = present_required
        summary["missing_required"] = [name for name in required_objects if name not in present_required]
        summary["valid"] = summary["object_count"] > 0 and not summary["missing_required"]
        return summary

    def write_async_fifo_regression_matrix(self, project_dir: Any) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "regression_matrix.md"
        lines = [
            "# async-fifo Regression Matrix",
            "",
            "P2.7 tracks the parameter combinations that should be kept under regression as the async FIFO flow grows.",
            "",
            "| DATA_WIDTH | ADDR_WIDTH | Scenario coverage | Status |",
            "|---:|---:|---|---|",
            "| 8 | 4 | basic/full/empty/reset/mixed | baseline-pass |",
            "| 16 | 4 | basic/full/empty/reset/mixed | planned |",
            "| 8 | 3 | basic/full/empty/reset/mixed | planned |",
            "",
            "Clock plan: keep the current asynchronous 5 ns write clock and 7 ns read clock for the first matrix pass.",
            "Next expansion: generate per-parameter RTL/TB directories or pass Verilog parameters through the Vivado script.",
        ]
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_path

    def write_async_fifo_wave_visibility_report(self, project_dir: Any) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        sim_dir = project_dir / "sim"
        xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
        wave_db_path = self.resolve_async_fifo_wave_db(sim_dir)
        gui_script_path = sim_dir / "open_async_fifo_project_gui.tcl"
        wcfg = self.parse_async_fifo_wcfg_summary(project_dir)
        probe_path = reports_dir / "wave_open_check.json"
        screenshot_metrics_path = reports_dir / "wave_screenshot_metrics.json"
        automated: Any = evaluate_wave_open_check(
            probe_path,
            screenshot_metrics_path=screenshot_metrics_path,
        )
        probe = automated["probe"] or {}
        screenshot_metrics = automated["screenshot_metrics"] or {}

        checks = [
            ("Vivado 工程存在", xpr_path.exists(), xpr_path),
            ("WDB 波形数据库存在", wave_db_path.exists(), wave_db_path),
            ("GUI Tcl 脚本存在", gui_script_path.exists(), gui_script_path),
            ("GUI 脚本会打开工程", gui_script_path.exists() and "open_project $xpr_path" in gui_script_path.read_text(encoding="utf-8", errors="replace"), gui_script_path),
            ("GUI 脚本会打开 WDB", gui_script_path.exists() and "open_wave_database $wave_db" in gui_script_path.read_text(encoding="utf-8", errors="replace"), gui_script_path),
            ("WCFG 有波形对象", wcfg["object_count"] > 0, wcfg["path"]),
            ("WCFG 关键对象齐全", wcfg["valid"], wcfg["path"]),
        ]
        preflight_passed = all(passed for _label, passed, _path in checks)
        visible = preflight_passed and automated["visible"]
        markdown_path = reports_dir / "wave_visibility.md"
        html_path = reports_dir / "wave_visibility.html"
        if not preflight_passed or automated["status"] == "FAIL":
            status = "FAIL"
        elif visible:
            status = "PASS"
        else:
            status = "PENDING"
        wcfg_status = "PASS" if wcfg["valid"] else "FAIL"
        runtime_status = str(automated["runtime_status"])
        screenshot_status = str(automated["screenshot_status"])
        non_uniform_ratio = float(
            screenshot_metrics.get("non_uniform_ratio", 0.0)
        )
        lines = [
            "# async-fifo 波形可见性验收",
            "",
            "- 总体状态：{}".format(status),
            "- 静态预检状态：{}".format("PASS" if preflight_passed else "FAIL"),
            "- 运行时探针状态：{}".format(runtime_status),
            "- 截图像素状态：{}".format(screenshot_status),
            "- WCFG 状态：{}".format(wcfg_status),
            "- 波形对象数：{}".format(wcfg["object_count"]),
            "- Scope 数：{}".format(probe.get("scope_count", "-")),
            "- Object 数：{}".format(probe.get("object_count", "-")),
            "- Wave 数：{}".format(probe.get("wave_count", "-")),
            "- Wave Config 数：{}".format(probe.get("wave_config_count", "-")),
            "- 截图唯一颜色数：{}".format(
                screenshot_metrics.get("unique_colors", "-")
            ),
            "- 非均匀像素比例：{:.2f}%".format(non_uniform_ratio * 100.0),
            "- WDB：`{}`".format(wave_db_path),
            "- WCFG：`{}`".format(wcfg["path"]),
            "- 运行时探针：`{}`".format(probe_path),
            "- 截图指标：`{}`".format(screenshot_metrics_path),
            "- 关键 Tcl 命令：`open_project` / `open_wave_database`",
            "",
            "## GUI 预检项",
            "",
        ]
        for label, passed, path in checks:
            lines.append("- {}：{} `{}`".format(label, "OK" if passed else "NO", path))
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for label, passed, path in checks:
            cards.append(
                '<article class="visibility-card {status}"><strong>{label}</strong><span>{result}</span><code>{path}</code></article>'.format(
                    status="pass" if passed else "fail",
                    label=html.escape(label),
                    result="OK" if passed else "NO",
                    path=html.escape(str(path)),
                )
            )
        for item in automated["checks"]:
            passed = item["status"] == "PASS"
            cards.append(
                '<article class="visibility-card {status}"><strong>{label}</strong><span>{result}</span><code>{path}</code></article>'.format(
                    status="pass" if passed else "fail",
                    label=html.escape(str(item["label"])),
                    result=html.escape(str(item["status"])),
                    path=html.escape(str(probe_path)),
                )
            )
        for item in automated["screenshot_checks"]:
            passed = item["status"] == "PASS"
            cards.append(
                '<article class="visibility-card {status}"><strong>{label}</strong><span>{result}</span><code>{path}</code></article>'.format(
                    status="pass" if passed else "fail",
                    label=html.escape(str(item["label"])),
                    result=html.escape(str(item["status"])),
                    path=html.escape(str(screenshot_metrics_path)),
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo 波形可见性验收</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1100px;margin:0 auto;padding:32px 22px}",
            ".hero{padding:26px;border-radius:8px;background:#17324d;color:#fff;box-shadow:0 18px 45px rgba(31,45,61,.10)}",
            ".hero h1{margin:0 0 8px;font-size:30px}",
            ".grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:20px}",
            ".visibility-card{display:grid;gap:8px;padding:16px;border-radius:8px;background:#fff;border:1px solid #dbe3ee}",
            ".visibility-card.pass{border-left:6px solid #0f8a5f}",
            ".visibility-card.fail{border-left:6px solid #b42318}",
            ".visibility-card span{font-weight:800}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:760px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo 波形可见性验收</h1><p>状态：{}</p></section>'.format(html.escape(status)),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "visible": visible,
            "status": status,
            "runtime_status": runtime_status,
            "screenshot_status": screenshot_status,
            "markdown_path": markdown_path,
            "html_path": html_path,
            "checks": checks,
            "automated": automated,
        }

    def write_async_fifo_wave_screenshot_report(self, project_dir: Any) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = reports_dir / "wave_visibility.png"
        markdown_path = reports_dir / "wave_screenshot.md"
        html_path = reports_dir / "wave_screenshot.html"
        capture_script_path = reports_dir / "capture_wave_screenshot.ps1"
        metrics_path = reports_dir / "wave_screenshot_metrics.json"
        captured = screenshot_path.exists() and screenshot_path.stat().st_size > 8
        automated: Any = evaluate_wave_open_check(
            reports_dir / "wave_open_check.json",
            screenshot_metrics_path=metrics_path,
        )
        screenshot_metrics = automated["screenshot_metrics"] or {}
        screenshot_status = (
            str(automated["screenshot_status"])
            if captured
            else "PENDING"
        )
        status = screenshot_status
        non_uniform_ratio = float(
            screenshot_metrics.get("non_uniform_ratio", 0.0)
        )
        capture_script = render_window_capture_script(
            screenshot_name="wave_visibility.png",
            metrics_name="wave_screenshot_metrics.json",
        )
        capture_script_path.write_text(capture_script, encoding="utf-8")

        lines = [
            "# async-fifo GUI 波形截图验收",
            "",
            "- 状态：{}".format(status),
            "- 截图：`{}`".format(screenshot_path),
            "- 截图指标：`{}`".format(metrics_path),
            "- 窗口标题：{}".format(
                screenshot_metrics.get("window_title", "-")
            ),
            "- 截图唯一颜色数：{}".format(
                screenshot_metrics.get("unique_colors", "-")
            ),
            "- 非均匀像素比例：{:.2f}%".format(
                non_uniform_ratio * 100.0
            ),
            "- 捕获脚本：`{}`".format(capture_script_path),
            "",
            "## 使用方式",
            "",
            "1. 先运行 `python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs` 打开 Vivado GUI 波形。",
            "2. 确认波形窗口可见后，在 PowerShell 中运行 `outputs/async-fifo/reports/capture_wave_screenshot.ps1`。",
            "3. 再运行 `python .trae/agent/agent.py --check-rtl async-fifo --output-dir outputs` 刷新报告索引。",
            "",
        ]
        if captured:
            lines.extend([
                "## 截图预览",
                "",
                "![async-fifo waveform](wave_visibility.png)",
                "",
            ])
        else:
            lines.extend([
                "## 截图预览",
                "",
                "尚未捕获 `wave_visibility.png`。该项不会阻断批处理自检，但用于人工确认 GUI 中确实能看到波形。",
                "",
            ])
        markdown_path.write_text("\n".join(lines), encoding="utf-8")

        screenshot_block = (
            '<img src="wave_visibility.png" alt="async-fifo waveform screenshot">'
            if captured
            else '<p class="empty">尚未捕获截图。打开 Vivado 波形后运行 capture_wave_screenshot.ps1。</p>'
        )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo GUI 波形截图验收</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1120px;margin:0 auto;padding:32px 22px}",
            ".hero{padding:26px;border-radius:8px;background:#17324d;color:#fff}",
            ".hero h1{margin:0 0 8px;font-size:30px}",
            ".screenshot-card{margin-top:18px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".screenshot-card.pass{border-left:6px solid #0f8a5f}",
            ".screenshot-card.pending{border-left:6px solid #b7791f}",
            ".screenshot-card.fail{border-left:6px solid #b42318}",
            ".screenshot-card img{display:block;width:100%;max-height:720px;object-fit:contain;border-radius:6px;border:1px solid #dbe3ee;background:#101828}",
            ".empty{margin:0;color:#6b778c}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo GUI 波形截图验收</h1><p>状态：{}</p></section>'.format(html.escape(status)),
            '<section class="screenshot-card {}">'.format(status.lower()),
            screenshot_block,
            '<p><strong>截图文件</strong></p><code>{}</code>'.format(html.escape(str(screenshot_path))),
            '<p><strong>截图指标</strong></p><code>{}</code>'.format(html.escape(str(metrics_path))),
            '<p><strong>捕获脚本</strong></p><code>{}</code>'.format(html.escape(str(capture_script_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "captured": captured,
            "screenshot_status": screenshot_status,
            "markdown_path": markdown_path,
            "html_path": html_path,
            "capture_script_path": capture_script_path,
            "screenshot_path": screenshot_path,
            "metrics_path": metrics_path,
            "automated": automated,
        }

    def write_async_fifo_uvm_wave_screenshot_report(self, project_dir: Any, wave_kind: Any="coverage") -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        if wave_kind not in ("smoke", "coverage"):
            raise ValueError("Unsupported UVM wave kind: {}".format(wave_kind))

        wave_db_name = "async_fifo_uvm_coverage.wdb" if wave_kind == "coverage" else "async_fifo_uvm_smoke.wdb"
        wave_db_path = sim_dir / wave_db_name
        screenshot_path = reports_dir / "uvm_wave_visibility.png"
        markdown_path = reports_dir / "uvm_wave_screenshot.md"
        html_path = reports_dir / "uvm_wave_screenshot.html"
        capture_script_path = reports_dir / "capture_uvm_wave_screenshot.ps1"
        probe_path = reports_dir / "uvm_{}_wave_open_check.json".format(
            wave_kind
        )
        metrics_path = reports_dir / "uvm_wave_screenshot_metrics.json"
        captured = screenshot_path.exists() and screenshot_path.stat().st_size > 8
        automated: Any = evaluate_wave_open_check(
            probe_path,
            screenshot_metrics_path=metrics_path,
        )
        probe = automated["probe"] or {}
        screenshot_metrics = automated["screenshot_metrics"] or {}
        runtime_status = str(automated["runtime_status"])
        screenshot_status = (
            str(automated["screenshot_status"])
            if captured
            else "PENDING"
        )
        if runtime_status == "FAIL" or screenshot_status == "FAIL":
            status = "FAIL"
        elif runtime_status == "PASS" and screenshot_status == "PASS":
            status = "PASS"
        else:
            status = "PENDING"
        non_uniform_ratio = float(
            screenshot_metrics.get("non_uniform_ratio", 0.0)
        )
        capture_script = (
            "# capture_uvm_wave_screenshot.ps1\n"
            + render_window_capture_script(
                screenshot_name="uvm_wave_visibility.png",
                metrics_name="uvm_wave_screenshot_metrics.json",
            )
        )
        capture_script_path.write_text(capture_script, encoding="utf-8")

        lines = [
            "# async-fifo UVM GUI 波形截图验收",
            "",
            "- 状态：{}".format(status),
            "- 运行时探针状态：{}".format(runtime_status),
            "- 截图像素状态：{}".format(screenshot_status),
            "- UVM 波形类型：{}".format(wave_kind),
            "- WDB：`{}`".format(wave_db_path),
            "- Scope 数：{}".format(probe.get("scope_count", "-")),
            "- Object 数：{}".format(probe.get("object_count", "-")),
            "- Wave 数：{}".format(probe.get("wave_count", "-")),
            "- Wave Config 数：{}".format(probe.get("wave_config_count", "-")),
            "- 截图：`{}`".format(screenshot_path),
            "- 截图指标：`{}`".format(metrics_path),
            "- 截图唯一颜色数：{}".format(
                screenshot_metrics.get("unique_colors", "-")
            ),
            "- 非均匀像素比例：{:.2f}%".format(
                non_uniform_ratio * 100.0
            ),
            "- 捕获脚本：`{}`".format(capture_script_path),
            "",
            "## 使用方式",
            "",
            "1. 先运行 `python .trae/agent/agent.py --open-uvm-wave async-fifo --uvm-wave-kind {} --output-dir outputs` 打开 Vivado GUI UVM 波形。".format(wave_kind),
            "2. 确认 UVM 波形窗口可见后，在 PowerShell 中运行 `outputs/async-fifo/reports/capture_uvm_wave_screenshot.ps1`。",
            "3. 再运行 `python .trae/agent/agent.py --open-uvm-wave async-fifo --uvm-wave-kind {} --output-dir outputs` 刷新截图验收报告。".format(wave_kind),
            "",
            "## 截图预览",
            "",
        ]
        if captured:
            lines.extend(["![async-fifo UVM waveform](uvm_wave_visibility.png)", ""])
        else:
            lines.extend([
                "尚未捕获 `uvm_wave_visibility.png`。该项不会阻断批处理自检，但用于人工确认 Vivado GUI 中确实能看到 UVM 波形。",
                "",
            ])
        markdown_path.write_text("\n".join(lines), encoding="utf-8")

        screenshot_block = (
            '<img src="uvm_wave_visibility.png" alt="async-fifo UVM waveform screenshot">'
            if captured
            else '<p class="empty">尚未捕获截图。打开 Vivado UVM 波形后运行 capture_uvm_wave_screenshot.ps1。</p>'
        )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM GUI 波形截图验收</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1120px;margin:0 auto;padding:32px 22px}",
            ".hero{padding:26px;border-radius:8px;background:#17324d;color:#fff}",
            ".hero h1{margin:0 0 8px;font-size:30px}",
            ".screenshot-card{margin-top:18px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".screenshot-card.pass{border-left:6px solid #0f8a5f}",
            ".screenshot-card.pending{border-left:6px solid #b7791f}",
            ".screenshot-card.fail{border-left:6px solid #b42318}",
            ".screenshot-card img{display:block;width:100%;max-height:720px;object-fit:contain;border-radius:6px;border:1px solid #dbe3ee;background:#101828}",
            ".empty{margin:0;color:#6b778c}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM GUI 波形截图验收</h1><p>状态：{} · 类型：{}</p></section>'.format(html.escape(status), html.escape(wave_kind)),
            '<section class="screenshot-card {}">'.format(status.lower()),
            screenshot_block,
            '<p><strong>WDB</strong></p><code>{}</code>'.format(html.escape(str(wave_db_path))),
            '<p><strong>运行时探针</strong></p><code>{}</code>'.format(html.escape(str(probe_path))),
            '<p><strong>截图文件</strong></p><code>{}</code>'.format(html.escape(str(screenshot_path))),
            '<p><strong>截图指标</strong></p><code>{}</code>'.format(html.escape(str(metrics_path))),
            '<p><strong>捕获脚本</strong></p><code>{}</code>'.format(html.escape(str(capture_script_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "captured": captured,
            "runtime_status": runtime_status,
            "screenshot_status": screenshot_status,
            "markdown_path": markdown_path,
            "html_path": html_path,
            "capture_script_path": capture_script_path,
            "screenshot_path": screenshot_path,
            "wave_db_path": wave_db_path,
            "probe_path": probe_path,
            "metrics_path": metrics_path,
            "automated": automated,
        }

    def write_async_fifo_reports_index(self, project_dir: Any) -> Any:
        return self.write_target_dashboard(
            project_dir,
            extra_resources=[
                {
                    "title": "问题复盘",
                    "path": (
                        self.project_root
                        / "docs"
                        / "vivado_async_fifo_lessons_learned.md"
                    ),
                }
            ],
        )
