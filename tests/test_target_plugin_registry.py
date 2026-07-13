import ast
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
TARGETS_DIR = AGENT_DIR / "targets"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent_runtime import PluginServices  # noqa: E402
from digital_ic_agent._runtime.target_plugins import (  # noqa: E402
    TargetHandlerRegistry,
    build_target_handlers,
    discover_target_handler_plugins,
    load_target_handler_plugins,
)

from digital_ic_agent._runtime import agent as agent_module  # noqa: E402


def _write_plugin_package(
    root: Path,
    package_name: str,
    modules: dict[str, tuple[str, tuple[str, ...]]],
) -> None:
    package_dir = root / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    for module_name, (handler_id, flows) in modules.items():
        flow_items = ", ".join(
            '"{}": (lambda **_kwargs: "{}")'.format(flow, flow)
            for flow in flows
        )
        (package_dir / "{}.py".format(module_name)).write_text(
            "\n".join(
                [
                    "from agent_runtime import TargetHandler",
                    "",
                    'HANDLER_ID = "{}"'.format(handler_id),
                    "",
                    "def create_handler(agent, target):",
                    "    return TargetHandler(target['name'], {{{}}})".format(
                        flow_items
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )


def test_trusted_target_plugins_auto_discover_without_central_mapping(
    tmp_path,
    monkeypatch,
):
    _write_plugin_package(
        tmp_path,
        "demo_target_plugins",
        {"sample": ("sample-handler", ("generate-rtl",))},
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    registry = TargetHandlerRegistry()
    discover_target_handler_plugins(
        registry,
        "demo_target_plugins",
    )
    targets = {
        "sample-target": {
            "name": "sample-target",
            "handler": "sample-handler",
            "aliases": [],
            "flows": ["generate-rtl"],
        }
    }

    handlers = build_target_handlers(object(), targets, registry)

    assert set(handlers) == {"sample-target"}
    assert handlers["sample-target"].run("generate-rtl") == "generate-rtl"


def test_target_plugin_discovery_failure_does_not_partially_register_handlers(
    tmp_path,
    monkeypatch,
):
    _write_plugin_package(
        tmp_path,
        "partial_target_plugins",
        {
            "first": ("first-handler", ("generate-rtl",)),
            "second": ("first-handler", ("generate-rtl",)),
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    registry = TargetHandlerRegistry()

    with pytest.raises(ValueError, match="Duplicate target handler"):
        discover_target_handler_plugins(
            registry,
            "partial_target_plugins",
        )

    assert registry.ids() == ()


def test_target_plugins_reject_duplicate_unknown_and_mismatched_handlers(
    tmp_path,
    monkeypatch,
):
    _write_plugin_package(
        tmp_path,
        "duplicate_target_plugins",
        {
            "first": ("duplicate", ("generate-rtl",)),
            "second": ("duplicate", ("generate-rtl",)),
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ValueError, match="Duplicate target handler"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "duplicate_target_plugins",
        )

    registry = TargetHandlerRegistry()
    with pytest.raises(ValueError, match="Unknown target handler"):
        build_target_handlers(
            object(),
            {
                "unknown-target": {
                    "name": "unknown-target",
                    "handler": "missing-handler",
                    "aliases": [],
                    "flows": ["generate-rtl"],
                }
            },
            registry,
        )

    _write_plugin_package(
        tmp_path,
        "mismatched_target_plugins",
        {"sample": ("mismatch", ("generate-rtl", "sim-rtl"))},
    )
    discover_target_handler_plugins(
        registry,
        "mismatched_target_plugins",
    )
    with pytest.raises(ValueError, match="flow mismatch"):
        build_target_handlers(
            object(),
            {
                "mismatch-target": {
                    "name": "mismatch-target",
                    "handler": "mismatch",
                    "aliases": [],
                    "flows": ["generate-rtl"],
                }
            },
            registry,
        )


def test_target_plugin_registry_rejects_empty_and_non_callable_factories():
    registry = TargetHandlerRegistry()

    with pytest.raises(ValueError, match="must not be empty"):
        registry.register("   ", lambda _services, _target: object())

    with pytest.raises(ValueError, match="factory is not callable"):
        registry.register("bad-factory", object())


def test_target_plugin_discovery_rejects_invalid_modules_and_packages(
    tmp_path,
    monkeypatch,
):
    package_dir = tmp_path / "invalid_target_plugins"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "empty.py").write_text(
        "HANDLER_ID = ''\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ValueError, match="Invalid target handler plugin module"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "invalid_target_plugins",
        )

    manifest_path = tmp_path / "missing_plugins.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trust": "trusted-local",
                "plugins": [
                    {
                        "module": "missing_target_plugins.sample",
                        "handler_id": "missing-handler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="package not found"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "missing_target_plugins",
            search_path=tmp_path,
            manifest_path=manifest_path,
            allowed_modules=("missing_target_plugins.sample",),
        )


def test_target_plugin_manifest_rejects_bad_schema_and_handler_mismatch(
    tmp_path,
    monkeypatch,
):
    _write_plugin_package(
        tmp_path,
        "manifest_bad_plugins",
        {"sample": ("actual-handler", ("generate-rtl",))},
    )
    manifest_path = tmp_path / "external_plugins.json"

    manifest_path.write_text(json.dumps({"plugins": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="plugins must be a list"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "manifest_bad_plugins",
            search_path=tmp_path,
            manifest_path=manifest_path,
            allowed_modules=("manifest_bad_plugins.sample",),
        )

    manifest_path.write_text(json.dumps({"plugins": ["bad"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="entry 0 must be an object"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "manifest_bad_plugins",
            search_path=tmp_path,
            manifest_path=manifest_path,
            allowed_modules=("manifest_bad_plugins.sample",),
        )

    manifest_path.write_text(json.dumps({"plugins": [{}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="entry 0 is incomplete"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "manifest_bad_plugins",
            search_path=tmp_path,
            manifest_path=manifest_path,
            allowed_modules=("manifest_bad_plugins.sample",),
        )

    mismatch_manifest = {
        "trust": "trusted-local",
        "plugins": [
            {
                "module": "manifest_bad_plugins.sample",
                "handler_id": "expected-handler",
            }
        ]
    }
    manifest_path.write_text(json.dumps(mismatch_manifest), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ValueError, match="manifest handler mismatch"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "manifest_bad_plugins",
            manifest_path=manifest_path,
            allowed_modules=("manifest_bad_plugins.sample",),
        )


def test_target_handler_build_rejects_missing_handler_and_bad_factory():
    registry = TargetHandlerRegistry()
    registry.register("bad-handler", lambda _services, _target: object())

    with pytest.raises(ValueError, match="missing handler declaration"):
        build_target_handlers(
            PluginServices(operations={}),
            {"bad-target": {"name": "bad-target", "flows": []}},
            registry,
        )

    with pytest.raises(ValueError, match="did not return TargetHandler"):
        build_target_handlers(
            PluginServices(operations={}),
            {
                "bad-target": {
                    "name": "bad-target",
                    "handler": "bad-handler",
                    "flows": [],
                }
            },
            registry,
        )


def test_builtin_target_handlers_use_explicit_module_whitelist():
    target_configs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(TARGETS_DIR.glob("*.json"))
    ]
    assert target_configs
    assert all(config.get("handler") for config in target_configs)

    from digital_ic_agent._runtime.target_flows import BUILTIN_HANDLER_MODULES

    assert BUILTIN_HANDLER_MODULES == (
        "digital_ic_agent._runtime.target_handlers.async_fifo",
        "digital_ic_agent._runtime.target_handlers.round_robin_arbiter",
        "digital_ic_agent._runtime.target_handlers.sync_fifo",
    )
    registry = load_target_handler_plugins(
        TargetHandlerRegistry(),
        BUILTIN_HANDLER_MODULES,
    )
    assert set(registry.ids()) == {
        "async-fifo",
        "round-robin-arbiter",
        "sync-fifo",
    }

    from digital_ic_agent._runtime.agent import DigitalICAgent

    agent = DigitalICAgent()
    assert set(agent.target_handlers) == {
        config["name"] for config in target_configs
    }


def test_core_targets_build_without_async_fifo_plugin(tmp_path):
    from digital_ic_agent._runtime.target_flows import build_plugin_services

    agent = agent_module.DigitalICAgent()
    registry = load_target_handler_plugins(
        TargetHandlerRegistry(),
        (
            "target_handlers.round_robin_arbiter",
            "target_handlers.sync_fifo",
        ),
    )
    targets = {
        name: agent.targets[name]
        for name in ("round-robin-arbiter", "sync-fifo")
    }

    handlers = build_target_handlers(
        build_plugin_services(agent),
        targets,
        registry,
    )

    assert set(handlers) == {"round-robin-arbiter", "sync-fifo"}
    assert handlers["sync-fifo"].run(
        "generate-rtl",
        output_dir=tmp_path,
    ).is_dir()
    assert handlers["round-robin-arbiter"].run(
        "generate-rtl",
        output_dir=tmp_path,
    ).is_dir()
    assert "async-fifo" not in handlers


def test_sync_fifo_and_arbiter_are_installed_by_plugins_not_core_agent_mixins():
    source = (AGENT_DIR / "agent.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    agent_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DigitalICAgent"
    )
    base_names = {
        base.id
        for base in agent_class.bases
        if isinstance(base, ast.Name)
    }

    assert "agent_sync_fifo" not in imported_modules
    assert "agent_round_robin_arbiter" not in imported_modules
    assert "SyncFifoMixin" not in base_names
    assert "RoundRobinArbiterMixin" not in base_names

    agent = agent_module.DigitalICAgent()
    for target_name, forbidden_method in (
        ("sync-fifo", "write_sync_fifo_project"),
        ("round-robin-arbiter", "write_round_robin_arbiter_project"),
    ):
        handler = agent.target_handlers[target_name]

        assert handler.target_name == target_name
        assert callable(handler.run)
        assert handler.plugin is None
        assert not hasattr(agent, forbidden_method)
