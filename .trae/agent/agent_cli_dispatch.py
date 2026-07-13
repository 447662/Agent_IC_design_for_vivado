from typing import Any
import sys

from agent_cli import build_requirement, parse_seed_list
from agent_errors import AgentError


def _status_exit(report: Any) -> int:
    return 1 if report["status"] == "FAIL" else 0


def _print_paths(report: Any, labels: tuple[tuple[str, str], ...]) -> None:
    for label, key in labels:
        print("{}: {}".format(label, report[key]))


def _run_boolean_flow(label: str, callback: Any, errors: tuple[type[Exception], ...]) -> int:
    try:
        return 0 if callback() else 1
    except errors as exc:
        print("{} failed: {}".format(label, exc), file=sys.stderr)
        if isinstance(exc, AgentError):
            return exc.exit_code
        return 1


def _handle_listing_and_scaffold(args: Any, agent: Any) -> Any:
    if args.list_skills:
        agent.list_skills()
        return 0
    if args.list_targets:
        agent.print_targets()
        return 0
    if args.create_target:
        return _create_target(args, agent)
    if args.diagnostic:
        return 0 if agent.run_diagnostic() else 1
    return None


def _create_target(args: Any, agent: Any) -> int:
    try:
        description = " ".join(args.requirement).strip() or None
        scaffold = agent.create_target_scaffold(
            args.create_target,
            output_dir=args.output_dir,
            description=description,
        )
    except (OSError, ValueError) as exc:
        print("Target scaffold generation failed: {}".format(exc), file=sys.stderr)
        return 1
    print("Created target scaffold: {}".format(scaffold["project_dir"]))
    print("Target config: {}".format(scaffold["config_path"]))
    print("TODO checklist: {}".format(scaffold["todo_path"]))
    return 0


def _handle_report_commands(args: Any, agent: Any) -> Any:
    if args.environment_report:
        return _write_environment_report(args, agent)
    if args.generate_overview:
        return _write_project_overview(args, agent)
    if args.coverage_closure:
        return _write_coverage_closure(args, agent)
    if args.verify_waveform_samples:
        return _write_waveform_sample_report(args, agent)
    return None


def _write_environment_report(args: Any, agent: Any) -> int:
    try:
        report = agent.write_environment_report(output_dir=args.output_dir)
    except (OSError, ValueError) as exc:
        print("环境预检报告生成失败: {}".format(exc), file=sys.stderr)
        return 1
    print("环境预检状态: {}".format(report["status"]))
    _print_paths(
        report,
        (
            ("Markdown", "markdown_path"),
            ("HTML", "html_path"),
            ("Artifact manifest", "manifest_path"),
        ),
    )
    return _status_exit(report)


def _write_project_overview(args: Any, agent: Any) -> int:
    try:
        overview = agent.write_project_overview(output_dir=args.output_dir)
    except (OSError, ValueError) as exc:
        print("项目总览生成失败: {}".format(exc), file=sys.stderr)
        return 1
    print("项目总览状态: {}".format(overview["status"]))
    _print_paths(overview, (("Markdown", "markdown_path"), ("HTML", "html_path")))
    return _status_exit(overview)


def _write_coverage_closure(args: Any, agent: Any) -> int:
    try:
        report = agent.write_coverage_closure_report(
            output_dir=args.output_dir,
            target_threshold=args.coverage_target,
        )
    except (OSError, ValueError) as exc:
        print("Coverage closure 生成失败: {}".format(exc), file=sys.stderr)
        return 1
    print("Coverage closure 状态: {}".format(report["status"]))
    _print_paths(report, (("Markdown", "markdown_path"), ("HTML", "html_path")))
    return _status_exit(report)


def _write_waveform_sample_report(args: Any, agent: Any) -> int:
    try:
        report = agent.write_waveform_sample_report(output_dir=args.output_dir)
    except (OSError, ValueError) as exc:
        print("波形样例验证报告生成失败: {}".format(exc), file=sys.stderr)
        return 1
    print("波形样例验证状态: {}".format(report["status"]))
    _print_paths(report, (("Markdown", "markdown_path"), ("HTML", "html_path")))
    return 0 if report["status"] == "PASS" else 1


