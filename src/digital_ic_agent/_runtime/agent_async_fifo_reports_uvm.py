# -*- coding: utf-8 -*-
import html
from pathlib import Path
from typing import TYPE_CHECKING, Any



class AsyncFifoUvmReportMixin:
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

    def write_async_fifo_uvm_smoke_report(
        self,
        project_dir: Any,
        sim_result: Any=None,
        verdict: Any=None,
    ) -> Any:
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
        passed = (
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in combined
            and "ASYNC_FIFO_UVM_TEST_DONE" in combined
            and (verdict is None or verdict.passed)
        )
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

    def write_async_fifo_uvm_coverage_report(
        self,
        project_dir: Any,
        sim_result: Any=None,
        verdict: Any=None,
    ) -> Any:
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
        passed = smoke_passed and coverage_ready and (verdict is None or verdict.passed)
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
