from typing import Any

from agent_cli_parser import build_parser


def parse_args(argv: Any=None) -> Any:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.no_tool_check and (
        args.diagnostic
        or args.environment_report
        or args.generate_overview
        or args.list_skills
        or args.list_targets
        or args.analyze_waveform
        or args.analyze_vcd
        or args.verify_waveform_samples
        or args.coverage_closure
        or args.smoke_loop
        or args.sim_smoke
        or args.generate_rtl
        or args.create_target
        or args.generate_spec
        or args.generate_verification_plan
        or args.sim_rtl
        or args.regress_rtl
        or args.uvm_smoke
        or args.uvm_coverage
        or args.uvm_random_regress
        or args.analyze_rtl_vcd
        or args.check_rtl
        or args.open_wave
        or args.open_uvm_wave
    ):
        parser.error("--no-tool-check 只能用于普通工作流模式")
    return args


def parse_seed_list(seed_text: Any) -> Any:
    seeds = []
    for part in str(seed_text).split(","):
        part = part.strip()
        if part:
            seeds.append(int(part))
    return seeds


def build_requirement(args: Any) -> Any:
    requirement = " ".join(args.requirement).strip()
    if requirement:
        return requirement

    print("欢迎使用数字IC前端设计Agent!")
    print("请输入您的设计需求:")
    try:
        return input("> ").strip()
    except EOFError:
        return ""
