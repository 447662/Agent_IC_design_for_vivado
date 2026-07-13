import builtins
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
PLUGIN_GUARD_RUNNER_PATH = AGENT_DIR / "plugin_guard_runner.py"
TARGET_PLUGINS_PATH = AGENT_DIR / "target_plugins.py"
MISSING_ATTRIBUTE = object()
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from agent_runtime import PluginServiceDenied, PluginServices, TargetHandler  # noqa: E402
import plugin_guard_runner as guard_runner  # noqa: E402
from target_plugins import (  # noqa: E402
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


def test_external_plugin_guard_is_a_standalone_module():
    source = TARGET_PLUGINS_PATH.read_text(encoding="utf-8")

    assert PLUGIN_GUARD_RUNNER_PATH.is_file()
    assert "plugin_guard_runner.py" in source
    assert '"-c"' not in source
    assert "script = (" not in source


def _guard_payload(tmp_path: Path) -> guard_runner.GuardPayload:
    return {
        "module": "guard_test_plugin",
        "module_path": str(tmp_path / "guard_test_plugin.py"),
        "agent_runtime_path": str(tmp_path / "agent_runtime.py"),
        "output_root": str(tmp_path / "outputs"),
        "handler_id": "guard-test-handler",
        "flow": "generate-rtl",
        "target": {"name": "guard-test-target"},
        "kwargs": {"output_dir": str(tmp_path / "outputs")},
    }


def test_plugin_guard_validates_payload_and_denies_path_escape(tmp_path, capsys):
    payload = _guard_payload(tmp_path)
    parsed = guard_runner.read_payload(io.StringIO(json.dumps(payload)))
    context = guard_runner.build_context(parsed)

    assert context.output_root == (tmp_path / "outputs").resolve()
    assert Path(payload["module_path"]).resolve() in context.allowed_reads
    guard_runner.guard_path(context, tmp_path / "outputs" / "result.txt", "w")

    with pytest.raises(SystemExit) as denied:
        guard_runner.guard_path(context, tmp_path / "escape.txt", "w")
    assert denied.value.code == 13
    event = json.loads(capsys.readouterr().out)
    assert event["event"]["reason"] == "output_dir_outside_allowed_root"

    with pytest.raises(ValueError, match="must be an object"):
        guard_runner.read_payload(io.StringIO("[]"))

    invalid_payloads = (
        ({**payload, "module": ""}, "non-empty string"),
        ({**payload, "target": []}, "target must be an object"),
        ({**payload, "kwargs": {"limit": 10}}, "kwargs must contain string values"),
    )
    for invalid_payload, message in invalid_payloads:
        with pytest.raises(ValueError, match=message):
            guard_runner.read_payload(io.StringIO(json.dumps(invalid_payload)))


def test_plugin_guard_denies_commands_without_executing_them(capsys):
    subprocess_names = ("run", "Popen", "call", "check_call", "check_output")
    os_names = (
        "system",
        "popen",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
    )
    original_subprocess = {name: getattr(subprocess, name) for name in subprocess_names}
    original_os = {name: getattr(os, name, MISSING_ATTRIBUTE) for name in os_names}
    try:
        guard_runner.install_command_guards()
        with pytest.raises(SystemExit) as denied:
            subprocess.run(["unauthorized-command"], check=False)
        assert denied.value.code == 13
    finally:
        for name, operation in original_subprocess.items():
            setattr(subprocess, name, operation)
        for name, operation in original_os.items():
            if operation is MISSING_ATTRIBUTE:
                delattr(os, name)
            else:
                setattr(os, name, operation)

    event = json.loads(capsys.readouterr().out)
    assert event["event"]["reason"] == "unauthorized_command"


def test_plugin_guard_runs_allowed_module_with_guards_installed(tmp_path):
    payload = _guard_payload(tmp_path)
    output_root = Path(payload["output_root"])
    output_root.mkdir()
    Path(payload["agent_runtime_path"]).write_text(
        "\n".join(
            [
                "class PluginServices:",
                "    def __init__(self, operations):",
                "        self.operations = operations",
            ]
        ),
        encoding="utf-8",
    )
    Path(payload["module_path"]).write_text(
        "\n".join(
            [
                'HANDLER_ID = "guard-test-handler"',
                "def create_handler(_services, target):",
                "    class Handler:",
                "        def run(self, flow, **kwargs):",
                "            return target['name'] + ':' + flow + ':' + kwargs['output_dir']",
                "    return Handler()",
            ]
        ),
        encoding="utf-8",
    )

    subprocess_names = ("run", "Popen", "call", "check_call", "check_output")
    os_names = (
        "system",
        "popen",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
    )
    original_subprocess = {name: getattr(subprocess, name) for name in subprocess_names}
    original_os = {name: getattr(os, name, MISSING_ATTRIBUTE) for name in os_names}
    original_open = builtins.open
    original_path_open = Path.open
    previous_runtime = sys.modules.get("agent_runtime")
    try:
        result = guard_runner.run(payload)
    finally:
        setattr(builtins, "open", original_open)
        setattr(Path, "open", original_path_open)
        for name, operation in original_subprocess.items():
            setattr(subprocess, name, operation)
        for name, operation in original_os.items():
            if operation is MISSING_ATTRIBUTE:
                delattr(os, name)
            else:
                setattr(os, name, operation)
        if previous_runtime is None:
            sys.modules.pop("agent_runtime", None)
        else:
            sys.modules["agent_runtime"] = previous_runtime
        sys.modules.pop(payload["module"], None)

    assert result == "guard-test-target:generate-rtl:{}".format(output_root)


def test_plugin_guard_main_emits_structured_result(monkeypatch, capsys, tmp_path):
    payload = _guard_payload(tmp_path)
    monkeypatch.setattr(guard_runner, "read_payload", lambda: payload)
    monkeypatch.setattr(guard_runner, "run", lambda _payload: "ok-result")

    assert guard_runner.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "ok",
        "result": "ok-result",
    }


