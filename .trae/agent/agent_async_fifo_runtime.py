# -*- coding: utf-8 -*-
from typing import Any, TYPE_CHECKING
import os
import sys
from pathlib import Path

from wave_visibility import render_wave_open_probe_tcl


class AsyncFifoRuntimeMixin:
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

    def resolve_async_fifo_vcd_path(self, output_dir: Any="outputs") -> Any:
        return Path(output_dir) / "async-fifo" / "sim" / "async_fifo_trace.vcd"

    def collect_async_fifo_vcd_analysis_with_rwave_batch(self, vcd_path: Any, limit: Any=20) -> Any:
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
            "vcd_path": vcd_path,
            "info": batch["info"],
            "write_events": batch["write_events"],
            "read_events": batch["read_events"],
        }

    def collect_async_fifo_vcd_analysis(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
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
            "info": info,
            "write_events": write_events,
            "read_events": read_events,
        }

    def analyze_async_fifo_vcd(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
        try:
            analysis = self.collect_async_fifo_vcd_analysis(
                output_dir=output_dir,
                limit=limit,
                waveform_backend=waveform_backend,
            )
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            print("Run --sim-rtl async-fifo first, or check --output-dir.", file=sys.stderr)
            return False
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return False

        vcd_path = analysis["vcd_path"]
        info = analysis["info"]
        write_events = analysis["write_events"]
        read_events = analysis["read_events"]

        print("Async FIFO VCD analysis")
        print("=" * 60)
        print("File: {}".format(vcd_path))
        print("Signals: {}".format(info.get("signal_count", "unknown")))
        print("Backend: {}".format(info.get("_waveform_backend", "unknown")))
        print("Time range: {} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")))
        print("Duration: {}".format(info.get("duration_h", "unknown")))
        print("Timescale: {}".format(info.get("timescale", "unknown")))
        print("Write handshakes: {}".format(write_events.get("total", write_events.get("shown", "unknown"))))
        print("Read handshakes: {}".format(read_events.get("total", read_events.get("shown", "unknown"))))

        for title, result in [("Writes", write_events), ("Reads", read_events)]:
            rows = result.get("segments") or result.get("intervals") or result.get("events") or []
            print("\n{}".format(title))
            for index, row in enumerate(rows[: int(limit)], start=1):
                begin = row.get("begin_h") or row.get("time_h") or row.get("at_h") or "unknown"
                end = row.get("end_h")
                values = row.get("values") or {}
                if end:
                    print("  {}. {} -> {} {}".format(index, begin, end, values))
                else:
                    print("  {}. {} {}".format(index, begin, values))

        return True

    def async_fifo_required_wcfg_objects(self) -> Any:
        return [
            "/tb_async_fifo/scenario_id",
            "/tb_async_fifo/wr_clk",
            "/tb_async_fifo/rd_clk",
            "/tb_async_fifo/write_count",
            "/tb_async_fifo/read_count",
            "/tb_async_fifo/dut/full_reg",
            "/tb_async_fifo/dut/empty_reg",
        ]

    def async_fifo_regression_cases(self) -> Any:
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

        print("Async FIFO RTL check")
        print("=" * 60)
        ok = True
        for label, passed, path in checks:
            print("[{}] {}: {}".format("OK" if passed else "NO", label, path))
            ok = ok and passed
        return ok

    def open_async_fifo_project_gui(self, project_dir: Any) -> Any:
        project_dir = Path(project_dir)
        sim_dir = project_dir / "sim"
        xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
        wave_db_path = self.resolve_async_fifo_wave_db(sim_dir)
        gui_script_path = sim_dir / "open_async_fifo_project_gui.tcl"

        if not xpr_path.exists():
            print("Vivado project not found: {}".format(xpr_path), file=sys.stderr)
            return False
        if not wave_db_path.exists():
            print("Vivado waveform database not found: {}".format(wave_db_path), file=sys.stderr)
            return False
        gui_script_path.write_text(
            self.render_async_fifo_open_project_gui_script(),
            encoding="utf-8",
        )

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found; cannot open waveform GUI.", file=sys.stderr)
            return False

        self.launch_vivado_gui(vivado_command, gui_script_path.name, sim_dir)
        print("Vivado project GUI launched: {}".format(xpr_path))
        print("Vivado waveform database: {}".format(wave_db_path))
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
            print("Vivado UVM waveform database not found: {}".format(wave_db_path), file=sys.stderr)
            return False

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found; cannot open UVM waveform GUI.", file=sys.stderr)
            return False

        self.launch_vivado_gui(vivado_command, gui_script_path.name, sim_dir)
        screenshot_report = self.write_async_fifo_uvm_wave_screenshot_report(project_dir, wave_kind=wave_kind)
        print("Vivado UVM waveform GUI launched: {}".format(wave_db_path))
        print("UVM waveform screenshot report: {}".format(screenshot_report["markdown_path"]))
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

    def run_async_fifo_vivado_sim(self, output_dir: Any="outputs", open_wave_gui: Any=True, data_width: Any=8, addr_width: Any=4) -> Any:
        project_dir = self.generate_rtl_project(
            "async-fifo",
            output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        sim_result = self.run_vivado_batch(
            vivado_command,
            "run_vivado_async_fifo.tcl",
            sim_dir,
        )
        if sim_result.returncode != 0:
            print(sim_result.stderr.strip() or sim_result.stdout.strip() or "async FIFO simulation failed", file=sys.stderr)
            return False

        vcd_path = sim_dir / "async_fifo_trace.vcd"
        wave_db_path = self.resolve_async_fifo_wave_db(sim_dir)
        if not vcd_path.exists():
            print("Simulation did not generate VCD: {}".format(vcd_path), file=sys.stderr)
            return False
        if not wave_db_path.exists():
            print("Simulation did not generate WDB: {}".format(wave_db_path), file=sys.stderr)
            return False

        project_result = self.run_vivado_batch(
            vivado_command,
            "create_async_fifo_project.tcl",
            sim_dir,
            extra_args=["-nojournal", "-nolog", "-notrace"],
        )
        if project_result.returncode != 0:
            print(project_result.stderr.strip() or project_result.stdout.strip() or "Vivado project generation failed", file=sys.stderr)
            return False

        print("Async FIFO simulation completed")
        print("Generated VCD: {}".format(vcd_path))
        print("Generated WDB: {}".format(wave_db_path))
        print("Vivado project: {}".format(project_dir / "vivado_project" / "async_fifo_project.xpr"))
        report_path = self.write_async_fifo_sim_report(
            project_dir=project_dir,
            vcd_path=vcd_path,
            wave_db_path=wave_db_path,
            sim_result=sim_result,
            project_result=project_result,
        )
        print("Simulation report: {}".format(report_path))
        if open_wave_gui:
            self.open_async_fifo_project_gui(project_dir)
        return True

    def run_async_fifo_regression(self, output_dir: Any="outputs", open_wave_gui: Any=False) -> Any:
        root_project_dir = self.write_async_fifo_project(output_dir)
        self.write_async_fifo_regression_matrix(root_project_dir)
        results = []
        all_passed = True

        for case in self.async_fifo_regression_cases():
            case_output_dir = root_project_dir / "regression" / case["name"]
            passed = self.run_async_fifo_vivado_sim(
                output_dir=case_output_dir,
                open_wave_gui=False,
                data_width=case["data_width"],
                addr_width=case["addr_width"],
            )
            all_passed = all_passed and passed
            results.append({
                "name": case["name"],
                "data_width": case["data_width"],
                "addr_width": case["addr_width"],
                "status": "PASS" if passed else "FAIL",
                "output_dir": case_output_dir / "async-fifo",
            })

        self.write_async_fifo_regression_summary(root_project_dir, results)
        if open_wave_gui and all_passed:
            self.open_async_fifo_project_gui(root_project_dir)
        return all_passed

    def run_async_fifo_uvm_smoke(self, output_dir: Any="outputs", open_wave_gui: Any=True, data_width: Any=8, addr_width: Any=4) -> Any:
        project_dir = self.generate_rtl_project(
            "async-fifo",
            output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        self.write_async_fifo_uvm_smoke_project(
            project_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        sim_result = self.run_vivado_batch(
            vivado_command,
            "run_vivado_async_fifo_uvm.tcl",
            sim_dir,
        )
        if sim_result.returncode != 0:
            self.write_async_fifo_uvm_smoke_report(project_dir, sim_result=sim_result)
            print(sim_result.stderr.strip() or sim_result.stdout.strip() or "async FIFO UVM smoke failed", file=sys.stderr)
            return False

        report = self.write_async_fifo_uvm_smoke_report(project_dir, sim_result=sim_result)
        if not report["passed"]:
            print("UVM smoke markers were not found in the simulation log.", file=sys.stderr)
            return False

        print("Async FIFO UVM smoke completed")
        print("UVM log: {}".format(report["log_path"]))
        print("Generated WDB: {}".format(report["wdb_path"]))
        print("UVM smoke report: {}".format(report["markdown_path"]))
        if open_wave_gui:
            self.open_async_fifo_project_gui(project_dir)
        return True

    def run_async_fifo_uvm_coverage(
        self,
        output_dir: Any="outputs",
        data_width: Any=8,
        addr_width: Any=4,
        coverage_threshold: Any=None,
        coverage_percent: Any=None,
        coverage_thresholds: Any=None,
        seed: Any=None,
    ) -> Any:
        project_dir = self.generate_rtl_project(
            "async-fifo",
            output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        self.write_async_fifo_uvm_coverage_project(
            project_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        env = None
        if seed is not None:
            env = os.environ.copy()
            env["ASYNC_FIFO_UVM_SEED"] = str(int(seed))

        sim_result = self.run_vivado_batch(
            vivado_command,
            "run_vivado_async_fifo_uvm_coverage.tcl",
            sim_dir,
            env=env,
        )
        if sim_result.returncode != 0:
            self.write_async_fifo_uvm_coverage_report(project_dir, sim_result=sim_result)
            summary_report = self.write_async_fifo_uvm_coverage_summary_report(
                project_dir,
                sim_result=sim_result,
                coverage_threshold=coverage_threshold,
                coverage_percent=coverage_percent,
                coverage_thresholds=coverage_thresholds,
            )
            self.write_async_fifo_coverage_history(
                project_dir,
                summary_report,
                status="FAIL",
                vivado_command=vivado_command,
                seed=seed,
            )
            self.write_async_fifo_reports_index(project_dir)
            print(sim_result.stderr.strip() or sim_result.stdout.strip() or "async FIFO UVM coverage failed", file=sys.stderr)
            return False

        functional_report = self.write_async_fifo_uvm_functional_coverage_report(project_dir)
        report = self.write_async_fifo_uvm_coverage_report(project_dir, sim_result=sim_result)
        auto_percent = coverage_percent
        if auto_percent is None:
            percent_summary = self.extract_async_fifo_coverage_percent(project_dir / "reports" / "uvm_coverage_percent.txt")
            if percent_summary["available"] and percent_summary["total_percent"] is not None:
                auto_percent = percent_summary["total_percent"]
        summary_report = self.write_async_fifo_uvm_coverage_summary_report(
            project_dir,
            sim_result=sim_result,
            coverage_threshold=coverage_threshold,
            coverage_percent=auto_percent,
            coverage_thresholds=coverage_thresholds,
        )
        if not report["passed"]:
            self.write_async_fifo_coverage_history(
                project_dir,
                summary_report,
                status="FAIL",
                vivado_command=vivado_command,
                seed=seed,
            )
            self.write_async_fifo_reports_index(project_dir)
            print("UVM coverage markers or xsim.codeCov database were not found.", file=sys.stderr)
            return False
        functional_log = ""
        if functional_report["log_path"].exists():
            functional_log = functional_report["log_path"].read_text(encoding="utf-8", errors="replace")
        if "ASYNC_FIFO_SVA_FAIL" in functional_log:
            self.write_async_fifo_coverage_history(
                project_dir,
                summary_report,
                status="FAIL",
                vivado_command=vivado_command,
                seed=seed,
            )
            self.write_async_fifo_reports_index(project_dir)
            print("UVM assertion failure marker was found.", file=sys.stderr)
            return False
        if not summary_report["coverage_gate_passed"]:
            self.write_async_fifo_coverage_history(
                project_dir,
                summary_report,
                status="FAIL",
                vivado_command=vivado_command,
                seed=seed,
            )
            self.write_async_fifo_reports_index(project_dir)
            print("UVM coverage threshold gate failed.", file=sys.stderr)
            print("UVM coverage summary: {}".format(summary_report["markdown_path"]))
            return False

        self.write_async_fifo_coverage_history(
            project_dir,
            summary_report,
            status="PASS",
            vivado_command=vivado_command,
            seed=seed,
        )
        self.write_async_fifo_reports_index(project_dir)
        print("Async FIFO UVM coverage completed")
        print("UVM log: {}".format(report["log_path"]))
        print("Generated WDB: {}".format(report["wdb_path"]))
        print("Coverage DB: {}".format(report["code_cov_dir"]))
        print("UVM coverage report: {}".format(report["markdown_path"]))
        print("UVM coverage summary: {}".format(summary_report["markdown_path"]))
        print("UVM functional coverage report: {}".format(functional_report["markdown_path"]))
        return True

    def run_async_fifo_uvm_random_regression(self, output_dir: Any="outputs", seeds: Any=None) -> Any:
        if seeds is None:
            seeds = [101, 202, 303]
        project_dir = Path(output_dir) / "async-fifo"
        results = []
        all_passed = True
        for seed in seeds:
            seed_value = int(seed)
            seed_output_dir = project_dir / "uvm_regression" / "seed_{}".format(seed_value)
            seed_project_dir = seed_output_dir / "async-fifo"
            passed = self.run_async_fifo_uvm_coverage(output_dir=seed_output_dir, seed=seed_value)
            all_passed = all_passed and passed
            failure_archive = None
            if not passed:
                failure_archive = self.archive_async_fifo_uvm_failed_seed(
                    project_dir,
                    seed_output_dir,
                    seed_project_dir,
                    output_dir,
                    seed_value,
                )
            results.append({
                "seed": seed_value,
                "status": "PASS" if passed else "FAIL",
                "log": seed_project_dir / "sim" / "async_fifo_uvm_coverage.log",
                "wdb": seed_project_dir / "sim" / "async_fifo_uvm_coverage.wdb",
                "project": seed_project_dir,
                "failure_archive": (
                    failure_archive["archive_dir"]
                    if failure_archive is not None
                    else None
                ),
                "reproduce": (
                    failure_archive["reproduce_script_path"]
                    if failure_archive is not None
                    else None
                ),
                "open_wdb": (
                    failure_archive["wave_open_script_path"]
                    if failure_archive is not None
                    else None
                ),
            })
        self.write_async_fifo_uvm_random_regression_report(project_dir, results)
        return all_passed
