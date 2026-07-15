import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUALITY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-quality.yml"

REQUIRED_RELEASE_PATHS = (
    ".github/scripts/run-vivado-integration.ps1",
    ".github/scripts/vivado-preflight.tcl",
    ".github/workflows/vivado-integration.yml",
    ".trae/agent/README.md",
    ".trae/agent/agent.json",
    ".trae/agent/agent.py",
    ".trae/agent/start_agent.bat",
    "src/digital_ic_agent/_runtime/agent.py",
    "src/digital_ic_agent/_runtime/agent_cli_dispatch.py",
    "src/digital_ic_agent/_runtime/agent_sim_smoke.py",
    "src/digital_ic_agent/_runtime/agent_waveform.py",
    "src/digital_ic_agent/_runtime/capability_preflight.py",
    "src/digital_ic_agent/_runtime/report_templates.py",
    "src/digital_ic_agent/_runtime/skill_runtime.py",
    "src/digital_ic_agent/_runtime/target_handlers/async_fifo.py",
    "src/digital_ic_agent/_runtime/target_handlers/round_robin_arbiter.py",
    "src/digital_ic_agent/_runtime/target_handlers/sync_fifo.py",
    "src/digital_ic_agent/_runtime/target_plugins.py",
    "src/digital_ic_agent/_runtime/target_service_host.py",
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


def test_required_runtime_and_architecture_files_are_in_release_tree():
    release_result = run_git("ls-files", "--cached", "--others", "--exclude-standard")
    assert release_result.returncode == 0, release_result.stderr
    release_paths = set(release_result.stdout.splitlines())

    missing = [
        relative_path
        for relative_path in REQUIRED_RELEASE_PATHS
        if relative_path not in release_paths
    ]

    assert not missing, "required files are absent from release tree: {}".format(
        ", ".join(missing)
    )


def test_quality_workflow_runs_release_tree_runtime_snapshot_gate():
    workflow = QUALITY_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "Verify release-tree runtime snapshot" in workflow
    assert "tests/test_repository_reproducibility.py" in workflow
    assert "uv run --frozen pytest" in workflow


def test_release_tree_snapshot_imports_agent_and_discovers_builtin_targets(
    tmp_path: Path,
):
    snapshot_dir = tmp_path / "release-tree-snapshot"
    snapshot_dir.mkdir()
    shutil.copytree(ROOT / "src", snapshot_dir / "src")
    shutil.copytree(ROOT / ".trae" / "skills", snapshot_dir / ".trae" / "skills")

    script = (
        "import json, sys\n"
        "sys.path.insert(0, {!r})\n"
        "from digital_ic_agent.agent import DigitalICAgent\n"
        "from digital_ic_agent._runtime.agent_runtime import PluginServices, TargetPlugin\n"
        "from digital_ic_agent._runtime.skill_runtime import SkillExecutionStatus\n"
        "agent = DigitalICAgent()\n"
        "payload = {{\n"
        "    'targets': sorted(agent.targets),\n"
        "    'has_async_method': hasattr(agent, 'write_async_fifo_project'),\n"
        "    'blocked_status': SkillExecutionStatus.BLOCKED.value,\n"
        "    'service_type': PluginServices.__name__,\n"
        "    'plugin_type': TargetPlugin.__name__,\n"
        "}}\n"
        "agent.close()\n"
        "print(json.dumps(payload))\n"
    ).format(str(snapshot_dir / "src"))
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
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
