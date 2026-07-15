# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from digital_ic_agent._runtime.agent_async_fifo_runtime_support import (
    AsyncFifoRegressionCase,
    AsyncFifoVcdAnalysis,
    PathLike,
    WaveInfo,
    WaveSearchResult,
    build_async_fifo_error_lines,
    build_async_fifo_rtl_check_lines,
    build_async_fifo_vcd_analysis_lines,
    emit_async_fifo_lines,
)
from digital_ic_agent._runtime.wave_visibility import render_wave_open_probe_tcl


class AsyncFifoAnalysisMixin:
    if TYPE_CHECKING:
        archive_async_fifo_uvm_failed_seed: Any
        extract_async_fifo_coverage_percent: Any
        generate_rtl_project: Any
        launch_vivado_gui: Any
        parse_async_fifo_wcfg_summary: Any
        render_async_fifo_open_project_gui_script: Any
        resolve_rwave_command: Any
        resolve_vivado_command: Any
        run_rwave_batch_json: Any
        run_vivado_batch: Any
        run_waveform_analyzer_json: Any
        write_async_fifo_coverage_history: Any
        write_async_fifo_project: Any
        write_async_fifo_regression_matrix: Any
        write_async_fifo_regression_summary: Any
        write_async_fifo_reports_index: Any
        write_async_fifo_sim_report: Any
        write_async_fifo_summary_report: Any
        write_async_fifo_uvm_coverage_project: Any
        write_async_fifo_uvm_coverage_report: Any
        write_async_fifo_uvm_coverage_summary_report: Any
        write_async_fifo_uvm_functional_coverage_report: Any
        write_async_fifo_uvm_random_regression_report: Any
        write_async_fifo_uvm_smoke_project: Any
        write_async_fifo_uvm_smoke_report: Any
        write_async_fifo_uvm_wave_screenshot_report: Any
        write_async_fifo_wave_screenshot_report: Any
        write_async_fifo_wave_visibility_report: Any

    def resolve_async_fifo_vcd_path(self, output_dir: PathLike = "outputs") -> Path:
        return Path(output_dir) / "async-fifo" / "sim" / "async_fifo_trace.vcd"

    def collect_async_fifo_vcd_analysis_with_rwave_batch(
        self,
        vcd_path: PathLike,
        limit: int = 20,
    ) -> AsyncFifoVcdAnalysis:
        command_lines = [
            "info #info",
            (
                "search --condition tb_async_fifo.full=0 "
                "--changed tb_async_fifo.write_count "
                "--show tb_async_fifo.wr_data,tb_async_fifo.write_count "
                "--limit {} #write_events"
            ).format(int(limit)),
            (
                "search --condition tb_async_fifo.error_count=0 "
                "--changed tb_async_fifo.read_count "
                "--show tb_async_fifo.rd_data,tb_async_fifo.read_count "
                "--limit {} #read_events"
            ).format(int(limit)),
        ]
        batch = self.run_rwave_batch_json(vcd_path, command_lines)
        return {
            "vcd_path": Path(vcd_path),
            "info": cast(WaveInfo, batch["info"]),
            "write_events": cast(WaveSearchResult, batch["write_events"]),
            "read_events": cast(WaveSearchResult, batch["read_events"]),
        }

    def collect_async_fifo_vcd_analysis(
        self,
        output_dir: PathLike = "outputs",
        limit: int = 20,
        waveform_backend: str = "auto",
    ) -> AsyncFifoVcdAnalysis:
        vcd_path = self.resolve_async_fifo_vcd_path(output_dir)
        if not vcd_path.exists():
            raise FileNotFoundError("Async FIFO VCD file not found: {}".format(vcd_path))

        backend = str(waveform_backend or "auto").strip().lower()
        if backend == "rwave" or (backend == "auto" and self.resolve_rwave_command()):
            try:
                return self.collect_async_fifo_vcd_analysis_with_rwave_batch(vcd_path, limit=limit)
            except FileNotFoundError:
                if backend == "rwave":
                    raise
            except RuntimeError:
                if backend == "rwave":
                    raise

        info = self.run_waveform_analyzer_json("info", vcd_path, backend=waveform_backend)
        write_events = self.run_waveform_analyzer_json(
            "search",
            vcd_path,
            "--condition",
            "tb_async_fifo.full=0",
            "--changed",
            "tb_async_fifo.write_count",
            "--show",
            "tb_async_fifo.wr_data,tb_async_fifo.write_count",
            "--limit",
            limit,
            backend=waveform_backend,
        )
        read_events = self.run_waveform_analyzer_json(
            "search",
            vcd_path,
            "--condition",
            "tb_async_fifo.error_count=0",
            "--changed",
            "tb_async_fifo.read_count",
            "--show",
            "tb_async_fifo.rd_data,tb_async_fifo.read_count",
            "--limit",
            limit,
            backend=waveform_backend,
        )
        return {
            "vcd_path": vcd_path,
            "info": cast(WaveInfo, info),
            "write_events": cast(WaveSearchResult, write_events),
            "read_events": cast(WaveSearchResult, read_events),
        }

    def analyze_async_fifo_vcd(
        self,
        output_dir: PathLike = "outputs",
        limit: int = 20,
        waveform_backend: str = "auto",
    ) -> bool:
        try:
            analysis = self.collect_async_fifo_vcd_analysis(
                output_dir=output_dir,
                limit=limit,
                waveform_backend=waveform_backend,
            )
        except FileNotFoundError as exc:
            emit_async_fifo_lines(
                build_async_fifo_error_lines(
                    str(exc),
                    "Run --sim-rtl async-fifo first, or check --output-dir.",
                ),
                stream=sys.stderr,
            )
            return False
        except RuntimeError as exc:
            emit_async_fifo_lines(build_async_fifo_error_lines(str(exc)), stream=sys.stderr)
            return False

        emit_async_fifo_lines(build_async_fifo_vcd_analysis_lines(analysis, limit=int(limit)))

        return True

    def async_fifo_required_wcfg_objects(self) -> list[str]:
        return [
            "/tb_async_fifo/scenario_id",
            "/tb_async_fifo/wr_clk",
            "/tb_async_fifo/rd_clk",
            "/tb_async_fifo/write_count",
            "/tb_async_fifo/read_count",
            "/tb_async_fifo/dut/full_reg",
            "/tb_async_fifo/dut/empty_reg",
        ]

    def async_fifo_regression_cases(self) -> list[AsyncFifoRegressionCase]:
        return [
            {"name": "dw8_aw4", "data_width": 8, "addr_width": 4},
            {"name": "dw16_aw4", "data_width": 16, "addr_width": 4},
            {"name": "dw8_aw3", "data_width": 8, "addr_width": 3},
        ]

    def check_async_fifo_rtl(self, output_dir: Any="outputs") -> Any:
        project_dir = Path(output_dir) / "async-fifo"
        rtl_path = project_dir / "rtl" / "async_fifo.v"
        tb_path = project_dir / "tb" / "tb_async_fifo.v"
        sim_script_path = project_dir / "sim" / "run_vivado_async_fifo.tcl"
        gui_script_path = project_dir / "sim" / "open_async_fifo_project_gui.tcl"
        project_script_path = project_dir / "sim" / "create_async_fifo_project.tcl"
        xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
        vcd_path = project_dir / "sim" / "async_fifo_trace.vcd"
        wave_db_path = self.resolve_async_fifo_wave_db(project_dir / "sim")
        report_path = project_dir / "reports" / "sim_report.md"
        summary_path = project_dir / "reports" / "sim_summary.md"
        regression_path = project_dir / "reports" / "regression_matrix.md"
        regression_summary_path = project_dir / "reports" / "regression_summary.md"
        wave_visibility_path = project_dir / "reports" / "wave_visibility.md"
        wave_screenshot_path = project_dir / "reports" / "wave_screenshot.md"
        reports_index_path = project_dir / "reports" / "index.md"
        if not regression_path.exists() and project_dir.exists():
            self.write_async_fifo_regression_matrix(project_dir)
        if not summary_path.exists() and report_path.exists():
            self.write_async_fifo_summary_report(
                project_dir=project_dir,
                vcd_path=vcd_path,
                wave_db_path=wave_db_path,
                analysis=None,
                analysis_error="Run --sim-rtl or --analyze-rtl-vcd to refresh VCD statistics.",
                regression_path=regression_path,
            )
        if project_dir.exists():
            self.write_async_fifo_wave_visibility_report(project_dir)
            self.write_async_fifo_wave_screenshot_report(project_dir)
            self.write_async_fifo_reports_index(project_dir)
        wcfg = self.parse_async_fifo_wcfg_summary(project_dir)
        wcfg_required = wcfg["exists"]

        checks = [
            ("RTL exists", rtl_path.exists(), rtl_path),
            ("Testbench exists", tb_path.exists(), tb_path),
            ("Vivado sim script exists", sim_script_path.exists(), sim_script_path),
            ("Vivado project script exists", project_script_path.exists(), project_script_path),
            ("Vivado GUI script exists", gui_script_path.exists(), gui_script_path),
            ("Vivado project exists", xpr_path.exists(), xpr_path),
            ("VCD exists", vcd_path.exists(), vcd_path),
            ("WDB exists", wave_db_path.exists(), wave_db_path),
            ("Simulation report exists", report_path.exists(), report_path),
            ("Simulation summary exists", summary_path.exists(), summary_path),
            ("Regression matrix exists", regression_path.exists(), regression_path),
            ("Regression summary exists", regression_summary_path.exists(), regression_summary_path),
            ("Wave visibility report exists", wave_visibility_path.exists(), wave_visibility_path),
            ("Wave screenshot report exists", wave_screenshot_path.exists(), wave_screenshot_path),
            ("Reports index exists", reports_index_path.exists(), reports_index_path),
            ("WCFG optional before GUI open", (not wcfg_required) or wcfg["exists"], wcfg["path"]),
            ("WCFG has waveform objects", (not wcfg_required) or wcfg["object_count"] > 0, wcfg["path"]),
            ("WCFG has required async FIFO signals", (not wcfg_required) or wcfg["valid"], wcfg["path"]),
        ]

        if rtl_path.exists():
            rtl = rtl_path.read_text(encoding="utf-8")
            checks.extend([
                ("RTL declares async_fifo", "module async_fifo" in rtl, rtl_path),
                ("RTL has async_reg synchronizers", '(* async_reg = "true" *)' in rtl, rtl_path),
                ("RTL has full logic", "assign full" in rtl, rtl_path),
                ("RTL has empty logic", "assign empty" in rtl, rtl_path),
            ])

        if tb_path.exists():
            tb = tb_path.read_text(encoding="utf-8")
            checks.extend([
                ("TB dumps async_fifo_trace.vcd", '$dumpfile("async_fifo_trace.vcd")' in tb, tb_path),
                ("TB has scoreboard storage", "expected_data" in tb, tb_path),
                ("TB has reusable write task", "task automatic try_write" in tb, tb_path),
                ("TB covers full boundary scenario", "ASYNC_FIFO_SCENARIO full_boundary PASS" in tb, tb_path),
                ("TB covers empty boundary scenario", "ASYNC_FIFO_SCENARIO empty_boundary PASS" in tb, tb_path),
                ("TB covers reset recovery scenario", "ASYNC_FIFO_SCENARIO reset_recovery PASS" in tb, tb_path),
                ("TB covers mixed stress scenario", "ASYNC_FIFO_SCENARIO mixed_stress PASS" in tb, tb_path),
                ("TB prints scoreboard pass", "ASYNC_FIFO_SCOREBOARD_PASS" in tb, tb_path),
                ("TB fatal on scoreboard fail", "ASYNC_FIFO_SCOREBOARD_FAIL" in tb and "$fatal" in tb, tb_path),
            ])

        ok = True
        emit_async_fifo_lines(build_async_fifo_rtl_check_lines(checks))
        for label, passed, path in checks:
            ok = ok and passed
        return ok

    def open_async_fifo_project_gui(self, project_dir: Any) -> Any:
        project_dir = Path(project_dir)
        sim_dir = project_dir / "sim"
        xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
        wave_db_path = self.resolve_async_fifo_wave_db(sim_dir)
        gui_script_path = sim_dir / "open_async_fifo_project_gui.tcl"

        if not xpr_path.exists():
            emit_async_fifo_lines(
                build_async_fifo_error_lines("Vivado project not found: {}".format(xpr_path)),
                stream=sys.stderr,
            )
            return False
        if not wave_db_path.exists():
            emit_async_fifo_lines(
                build_async_fifo_error_lines(
                    "Vivado waveform database not found: {}".format(wave_db_path)
                ),
                stream=sys.stderr,
            )
            return False
        gui_script_path.write_text(
            self.render_async_fifo_open_project_gui_script(),
            encoding="utf-8",
        )

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            emit_async_fifo_lines(
                build_async_fifo_error_lines(
                    "Vivado command not found; cannot open waveform GUI."
                ),
                stream=sys.stderr,
            )
            return False

        self.launch_vivado_gui(vivado_command, gui_script_path.name, sim_dir)
        emit_async_fifo_lines(
            [
                "Vivado project GUI launched: {}".format(xpr_path),
                "Vivado waveform database: {}".format(wave_db_path),
            ]
        )
        return True

    def open_async_fifo_uvm_wave_gui(self, project_dir: Any, wave_kind: Any="coverage") -> Any:
        project_dir = Path(project_dir)
        sim_dir = project_dir / "sim"
        if wave_kind not in ("smoke", "coverage"):
            raise ValueError("Unsupported UVM wave kind: {}".format(wave_kind))

        wave_db_name = "async_fifo_uvm_coverage.wdb" if wave_kind == "coverage" else "async_fifo_uvm_smoke.wdb"
        wave_db_path = sim_dir / wave_db_name
        gui_script_path = sim_dir / "open_async_fifo_uvm_{}_wave.tcl".format(wave_kind)
        probe_tcl = render_wave_open_probe_tcl(
            "../reports/uvm_{}_wave_open_check.json".format(wave_kind),
            target_name="async-fifo",
            flow_name="uvm-{}".format(wave_kind),
        )
        gui_script_path.write_text(
            """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set wave_db __WAVE_DB__
if {![file exists $wave_db]} {
    puts stderr "UVM waveform database not found: $wave_db"
    exit 1
}
start_gui
open_wave_database $wave_db
add_wave -r /tb_async_fifo_uvm
__WAVE_OPEN_PROBE__
""".replace("__WAVE_DB__", wave_db_name).replace(
                "__WAVE_OPEN_PROBE__",
                probe_tcl,
            ),
            encoding="utf-8",
        )

        if not wave_db_path.exists():
            emit_async_fifo_lines(
                build_async_fifo_error_lines(
                    "Vivado UVM waveform database not found: {}".format(wave_db_path)
                ),
                stream=sys.stderr,
            )
            return False

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            emit_async_fifo_lines(
                build_async_fifo_error_lines(
                    "Vivado command not found; cannot open UVM waveform GUI."
                ),
                stream=sys.stderr,
            )
            return False

        self.launch_vivado_gui(vivado_command, gui_script_path.name, sim_dir)
        screenshot_report = self.write_async_fifo_uvm_wave_screenshot_report(project_dir, wave_kind=wave_kind)
        emit_async_fifo_lines(
            [
                "Vivado UVM waveform GUI launched: {}".format(wave_db_path),
                "UVM waveform screenshot report: {}".format(screenshot_report["markdown_path"]),
            ]
        )
        return True

    def resolve_async_fifo_wave_db(self, sim_dir: Any) -> Any:
        sim_dir = Path(sim_dir)
        latest_path = sim_dir / "latest_async_fifo_wdb.txt"
        if latest_path.exists():
            latest_name = latest_path.read_text(encoding="utf-8").strip()
            if latest_name:
                latest_wdb = sim_dir / latest_name
                if latest_wdb.exists():
                    return latest_wdb
        legacy_wdb = sim_dir / "async_fifo_smoke.wdb"
        if legacy_wdb.exists():
            return legacy_wdb
        candidates = sorted(
            sim_dir.glob("async_fifo_smoke_*.wdb"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else legacy_wdb