def test_plugin_services_expose_only_explicit_operations():
    services = PluginServices(
        operations={"sample_action": lambda: "first"},
    )

    assert services.call("sample_action") == "first"
    assert not hasattr(services, "agent")
    assert not hasattr(services, "command_runner")
    assert not hasattr(services, "project_root")
    assert services.denials == ()

    with pytest.raises(PluginServiceDenied) as denied:
        services.call("undeclared_action")
    assert denied.value.event == {
        "event": "plugin_service_denied",
        "service": "undeclared_action",
        "reason": "undeclared_service",
    }
    assert services.denials == (denied.value.event,)


def test_plugin_services_have_explicit_service_facades():
    services = PluginServices(
        operations={"sample_action": lambda: "first"},
    )

    assert hasattr(services, "vivado")
    assert hasattr(services, "waveform")
    assert hasattr(services, "artifacts")
    assert type(services.vivado).__name__ == "VivadoService"
    assert type(services.waveform).__name__ == "WaveformService"
    assert type(services.artifacts).__name__ == "ArtifactService"
    assert services.vivado.call("sample_action") == "first"
    assert services.waveform.call("sample_action") == "first"
    assert services.artifacts.call("sample_action") == "first"


def test_plugin_service_rejects_output_dir_escape_during_target_run(tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    calls = []
    services = PluginServices(
        operations={
            "write_allowed": lambda output_dir: calls.append(Path(output_dir)),
            "write_escape": lambda output_dir: calls.append(Path(output_dir)),
        },
    )
    handler = TargetHandler(
        "malicious-target",
        {
            "generate-rtl": lambda output_dir: services.call(
                "write_escape",
                output_dir=Path(output_dir).parent / "escape",
            )
        },
    )

    with pytest.raises(PluginServiceDenied) as denied:
        handler.run("generate-rtl", output_dir=allowed_root)

    assert denied.value.event["event"] == "plugin_service_denied"
    assert denied.value.event["service"] == "write_escape"
    assert denied.value.event["reason"] == "output_dir_outside_allowed_root"
    assert calls == []
    assert services.denials == (denied.value.event,)

    safe_handler = TargetHandler(
        "safe-target",
        {
            "generate-rtl": lambda output_dir: services.call(
                "write_allowed",
                output_dir=Path(output_dir) / "safe-child",
            )
        },
    )
    safe_handler.run("generate-rtl", output_dir=allowed_root)
    assert calls == [allowed_root / "safe-child"]


def test_plugin_service_allows_vivado_executable_and_checks_batch_cwd(tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_sim = allowed_root / "async-fifo" / "sim"
    calls = []
    vivado_executable = Path("D:/vivado/2025.2/Vivado/bin/vivado.bat")
    services = PluginServices(
        operations={
            "run_vivado_batch": (
                lambda command, script_name, cwd, **_kwargs: calls.append(
                    (Path(command), script_name, Path(cwd))
                )
            )
        },
    )
    handler = TargetHandler(
        "async-fifo",
        {
            "sim-rtl": lambda output_dir: services.call(
                "run_vivado_batch",
                vivado_executable,
                "run_vivado_async_fifo.tcl",
                Path(output_dir) / "async-fifo" / "sim",
            )
        },
    )

    handler.run("sim-rtl", output_dir=allowed_root)
    assert calls == [
        (vivado_executable, "run_vivado_async_fifo.tcl", allowed_sim)
    ]

    escape_handler = TargetHandler(
        "async-fifo",
        {
            "sim-rtl": lambda output_dir: services.call(
                "run_vivado_batch",
                vivado_executable,
                "run_vivado_async_fifo.tcl",
                Path(output_dir).parent / "escape",
            )
        },
    )
    with pytest.raises(PluginServiceDenied) as denied:
        escape_handler.run("sim-rtl", output_dir=allowed_root)
    assert denied.value.event["service"] == "run_vivado_batch"
    assert denied.value.event["reason"] == "output_dir_outside_allowed_root"


def test_target_plugin_discovery_search_path_does_not_mutate_sys_path(tmp_path):
    _write_plugin_package(
        tmp_path,
        "isolated_target_plugins",
        {"sample": ("isolated-handler", ("generate-rtl",))},
    )
    registry = TargetHandlerRegistry()
    before = tuple(sys.path)

    discover_target_handler_plugins(
        registry,
        "isolated_target_plugins",
        search_path=tmp_path,
    )

    assert registry.ids() == ("isolated-handler",)
    assert tuple(sys.path) == before


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
    assert handlers["subprocess-target"].plugin["isolation"] == "subprocess"


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
