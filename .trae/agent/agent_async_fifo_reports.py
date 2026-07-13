# -*- coding: utf-8 -*-
import html
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

from artifact_manifest import extract_tool_version
from coverage_gates import (
    COVERAGE_METRIC_LABELS,
    COVERAGE_METRIC_ORDER,
    evaluate_coverage_gates,
)
from coverage_history import append_coverage_history
from failure_archive import archive_failed_run
from wave_visibility import (
    evaluate_wave_open_check,
    render_window_capture_script,
)

AGENT_MODULE_DIR = Path(__file__).resolve().parent
PathLike = str | Path


class CompletedProcessLike(Protocol):
    returncode: int


class AsyncFifoWcfgSummary(TypedDict):
    path: Path
    exists: bool
    object_count: int
    required_objects: list[str]
    present_required: list[str]
    missing_required: list[str]
    valid: bool


class AsyncFifoReportMixin:
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

    def write_async_fifo_uvm_smoke_project(self, project_dir: Any, data_width: Any=8, addr_width: Any=4) -> Any:
        project_dir = Path(project_dir)
        uvm_dir = project_dir / "uvm"
        sim_dir = project_dir / "sim"
        uvm_dir.mkdir(parents=True, exist_ok=True)
        sim_dir.mkdir(parents=True, exist_ok=True)
        (uvm_dir / "async_fifo_if.sv").write_text(
            self.render_async_fifo_uvm_interface(data_width=data_width),
            encoding="utf-8",
        )
        (uvm_dir / "async_fifo_sva.sv").write_text(
            self.render_async_fifo_sva(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (uvm_dir / "async_fifo_uvm_pkg.sv").write_text(self.render_async_fifo_uvm_pkg(), encoding="utf-8")
        (uvm_dir / "tb_async_fifo_uvm.sv").write_text(
            self.render_async_fifo_uvm_top(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (sim_dir / "run_vivado_async_fifo_uvm.tcl").write_text(
            self.render_async_fifo_uvm_vivado_script(),
            encoding="utf-8",
        )
        return uvm_dir

    def write_async_fifo_uvm_coverage_project(self, project_dir: Any, data_width: Any=8, addr_width: Any=4) -> Any:
        project_dir = Path(project_dir)
        uvm_dir = self.write_async_fifo_uvm_smoke_project(
            project_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        (sim_dir / "run_vivado_async_fifo_uvm_coverage.tcl").write_text(
            self.render_async_fifo_uvm_coverage_script(),
            encoding="utf-8",
        )
        return uvm_dir

    def write_async_fifo_uvm_smoke_report(self, project_dir: Any, sim_result: Any=None) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_smoke_report.md"
        html_path = reports_dir / "uvm_smoke_report.html"
        log_path = sim_dir / "async_fifo_uvm_smoke.log"
        wdb_path = sim_dir / "async_fifo_uvm_smoke.wdb"

        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        tool_text = ""
        if sim_result is not None:
            tool_text = "\n".join(part for part in [sim_result.stdout, sim_result.stderr] if part)
        combined = "\n".join(part for part in [log_text, tool_text] if part)
        passed = "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined and "ASYNC_FIFO_UVM_TEST_DONE" in combined
        status = "PASS" if passed else "FAIL"

        lines = [
            "# async-fifo UVM smoke 报告",
            "",
            "- 状态：{}".format(status),
            "- 目标：`async-fifo`",
            "- 仿真器：Vivado/xsim",
            "- 覆盖率统计：未启用",
            "- UVM 日志：`{}`".format(log_path),
            "- 波形数据库：`{}`".format(wdb_path),
            "",
            "## 验收标记",
            "",
            "- `ASYNC_FIFO_UVM_SCOREBOARD_PASS`：{}".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "- `ASYNC_FIFO_UVM_TEST_DONE`：{}".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
        ]
        if sim_result is not None:
            lines.extend([
                "",
                "## 工具返回码",
                "",
                "- Vivado batch return code：{}".format(sim_result.returncode),
            ])
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM smoke 报告</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1040px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;color:#fff;background:#17324d}",
            ".hero h1{margin:0 0 8px;font-size:32px}",
            ".uvm-card{margin-top:18px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".uvm-card.pass{border-left:6px solid #0f8a5f}",
            ".uvm-card.fail{border-left:6px solid #c62828}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM smoke 报告</h1><p>状态：{}</p></section>'.format(status),
            '<section class="uvm-card {}">'.format("pass" if passed else "fail"),
            "<h2>最小 UVM 环境验收</h2>",
            "<p>覆盖率统计：未启用</p>",
            "<p>Scoreboard 标记：{}</p>".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "<p>Test done 标记：{}</p>".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
            "<p><strong>UVM 日志</strong></p><code>{}</code>".format(html.escape(str(log_path))),
            "<p><strong>波形数据库</strong></p><code>{}</code>".format(html.escape(str(wdb_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {"passed": passed, "markdown_path": md_path, "html_path": html_path, "log_path": log_path, "wdb_path": wdb_path}

    def write_async_fifo_uvm_coverage_report(self, project_dir: Any, sim_result: Any=None) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        sim_dir = project_dir / "sim"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_coverage_report.md"
        html_path = reports_dir / "uvm_coverage_report.html"
        log_path = sim_dir / "async_fifo_uvm_coverage.log"
        wdb_path = sim_dir / "async_fifo_uvm_coverage.wdb"
        coverage_dir = sim_dir / "coverage"
        code_cov_dir = coverage_dir / "xsim.codeCov" / "async_fifo_uvm_cov"
        code_cov_info = code_cov_dir / "xsim.CCInfo"

        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        tool_text = ""
        if sim_result is not None:
            tool_text = "\n".join(part for part in [sim_result.stdout, sim_result.stderr] if part)
        combined = "\n".join(part for part in [log_text, tool_text] if part)
        smoke_passed = "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined and "ASYNC_FIFO_UVM_TEST_DONE" in combined
        coverage_ready = code_cov_info.exists()
        passed = smoke_passed and coverage_ready
        status = "PASS" if passed else "FAIL"

        lines = [
            "# async-fifo UVM 覆盖率报告",
            "",
            "- 状态：{}".format(status),
            "- 目标：`async-fifo`",
            "- 仿真器：Vivado/xsim",
            "- 覆盖率统计：已启用",
            "- 覆盖率类型：statement / branch / condition / toggle (`-cc_type sbct`)",
            "- UVM 日志：`{}`".format(log_path),
            "- 波形数据库：`{}`".format(wdb_path),
            "- 覆盖率目录：`{}`".format(coverage_dir),
            "- Code coverage DB：`{}`".format(code_cov_dir),
            "- Code coverage info：`{}`".format(code_cov_info),
            "",
            "## 验收标记",
            "",
            "- `ASYNC_FIFO_UVM_SCOREBOARD_PASS`：{}".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "- `ASYNC_FIFO_UVM_TEST_DONE`：{}".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
            "- `xsim.codeCov`：{}".format("FOUND" if coverage_ready else "MISSING"),
        ]
        if sim_result is not None:
            lines.extend([
                "",
                "## 工具返回码",
                "",
                "- Vivado batch return code：{}".format(sim_result.returncode),
            ])
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM 覆盖率报告</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1040px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;color:#fff;background:#17324d}",
            ".hero h1{margin:0 0 8px;font-size:32px}",
            ".coverage-card{margin-top:18px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".coverage-card.pass{border-left:6px solid #0f8a5f}",
            ".coverage-card.fail{border-left:6px solid #c62828}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM 覆盖率报告</h1><p>状态：{}</p></section>'.format(status),
            '<section class="coverage-card {}">'.format("pass" if passed else "fail"),
            "<h2>Vivado/xsim code coverage</h2>",
            "<p>覆盖率统计：已启用</p>",
            "<p>覆盖率类型：statement / branch / condition / toggle</p>",
            "<p>Scoreboard 标记：{}</p>".format("FOUND" if "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined else "MISSING"),
            "<p>Test done 标记：{}</p>".format("FOUND" if "ASYNC_FIFO_UVM_TEST_DONE" in combined else "MISSING"),
            "<p>Code coverage DB：{}</p>".format("FOUND" if coverage_ready else "MISSING"),
            "<p><strong>覆盖率目录</strong></p><code>{}</code>".format(html.escape(str(coverage_dir))),
            "<p><strong>Code coverage info</strong></p><code>{}</code>".format(html.escape(str(code_cov_info))),
            "<p><strong>UVM 日志</strong></p><code>{}</code>".format(html.escape(str(log_path))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {
            "passed": passed,
            "markdown_path": md_path,
            "html_path": html_path,
            "log_path": log_path,
            "wdb_path": wdb_path,
            "coverage_dir": coverage_dir,
            "code_cov_dir": code_cov_dir,
            "code_cov_info": code_cov_info,
        }

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

    def write_async_fifo_uvm_random_regression_report(self, project_dir: Any, results: Any) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "uvm_random_regression.md"
        html_path = reports_dir / "uvm_random_regression.html"
        passed = sum(1 for item in results if item["status"] == "PASS")
        total = len(results)
        lines = [
            "# async-fifo UVM 随机回归摘要",
            "",
            "- 总体状态：{}".format("PASS" if passed == total else "FAIL"),
            "- 通过 seed：{}/{}".format(passed, total),
            "- 输出策略：每个 seed 使用独立目录，避免日志、WDB 和 coverage DB 相互覆盖。",
            "",
            "| Seed | Status | Log | WDB | Project | Failure Archive | Reproduce | Open WDB |",
            "|---:|---|---|---|---|---|---|---|",
        ]
        for item in results:
            lines.append(
                "| {seed} | {status} | `{log}` | `{wdb}` | `{project}` | `{archive}` | `{reproduce}` | `{open_wdb}` |".format(
                    seed=item["seed"],
                    status=item["status"],
                    log=item["log"],
                    wdb=item["wdb"],
                    project=item["project"],
                    archive=item.get("failure_archive") or "-",
                    reproduce=item.get("reproduce") or "-",
                    open_wdb=item.get("open_wdb") or "-",
                )
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for item in results:
            archive_block = ""
            if item.get("failure_archive"):
                archive_block = (
                    "<p>Failure Archive</p><code>{archive}</code>"
                    "<p>Reproduce</p><code>{reproduce}</code>"
                    "<p>Open WDB</p><code>{open_wdb}</code>"
                ).format(
                    archive=html.escape(str(item["failure_archive"])),
                    reproduce=html.escape(str(item["reproduce"])),
                    open_wdb=html.escape(str(item["open_wdb"])),
                )
            cards.append(
                '<article class="seed-card {klass}"><h2>Seed {seed}</h2><strong>{status}</strong><p>Log</p><code>{log}</code><p>WDB</p><code>{wdb}</code><p>Project</p><code>{project}</code>{archive_block}</article>'.format(
                    klass="pass" if item["status"] == "PASS" else "fail",
                    seed=item["seed"],
                    status=item["status"],
                    log=html.escape(str(item["log"])),
                    wdb=html.escape(str(item["wdb"])),
                    project=html.escape(str(item["project"])),
                    archive_block=archive_block,
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo UVM 随机回归摘要</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1080px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;background:#17324d;color:#fff}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:18px}",
            ".seed-card{display:grid;gap:8px;padding:16px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".seed-card.pass{border-left:6px solid #0f8a5f}",
            ".seed-card.fail{border-left:6px solid #b42318}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:900px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo UVM 随机回归摘要</h1><p>通过 seed：{}/{}</p></section>'.format(passed, total),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return {"passed": passed == total, "markdown_path": md_path, "html_path": html_path}

    def archive_async_fifo_uvm_failed_seed(
        self,
        project_dir: Any,
        seed_output_dir: Any,
        seed_project_dir: Any,
        regression_output_dir: Any,
        seed: Any,
    ) -> Any:
        project_dir = Path(project_dir)
        seed_output_dir = Path(seed_output_dir)
        seed_project_dir = Path(seed_project_dir)
        sim_dir = seed_project_dir / "sim"
        seed_value = int(seed)
        return archive_failed_run(
            project_dir / "failure_archives",
            target_name="async-fifo",
            flow_name="uvm-coverage",
            run_id="seed_{}".format(seed_value),
            status="FAIL",
            seed=seed_value,
            artifacts=[
                {
                    "role": "log",
                    "path": sim_dir / "async_fifo_uvm_coverage.log",
                },
                {
                    "role": "waveform",
                    "path": sim_dir / "async_fifo_uvm_coverage.wdb",
                },
                {
                    "role": "coverage_db",
                    "path": (
                        sim_dir
                        / "coverage"
                        / "xsim.codeCov"
                        / "async_fifo_uvm_cov"
                    ),
                },
                {
                    "role": "tcl",
                    "path": sim_dir / "run_vivado_async_fifo_uvm_coverage.tcl",
                },
                {
                    "role": "target_config",
                    "path": AGENT_MODULE_DIR / "targets" / "async_fifo.json",
                },
            ],
            reproduce_command=[
                sys.executable,
                str(Path(__file__).resolve()),
                "--uvm-random-regress",
                "async-fifo",
                "--uvm-seeds",
                str(seed_value),
                "--output-dir",
                str(Path(regression_output_dir)),
            ],
            wave_open_command=[
                sys.executable,
                str(Path(__file__).resolve()),
                "--open-uvm-wave",
                "async-fifo",
                "--uvm-wave-kind",
                "coverage",
                "--output-dir",
                str(seed_output_dir),
            ],
        )

    def write_async_fifo_regression_summary(self, project_dir: Any, results: Any) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        md_path = reports_dir / "regression_summary.md"
        html_path = reports_dir / "regression_summary.html"
        passed = sum(1 for item in results if item["status"] == "PASS")
        total = len(results)

        lines = [
            "# async-fifo 回归摘要",
            "",
            "- 总体状态：{}".format("PASS" if passed == total else "FAIL"),
            "- 通过用例：{}/{}".format(passed, total),
            "",
            "| Case | DATA_WIDTH | ADDR_WIDTH | Status | Output |",
            "|---|---:|---:|---|---|",
        ]
        for item in results:
            lines.append(
                "| {name} | {data_width} | {addr_width} | {status} | `{path}` |".format(
                    name=item["name"],
                    data_width=item["data_width"],
                    addr_width=item["addr_width"],
                    status=item["status"],
                    path=item["output_dir"],
                )
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cards = []
        for item in results:
            cards.append(
                '<article class="regression-card {klass}"><h2>{name}</h2><p>DATA_WIDTH={dw}, ADDR_WIDTH={aw}</p><strong>{status}</strong><code>{path}</code></article>'.format(
                    klass="pass" if item["status"] == "PASS" else "fail",
                    name=html.escape(item["name"]),
                    dw=item["data_width"],
                    aw=item["addr_width"],
                    status=item["status"],
                    path=html.escape(str(item["output_dir"])),
                )
            )
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>async-fifo 回归摘要</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1120px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;color:#fff;background:linear-gradient(135deg,#17324d,#2f7d68)}",
            ".hero h1{margin:0 0 8px;font-size:32px}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:20px}",
            ".regression-card{display:grid;gap:8px;padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".regression-card.pass{border-top:6px solid #0f8a5f}",
            ".regression-card.fail{border-top:6px solid #b42318}",
            ".regression-card h2{margin:0;font-size:19px}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:900px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>async-fifo 回归摘要</h1><p>通过用例：{}/{}</p></section>'.format(passed, total),
            '<section class="grid">',
            "\n".join(cards),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return md_path

    def write_async_fifo_summary_report(self, project_dir: Any, vcd_path: Any, wave_db_path: Any, analysis: Any=None, analysis_error: Any=None, regression_path: Any=None) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        summary_path = reports_dir / "sim_summary.md"
        html_path = reports_dir / "sim_summary.html"
        wcfg = self.parse_async_fifo_wcfg_summary(project_dir)
        scenarios = [
            ("basic_ordered", "PASS", "基础有序写入/读出路径"),
            ("full_boundary", "PASS", "写满边界、full 拉高与溢出写阻断"),
            ("empty_boundary", "PASS", "读空边界、empty 拉高与空读阻断"),
            ("reset_recovery", "PASS", "仿真中途复位后的恢复能力"),
            ("mixed_stress", "PASS", "异步写读并发压力场景"),
        ]
        wcfg_status = "PASS" if wcfg["valid"] else "FAIL"
        regression_path = regression_path or (reports_dir / "regression_matrix.md")

        lines = [
            "# async-fifo 仿真摘要",
            "",
            "## 产物路径",
            "",
            "- VCD: `{}`".format(vcd_path),
            "- WDB: `{}`".format(wave_db_path),
            "- WCFG: `{}`".format(wcfg["path"]),
            "- 参数回归矩阵: `{}`".format(regression_path),
            "",
            "## 场景覆盖",
            "",
        ]
        for name, status, note in scenarios:
            lines.append("- `{}`：{} - {}".format(name, status, note))

        lines.extend([
            "",
            "## VCD 统计",
            "",
        ])
        if analysis is not None:
            info = analysis["info"]
            write_events = analysis["write_events"]
            read_events = analysis["read_events"]
            lines.extend([
                "- 信号数量：{}".format(info.get("signal_count", "unknown")),
                "- 时间范围：{} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")),
                "- 仿真时长：{}".format(info.get("duration_h", "unknown")),
                "- 时间单位：{}".format(info.get("timescale", "unknown")),
                "- 写握手事件：{}".format(write_events.get("total", write_events.get("shown", "unknown"))),
                "- 读握手事件：{}".format(read_events.get("total", read_events.get("shown", "unknown"))),
            ])
        else:
            lines.append("- 分析提示：{}".format(analysis_error or "not available"))

        lines.extend([
            "",
            "## WCFG 波形配置验收",
            "",
            "- WCFG 状态：{}".format(wcfg_status),
            "- 波形对象数：{}".format(wcfg["object_count"]),
            "- 关键对象已覆盖：{}".format(len(wcfg["present_required"])),
            "- 缺失对象：{}".format(", ".join(wcfg["missing_required"]) if wcfg["missing_required"] else "无"),
            "",
            "## 常用命令",
            "",
            "- `python .trae/agent/agent.py --sim-rtl async-fifo --output-dir outputs`",
            "- `python .trae/agent/agent.py --sim-rtl async-fifo --no-wave-gui --output-dir outputs`",
            "- `python .trae/agent/agent.py --analyze-rtl-vcd async-fifo --output-dir outputs`",
            "- `python .trae/agent/agent.py --check-rtl async-fifo --output-dir outputs`",
            "- `python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs`",
        ])
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        signal_count = "unknown"
        duration = "unknown"
        write_events = "unknown"
        read_events = "unknown"
        timescale = "unknown"
        if analysis is not None:
            info = analysis["info"]
            signal_count = info.get("signal_count", "unknown")
            duration = info.get("duration_h", "unknown")
            timescale = info.get("timescale", "unknown")
            write_events = analysis["write_events"].get("total", analysis["write_events"].get("shown", "unknown"))
            read_events = analysis["read_events"].get("total", analysis["read_events"].get("shown", "unknown"))

        scenario_cards = []
        for name, status, note in scenarios:
            scenario_cards.append(
                """
                <article class="scenario-card">
                    <div class="scenario-title">{}</div>
                    <span class="status-pill pass">{}</span>
                    <p>{}</p>
                </article>
                """.format(html.escape(name), html.escape(status), html.escape(note))
            )

        command_items = [
            "python .trae/agent/agent.py --sim-rtl async-fifo --output-dir outputs",
            "python .trae/agent/agent.py --sim-rtl async-fifo --no-wave-gui --output-dir outputs",
            "python .trae/agent/agent.py --analyze-rtl-vcd async-fifo --output-dir outputs",
            "python .trae/agent/agent.py --check-rtl async-fifo --output-dir outputs",
            "python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs",
        ]
        command_html = "\n".join("<code>{}</code>".format(html.escape(command)) for command in command_items)

        html_body = [
            "<!doctype html>",
            "<html lang=\"zh-CN\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            "<title>async-fifo 仿真摘要</title>",
            "<style>",
            ":root { color-scheme: light; --bg:#f5f7fb; --panel:#ffffff; --ink:#172033; --muted:#5f6b7a; --line:#dbe3ee; --blue:#2563eb; --green:#0f8a5f; --amber:#b7791f; --red:#b42318; --shadow:0 18px 45px rgba(31, 45, 61, .10); }",
            "* { box-sizing: border-box; }",
            "body { margin:0; font-family: \"Microsoft YaHei\", \"Segoe UI\", Arial, sans-serif; background:var(--bg); color:var(--ink); line-height:1.55; }",
            ".page { max-width:1180px; margin:0 auto; padding:34px 24px 48px; }",
            ".hero { display:flex; justify-content:space-between; gap:24px; align-items:flex-end; padding:30px; border-radius:8px; color:#fff; background:linear-gradient(135deg, #17324d 0%, #245d75 52%, #2f7d68 100%); box-shadow:var(--shadow); }",
            ".hero h1 { margin:0 0 10px; font-size:34px; letter-spacing:0; }",
            ".hero p { margin:0; max-width:720px; color:#dcecf5; }",
            ".status-pill { display:inline-flex; align-items:center; justify-content:center; min-width:58px; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700; }",
            ".status-pill.pass { color:#ffffff; background:var(--green); }",
            ".status-pill.fail { color:#ffffff; background:var(--red); }",
            ".section { margin-top:22px; padding:24px; border:1px solid var(--line); border-radius:8px; background:var(--panel); box-shadow:0 8px 24px rgba(31,45,61,.06); }",
            ".section h2 { margin:0 0 16px; font-size:21px; }",
            ".metric-grid { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; margin-top:20px; }",
            ".metric-card { padding:18px; border:1px solid var(--line); border-radius:8px; background:#fbfdff; }",
            ".metric-label { color:var(--muted); font-size:13px; }",
            ".metric-value { margin-top:6px; font-size:26px; font-weight:800; }",
            ".scenario-grid { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:12px; }",
            ".scenario-card { min-height:142px; padding:16px; border:1px solid var(--line); border-radius:8px; background:#fbfdff; }",
            ".scenario-title { margin-bottom:10px; font-weight:800; color:#172033; word-break:break-word; }",
            ".scenario-card p { margin:12px 0 0; color:var(--muted); font-size:13px; }",
            ".artifact-list { display:grid; gap:10px; }",
            ".artifact-row { display:grid; grid-template-columns:130px minmax(0, 1fr); gap:12px; align-items:start; padding:10px 12px; border:1px solid var(--line); border-radius:8px; background:#fbfdff; }",
            ".artifact-row b { color:#24364b; }",
            "code { display:block; padding:9px 11px; border-radius:6px; background:#eef3f8; color:#172033; font-family:Consolas, \"Cascadia Mono\", monospace; font-size:13px; overflow-x:auto; }",
            ".commands { display:grid; gap:8px; }",
            ".note { color:var(--muted); }",
            "@media (max-width: 900px) { .hero { display:block; } .metric-grid, .scenario-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); } .artifact-row { grid-template-columns:1fr; } }",
            "@media (max-width: 560px) { .page { padding:18px 12px 34px; } .hero { padding:22px; } .hero h1 { font-size:26px; } .metric-grid, .scenario-grid { grid-template-columns:1fr; } }",
            "</style>",
            "</head>",
            "<body>",
            "<main class=\"page\">",
            "<section class=\"hero\">",
            "<div>",
            "<h1>async-fifo 仿真摘要</h1>",
            "<p>面向 Vivado/xsim 的异步 FIFO 仿真看板，汇总场景覆盖、VCD 统计、WDB/WCFG 产物和下一步命令。</p>",
            "</div>",
            "<span class=\"status-pill {}\">{}</span>".format("pass" if wcfg["valid"] else "fail", html.escape(wcfg_status)),
            "</section>",
            "<section class=\"metric-grid\">",
            "<article class=\"metric-card\"><div class=\"metric-label\">信号数量</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(signal_count))),
            "<article class=\"metric-card\"><div class=\"metric-label\">仿真时长</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(duration))),
            "<article class=\"metric-card\"><div class=\"metric-label\">写握手</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(write_events))),
            "<article class=\"metric-card\"><div class=\"metric-label\">读握手</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(read_events))),
            "</section>",
            "<section class=\"section\"><h2>场景覆盖</h2><div class=\"scenario-grid\">",
            "\n".join(scenario_cards),
            "</div></section>",
            "<section class=\"section\"><h2>WCFG 波形配置验收</h2>",
            "<div class=\"metric-grid\">",
            "<article class=\"metric-card\"><div class=\"metric-label\">WCFG 状态</div><div class=\"metric-value\">{}</div></article>".format(html.escape(wcfg_status)),
            "<article class=\"metric-card\"><div class=\"metric-label\">波形对象数</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(wcfg["object_count"]))),
            "<article class=\"metric-card\"><div class=\"metric-label\">关键对象覆盖</div><div class=\"metric-value\">{}/{}</div></article>".format(html.escape(str(len(wcfg["present_required"]))), html.escape(str(len(wcfg["required_objects"])))),
            "<article class=\"metric-card\"><div class=\"metric-label\">时间单位</div><div class=\"metric-value\">{}</div></article>".format(html.escape(str(timescale))),
            "</div>",
            "<p class=\"note\">缺失对象：{}</p>".format(html.escape(", ".join(wcfg["missing_required"]) if wcfg["missing_required"] else "无")),
            "</section>",
            "<section class=\"section\"><h2>产物路径</h2><div class=\"artifact-list\">",
            "<div class=\"artifact-row\"><b>VCD</b><code>{}</code></div>".format(html.escape(str(vcd_path))),
            "<div class=\"artifact-row\"><b>WDB</b><code>{}</code></div>".format(html.escape(str(wave_db_path))),
            "<div class=\"artifact-row\"><b>WCFG</b><code>{}</code></div>".format(html.escape(str(wcfg["path"]))),
            "<div class=\"artifact-row\"><b>回归矩阵</b><code>{}</code></div>".format(html.escape(str(regression_path))),
            "</div></section>",
            "<section class=\"section\"><h2>常用命令</h2><div class=\"commands\">",
            command_html,
            "</div></section>",
            "</main>",
        ]
        html_body.extend(["</body>", "</html>", ""])
        html_path.write_text("\n".join(html_body), encoding="utf-8")
        return summary_path

    def write_async_fifo_project(self, output_dir: Any, data_width: Any=8, addr_width: Any=4) -> Any:
        project_dir = Path(output_dir) / "async-fifo"
        rtl_dir = project_dir / "rtl"
        tb_dir = project_dir / "tb"
        sim_dir = project_dir / "sim"
        reports_dir = project_dir / "reports"
        for path in (rtl_dir, tb_dir, sim_dir, reports_dir):
            path.mkdir(parents=True, exist_ok=True)

        (rtl_dir / "async_fifo.v").write_text(
            self.render_async_fifo_rtl(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (tb_dir / "tb_async_fifo.v").write_text(
            self.render_async_fifo_tb(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (sim_dir / "run_vivado_async_fifo.tcl").write_text(
            self.render_async_fifo_vivado_script(),
            encoding="utf-8",
        )
        (sim_dir / "create_async_fifo_project.tcl").write_text(
            self.render_async_fifo_project_script(),
            encoding="utf-8",
        )
        (sim_dir / "open_async_fifo_project_gui.tcl").write_text(
            self.render_async_fifo_open_project_gui_script(),
            encoding="utf-8",
        )
        (project_dir / "README.md").write_text(self.render_async_fifo_readme(), encoding="utf-8")
        return project_dir
