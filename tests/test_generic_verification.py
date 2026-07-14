from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.design_workspace import (  # noqa: E402
    initialize_workspace,
    resume_workspace,
)
from digital_ic_agent._runtime.generic_verification import (  # noqa: E402
    verify_workspace,
)


def _design_intent() -> dict[str, Any]:
    return {
        "schema_version": "digital-ic-agent.design-intent.v1",
        "module": {"name": "timer", "kind": "sequential"},
        "parameters": [],
        "ports": [
            {"name": "clk", "direction": "input", "width": 1, "semantics": "clock"},
            {"name": "rst_n", "direction": "input", "width": 1, "semantics": "reset"},
            {"name": "expired", "direction": "output", "width": 1, "semantics": "expiry"},
        ],
        "clocks": [
            {"name": "core", "signal": "clk", "edge": "rising", "frequency_hz": 100000000}
        ],
        "resets": [
            {
                "name": "reset",
                "signal": "rst_n",
                "active_level": "low",
                "kind": "asynchronous",
                "clock": "core",
            }
        ],
        "protocols": [],
        "timing": {"latency_cycles": 1, "throughput_per_cycle": 1},
        "exceptional_behavior": [],
        "implementation_constraints": {"synthesizable": True, "latches_allowed": False},
        "acceptance_criteria": ["Timer emits one expiry pulse"],
    }


def _verification_intent(
    *,
    max_iterations: int = 3,
    no_progress_limit: int = 1,
) -> dict[str, Any]:
    return {
        "schema_version": "digital-ic-agent.verification-intent.v1",
        "module": "timer",
        "testbench_top": "tb_timer",
        "source_files": ["rtl/timer.sv", "uvm/timer_pkg.sv", "uvm/tb_timer.sv"],
        "include_dirs": ["uvm"],
        "uvm_enabled": True,
        "timescale": "1ns/1ps",
        "pass_markers": ["TIMER_SCOREBOARD_PASS"],
        "directed_scenarios": [
            {"id": "expiry", "description": "Timer expires", "expected": "one pulse"}
        ],
        "random_constraints": [],
        "scoreboard": {
            "enabled": True,
            "strategy": "cycle-accurate",
            "compare_signals": ["expired"],
        },
        "assertions": [
            {"id": "pulse", "description": "Expiry is one cycle", "signals": ["expired"]}
        ],
        "functional_coverage": [
            {"id": "expired", "description": "Expiry observed", "signals": ["expired"]}
        ],
        "code_coverage": {"statement": 90, "branch": 80, "condition": 80, "toggle": 70},
        "coverage_strategy": {
            "code_coverage": True,
            "functional_coverage": True,
            "export_report": True,
        },
        "iteration_limits": {
            "max_iterations": max_iterations,
            "max_time_seconds": 120,
            "no_progress_limit": no_progress_limit,
        },
        "exit_criteria": {
            "zero_uvm_errors": True,
            "zero_uvm_fatals": True,
            "scoreboard_pass": True,
            "all_assertions_pass": True,
            "coverage_must_pass": True,
        },
    }


def _workspace(tmp_path: Path, **verification_options: int) -> Path:
    workspace = tmp_path / "timer-workspace"
    initialize_workspace(workspace)
    (workspace / "contracts" / "design_intent.json").write_text(
        json.dumps(_design_intent()),
        encoding="utf-8",
    )
    (workspace / "contracts" / "verification_intent.json").write_text(
        json.dumps(_verification_intent(**verification_options)),
        encoding="utf-8",
    )
    (workspace / "rtl" / "timer.sv").write_text(
        "module timer(input logic clk, rst_n, output logic expired); endmodule\n",
        encoding="utf-8",
    )
    (workspace / "uvm" / "timer_pkg.sv").write_text(
        "package timer_pkg; endpackage\n",
        encoding="utf-8",
    )
    (workspace / "uvm" / "tb_timer.sv").write_text(
        "module tb_timer; endmodule\n",
        encoding="utf-8",
    )
    return workspace


