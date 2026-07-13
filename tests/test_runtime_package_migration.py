import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PACKAGE_DIR = SRC_DIR / "digital_ic_agent"
RUNTIME_DIR = PACKAGE_DIR / "_runtime"
MIGRATION_MANIFEST_PATH = (
    ROOT / "docs" / "testing" / "evidence" / "runtime_migration_manifest.json"
)
QUALITY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-quality.yml"
DISTRIBUTION_SMOKE_PATH = ROOT / "scripts" / "smoke_test_distribution.py"


def _run_isolated(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_runtime_package_contains_code_config_targets_and_handlers():
    required = (
        "__init__.py",
        "agent.py",
        "agent_runtime.py",
        "agent_cli.py",
        "agent_entrypoint.py",
        "agent.json",
        "targets/async_fifo.json",
        "targets/sync_fifo.json",
        "targets/round_robin_arbiter.json",
        "target_handlers/async_fifo.py",
        "target_handlers/sync_fifo.py",
        "target_handlers/round_robin_arbiter.py",
    )

    assert all((RUNTIME_DIR / relative).is_file() for relative in required)


def test_runtime_migration_manifest_closes_every_declared_path():
    manifest = json.loads(MIGRATION_MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["source_root"] == ".trae/agent"
    assert manifest["runtime_root"] == "src/digital_ic_agent/_runtime"
    assert manifest["dist_policy"] == "generated-local-artifact"

    moved_sources = set()
    moved_targets = set()
    for relative_path in manifest["moved"]:
        source = f'{manifest["source_root"]}/{relative_path}'
        target = f'{manifest["runtime_root"]}/{relative_path}'
        source_path = ROOT / source
        target_path = ROOT / target
        moved_sources.add(source)
        moved_targets.add(target)
        assert not source_path.exists(), relative_path
        assert target_path.is_file(), relative_path

    copied_targets = set()
    for relative_path in manifest["copied"]:
        source = f'{manifest["source_root"]}/{relative_path}'
        target = f'{manifest["runtime_root"]}/{relative_path}'
        copied_targets.add(target)
        assert (ROOT / source).is_file(), relative_path
        assert (ROOT / target).is_file(), relative_path

    facade_targets = set()
    for relative_path in manifest["facaded"]:
        source = f'{manifest["source_root"]}/{relative_path}'
        target = f'{manifest["runtime_root"]}/{relative_path}'
        facade_targets.add(target)
        assert (ROOT / source).is_file(), relative_path
        assert (ROOT / target).is_file(), relative_path

    added_targets = set()
    for relative_path in manifest["added"]:
        target = f'{manifest["runtime_root"]}/{relative_path}'
        added_targets.add(target)
        assert (ROOT / target).is_file(), relative_path

    compatibility_paths = set(manifest["compatibility"])
    assert compatibility_paths == {
        ".trae/agent/README.md",
        ".trae/agent/agent.json",
        ".trae/agent/agent.py",
        ".trae/agent/start_agent.bat",
    }
    assert all((ROOT / path).is_file() for path in compatibility_paths)
    assert manifest["retired"] == [
        {
            "path": ".trae/agent/agent_bootstrap.py",
            "reason": "package imports replaced dynamic local-module bootstrap",
        }
    ]

    runtime_files = {
        path.relative_to(ROOT).as_posix()
        for path in RUNTIME_DIR.rglob("*")
        if (
            path.is_file()
            and path != RUNTIME_DIR / "__init__.py"
            and "__pycache__" not in path.parts
        )
    }
    assert moved_targets | copied_targets | facade_targets | added_targets == runtime_files
    assert len(moved_sources) == len(moved_targets)

    assert manifest["public_facades"] == {
        "src/digital_ic_agent/agent.py": "digital_ic_agent._runtime.agent",
        "src/digital_ic_agent/cli.py": "digital_ic_agent._runtime.agent_cli",
        "src/digital_ic_agent/entrypoint.py": (
            "digital_ic_agent._runtime.agent_entrypoint"
        ),
    }
    assert manifest["package_data"] == [
        "digital_ic_agent/_runtime/agent.json",
        "digital_ic_agent/_runtime/targets/*.json",
        "digital_ic_agent/skills/*/SKILL.md",
    ]


def test_public_facades_import_runtime_without_legacy_loader():
    for filename in ("agent.py", "cli.py", "entrypoint.py"):
        source = (PACKAGE_DIR / filename).read_text(encoding="utf-8")
        assert "digital_ic_agent._legacy" not in source
        assert "digital_ic_agent._runtime" in source


def test_runtime_import_preserves_sys_path_and_discovers_three_targets():
    script = (
        "import inspect, json, pathlib, sys\n"
        "sys.path.insert(0, {!r})\n"
        "before = tuple(sys.path)\n"
        "from digital_ic_agent.agent import DigitalICAgent\n"
        "agent = DigitalICAgent()\n"
        "payload = {{\n"
        "  'module': DigitalICAgent.__module__,\n"
        "  'source': pathlib.Path(inspect.getfile(DigitalICAgent)).resolve().as_posix(),\n"
        "  'targets': sorted(agent.targets),\n"
        "  'path_unchanged': tuple(sys.path) == before,\n"
        "}}\n"
        "agent.close()\n"
        "print(json.dumps(payload))\n"
    ).format(str(SRC_DIR))
    result = _run_isolated(script)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["module"] == "digital_ic_agent._runtime.agent"
    assert "/src/digital_ic_agent/_runtime/agent.py" in payload["source"]
    assert payload["targets"] == [
        "async-fifo",
        "round-robin-arbiter",
        "sync-fifo",
    ]
    assert payload["path_unchanged"] is True


def test_runtime_cli_lists_targets_from_src_package():
    script = (
        "import sys\n"
        "sys.path.insert(0, {!r})\n"
        "from digital_ic_agent.agent import main\n"
        "raise SystemExit(main(['--list-targets']))\n"
    ).format(str(SRC_DIR))
    result = _run_isolated(script)

    assert result.returncode == 0, result.stderr
    assert "async-fifo" in result.stdout
    assert "sync-fifo" in result.stdout
    assert "round-robin-arbiter" in result.stdout


def test_ci_builds_and_smoke_tests_wheel_and_sdist_outside_source_tree():
    workflow = QUALITY_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert DISTRIBUTION_SMOKE_PATH.is_file()
    assert "Build wheel and sdist" in workflow
    assert "uv build --wheel --sdist" in workflow
    assert workflow.count("scripts/smoke_test_distribution.py") == 2
    assert "--kind wheel" in workflow
    assert "--kind sdist" in workflow


def test_distribution_build_outputs_are_declared_local_artifacts():
    ignored = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "dist/" in ignored