def _handle_smoke_and_generation(args: Any, agent: Any) -> Any:
    if args.smoke_loop:
        return 0 if agent.run_smoke_loop(
            output_dir=args.output_dir,
            limit=args.vcd_limit,
            waveform_backend=args.wave_backend,
        ) else 1
    if args.sim_smoke:
        return _run_boolean_flow(
            "Simulation smoke",
            lambda: agent.run_sim_smoke(
                output_dir=args.output_dir,
                limit=args.vcd_limit,
                open_wave_gui=not args.no_wave_gui,
                waveform_backend=args.wave_backend,
            ),
            (RuntimeError,),
        )
    if args.generate_rtl:
        return _generate_rtl_project(args, agent)
    if args.generate_spec:
        return _write_design_spec(args, agent)
    if args.generate_verification_plan:
        return _write_verification_plan(args, agent)
    return None


def _generate_rtl_project(args: Any, agent: Any) -> int:
    try:
        project_dir = agent.generate_rtl_project(args.generate_rtl, args.output_dir)
    except (OSError, ValueError) as exc:
        print("RTL project generation failed: {}".format(exc), file=sys.stderr)
        return 1
    print("Generated RTL project: {}".format(project_dir))
    for label, pattern in (("RTL", "rtl/*.v"), ("Testbench", "tb/*.v"), ("Vivado script", "sim/run_vivado_*.tcl")):
        matches = sorted(project_dir.glob(pattern))
        if matches:
            print("{}: {}".format(label, matches[0]))
    return 0


def _write_design_spec(args: Any, agent: Any) -> int:
    try:
        report = agent.write_target_design_spec(
            args.generate_spec,
            output_dir=args.output_dir,
            requirement=" ".join(args.requirement).strip() or None,
        )
    except (OSError, ValueError) as exc:
        print("Design spec generation failed: {}".format(exc), file=sys.stderr)
        return 1
    print("Generated design spec: {}".format(report["md_path"]))
    print("Generated design spec HTML: {}".format(report["html_path"]))
    return 0


def _write_verification_plan(args: Any, agent: Any) -> int:
    try:
        report = agent.write_target_verification_plan(
            args.generate_verification_plan,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError) as exc:
        print("Verification plan generation failed: {}".format(exc), file=sys.stderr)
        return 1
    print("Generated verification plan: {}".format(report["md_path"]))
    print("Generated verification plan HTML: {}".format(report["html_path"]))
    return 0


def _handle_rtl_and_uvm_flows(args: Any, agent: Any) -> Any:
    if args.sim_rtl:
        return _run_boolean_flow(
            "RTL simulation",
            lambda: agent.run_rtl_sim(
                args.sim_rtl,
                output_dir=args.output_dir,
                open_wave_gui=not args.no_wave_gui,
            ),
            (OSError, RuntimeError, ValueError),
        )
    if args.regress_rtl:
        return _run_boolean_flow(
            "RTL regression",
            lambda: agent.regress_rtl(args.regress_rtl, output_dir=args.output_dir, open_wave_gui=False),
            (OSError, ValueError),
        )
    if args.uvm_smoke:
        return _run_boolean_flow(
            "UVM smoke",
            lambda: agent.run_uvm_smoke(
                args.uvm_smoke,
                output_dir=args.output_dir,
                open_wave_gui=not args.no_wave_gui,
            ),
            (OSError, RuntimeError, ValueError),
        )
    if args.uvm_coverage:
        return _run_uvm_coverage(args, agent)
    if args.uvm_random_regress:
        return _run_boolean_flow(
            "UVM random regression",
            lambda: agent.run_uvm_random_regression(
                args.uvm_random_regress,
                output_dir=args.output_dir,
                seeds=parse_seed_list(args.uvm_seeds),
            ),
            (OSError, ValueError),
        )
    return None


