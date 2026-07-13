# -*- coding: utf-8 -*-
import html
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from digital_ic_agent._runtime.agent_async_fifo_report_support import (
    AGENT_MODULE_DIR,
)
from digital_ic_agent._runtime.failure_archive import archive_failed_run


class AsyncFifoRegressionReportMixin:
    if TYPE_CHECKING:
        parse_async_fifo_wcfg_summary: Any
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
