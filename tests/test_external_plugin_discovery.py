import json
import sys
from pathlib import Path

import pytest

from digital_ic_agent._runtime.agent_runtime import PluginServices
from digital_ic_agent._runtime.target_plugins import (
    TargetHandlerRegistry,
    build_target_handlers,
    discover_target_handler_plugins,
)

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


def test_external_search_path_requires_manifest_before_import(tmp_path):
    _write_plugin_package(
        tmp_path,
        "isolated_target_plugins",
        {"sample": ("isolated-handler", ("generate-rtl",))},
    )
    sentinel_path = tmp_path / "external_plugin_imported.txt"
    module_path = tmp_path / "isolated_target_plugins" / "sample.py"
    module_path.write_text(
        "from pathlib import Path\n"
        + "Path({!r}).write_text('imported', encoding='utf-8')\n".format(
            str(sentinel_path)
        )
        + module_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    before = tuple(sys.path)

    with pytest.raises(ValueError, match="requires a manifest"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "isolated_target_plugins",
            search_path=tmp_path,
            allowed_modules=("isolated_target_plugins.sample",),
        )

    assert not sentinel_path.exists()
    assert tuple(sys.path) == before


def test_external_search_path_requires_allowlist_before_import(tmp_path):
    _write_plugin_package(
        tmp_path,
        "allowlist_target_plugins",
        {"sample": ("allowlist-handler", ("generate-rtl",))},
    )
    sentinel_path = tmp_path / "allowlist_plugin_imported.txt"
    module_path = tmp_path / "allowlist_target_plugins" / "sample.py"
    module_path.write_text(
        "from pathlib import Path\n"
        + "Path({!r}).write_text('imported', encoding='utf-8')\n".format(
            str(sentinel_path)
        )
        + module_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "external_plugins.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trust": "trusted-local",
                "plugins": [
                    {
                        "module": "allowlist_target_plugins.sample",
                        "handler_id": "allowlist-handler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires an explicit allowlist"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "allowlist_target_plugins",
            search_path=tmp_path,
            manifest_path=manifest_path,
        )

    assert not sentinel_path.exists()


@pytest.mark.parametrize(
    ("module_name", "message"),
    [
        ("other_target_plugins.sample", "must belong to package"),
        (r"validated_target_plugins.\\..\\escape", "valid qualified name"),
    ],
)
def test_external_manifest_rejects_unsafe_module_names(
    tmp_path,
    module_name,
    message,
):
    _write_plugin_package(
        tmp_path,
        "validated_target_plugins",
        {"sample": ("validated-handler", ("generate-rtl",))},
    )
    manifest_path = tmp_path / "external_plugins.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trust": "trusted-local",
                "plugins": [
                    {
                        "module": module_name,
                        "handler_id": "validated-handler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "validated_target_plugins",
            search_path=tmp_path,
            manifest_path=manifest_path,
            allowed_modules=(module_name,),
        )


def test_external_target_plugins_require_manifest_allowlist(tmp_path):
    _write_plugin_package(
        tmp_path,
        "external_target_plugins",
        {
            "allowed": ("allowed-handler", ("generate-rtl",)),
            "unlisted": ("unlisted-handler", ("generate-rtl",)),
        },
    )
    manifest_path = tmp_path / "external_plugins.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trust": "trusted-local",
                "plugins": [
                    {
                        "module": "external_target_plugins.allowed",
                        "handler_id": "allowed-handler",
                    },
                    {
                        "module": "external_target_plugins.unlisted",
                        "handler_id": "unlisted-handler",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not allowlisted"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "external_target_plugins",
            search_path=tmp_path,
            manifest_path=manifest_path,
            allowed_modules=("external_target_plugins.allowed",),
        )

    registry = discover_target_handler_plugins(
        TargetHandlerRegistry(),
        "external_target_plugins",
        search_path=tmp_path,
        manifest_path=manifest_path,
        allowed_modules=(
            "external_target_plugins.allowed",
            "external_target_plugins.unlisted",
        ),
    )

    assert registry.ids() == ("allowed-handler", "unlisted-handler")


def test_manifest_external_plugins_are_not_imported_in_main_process(tmp_path):
    package_dir = tmp_path / "subprocess_target_plugins"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    sentinel_path = tmp_path / "main_process_imported.txt"
    (package_dir / "external.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "from agent_runtime import TargetHandler",
                "",
                'HANDLER_ID = "external-handler"',
                'Path({!r}).write_text("imported", encoding="utf-8")'.format(
                    str(sentinel_path)
                ),
                "",
                "def create_handler(services, target):",
                "    return TargetHandler(target['name'], {",
                '        "generate-rtl": lambda **_kwargs: "generated"',
                "    })",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "external_plugins.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trust": "trusted-local",
                "plugins": [
                    {
                        "module": "subprocess_target_plugins.external",
                        "handler_id": "external-handler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    registry = discover_target_handler_plugins(
        TargetHandlerRegistry(),
        "subprocess_target_plugins",
        search_path=tmp_path,
        manifest_path=manifest_path,
        allowed_modules=("subprocess_target_plugins.external",),
    )

    assert registry.ids() == ("external-handler",)
    assert not sentinel_path.exists()


def test_manifest_external_plugin_flow_runs_through_subprocess_proxy(tmp_path):
    package_dir = tmp_path / "subprocess_flow_plugins"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    child_marker = output_dir / "child_process_ran.txt"
    (package_dir / "external.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "from agent_runtime import TargetHandler",
                "",
                'HANDLER_ID = "external-flow-handler"',
                "",
                "def create_handler(services, target):",
                "    def generate(**kwargs):",
                '        Path({!r}).write_text(kwargs["output_dir"], encoding="utf-8")'.format(
                    str(child_marker)
                ),
                '        return "child:" + target["name"] + ":" + kwargs["output_dir"]',
                "    return TargetHandler(target['name'], {'generate-rtl': generate})",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "external_plugins.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trust": "trusted-local",
                "plugins": [
                    {
                        "module": "subprocess_flow_plugins.external",
                        "handler_id": "external-flow-handler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    registry = discover_target_handler_plugins(
        TargetHandlerRegistry(),
        "subprocess_flow_plugins",
        search_path=tmp_path,
        manifest_path=manifest_path,
        allowed_modules=("subprocess_flow_plugins.external",),
    )
    handlers = build_target_handlers(
        PluginServices(operations={}),
        {
            "subprocess-target": {
                "name": "subprocess-target",
                "handler": "external-flow-handler",
                "aliases": [],
                "flows": ["generate-rtl"],
            }
        },
        registry,
    )

    result = handlers["subprocess-target"].run(
        "generate-rtl",
        output_dir=output_dir,
    )

    assert result == "child:subprocess-target:{}".format(output_dir)
    assert child_marker.read_text(encoding="utf-8") == str(output_dir)
    plugin_metadata = handlers["subprocess-target"].plugin
    assert plugin_metadata["isolation"] == "python-guarded-subprocess"
    assert plugin_metadata["sandbox"] == "none"
    assert plugin_metadata["security_boundary"] == "defense-in-depth-only"
    assert handlers["subprocess-target"].plugin["trust"] == "trusted-local"
