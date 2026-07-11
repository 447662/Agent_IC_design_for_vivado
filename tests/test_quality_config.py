import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"
DEV_REQUIREMENTS_PATH = ROOT / "requirements-dev.txt"
UV_LOCK_PATH = ROOT / "uv.lock"
QUALITY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-quality.yml"
GITIGNORE_PATH = ROOT / ".gitignore"


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
    assert {
        ".trae/agent/adapters/report.py",
        ".trae/agent/adapters/vivado.py",
        ".trae/agent/adapters/waveform.py",
    } <= set(tools["mypy"]["files"])
    assert tools["coverage"]["report"]["fail_under"] == 68
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
    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "astral-sh/setup-uv@v6" in workflow
    assert "uv sync --frozen --group dev" in workflow
    assert "uv run --frozen ruff check .trae/agent tests" in workflow
    assert "uv run --frozen mypy" in workflow
    assert "uv run --frozen pytest tests" in workflow
    assert "--cov=.trae/agent" in workflow
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


def test_p5_8_artifact_manifest_is_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/artifact_manifest.py" in config["tool"]["mypy"]["files"]


def test_p5_10_environment_report_is_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/environment_report.py" in config["tool"]["mypy"]["files"]


def test_p5_11_project_overview_is_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/project_overview.py" in config["tool"]["mypy"]["files"]


def test_p1_1_target_service_host_is_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/target_service_host.py" in config["tool"]["mypy"]["files"]


def test_p1_1_report_templates_are_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/report_templates.py" in config["tool"]["mypy"]["files"]


def test_p1_1_cli_dispatch_is_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/agent_cli_dispatch.py" in config["tool"]["mypy"]["files"]


def test_p1_1_cli_parser_is_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/agent_cli_parser.py" in config["tool"]["mypy"]["files"]


def test_p1_1_agent_diagnostics_is_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/agent_diagnostics.py" in config["tool"]["mypy"]["files"]


def test_p1_1_agent_design_spec_is_in_mypy_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert ".trae/agent/agent_design_spec.py" in config["tool"]["mypy"]["files"]
