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
    assert "timeout-minutes:" in workflow
    assert "uv sync --frozen --group dev" in workflow
    assert "run-vivado-integration.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "if: always()" in workflow


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
