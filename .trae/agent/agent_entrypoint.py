from typing import Any
import sys

from agent_cli import build_requirement, parse_args, parse_seed_list


def run_cli(argv: Any, agent_factory: Any) -> Any:
    args = parse_args(argv)
    agent = agent_factory()
    if agent is None:
        return 1

    if args.list_skills:
        agent.list_skills()
        return 0

    if args.list_targets:
        agent.print_targets()
        return 0

    if args.create_target:
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

    if args.diagnostic:
        return 0 if agent.run_diagnostic() else 1

    if args.environment_report:
        try:
            report = agent.write_environment_report(output_dir=args.output_dir)
        except (OSError, ValueError) as exc:
            print("环境预检报告生成失败: {}".format(exc), file=sys.stderr)
            return 1
        print("环境预检状态: {}".format(report["status"]))
        print("Markdown: {}".format(report["markdown_path"]))
        print("HTML: {}".format(report["html_path"]))
        print("Artifact manifest: {}".format(report["manifest_path"]))
        return 1 if report["status"] == "FAIL" else 0

    if args.generate_overview:
        try:
            overview = agent.write_project_overview(output_dir=args.output_dir)
        except (OSError, ValueError) as exc:
            print("项目总览生成失败: {}".format(exc), file=sys.stderr)
            return 1
        print("项目总览状态: {}".format(overview["status"]))
        print("Markdown: {}".format(overview["markdown_path"]))
        print("HTML: {}".format(overview["html_path"]))
        return 1 if overview["status"] == "FAIL" else 0

    if args.coverage_closure:
        try:
            report = agent.write_coverage_closure_report(
                output_dir=args.output_dir,
                target_threshold=args.coverage_target,
            )
        except (OSError, ValueError) as exc:
            print("Coverage closure 生成失败: {}".format(exc), file=sys.stderr)
            return 1
        print("Coverage closure 状态: {}".format(report["status"]))
        print("Markdown: {}".format(report["markdown_path"]))
        print("HTML: {}".format(report["html_path"]))
        return 1 if report["status"] == "FAIL" else 0

    if args.verify_waveform_samples:
        try:
            report = agent.write_waveform_sample_report(output_dir=args.output_dir)
        except (OSError, ValueError) as exc:
            print("波形样例验证报告生成失败: {}".format(exc), file=sys.stderr)
            return 1
        print("波形样例验证状态: {}".format(report["status"]))
        print("Markdown: {}".format(report["markdown_path"]))
        print("HTML: {}".format(report["html_path"]))
        return 0 if report["status"] == "PASS" else 1

    if args.smoke_loop:
        return (
            0
            if agent.run_smoke_loop(
                output_dir=args.output_dir,
                limit=args.vcd_limit,
                waveform_backend=args.wave_backend,
            )
            else 1
        )

    if args.sim_smoke:
        try:
            return (
                0
                if agent.run_sim_smoke(
                    output_dir=args.output_dir,
                    limit=args.vcd_limit,
                    open_wave_gui=not args.no_wave_gui,
                    waveform_backend=args.wave_backend,
                )
                else 1
            )
        except RuntimeError as exc:
            print("Simulation smoke failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.generate_rtl:
        try:
            project_dir = agent.generate_rtl_project(args.generate_rtl, args.output_dir)
        except (OSError, ValueError) as exc:
            print("RTL project generation failed: {}".format(exc), file=sys.stderr)
            return 1
        print("Generated RTL project: {}".format(project_dir))
        rtl_files = sorted((project_dir / "rtl").glob("*.v"))
        tb_files = sorted((project_dir / "tb").glob("*.v"))
        vivado_scripts = sorted((project_dir / "sim").glob("run_vivado_*.tcl"))
        if rtl_files:
            print("RTL: {}".format(rtl_files[0]))
        if tb_files:
            print("Testbench: {}".format(tb_files[0]))
        if vivado_scripts:
            print("Vivado script: {}".format(vivado_scripts[0]))
        return 0

    if args.generate_spec:
        try:
            requirement = " ".join(args.requirement).strip() or None
            report = agent.write_target_design_spec(
                args.generate_spec,
                output_dir=args.output_dir,
                requirement=requirement,
            )
        except (OSError, ValueError) as exc:
            print("Design spec generation failed: {}".format(exc), file=sys.stderr)
            return 1
        print("Generated design spec: {}".format(report["md_path"]))
        print("Generated design spec HTML: {}".format(report["html_path"]))
        return 0

    if args.generate_verification_plan:
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

    if args.sim_rtl:
        try:
            return (
                0
                if agent.run_rtl_sim(
                    args.sim_rtl,
                    output_dir=args.output_dir,
                    open_wave_gui=not args.no_wave_gui,
                )
                else 1
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print("RTL simulation failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.regress_rtl:
        try:
            return (
                0
                if agent.regress_rtl(
                    args.regress_rtl,
                    output_dir=args.output_dir,
                    open_wave_gui=False,
                )
                else 1
            )
        except (OSError, ValueError) as exc:
            print("RTL regression failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.uvm_smoke:
        try:
            return (
                0
                if agent.run_uvm_smoke(
                    args.uvm_smoke,
                    output_dir=args.output_dir,
                    open_wave_gui=not args.no_wave_gui,
                )
                else 1
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print("UVM smoke failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.uvm_coverage:
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
            return (
                0
                if agent.run_uvm_coverage(
                    args.uvm_coverage,
                    output_dir=args.output_dir,
                    coverage_threshold=args.coverage_threshold,
                    coverage_percent=args.coverage_percent,
                    coverage_thresholds=coverage_thresholds,
                )
                else 1
            )
        except (OSError, ValueError) as exc:
            print("UVM coverage failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.uvm_random_regress:
        try:
            return (
                0
                if agent.run_uvm_random_regression(
                    args.uvm_random_regress,
                    output_dir=args.output_dir,
                    seeds=parse_seed_list(args.uvm_seeds),
                )
                else 1
            )
        except (OSError, ValueError) as exc:
            print("UVM random regression failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.analyze_rtl_vcd:
        try:
            return (
                0
                if agent.run_target_flow(
                    args.analyze_rtl_vcd,
                    "analyze-rtl-vcd",
                    output_dir=args.output_dir,
                    limit=args.vcd_limit,
                    waveform_backend=args.wave_backend,
                )
                else 1
            )
        except (OSError, ValueError) as exc:
            print("RTL VCD analysis failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.check_rtl:
        try:
            return (
                0
                if agent.run_target_flow(
                    args.check_rtl,
                    "check-rtl",
                    output_dir=args.output_dir,
                )
                else 1
            )
        except (OSError, ValueError) as exc:
            print("RTL check failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.open_wave:
        try:
            return (
                0
                if agent.open_rtl_wave(
                    args.open_wave,
                    output_dir=args.output_dir,
                )
                else 1
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print("RTL wave open failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.open_uvm_wave:
        try:
            return (
                0
                if agent.open_uvm_wave(
                    args.open_uvm_wave,
                    output_dir=args.output_dir,
                    wave_kind=args.uvm_wave_kind,
                )
                else 1
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print("UVM wave open failed: {}".format(exc), file=sys.stderr)
            return 1

    if args.analyze_vcd:
        return (
            0
            if agent.analyze_vcd(
                args.analyze_vcd,
                condition=args.vcd_condition,
                show=args.vcd_show,
                limit=args.vcd_limit,
                waveform_backend=args.wave_backend,
            )
            else 1
        )

    if args.analyze_waveform:
        return (
            0
            if agent.analyze_waveform(
                args.analyze_waveform,
                condition=args.vcd_condition,
                show=args.vcd_show,
                limit=args.vcd_limit,
                waveform_backend=args.wave_backend,
            )
            else 1
        )

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
