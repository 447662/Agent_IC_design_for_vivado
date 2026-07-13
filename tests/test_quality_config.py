import re
import tomllib
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"
DEV_REQUIREMENTS_PATH = ROOT / "requirements-dev.txt"
UV_LOCK_PATH = ROOT / "uv.lock"
QUALITY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-quality.yml"
GITIGNORE_PATH = ROOT / ".gitignore"
VIVADO_ADAPTER_PATH = ROOT / "src" / "digital_ic_agent" / "_runtime" / "adapters" / "vivado.py"
TYPE_BOUNDARY_ANY_LIMITS = {
    ROOT / "src" / "digital_ic_agent" / "_runtime" / "agent.py": 66,
    ROOT / "src" / "digital_ic_agent" / "_runtime" / "agent_skill_execution.py": 0,
    ROOT / "src" / "digital_ic_agent" / "_runtime" / "agent_legacy_target_facades.py": 0,
    ROOT / "src" / "digital_ic_agent" / "_runtime" / "agent_cli_dispatch.py": 0,
    ROOT / "src" / "digital_ic_agent" / "_runtime" / "agent_workflow.py": 0,
    ROOT / "src" / "digital_ic_agent" / "_runtime" / "agent_runtime.py": 12,
    ROOT / "src" / "digital_ic_agent" / "_runtime" / "target_plugins.py": 4,
    ROOT / "src" / "digital_ic_agent" / "_runtime" / "target_scaffolder.py": 0,
    ROOT / "src" / "digital_ic_agent" / "agent.py": 0,
}


