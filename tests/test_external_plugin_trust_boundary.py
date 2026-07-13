import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent_runtime import PluginServiceDenied, PluginServices  # noqa: E402
from digital_ic_agent._runtime import target_plugins  # noqa: E402
from digital_ic_agent._runtime.target_plugins import (  # noqa: E402
    TargetHandlerRegistry,
    build_target_handlers,
    discover_target_handler_plugins,
)


def _write_package(root: Path, package_name: str, module_body: str) -> Path:
    package_dir = root / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "sample.py").write_text(module_body, encoding="utf-8")
    return package_dir


def _write_manifest(
    root: Path,
    package_name: str,
    *,
    trust: str | None = "trusted-local",
) -> Path:
    payload: dict[str, object] = {
        "plugins": [
            {
                "module": f"{package_name}.sample",
                "handler_id": "sample-handler",
            }
        ]
    }
    if trust is not None:
        payload["trust"] = trust
    manifest = root / "external_plugins.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def _discover(root: Path, package_name: str, manifest: Path):
    return discover_target_handler_plugins(
        TargetHandlerRegistry(),
        package_name,
        search_path=root,
        manifest_path=manifest,
        allowed_modules=(f"{package_name}.sample",),
    )


def _handler(root: Path, package_name: str, module_body: str):
    _write_package(root, package_name, module_body)
    registry = _discover(root, package_name, _write_manifest(root, package_name))
    handlers = build_target_handlers(
        PluginServices(operations={}),
        {
            "sample-target": {
                "name": "sample-target",
                "handler": "sample-handler",
                "aliases": [],
                "flows": ["generate-rtl"],
            }
        },
        registry,
    )
    return handlers["sample-target"]


def test_external_manifest_requires_explicit_trusted_local_contract(tmp_path):
    _write_package(tmp_path, "trust_plugins", "HANDLER_ID = 'sample-handler'\n")

    with pytest.raises(ValueError, match="trusted-local"):
        _discover(
            tmp_path,
            "trust_plugins",
            _write_manifest(tmp_path, "trust_plugins", trust=None),
        )

    with pytest.raises(ValueError, match="trusted-local"):
        _discover(
            tmp_path,
            "trust_plugins",
            _write_manifest(tmp_path, "trust_plugins", trust="untrusted"),
        )


def test_external_module_must_reject_symlink_resolution_outside_search_root(
    tmp_path,
    monkeypatch,
):
    root = tmp_path.resolve()
    package_path = root / "escape_plugins"
    module_path = package_path / "sample.py"
    resolved_package = root.parent / "outside" / "escape_plugins"
    real_resolve = Path.resolve

    def resolve(path: Path, strict: bool = False):
        if path == root:
            return root
        if path == package_path:
            return resolved_package
        if path == module_path:
            return resolved_package / "sample.py"
        return real_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ValueError, match="outside external plugin root"):
        target_plugins._resolve_external_module_path(
            root,
            "escape_plugins",
            "escape_plugins.sample",
        )


def test_external_module_must_be_a_regular_file(tmp_path):
    package_dir = tmp_path / "non_file_plugins"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "sample.py").mkdir()

    with pytest.raises(ValueError, match="regular file"):
        _discover(
            tmp_path,
            "non_file_plugins",
            _write_manifest(tmp_path, "non_file_plugins"),
        )


def test_external_plugin_subprocess_receives_minimal_environment(tmp_path, monkeypatch):
    handler = _handler(
        tmp_path,
        "environment_plugins",
        "from agent_runtime import TargetHandler\n"
        "HANDLER_ID = 'sample-handler'\n"
        "def create_handler(_services, target):\n"
        "    return TargetHandler(target['name'], {'generate-rtl': lambda **_: 'ok'})\n",
    )
    captured: dict[str, object] = {}
    monkeypatch.setenv("DIGITAL_IC_AGENT_TEST_SECRET", "must-not-cross-boundary")

    def run(*args: object, **kwargs: object):
        captured.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, '{"result":"ok"}\n', "")

    monkeypatch.setattr(target_plugins.subprocess, "run", run)

    assert handler.run("generate-rtl", output_dir=tmp_path / "outputs") == "ok"
    child_env = captured["env"]
    assert isinstance(child_env, dict)
    assert "DIGITAL_IC_AGENT_TEST_SECRET" not in child_env
    assert child_env["PYTHONIOENCODING"] == "utf-8"
    assert handler.plugin["trust"] == "trusted-local"
    assert handler.plugin["isolation"] == "python-guarded-subprocess"
    assert handler.plugin["sandbox"] == "none"
    assert handler.plugin["security_boundary"] == "defense-in-depth-only"


def test_external_plugin_os_open_cannot_read_outside_allowed_roots(tmp_path):
    secret_path = tmp_path / "secret.txt"
    secret_path.write_text("private", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    handler = _handler(
        tmp_path,
        "low_level_plugins",
        "import os\n"
        "from agent_runtime import TargetHandler\n"
        "HANDLER_ID = 'sample-handler'\n"
        "def create_handler(_services, target):\n"
        "    def generate(**_kwargs):\n"
        f"        descriptor = os.open({str(secret_path)!r}, os.O_RDONLY)\n"
        "        try:\n"
        "            return os.read(descriptor, 32).decode('utf-8')\n"
        "        finally:\n"
        "            os.close(descriptor)\n"
        "    return TargetHandler(target['name'], {'generate-rtl': generate})\n",
    )

    with pytest.raises(PluginServiceDenied) as raised:
        handler.run("generate-rtl", output_dir=output_dir)

    assert raised.value.event["reason"] == "read_outside_allowed_root"
