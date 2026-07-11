import importlib
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PACKAGE_DIR = SRC_DIR / "digital_ic_agent"
PYPROJECT_PATH = ROOT / "pyproject.toml"
LEGACY_AGENT_PATH = ROOT / ".trae" / "agent" / "agent.py"


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

    _clear_imports()
    monkeypatch.syspath_prepend(str(SRC_DIR))
    package = importlib.import_module("digital_ic_agent")
    agent_module = importlib.import_module("digital_ic_agent.agent")
    cli_module = importlib.import_module("digital_ic_agent.cli")
    entrypoint_module = importlib.import_module("digital_ic_agent.entrypoint")

    assert package.DigitalICAgent is agent_module.DigitalICAgent
    assert package.create_agent is agent_module.create_agent
    assert package.main is agent_module.main
    assert cli_module.parse_args(["--list-targets"]).list_targets is True
    assert entrypoint_module.run_cli is not None


def test_src_package_is_in_quality_and_coverage_scope():
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert "src/digital_ic_agent" in config["tool"]["mypy"]["files"]
    assert "src/digital_ic_agent" in config["tool"]["coverage"]["run"]["source"]


def test_legacy_core_entrypoint_no_longer_inserts_sys_path():
    source = LEGACY_AGENT_PATH.read_text(encoding="utf-8")

    assert "sys.path.insert" not in source
