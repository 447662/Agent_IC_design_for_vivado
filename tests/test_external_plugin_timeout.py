import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent_errors import ToolExecutionError  # noqa: E402
from digital_ic_agent._runtime.agent_runtime import PluginServices  # noqa: E402
from digital_ic_agent._runtime.capability_preflight import PreflightReport  # noqa: E402
from digital_ic_agent._runtime import target_plugins  # noqa: E402
from digital_ic_agent._runtime.target_plugins import (  # noqa: E402
    TargetHandlerRegistry,
    build_target_handlers,
    discover_target_handler_plugins,
)
from digital_ic_agent._runtime.target_flows import run_target_flow  # noqa: E402


def _external_handler(tmp_path: Path, body: str):
    package_dir = tmp_path / "timeout_plugins"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "hung.py").write_text(body, encoding="utf-8")
    manifest_path = tmp_path / "external_plugins.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trust": "trusted-local",
                "plugins": [
                    {
                        "module": "timeout_plugins.hung",
                        "handler_id": "hung-handler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    registry = discover_target_handler_plugins(
        TargetHandlerRegistry(),
        "timeout_plugins",
        search_path=tmp_path,
        manifest_path=manifest_path,
        allowed_modules=("timeout_plugins.hung",),
    )
    handlers = build_target_handlers(
        PluginServices(operations={}),
        {
            "hung-target": {
                "name": "hung-target",
                "handler": "hung-handler",
                "aliases": [],
                "flows": ["generate-rtl"],
            }
        },
        registry,
    )
    return handlers["hung-target"]


def test_external_plugin_subprocess_passes_timeout_and_raises_structured_error(
    tmp_path,
    monkeypatch,
):
    handler = _external_handler(
        tmp_path,
        "from agent_runtime import TargetHandler\n"
        "HANDLER_ID = 'hung-handler'\n"
        "def create_handler(_services, _target):\n"
        "    return TargetHandler('hung-target', {'generate-rtl': lambda **_: True})\n",
    )

    def timeout(*args: object, **kwargs: object):
        assert kwargs["timeout"] == target_plugins.EXTERNAL_PLUGIN_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(target_plugins.subprocess, "run", timeout)

    with pytest.raises(ToolExecutionError) as raised:
        handler.run("generate-rtl", output_dir=tmp_path / "outputs")

    payload = raised.value.as_payload()
    assert payload["stage"] == "external_plugin"
    assert payload["details"]["reason"] == "timeout"
    assert payload["details"]["flow"] == "generate-rtl"
    assert payload["details"]["timeout_seconds"] > 0


def test_external_plugin_dead_loop_is_terminated_by_timeout(tmp_path, monkeypatch):
    handler = _external_handler(
        tmp_path,
        "from agent_runtime import TargetHandler\n"
        "HANDLER_ID = 'hung-handler'\n"
        "def hang(**_kwargs):\n"
        "    while True:\n"
        "        pass\n"
        "def create_handler(_services, _target):\n"
        "    return TargetHandler('hung-target', {'generate-rtl': hang})\n",
    )
    monkeypatch.setattr(target_plugins, "EXTERNAL_PLUGIN_TIMEOUT_SECONDS", 0.2)

    started = time.perf_counter()
    with pytest.raises(ToolExecutionError) as raised:
        handler.run("generate-rtl", output_dir=tmp_path / "outputs")

    assert time.perf_counter() - started < 5
    assert raised.value.as_payload()["details"]["reason"] == "timeout"


def test_target_flow_preserves_structured_external_plugin_timeout(
    tmp_path,
    monkeypatch,
):
    handler = _external_handler(
        tmp_path,
        "from agent_runtime import TargetHandler\n"
        "HANDLER_ID = 'hung-handler'\n"
        "def hang(**_kwargs):\n"
        "    while True:\n"
        "        pass\n"
        "def create_handler(_services, _target):\n"
        "    return TargetHandler('hung-target', {'generate-rtl': hang})\n",
    )
    monkeypatch.setattr(target_plugins, "EXTERNAL_PLUGIN_TIMEOUT_SECONDS", 0.2)

    class FlowAgent:
        targets = {
            "hung-target": {
                "name": "hung-target",
                "flows": ["generate-rtl"],
            }
        }
        target_handlers = {"hung-target": handler}

        def __init__(self):
            self.errors: list[ToolExecutionError] = []

        @staticmethod
        def normalize_rtl_target(target: str) -> str:
            return target

        @staticmethod
        def run_preflight(flow: str) -> PreflightReport:
            return PreflightReport(flow, (), (), (), ())

        def record_artifact_run(self, *_args: object, **kwargs: object) -> Path:
            error = kwargs.get("error")
            if isinstance(error, ToolExecutionError):
                self.errors.append(error)
            return tmp_path / "artifacts.json"

    agent = FlowAgent()
    with pytest.raises(ToolExecutionError) as raised:
        run_target_flow(
            agent,
            "hung-target",
            "generate-rtl",
            output_dir=tmp_path / "outputs",
        )

    assert raised.value.as_payload()["details"]["reason"] == "timeout"
    assert agent.errors[-1].as_payload()["details"]["reason"] == "timeout"
