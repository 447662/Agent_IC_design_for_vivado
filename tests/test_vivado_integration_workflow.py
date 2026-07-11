from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "vivado-integration.yml"
RUNNER_SCRIPT_PATH = (
    ROOT / ".github" / "scripts" / "run-vivado-integration.ps1"
)
PREFLIGHT_SCRIPT_PATH = ROOT / ".github" / "scripts" / "vivado-preflight.tcl"


def test_vivado_integration_workflow_uses_controlled_self_hosted_runner():
    assert WORKFLOW_PATH.exists()
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "pull_request:" in workflow
    assert "vivado-integration" in workflow
    assert "runs-on: [self-hosted, Windows, vivado]" in workflow
    assert "environment:" in workflow
    assert "vivado-trusted-runner" in workflow
    assert "timeout-minutes:" in workflow
    assert "uv sync --frozen --group dev" in workflow
    assert "run-vivado-integration.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "if: always()" in workflow


def test_vivado_runner_covers_p0_3_release_gate_matrix():
    assert RUNNER_SCRIPT_PATH.exists()
    script = RUNNER_SCRIPT_PATH.read_text(encoding="utf-8")

    matrix_requirements = {
        "sync-fifo": {
            "flows": ("--sim-rtl",),
            "artifacts": (
                "rtl\\sync_fifo.v",
                "tb\\tb_sync_fifo.v",
                "sim\\sync_fifo_trace.vcd",
                "vivado_project\\sync_fifo_project.xpr",
                "reports\\sim_report.md",
                "sim\\sync_fifo_smoke.wdb",
            ),
            "markers": ("SYNC_FIFO_SCOREBOARD_PASS",),
        },
        "async-fifo": {
            "flows": ("--sim-rtl", "--uvm-smoke", "--uvm-coverage"),
            "artifacts": (
                "rtl\\async_fifo.v",
                "tb\\tb_async_fifo.v",
                "sim\\async_fifo_trace.vcd",
                "vivado_project\\async_fifo_project.xpr",
                "reports\\sim_report.md",
                "sim\\async_fifo_smoke.wdb",
                "sim\\async_fifo_uvm_smoke.wdb",
                "sim\\async_fifo_uvm_coverage.wdb",
                "reports\\uvm_smoke_report.md",
                "reports\\uvm_coverage_summary.md",
            ),
            "markers": (
                "ASYNC_FIFO_SCOREBOARD_PASS",
                "ASYNC_FIFO_UVM_SCOREBOARD_PASS",
                "ASYNC_FIFO_UVM_TEST_DONE",
            ),
        },
        "round-robin-arbiter": {
            "flows": ("--sim-rtl",),
            "artifacts": (
                "rtl\\round_robin_arbiter.v",
                "tb\\tb_round_robin_arbiter.v",
                "sim\\round_robin_arbiter_trace.vcd",
                "vivado_project\\round_robin_arbiter_project.xpr",
                "reports\\sim_report.md",
                "sim\\round_robin_arbiter_smoke.wdb",
            ),
            "markers": ("ROUND_ROBIN_ARBITER_SCOREBOARD_PASS",),
        },
    }

    assert "$targetGates" in script
    for target, requirement in matrix_requirements.items():
        assert target in script
        for flow in requirement["flows"]:
            assert flow in script
        for artifact in requirement["artifacts"]:
            assert artifact in script
        for marker in requirement["markers"]:
            assert marker in script

    assert "Assert-RuntimeManifest" in script
    assert "produced_by_run_id" in script
    assert '"CURRENT"' in script
    assert "Assert-ScoreboardMarker" in script


def test_vivado_runner_rejects_false_passes_for_each_release_gate_target():
    assert RUNNER_SCRIPT_PATH.exists()
    script = RUNNER_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "foreach ($negativeGate in $targetGates)" in script
    for run_script in (
        "run_vivado_sync_fifo.tcl",
        "run_vivado_async_fifo.tcl",
        "run_vivado_round_robin_arbiter.tcl",
    ):
        assert run_script in script

    assert "THIS_TOKEN_IS_INTENTIONALLY_INVALID_VERILOG" in script
    assert "accepted invalid RTL syntax" in script
    assert "Real simulator output did not contain" in script
    assert "Vivado startup or license preflight did not report PASS" in script


def test_vivado_runner_executes_real_flow_and_rejects_false_passes():
    assert RUNNER_SCRIPT_PATH.exists()
    script = RUNNER_SCRIPT_PATH.read_text(encoding="utf-8")

    required_fragments = (
        "Get-Command vivado",
        "-version",
        "TCLLIBPATH",
        "support\\appinit",
        "vivado-preflight.tcl",
        "--sim-rtl",
        "sync-fifo",
        "--no-wave-gui",
        "SYNC_FIFO_SCOREBOARD_PASS",
        "sync_fifo_trace.vcd",
        "sync_fifo_project.xpr",
        "artifacts.json",
        "run_id",
        "*.wdb",
        "Add-Content",
        "negative-syntax",
        "accepted invalid RTL syntax",
    )
    for fragment in required_fragments:
        assert fragment in script

    version_block = script.split("$versionResult =", maxsplit=1)[1].split(
        "$preflightResult =",
        maxsplit=1,
    )[0]
    assert "-AllowFailure" in version_block
    assert "valid version banner" in version_block
    assert '$ErrorActionPreference = "Continue"' in script
    assert "New-Item -ItemType File" not in script
    assert "Set-Content" not in script
    assert "Remove-Item" not in script


def test_vivado_preflight_starts_real_tool_and_reports_blocked_state():
    assert PREFLIGHT_SCRIPT_PATH.exists()
    script = PREFLIGHT_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "version -short" in script
    assert "create_project -in_memory" in script
    assert "VIVADO_PREFLIGHT_PASS" in script
    assert "VIVADO_PREFLIGHT_BLOCKED" in script
    assert "exit 2" in script
