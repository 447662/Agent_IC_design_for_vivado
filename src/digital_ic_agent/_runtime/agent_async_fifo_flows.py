# -*- coding: utf-8 -*-
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from digital_ic_agent._runtime.agent_async_fifo_runtime_support import (
    build_async_fifo_error_lines,
    build_async_fifo_sim_completed_lines,
    build_async_fifo_uvm_coverage_completed_lines,
    build_async_fifo_uvm_smoke_completed_lines,
    emit_async_fifo_lines,
)
from digital_ic_agent._runtime.verification_verdict import (
    aggregate_verification_verdicts,
    evaluate_process_results,
    format_verification_failure,
    write_verification_verdict,
)


class AsyncFifoFlowMixin:
    if TYPE_CHECKING:
        async_fifo_regression_cases: Any
        archive_async_fifo_uvm_failed_seed: Any
        extract_async_fifo_coverage_percent: Any
        generate_rtl_project: Any
        launch_vivado_gui: Any
        parse_async_fifo_wcfg_summary: Any
        open_async_fifo_project_gui: Any
        render_async_fifo_open_project_gui_script: Any
        resolve_async_fifo_wave_db: Any
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
            emit_async_fifo_lines(
                build_async_fifo_error_lines("Vivado command not found."),
                stream=sys.stderr,
            )
            return False

        started_at = datetime.now(UTC)
        sim_result = self.run_vivado_batch(
            vivado_command,
            "run_vivado_async_fifo.tcl",
            sim_dir,
        )
        vcd_path = sim_dir / "async_fifo_trace.vcd"
        wave_db_path = self.resolve_async_fifo_wave_db(sim_dir)
        xsim_log_path = sim_dir / "xsim.log"
        sim_verdict = evaluate_process_results(
            process_results={"simulation": sim_result},
            evidence_paths={"xsim.log": xsim_log_path},
            required_pass_markers=("ASYNC_FIFO_SCOREBOARD_PASS",),
            required_artifact_paths=(vcd_path, wave_db_path, xsim_log_path),
            started_at=started_at,
            coverage_required=False,
        )
        if not sim_verdict.passed:
            self.write_async_fifo_sim_report(
                project_dir=project_dir,
                vcd_path=vcd_path,
                wave_db_path=wave_db_path,
                sim_result=sim_result,
                verdict=sim_verdict,
            )
            write_verification_verdict(project_dir, sim_verdict)
            emit_async_fifo_lines(
                build_async_fifo_error_lines(format_verification_failure(sim_verdict)),
                stream=sys.stderr,
            )
            return False

        project_result = self.run_vivado_batch(
            vivado_command,
            "create_async_fifo_project.tcl",
            sim_dir,
            extra_args=["-nojournal", "-nolog", "-notrace"],
        )
        xpr_path = project_dir / "vivado_project" / "async_fifo_project.xpr"
        verdict = evaluate_process_results(
            process_results={"simulation": sim_result, "project": project_result},
            evidence_paths={"xsim.log": xsim_log_path},
            required_pass_markers=("ASYNC_FIFO_SCOREBOARD_PASS",),
            required_artifact_paths=(vcd_path, wave_db_path, xsim_log_path, xpr_path),
            started_at=started_at,
            coverage_required=False,
        )

        report_path = self.write_async_fifo_sim_report(
            project_dir=project_dir,
            vcd_path=vcd_path,
            wave_db_path=wave_db_path,
            sim_result=sim_result,
            project_result=project_result,
            verdict=verdict,
        )
        write_verification_verdict(project_dir, verdict)
        if not verdict.passed:
            emit_async_fifo_lines(
                build_async_fifo_error_lines(format_verification_failure(verdict)),
                stream=sys.stderr,
            )
            return False
        emit_async_fifo_lines(
            build_async_fifo_sim_completed_lines(
                project_dir,
                vcd_path,
                wave_db_path,
                report_path,
            )
        )
        if open_wave_gui:
            self.open_async_fifo_project_gui(project_dir)
        return True

    def run_async_fifo_regression(self, output_dir: Any="outputs", open_wave_gui: Any=False) -> Any:
        root_project_dir = self.write_async_fifo_project(output_dir)
        self.write_async_fifo_regression_matrix(root_project_dir)
        results: list[dict[str, Any]] = []
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
        verdict = aggregate_verification_verdicts(
            tuple(
                Path(result["output_dir"])
                / "reports"
                / "verification_verdict.json"
                for result in results
            )
        )
        write_verification_verdict(root_project_dir, verdict)
        all_passed = all_passed and verdict.passed
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
            emit_async_fifo_lines(
                build_async_fifo_error_lines("Vivado command not found."),
                stream=sys.stderr,
            )
            return False

        started_at = datetime.now(UTC)
        sim_result = self.run_vivado_batch(
            vivado_command,
            "run_vivado_async_fifo_uvm.tcl",
            sim_dir,
        )
        log_path = sim_dir / "async_fifo_uvm_smoke.log"
        wdb_path = sim_dir / "async_fifo_uvm_smoke.wdb"
        verdict = evaluate_process_results(
            process_results={"vivado_uvm_smoke": sim_result},
            evidence_paths={"async_fifo_uvm_smoke.log": log_path},
            required_pass_markers=(
                "ASYNC_FIFO_UVM_SCOREBOARD_PASS",
                "ASYNC_FIFO_UVM_TEST_DONE",
            ),
            required_artifact_paths=(log_path, wdb_path),
            started_at=started_at,
            coverage_required=False,
        )
        write_verification_verdict(project_dir, verdict)
        report = self.write_async_fifo_uvm_smoke_report(
            project_dir,
            sim_result=sim_result,
            verdict=verdict,
        )
        if not verdict.passed:
            emit_async_fifo_lines(
                build_async_fifo_error_lines(
                    format_verification_failure(verdict)
                ),
                stream=sys.stderr,
            )
            return False

        emit_async_fifo_lines(build_async_fifo_uvm_smoke_completed_lines(report))
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
            emit_async_fifo_lines(
                build_async_fifo_error_lines("Vivado command not found."),
                stream=sys.stderr,
            )
            return False

        env = None
        if seed is not None:
            env = os.environ.copy()
            env["ASYNC_FIFO_UVM_SEED"] = str(int(seed))

        started_at = datetime.now(UTC)
        sim_result = self.run_vivado_batch(
            vivado_command,
            "run_vivado_async_fifo_uvm_coverage.tcl",
            sim_dir,
            env=env,
        )
        functional_report = self.write_async_fifo_uvm_functional_coverage_report(project_dir)
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
        configured_results = [
            str(gate["result"])
            for gate in summary_report["coverage_gates"].values()
            if gate["threshold"] is not None
        ]
        if not configured_results:
            configured_gate = "SKIP"
        elif "FAIL" in configured_results:
            configured_gate = "FAIL"
        elif "MISSING" in configured_results:
            configured_gate = "MISSING"
        else:
            configured_gate = "PASS"
        log_path = sim_dir / "async_fifo_uvm_coverage.log"
        wdb_path = sim_dir / "async_fifo_uvm_coverage.wdb"
        code_cov_info = (
            sim_dir
            / "coverage"
            / "xsim.codeCov"
            / "async_fifo_uvm_cov"
            / "xsim.CCInfo"
        )
        verdict = evaluate_process_results(
            process_results={"vivado_uvm_coverage": sim_result},
            evidence_paths={"async_fifo_uvm_coverage.log": log_path},
            required_pass_markers=(
                "ASYNC_FIFO_UVM_SCOREBOARD_PASS",
                "ASYNC_FIFO_UVM_TEST_DONE",
                "ASYNC_FIFO_UVM_FCOV_PASS",
                "ASYNC_FIFO_UVM_ASSERT_PASS",
            ),
            required_artifact_paths=(log_path, wdb_path, code_cov_info),
            started_at=started_at,
            coverage_required=True,
            coverage_gates={
                "configured_thresholds": configured_gate,
                "functional": "PASS" if functional_report["passed"] else "FAIL",
                "xsim_code_coverage": (
                    "PASS"
                    if summary_report["coverage_summary"]["available"]
                    else "MISSING"
                ),
            },
        )
        write_verification_verdict(project_dir, verdict)
        report = self.write_async_fifo_uvm_coverage_report(
            project_dir,
            sim_result=sim_result,
            verdict=verdict,
        )
        summary_report = self.write_async_fifo_uvm_coverage_summary_report(
            project_dir,
            sim_result=sim_result,
            coverage_threshold=coverage_threshold,
            coverage_percent=auto_percent,
            coverage_thresholds=coverage_thresholds,
            verdict=verdict,
        )

        self.write_async_fifo_coverage_history(
            project_dir,
            summary_report,
            status=verdict.status,
            vivado_command=vivado_command,
            seed=seed,
        )
        self.write_async_fifo_reports_index(project_dir)
        if not verdict.passed:
            emit_async_fifo_lines(
                build_async_fifo_error_lines(
                    format_verification_failure(verdict),
                    "UVM coverage summary: {}".format(summary_report["markdown_path"]),
                ),
                stream=sys.stderr,
            )
            return False
        emit_async_fifo_lines(
            build_async_fifo_uvm_coverage_completed_lines(
                report,
                summary_report,
                functional_report,
            )
        )
        return True

    def run_async_fifo_uvm_random_regression(self, output_dir: Any="outputs", seeds: Any=None) -> Any:
        if seeds is None:
            seeds = [101, 202, 303]
        project_dir = Path(output_dir) / "async-fifo"
        results: list[dict[str, Any]] = []
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
        verdict = aggregate_verification_verdicts(
            tuple(
                Path(result["project"])
                / "reports"
                / "verification_verdict.json"
                for result in results
            )
        )
        write_verification_verdict(project_dir, verdict)
        return all_passed and verdict.passed
