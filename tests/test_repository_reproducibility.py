import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUALITY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-quality.yml"

REQUIRED_TRACKED_PATHS = (
    ".github/scripts/run-vivado-integration.ps1",
    ".github/scripts/vivado-preflight.tcl",
    ".github/workflows/vivado-integration.yml",
    ".trae/agent/agent_async_fifo_render.py",
    ".trae/agent/agent_async_fifo_reports.py",
    ".trae/agent/agent_async_fifo_runtime.py",
    ".trae/agent/agent_cli_parser.py",
    ".trae/agent/agent_cli_dispatch.py",
    ".trae/agent/agent_design_spec.py",
    ".trae/agent/agent_diagnostics.py",
    ".trae/agent/agent_round_robin_arbiter.py",
    ".trae/agent/agent_sync_fifo.py",
    ".trae/agent/capability_preflight.py",
    ".trae/agent/skill_runtime.py",
    ".trae/agent/target_examples/__init__.py",
    ".trae/agent/target_examples/async_fifo.py",
    ".trae/agent/target_handlers/__init__.py",
    ".trae/agent/target_handlers/async_fifo.py",
    ".trae/agent/target_handlers/round_robin_arbiter.py",
    ".trae/agent/target_handlers/sync_fifo.py",
    ".trae/agent/target_plugins.py",
    ".trae/agent/target_service_host.py",
    ".trae/agent/report_templates.py",
    "tests/test_architecture_runtime.py",
    "tests/test_config_schema.py",
    "tests/test_process_lifecycle.py",
    "tests/test_repository_reproducibility.py",
    "tests/test_vivado_integration_workflow.py",
    "uv.lock",
)


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_required_runtime_and_architecture_files_are_tracked():
    tracked_result = run_git("ls-files", "--cached")
    assert tracked_result.returncode == 0, tracked_result.stderr
    tracked_paths = set(tracked_result.stdout.splitlines())

    missing = [
        relative_path
        for relative_path in REQUIRED_TRACKED_PATHS
        if relative_path not in tracked_paths
    ]

    assert not missing, "required files are not tracked: {}".format(
        ", ".join(missing)
    )


def test_quality_workflow_runs_tracked_runtime_snapshot_gate():
    workflow = QUALITY_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "Verify tracked runtime snapshot" in workflow
    assert "tests/test_repository_reproducibility.py" in workflow
    assert "uv run --frozen pytest" in workflow


def test_git_index_snapshot_imports_agent_and_discovers_builtin_targets(
    tmp_path: Path,
):
    snapshot_dir = tmp_path / "index-snapshot"
    snapshot_dir.mkdir()
    prefix = str(snapshot_dir.resolve()) + os.sep
    checkout_result = run_git(
        "checkout-index",
        "--all",
        "--force",
        "--prefix={}".format(prefix),
    )
    assert checkout_result.returncode == 0, checkout_result.stderr

    agent_dir = snapshot_dir / ".trae" / "agent"
    script = (
        "import json, sys\n"
        "sys.path.insert(0, {!r})\n"
        "from agent import DigitalICAgent\n"
        "from agent_runtime import PluginServices, TargetPlugin\n"
        "from skill_runtime import SkillExecutionStatus\n"
        "agent = DigitalICAgent()\n"
        "payload = {{\n"
        "    'targets': sorted(agent.targets),\n"
        "    'has_async_method': hasattr(agent, 'write_async_fifo_project'),\n"
        "    'blocked_status': SkillExecutionStatus.BLOCKED.value,\n"
        "    'service_type': PluginServices.__name__,\n"
        "    'plugin_type': TargetPlugin.__name__,\n"
        "}}\n"
        "print(json.dumps(payload))\n"
    ).format(str(agent_dir))
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=snapshot_dir,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload == {
        "targets": [
            "async-fifo",
            "round-robin-arbiter",
            "sync-fifo",
        ],
        "has_async_method": False,
        "blocked_status": "blocked",
        "service_type": "PluginServices",
        "plugin_type": "TargetPlugin",
    }
