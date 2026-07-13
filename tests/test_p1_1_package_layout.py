import importlib
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PACKAGE_DIR = SRC_DIR / "digital_ic_agent"
RUNTIME_DIR = PACKAGE_DIR / "_runtime"
PYPROJECT_PATH = ROOT / "pyproject.toml"
THIN_AGENT_PATH = ROOT / ".trae" / "agent" / "agent.py"


def test_src_package_exports_core_agent_entrypoints_without_path_insertion(
    monkeypatch,
):
    assert PACKAGE_DIR.is_dir()
    for filename in (
        "__init__.py",
        "__main__.py",
        "agent.py",
        "cli.py",
        "entrypoint.py",
    ):
        assert (PACKAGE_DIR / filename).is_file()

    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(PACKAGE_DIR.glob("*.py"))
    )
    assert "sys.path.insert" not in package_source
    assert "sys.path.append" not in package_source

    monkeypatch.syspath_prepend(str(SRC_DIR))
    import_path_before = tuple(sys.path)
    package = importlib.import_module("digital_ic_agent")
    agent_module = importlib.import_module("digital_ic_agent.agent")
    cli_module = importlib.import_module("digital_ic_agent.cli")
    entrypoint_module = importlib.import_module("digital_ic_agent.entrypoint")

    assert package.DigitalICAgent is agent_module.DigitalICAgent
    assert package.create_agent is agent_module.create_agent
    assert package.main is agent_module.main
    assert cli_module.parse_args(["--list-targets"]).list_targets is True
    assert entrypoint_module.run_cli is not None
    assert tuple(sys.path) == import_path_before


def test_runtime_is_owned_by_the_src_package_without_legacy_loader():
    assert (RUNTIME_DIR / "agent.py").is_file()
    assert (RUNTIME_DIR / "target_plugins.py").is_file()
    assert not (PACKAGE_DIR / "_legacy.py").exists()


def test_src_package_is_in_quality_and_coverage_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert "src/digital_ic_agent" in config["tool"]["mypy"]["files"]
    assert "src/digital_ic_agent" in config["tool"]["coverage"]["run"]["source"]


def test_trae_core_entrypoint_is_a_thin_package_delegate():
    source = THIN_AGENT_PATH.read_text(encoding="utf-8")

    assert "sys.path.insert" not in source
    assert "digital_ic_agent.agent" in source
    assert "class DigitalICAgent" not in source
