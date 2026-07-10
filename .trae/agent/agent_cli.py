import argparse


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="数字IC前端设计Agent")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--analyze-vcd",
        metavar="FILE",
        help="Analyze a VCD waveform file",
    )
    mode_group.add_argument(
        "--smoke-loop",
        action="store_true",
        help="Generate a built-in VCD and analyze it",
    )
    mode_group.add_argument(
        "--sim-smoke",
        action="store_true",
        help="Run a Verilog simulator smoke test and analyze VCD",
    )
    mode_group.add_argument(
        "--generate-rtl",
        metavar="TARGET",
        help="Generate an RTL project skeleton, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--create-target",
        metavar="TARGET",
        help="Create a candidate target scaffold without installing it",
    )
    mode_group.add_argument(
        "--generate-spec",
        metavar="TARGET",
        help="Generate target design_spec.md/html, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--generate-verification-plan",
        metavar="TARGET",
        help="Generate target verification_plan.md/html, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--sim-rtl",
        metavar="TARGET",
        help="Run RTL simulation and open Vivado project/wave GUI, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--regress-rtl",
        metavar="TARGET",
        help="Run RTL parameter regression, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--uvm-smoke",
        metavar="TARGET",
        help="Run minimal UVM smoke, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--uvm-coverage",
        metavar="TARGET",
        help="Run UVM smoke with Vivado/xsim code coverage, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--uvm-random-regress",
        metavar="TARGET",
        help="Run UVM random seed regression, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--analyze-rtl-vcd",
        metavar="TARGET",
        help="Analyze a generated RTL VCD, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--check-rtl",
        metavar="TARGET",
        help="Check generated RTL project artifacts, e.g. async-fifo",
    )
    mode_group.add_argument(
        "--open-wave",
        metavar="TARGET",
        help="Open the latest generated RTL waveform without re-running simulation",
    )
    mode_group.add_argument(
        "--open-uvm-wave",
        metavar="TARGET",
        help="Open a generated UVM WDB waveform, e.g. async-fifo",
    )
    parser.add_argument(
        "--no-wave-gui",
        action="store_true",
        help="Do not open Vivado/xsim GUI waveform after simulation",
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=None,
        help="Minimum UVM code coverage percentage gate",
    )
    parser.add_argument(
        "--coverage-percent",
        type=float,
        default=None,
        help="Measured UVM code coverage percentage for gate/reporting",
    )
    parser.add_argument(
        "--uvm-seeds",
        default="101,202,303",
        help="Comma-separated UVM random regression seeds",
    )
    parser.add_argument(
        "--uvm-wave-kind",
        choices=["smoke", "coverage"],
        default="coverage",
        help="UVM WDB type to open",
    )
    parser.add_argument(
        "--vcd-condition",
        default=None,
        help="VCD condition expression, e.g. valid=1,ready=1",
    )
    parser.add_argument(
        "--vcd-show",
        default=None,
        help="Signals to show when the VCD condition holds",
    )
    parser.add_argument(
        "--vcd-limit",
        type=int,
        default=20,
        help="Maximum VCD rows to display",
    )
    parser.add_argument(
        "--wave-backend",
        choices=["auto", "rwave", "vcd-analyzer"],
        default="auto",
        help=(
            "Waveform analyzer backend: auto prefers RWaveAnalyzer rwave, "
            "then falls back to VCD_ANALYZER"
        ),
    )
    mode_group.add_argument(
        "--diagnostic",
        action="store_true",
        help="只运行环境诊断",
    )
    mode_group.add_argument(
        "--environment-report",
        action="store_true",
        help="生成中文环境预检 Markdown/HTML 报告",
    )
    mode_group.add_argument(
        "--generate-overview",
        action="store_true",
        help="生成多 target 顶层 Markdown/HTML 项目总览",
    )
    mode_group.add_argument(
        "--list-skills",
        action="store_true",
        help="列出技能配置",
    )
    mode_group.add_argument(
        "--list-targets",
        action="store_true",
        help="List registered RTL design targets",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="设计文档模板输出目录，默认 outputs",
    )
    parser.add_argument(
        "--no-tool-check",
        action="store_true",
        help="跳过 Vivado、SynthPilot 等外部工具检查",
    )
    parser.add_argument(
        "requirement",
        nargs="*",
        help="用户自然语言设计需求",
    )

    args = parser.parse_args(argv)
    if args.no_tool_check and (
        args.diagnostic
        or args.environment_report
        or args.generate_overview
        or args.list_skills
        or args.list_targets
        or args.analyze_vcd
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


def parse_seed_list(seed_text):
    seeds = []
    for part in str(seed_text).split(","):
        part = part.strip()
        if part:
            seeds.append(int(part))
    return seeds


def build_requirement(args):
    requirement = " ".join(args.requirement).strip()
    if requirement:
        return requirement

    print("欢迎使用数字IC前端设计Agent!")
    print("请输入您的设计需求:")
    try:
        return input("> ").strip()
    except EOFError:
        return ""