class FakeVivadoRunner:
    def __init__(self, workspace: Path, *, simulation_passes: bool = True) -> None:
        self.workspace = workspace
        self.simulation_passes = simulation_passes
        self.calls: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        encoding: str,
        errors: str,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert encoding == "utf-8"
        assert errors == "replace"
        assert timeout > 0
        assert check is False
        self.calls.append(command)
        tool = Path(command[0]).stem.lower()
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, "Vivado Simulator v2025.2\n", "")
        if tool == "xsim":
            marker = "TIMER_SCOREBOARD_PASS\n" if self.simulation_passes else "TEST_FAILED\n"
            (cwd / "xsim.log").write_text(
                marker + "UVM_ERROR : 0\nUVM_FATAL : 0\n",
                encoding="utf-8",
            )
            (cwd / "simulation.wdb").write_text("wave database\n", encoding="utf-8")
        elif tool == "xelab":
            (cwd / "timer_snapshot").mkdir(exist_ok=True)
        elif tool == "xcrg":
            report_dir = Path(command[command.index("-report_dir") + 1])
            self._write_coverage(report_dir)
            log_path = Path(command[command.index("-log") + 1])
            log_path.write_text("xcrg completed\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, f"{tool} completed\n", "")

    def _write_coverage(self, report_dir: Path) -> None:
        code_dir = report_dir / "codeCoverageReport"
        functional_dir = report_dir / "functionalCoverageReport"
        code_dir.mkdir(parents=True)
        functional_dir.mkdir(parents=True)
        source = (self.workspace / "rtl" / "timer.sv").as_posix()
        (code_dir / "files.html").write_text(
            f"""
<table><tr><td>File Path</td><td>Statement Coverage Score</td>
<td>Branch Coverage Score</td><td>Condition Coverage Score</td>
<td>Toggle Coverage Score</td></tr>
<tr><td>{source}</td><td>100</td><td>90</td><td>85</td><td>75</td></tr></table>
""",
            encoding="utf-8",
        )
        (functional_dir / "groups.html").write_text(
            """
<table><tr><td>Name</td><td>Score</td><td>Goal</td></tr>
<tr><td>timer_cg</td><td>100</td><td>100</td></tr></table>
""",
            encoding="utf-8",
        )


def _tools(tmp_path: Path) -> Path:
    tools = tmp_path / "vivado-bin"
    tools.mkdir()
    for name in ("xvlog.bat", "xelab.bat", "xsim.bat", "xcrg.bat"):
        (tools / name).write_text("@echo off\n", encoding="utf-8")
    return tools


def test_generic_workspace_verification_runs_vivado_and_records_iteration(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    runner = FakeVivadoRunner(workspace)

    result = verify_workspace(workspace, vivado_bin=_tools(tmp_path), runner=runner)

    assert result["verdict"]["status"] == "PASS"
    assert result["iteration"] == 1
    tools = [Path(command[0]).stem.lower() for command in runner.calls]
    assert tools == ["xvlog", "xvlog", "xelab", "xsim", "xcrg"]
    compile_command = runner.calls[1]
    source_arguments = [
        str((workspace / relative).resolve())
        for relative in _verification_intent()["source_files"]
    ]
    assert [item for item in compile_command if item in source_arguments] == source_arguments
    assert "tb_timer" in runner.calls[2]

    iteration_dir = workspace / "iterations" / "0001"
    evidence = json.loads((iteration_dir / "iteration.json").read_text(encoding="utf-8"))
    assert evidence["intent_sha256"]
    assert evidence["tool_version"] == "Vivado Simulator v2025.2"
    assert evidence["coverage_gates"] == {
        "branch": "PASS",
        "condition": "PASS",
        "functional": "PASS",
        "statement": "PASS",
        "toggle": "PASS",
    }
    assert evidence["verdict"]["status"] == "PASS"
    assert (iteration_dir / "source.diff").is_file()
    assert (iteration_dir / "sources" / "rtl" / "timer.sv").is_file()
    assert (workspace / "reports" / "verification_verdict.json").is_file()
    assert resume_workspace(workspace)["resume_from"] == "VERIFIED"


def test_generic_workspace_verification_stops_on_no_progress(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, max_iterations=3, no_progress_limit=1)
    runner = FakeVivadoRunner(workspace, simulation_passes=False)
    tools = _tools(tmp_path)

    first = verify_workspace(workspace, vivado_bin=tools, runner=runner)
    call_count = len(runner.calls)
    second = verify_workspace(workspace, vivado_bin=tools, runner=runner)

    assert first["verdict"]["status"] == "FAIL"
    assert second["verdict"]["status"] == "FAIL"
    assert second["verdict"]["reasons"][0]["code"] == "NO_PROGRESS_LIMIT_REACHED"
    assert len(runner.calls) == call_count
    assert second["iteration"] == 2
    assert (workspace / "iterations" / "0002" / "iteration.json").is_file()


def test_generic_workspace_verification_stops_at_iteration_limit(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, max_iterations=1, no_progress_limit=1)
    runner = FakeVivadoRunner(workspace, simulation_passes=False)
    tools = _tools(tmp_path)

    first = verify_workspace(workspace, vivado_bin=tools, runner=runner)
    call_count = len(runner.calls)
    second = verify_workspace(workspace, vivado_bin=tools, runner=runner)

    assert first["verdict"]["status"] == "FAIL"
    assert second["verdict"]["reasons"][0]["code"] == "MAX_ITERATIONS_REACHED"
    assert len(runner.calls) == call_count
    assert second["iteration"] == 1


def test_generic_workspace_verification_records_changed_source_diff(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, max_iterations=3, no_progress_limit=1)
    tools = _tools(tmp_path)
    failing_runner = FakeVivadoRunner(workspace, simulation_passes=False)
    verify_workspace(workspace, vivado_bin=tools, runner=failing_runner)
    (workspace / "rtl" / "timer.sv").write_text(
        "module timer(input logic clk, rst_n, output logic expired);\nassign expired = 1'b0;\nendmodule\n",
        encoding="utf-8",
    )

    passing_runner = FakeVivadoRunner(workspace)
    result = verify_workspace(workspace, vivado_bin=tools, runner=passing_runner)

    assert result["iteration"] == 2
    diff = (workspace / "iterations" / "0002" / "source.diff").read_text(
        encoding="utf-8"
    )
    assert "+assign expired = 1'b0;" in diff