def _run_uvm_coverage(args: Any, agent: Any) -> int:
    try:
        coverage_thresholds = {
            metric: value
            for metric, value in (
                ("statement", args.coverage_line_threshold),
                ("branch", args.coverage_branch_threshold),
                ("condition", args.coverage_condition_threshold),
                ("toggle", args.coverage_toggle_threshold),
                ("functional", args.coverage_functional_threshold),
            )
            if value is not None
        }
        return 0 if agent.run_uvm_coverage(
            args.uvm_coverage,
            output_dir=args.output_dir,
            coverage_threshold=args.coverage_threshold,
            coverage_percent=args.coverage_percent,
            coverage_thresholds=coverage_thresholds,
        ) else 1
    except (OSError, ValueError) as exc:
        print("UVM coverage failed: {}".format(exc), file=sys.stderr)
        return 1


def _handle_target_analysis_flows(args: Any, agent: Any) -> Any:
    if args.analyze_rtl_vcd:
        if args.analyze_rtl_vcd == "sync-fifo":
            return _run_boolean_flow(
                "RTL VCD analysis",
                lambda: agent.analyze_sync_fifo_vcd(
                    output_dir=args.output_dir,
                    limit=args.vcd_limit,
                    waveform_backend=args.wave_backend,
                ),
                (OSError, ValueError),
            )
        if args.analyze_rtl_vcd == "round-robin-arbiter":
            return _run_boolean_flow(
                "RTL VCD analysis",
                lambda: agent.analyze_round_robin_arbiter_vcd(
                    output_dir=args.output_dir,
                    limit=args.vcd_limit,
                    waveform_backend=args.wave_backend,
                ),
                (OSError, ValueError),
            )
        return _run_boolean_flow(
            "RTL VCD analysis",
            lambda: agent.run_target_flow(
                args.analyze_rtl_vcd,
                "analyze-rtl-vcd",
                output_dir=args.output_dir,
                limit=args.vcd_limit,
                waveform_backend=args.wave_backend,
            ),
            (OSError, ValueError),
        )
    if args.check_rtl:
        return _run_boolean_flow(
            "RTL check",
            lambda: agent.run_target_flow(args.check_rtl, "check-rtl", output_dir=args.output_dir),
            (OSError, ValueError),
        )
    if args.open_wave:
        return _run_boolean_flow(
            "RTL wave open",
            lambda: agent.open_rtl_wave(args.open_wave, output_dir=args.output_dir),
            (OSError, RuntimeError, ValueError),
        )
    if args.open_uvm_wave:
        return _run_boolean_flow(
            "UVM wave open",
            lambda: agent.open_uvm_wave(
                args.open_uvm_wave,
                output_dir=args.output_dir,
                wave_kind=args.uvm_wave_kind,
            ),
            (OSError, RuntimeError, ValueError),
        )
    return None


def _handle_waveform_analysis(args: Any, agent: Any) -> Any:
    if args.analyze_vcd:
        return 0 if agent.analyze_vcd(
            args.analyze_vcd,
            condition=args.vcd_condition,
            show=args.vcd_show,
            limit=args.vcd_limit,
            waveform_backend=args.wave_backend,
        ) else 1
    if args.analyze_waveform:
        return 0 if agent.analyze_waveform(
            args.analyze_waveform,
            condition=args.vcd_condition,
            show=args.vcd_show,
            limit=args.vcd_limit,
            waveform_backend=args.wave_backend,
        ) else 1
    return None


def _handle_default_workflow(args: Any, agent: Any) -> int:
    requirement = build_requirement(args)
    if not requirement:
        print("错误: 用户需求不能为空", file=sys.stderr)
        return 1
    success = agent.execute_workflow(
        requirement,
        output_dir=args.output_dir,
        skip_tool_check=args.no_tool_check,
    )
    return 0 if success else 1


def dispatch_cli_command(args: Any, agent: Any) -> Any:
    handlers = (
        _handle_listing_and_scaffold,
        _handle_report_commands,
        _handle_smoke_and_generation,
        _handle_rtl_and_uvm_flows,
        _handle_target_analysis_flows,
        _handle_waveform_analysis,
    )
    for handler in handlers:
        result = handler(args, agent)
        if result is not None:
            return result
    return _handle_default_workflow(args, agent)
