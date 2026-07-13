import importlib
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PACKAGE_DIR = SRC_DIR / "digital_ic_agent"
PYPROJECT_PATH = ROOT / "pyproject.toml"
LEGACY_AGENT_PATH = ROOT / ".trae" / "agent" / "agent.py"
LEGACY_LOADER_PATH = PACKAGE_DIR / "_legacy.py"


def _clear_imports() -> None:
    for name in tuple(sys.modules):
        if name == "digital_ic_agent" or name.startswith("digital_ic_agent."):
            sys.modules.pop(name, None)


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

    _clear_imports()
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


def test_installed_legacy_loader_prefers_regular_package_imports():
    source = LEGACY_LOADER_PATH.read_text(encoding="utf-8")

    assert "importlib.import_module" in source
    assert "digital_ic_agent._legacy_agent" in source


def test_src_package_is_in_quality_and_coverage_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert "src/digital_ic_agent" in config["tool"]["mypy"]["files"]
    assert "src/digital_ic_agent" in config["tool"]["coverage"]["run"]["source"]


def test_legacy_core_entrypoint_no_longer_inserts_sys_path():
    source = LEGACY_AGENT_PATH.read_text(encoding="utf-8")

    assert "sys.path.insert" not in source
