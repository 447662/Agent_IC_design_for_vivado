import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

from digital_ic_agent._runtime.agent_runtime import PluginServiceDenied, PluginServices  # noqa: E402
from digital_ic_agent._runtime.target_plugins import (  # noqa: E402
    TargetHandlerRegistry,
    build_target_handlers,
    discover_target_handler_plugins,
)

def test_manifest_external_plugin_subprocess_rejects_direct_file_escape(tmp_path):
    package_dir = tmp_path / "subprocess_escape_plugins"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    escape_path = tmp_path / "escape.txt"
    root_secret = ROOT / "pyproject.toml"
    (package_dir / "external.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "from agent_runtime import TargetHandler",
                "",
                'HANDLER_ID = "external-escape-handler"',
                "",
                "def create_handler(services, target):",
                "    def write_escape(**kwargs):",
                '        Path({!r}).write_text("bad", encoding="utf-8")'.format(
                    str(escape_path)
                ),
                '        return "bad"',
                "    def read_root(**kwargs):",
                "        return Path({!r}).read_text(encoding='utf-8')".format(
                    str(root_secret)
                ),
                "    return TargetHandler(",
                "        target['name'],",
                "        {'write-escape': write_escape, 'read-root': read_root},",
                "    )",
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
                        "module": "subprocess_escape_plugins.external",
                        "handler_id": "external-escape-handler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    registry = discover_target_handler_plugins(
        TargetHandlerRegistry(),
        "subprocess_escape_plugins",
        search_path=tmp_path,
        manifest_path=manifest_path,
        allowed_modules=("subprocess_escape_plugins.external",),
    )
    handlers = build_target_handlers(
        PluginServices(operations={}),
        {
            "subprocess-escape-target": {
                "name": "subprocess-escape-target",
                "handler": "external-escape-handler",
                "aliases": [],
                "flows": ["write-escape", "read-root"],
            }
        },
        registry,
    )
    output_dir = tmp_path / "outputs"

    with pytest.raises(PluginServiceDenied) as write_denied:
        handlers["subprocess-escape-target"].run(
            "write-escape",
            output_dir=output_dir,
        )
    assert write_denied.value.event["reason"] == "output_dir_outside_allowed_root"
    assert not escape_path.exists()

    with pytest.raises(PluginServiceDenied) as read_denied:
        handlers["subprocess-escape-target"].run(
            "read-root",
            output_dir=output_dir,
        )
    assert read_denied.value.event["reason"] == "read_outside_allowed_root"


def test_manifest_external_plugin_subprocess_rejects_unauthorized_commands(tmp_path):
    package_dir = tmp_path / "subprocess_command_plugins"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    command_marker = tmp_path / "unauthorized_command_ran.txt"
    command_code = (
        "from pathlib import Path; "
        "Path({!r}).write_text(\"bad\", encoding=\"utf-8\")"
    ).format(str(command_marker))
    (package_dir / "external.py").write_text(
        "\n".join(
            [
                "import subprocess",
                "from agent_runtime import TargetHandler",
                "",
                'HANDLER_ID = "external-command-handler"',
                "",
                "def create_handler(services, target):",
                "    def run_command(**kwargs):",
                "        subprocess.run([",
                "            'python',",
                "            '-c',",
                "            __COMMAND_CODE__,",
                "        ], check=False)",
                '        return "bad"',
                "    return TargetHandler(target['name'], {'run-command': run_command})",
                "",
            ]
        ).replace("__COMMAND_CODE__", repr(command_code)),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "external_plugins.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trust": "trusted-local",
                "plugins": [
                    {
                        "module": "subprocess_command_plugins.external",
                        "handler_id": "external-command-handler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    registry = discover_target_handler_plugins(
        TargetHandlerRegistry(),
        "subprocess_command_plugins",
        search_path=tmp_path,
        manifest_path=manifest_path,
        allowed_modules=("subprocess_command_plugins.external",),
    )
    handlers = build_target_handlers(
        PluginServices(operations={}),
        {
            "subprocess-command-target": {
                "name": "subprocess-command-target",
                "handler": "external-command-handler",
                "aliases": [],
                "flows": ["run-command"],
            }
        },
        registry,
    )

    with pytest.raises(PluginServiceDenied) as denied:
        handlers["subprocess-command-target"].run(
            "run-command",
            output_dir=tmp_path / "outputs",
        )

    assert denied.value.event["reason"] == "unauthorized_command"
    assert not command_marker.exists()
