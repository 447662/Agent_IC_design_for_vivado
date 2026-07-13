import argparse


def _add_primary_mode_arguments(mode_group: argparse._MutuallyExclusiveGroup) -> None:
    mode_group.add_argument(
        "--analyze-waveform",
        metavar="FILE",
        help="Analyze a VCD, FST, or GHW waveform file",
    )
    mode_group.add_argument(
        "--analyze-vcd",
        metavar="FILE",
        help="Analyze a VCD waveform file",
    )
    mode_group.add_argument(
        "--verify-waveform-samples",
        action="store_true",
        help="Verify bundled VCD/FST/GHW samples with RWaveAnalyzer",
    )
    mode_group.add_argument(
        "--coverage-closure",
        action="store_true",
        help="Generate a multi-target coverage closure dashboard",
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


def _add_target_generation_modes(mode_group: argparse._MutuallyExclusiveGroup) -> None:
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


def _add_target_flow_modes(mode_group: argparse._MutuallyExclusiveGroup) -> None:
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


def _add_target_analysis_modes(mode_group: argparse._MutuallyExclusiveGroup) -> None:
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


def _add_report_and_listing_modes(mode_group: argparse._MutuallyExclusiveGroup) -> None:
    mode_group.add_argument(
        "--diagnostic",
        action="store_true",
        help="运行环境诊断",
    )
    mode_group.add_argument(
        "--environment-report",
        action="store_true",
        help="生成环境预检 Markdown/HTML 报告",
    )
    mode_group.add_argument(
        "--generate-overview",
        action="store_true",
        help="生成 target 总览 Markdown/HTML 报告",
    )
    mode_group.add_argument(
        "--list-skills",
        action="store_true",
        help="列出当前配置的技能",
    )
    mode_group.add_argument(
        "--list-targets",
        action="store_true",
        help="List registered RTL design targets",
    )


def _add_mode_arguments(parser: argparse.ArgumentParser) -> None:
    mode_group = parser.add_mutually_exclusive_group()
    _add_primary_mode_arguments(mode_group)
    _add_target_generation_modes(mode_group)
    _add_target_flow_modes(mode_group)
    _add_target_analysis_modes(mode_group)
    _add_report_and_listing_modes(mode_group)


def _add_coverage_options(parser: argparse.ArgumentParser) -> None:
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
        "--coverage-line-threshold",
        type=float,
        default=None,
        help="Minimum UVM statement/line coverage percentage gate",
    )
    parser.add_argument(
        "--coverage-branch-threshold",
        type=float,
        default=None,
        help="Minimum UVM branch coverage percentage gate",
    )
    parser.add_argument(
        "--coverage-condition-threshold",
        type=float,
        default=None,
        help="Minimum UVM condition coverage percentage gate",
    )
    parser.add_argument(
        "--coverage-toggle-threshold",
        type=float,
        default=None,
        help="Minimum UVM toggle coverage percentage gate",
    )
    parser.add_argument(
        "--coverage-functional-threshold",
        type=float,
        default=None,
        help="Minimum UVM functional coverage percentage gate",
    )
    parser.add_argument(
        "--coverage-target",
        type=float,
        default=80.0,
        help="Target percentage used by the coverage closure dashboard",
    )


def _add_flow_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-wave-gui",
        action="store_true",
        help="Do not open Vivado/xsim GUI waveform after simulation",
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


def _add_waveform_options(parser: argparse.ArgumentParser) -> None:
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


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="输出目录，默认为 outputs",
    )
    parser.add_argument(
        "--no-tool-check",
        action="store_true",
        help="跳过 Vivado、SynthPilot 等外部工具检查",
    )
    parser.add_argument(
        "requirement",
        nargs="*",
        help="用户的数字 IC 设计需求",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="数字 IC 前端设计 Agent")
    _add_mode_arguments(parser)
    _add_coverage_options(parser)
    _add_flow_options(parser)
    _add_waveform_options(parser)
    _add_common_options(parser)
    return parser