def load_vivado_adapter():
    spec = importlib.util.spec_from_file_location(
        "vivado_adapter_under_test",
        VIVADO_ADAPTER_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_priority_type_boundaries_have_explicit_any_budgets():
    counts = {
        path.relative_to(ROOT).as_posix(): len(
            re.findall(r"\bAny\b", path.read_text(encoding="utf-8"))
        )
        for path in TYPE_BOUNDARY_ANY_LIMITS
    }
    violations = {
        path.relative_to(ROOT).as_posix(): (counts[path.relative_to(ROOT).as_posix()], limit)
        for path, limit in TYPE_BOUNDARY_ANY_LIMITS.items()
        if counts[path.relative_to(ROOT).as_posix()] > limit
    }

    assert not violations, "Any budgets exceeded: {}".format(violations)


def test_pyproject_defines_python_quality_gates():
    assert PYPROJECT_PATH.exists()

    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    tools = config["tool"]

    assert tools["pytest"]["ini_options"]["testpaths"] == ["tests"]
    assert tools["ruff"]["target-version"] == "py311"
    assert tools["mypy"]["python_version"] == "3.11"
    assert tools["mypy"]["check_untyped_defs"] is True
    assert tools["mypy"]["disallow_untyped_defs"] is True
    assert tools["mypy"]["strict_equality"] is True
    assert tools["mypy"]["warn_return_any"] is True


def test_ruff_enables_reviewed_low_noise_rule_subset():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    tools = config["tool"]
    selected = set(config["tool"]["ruff"]["lint"]["select"])

    assert {
        "B904",
        "B905",
        "UP017",
        "SIM105",
        "SIM300",
        "RUF005",
    } <= selected
    assert tools["mypy"]["files"] == ["src/digital_ic_agent"]
    assert tools["coverage"]["report"]["fail_under"] == 85
    assert tools["coverage"]["report"]["show_missing"] is True
    assert not any(
        override.get("ignore_errors") is True
        for override in tools["mypy"].get("overrides", [])
    )


def test_development_requirements_include_quality_tools():
    requirement_lines = [
        line.split(";", 1)[0].strip()
        for line in DEV_REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    requirements = {
        re.split(r"[<>=!~]", line, maxsplit=1)[0].lower()
        for line in requirement_lines
    }

    assert {"pytest", "pytest-cov", "ruff", "mypy"} <= requirements
    assert all("==" in line for line in requirement_lines)
    assert UV_LOCK_PATH.is_file()


def test_github_actions_runs_all_python_quality_gates():
    assert QUALITY_WORKFLOW_PATH.exists()

    workflow = QUALITY_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "actions/checkout@" in workflow
    assert "actions/setup-python@" in workflow
    assert "astral-sh/setup-uv@" in workflow
    for action_name in (
        "actions/checkout",
        "actions/setup-python",
        "astral-sh/setup-uv",
    ):
        match = re.search(r"uses:\s+{}@([0-9a-f]{{40}})".format(action_name), workflow)
        assert match is not None, "{} must be pinned to a commit SHA".format(action_name)
    assert "uv sync --frozen --group dev" in workflow
    assert (
        "uv run --frozen ruff check .trae/agent tests src/digital_ic_agent scripts"
        in workflow
    )
    assert "uv run --frozen mypy" in workflow
    assert "uv run --frozen pytest tests" in workflow
    assert "--junitxml .tmp/pytest-results.xml" in workflow
    assert "--cov=.trae/agent" not in workflow
    assert "--cov=src/digital_ic_agent" in workflow
    assert "--cov-report=xml:coverage.xml" in workflow
    assert "-p no:cacheprovider" in workflow
    assert "scripts/generate_quality_summary.py" in workflow
    assert "scripts/generate_agent_eval_report.py" in workflow
    assert "--eval-cases tests/fixtures/agent_eval_cases.json" in workflow
    assert "scripts/generate_test_module_report.py" in workflow
    assert "--line-limit 1000" in workflow
    assert "--output-dir docs/generated" in workflow
    assert "--write-readme" in workflow
    assert "Verify generated quality reports" in workflow
    for generated_path in (
        "docs/generated/quality_summary.md",
        "docs/generated/capability_matrix.md",
        "docs/generated/agent_eval_report.json",
        "docs/generated/agent_eval_report.md",
        "docs/generated/test_module_report.json",
        "docs/generated/test_module_report.md",
        "coverage.xml",
        ".tmp/pytest-results.xml",
    ):
        assert f"test -s {generated_path}" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    assert "digital-ic-agent-generated-quality-${{ matrix.python-version }}" in workflow
    assert "docs/generated" in workflow
    assert "coverage.xml" in workflow
    assert ".tmp/pytest-results.xml" in workflow
    assert "if-no-files-found: error" in workflow
    assert "--cov-fail-under" not in workflow


def test_python_quality_artifacts_are_gitignored():
    assert GITIGNORE_PATH.exists()

    ignored = {
        line.strip()
        for line in GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".coverage",
        "coverage.xml",
        "htmlcov/",
        ".tmp-*/",
    } <= ignored


def test_runtime_production_modules_respect_800_line_budget():
    runtime_dir = ROOT / "src" / "digital_ic_agent" / "_runtime"
    over_budget = {}

    for path in runtime_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 800:
            over_budget[path.relative_to(ROOT).as_posix()] = line_count

    assert not over_budget, "runtime modules over 800 lines: {}".format(over_budget)


def _assert_runtime_module_in_mypy_scope(module_name: str) -> None:
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert config["tool"]["mypy"]["files"] == ["src/digital_ic_agent"]
    assert (ROOT / "src" / "digital_ic_agent" / "_runtime" / module_name).is_file()


def test_p5_8_artifact_manifest_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("artifact_manifest.py")


def test_p5_10_environment_report_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("environment_report.py")


def test_p5_11_project_overview_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("project_overview.py")


def test_p1_1_target_service_host_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("target_service_host.py")


def test_p1_1_report_templates_are_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("report_templates.py")


def test_p1_1_cli_dispatch_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("agent_cli_dispatch.py")


def test_p1_1_cli_parser_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("agent_cli_parser.py")


def test_p1_1_agent_diagnostics_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("agent_diagnostics.py")


def test_p1_1_agent_design_spec_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("agent_design_spec.py")


def test_p1_1_agent_sim_smoke_is_in_mypy_scope():
    _assert_runtime_module_in_mypy_scope("agent_sim_smoke.py")


def test_p1_4_vivado_resolution_uses_env_or_discovery_not_machine_defaults(
    monkeypatch,
    tmp_path,
):
    module = load_vivado_adapter()
    source = VIVADO_ADAPTER_PATH.read_text(encoding="utf-8")

    assert r"D:\vivado" not in source
    assert r"C:\Xilinx" not in source

    configured_vivado = tmp_path / "Vivado" / "bin" / "vivado.bat"
    configured_vivado.parent.mkdir(parents=True)
    configured_vivado.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("DIGITAL_IC_AGENT_VIVADO", str(configured_vivado))
    monkeypatch.setenv("VIVADO_PATH", str(tmp_path / "ignored-vivado.bat"))
    monkeypatch.setattr(
        module.shutil,
        "which",
        lambda name: str(tmp_path / "path-vivado") if name == "vivado" else None,
    )

    class Agent:
        vivado_command = None

    assert module.resolve_vivado_command(Agent()) == str(configured_vivado)

    monkeypatch.delenv("DIGITAL_IC_AGENT_VIVADO")
    assert module.resolve_vivado_command(Agent()) == str(tmp_path / "ignored-vivado.bat")

    monkeypatch.delenv("VIVADO_PATH")
    assert module.resolve_vivado_command(Agent()) == str(tmp_path / "path-vivado")


def test_p1_4_package_has_reproducible_build_backend_entrypoint_and_version():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert config["build-system"]["requires"] == ["hatchling==1.27.0"]
    assert config["build-system"]["build-backend"] == "hatchling.build"
    assert config["project"]["dynamic"] == ["version"]
    assert config["tool"]["hatch"]["version"]["path"] == "src/digital_ic_agent/__about__.py"
    assert config["project"]["scripts"] == {
        "digital-ic-agent": "digital_ic_agent.agent:main",
    }

    version_source = (ROOT / "src" / "digital_ic_agent" / "__about__.py").read_text(
        encoding="utf-8"
    )
    assert '__version__ = "1.0.0"' in version_source
    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"] == {
        ".trae/skills": "digital_ic_agent/skills",
    }


def test_p1_4_package_uses_src_runtime_without_legacy_loader():
    package_dir = ROOT / "src" / "digital_ic_agent"

    assert (package_dir / "_runtime" / "agent.py").is_file()
    assert not (package_dir / "_legacy.py").exists()
    assert "digital_ic_agent/_legacy_agent" not in PYPROJECT_PATH.read_text(encoding="utf-8")


def test_p1_4_github_actions_are_pinned_to_commit_shas():
    for workflow_path in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in workflow_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith("uses: "):
                continue
            action_ref = stripped.removeprefix("uses: ").strip()
            assert "@" in action_ref
            revision = action_ref.rsplit("@", 1)[1]
            assert re.fullmatch(r"[0-9a-f]{40}", revision), (
                "{} uses non-SHA action reference: {}".format(
                    workflow_path.relative_to(ROOT),
                    action_ref,
                )
            )
