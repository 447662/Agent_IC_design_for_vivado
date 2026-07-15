import ast
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime import agent as agent_module  # noqa: E402
from digital_ic_agent._runtime.agent_runtime import PluginServices, TargetPlugin  # noqa: E402
from digital_ic_agent._runtime.target_examples.async_fifo import (  # noqa: E402
    ASYNC_FIFO_SERVICE_NAMES,
    AsyncFifoPlugin,
)


def test_async_fifo_example_is_installed_by_plugin_not_core_agent_mixin():
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

    assert not any(name.startswith("agent_async_fifo") for name in imported_modules)
    assert not any(name.startswith("AsyncFifo") for name in base_names)

    agent = agent_module.DigitalICAgent()
    handler = agent.target_handlers["async-fifo"]
    plugin = handler.plugin

    assert handler.target_name == "async-fifo"
    assert callable(handler.run)
    assert "write_async_fifo_project" in handler.extension_methods
    assert isinstance(plugin, TargetPlugin)
    assert agent.target_plugins["async-fifo"] is plugin
    assert isinstance(plugin.services, PluginServices)
    assert not hasattr(plugin.services, "agent")
    assert not hasattr(plugin.services, "command_runner")
    assert not hasattr(plugin.services, "project_root")
    assert not hasattr(agent, "write_async_fifo_project")
    assert "write_async_fifo_project" not in plugin.services.operations
    assert set(plugin.services.operations) == set(ASYNC_FIFO_SERVICE_NAMES)
    assert not any(
        getattr(operation, "__self__", None) is agent
        for operation in plugin.services.operations.values()
    )


def test_async_fifo_plugin_facades_delegate_only_declared_services():
    calls = []

    def operation(name):
        def invoke(*args, **kwargs):
            calls.append((name, args, kwargs))
            return name

        return invoke

    plugin = AsyncFifoPlugin(
        "async-fifo",
        PluginServices(
            operations={
                name: operation(name)
                for name in ASYNC_FIFO_SERVICE_NAMES
            }
        ),
    )

    assert plugin.project_root == ROOT
    assert plugin.launch_vivado_gui("vivado") == "launch_vivado_gui"
    assert plugin.render_vivado_tclstore_bootstrap() == "render_vivado_tclstore_bootstrap"
    assert plugin.resolve_rwave_command() == "resolve_rwave_command"
    assert plugin.resolve_vivado_command() == "resolve_vivado_command"
    assert plugin.run_rwave_batch_json("trace.vcd", ["info"]) == "run_rwave_batch_json"
    assert plugin.run_vivado_batch("vivado", "run.tcl", ROOT) == "run_vivado_batch"
    assert (
        plugin.run_waveform_analyzer_json("info", "trace.vcd")
        == "run_waveform_analyzer_json"
    )
    assert plugin.write_target_dashboard(ROOT) == "write_target_dashboard"
    assert [name for name, _args, _kwargs in calls] == list(ASYNC_FIFO_SERVICE_NAMES)


def _async_fifo_test_services() -> PluginServices:
    return PluginServices(
        operations={
            name: (lambda *args, **kwargs: None)
            for name in ASYNC_FIFO_SERVICE_NAMES
        }
    )


def test_async_fifo_plugin_execute_dispatches_all_supported_flows(
    monkeypatch,
    tmp_path,
):
    plugin = AsyncFifoPlugin("async-fifo", _async_fifo_test_services())
    calls = []

    def record(name):
        def invoke(*args, **kwargs):
            calls.append((name, args, kwargs))
            return name

        return invoke

    monkeypatch.setattr(plugin, "write_async_fifo_project", record("generate"))
    monkeypatch.setattr(plugin, "run_async_fifo_vivado_sim", record("sim"))
    monkeypatch.setattr(plugin, "run_async_fifo_regression", record("regress"))
    monkeypatch.setattr(plugin, "run_async_fifo_uvm_smoke", record("uvm-smoke"))
    monkeypatch.setattr(plugin, "run_async_fifo_uvm_coverage", record("uvm-coverage"))
    monkeypatch.setattr(
        plugin,
        "run_async_fifo_uvm_random_regression",
        record("uvm-random-regress"),
    )
    monkeypatch.setattr(plugin, "analyze_async_fifo_vcd", record("analyze"))
    monkeypatch.setattr(plugin, "check_async_fifo_rtl", record("check"))
    monkeypatch.setattr(plugin, "open_async_fifo_project_gui", record("open-wave"))
    monkeypatch.setattr(
        plugin,
        "open_async_fifo_uvm_wave_gui",
        record("open-uvm-wave"),
    )

    assert plugin.execute(
        "generate-rtl",
        output_dir=tmp_path,
        data_width=16,
        addr_width=5,
    ) == "generate"
    assert plugin.execute(
        "sim-rtl",
        {"output_dir": tmp_path, "open_wave_gui": False},
    ) == "sim"
    assert plugin.execute("regress-rtl", output_dir=tmp_path) == "regress"
    assert plugin.execute(
        "uvm-smoke",
        output_dir=tmp_path,
        open_wave_gui=False,
    ) == "uvm-smoke"
    assert plugin.execute(
        "uvm-coverage",
        output_dir=tmp_path,
        coverage_threshold=90,
        coverage_percent=91,
        coverage_thresholds={"branch": 80},
    ) == "uvm-coverage"
    assert plugin.execute(
        "uvm-random-regress",
        output_dir=tmp_path,
        seeds=[1, 2],
    ) == "uvm-random-regress"
    assert plugin.execute(
        "analyze-rtl-vcd",
        output_dir=tmp_path,
        limit=7,
        waveform_backend="rwave",
    ) == "analyze"
    assert plugin.execute("check-rtl", output_dir=tmp_path) == "check"
    assert plugin.execute("open-wave", output_dir=tmp_path) == "open-wave"
    assert plugin.execute(
        "open-uvm-wave",
        output_dir=tmp_path,
        wave_kind="smoke",
    ) == "open-uvm-wave"

    assert [name for name, _args, _kwargs in calls] == [
        "generate",
        "sim",
        "regress",
        "uvm-smoke",
        "uvm-coverage",
        "uvm-random-regress",
        "analyze",
        "check",
        "open-wave",
        "open-uvm-wave",
    ]

    assert calls[0][1] == (tmp_path,)
    assert calls[0][2] == {"data_width": 16, "addr_width": 5}
    assert calls[4][2]["coverage_thresholds"] == {"branch": 80}
    assert calls[9][2] == {"wave_kind": "smoke"}


def test_async_fifo_plugin_rejects_wrong_target_and_unsupported_flow(tmp_path):
    plugin = AsyncFifoPlugin("async-fifo", _async_fifo_test_services())

    with pytest.raises(ValueError, match="cannot generate target"):
        plugin.generate_rtl_project("sync-fifo", output_dir=tmp_path)

    with pytest.raises(ValueError, match="does not support flow"):
        plugin.execute("unknown-flow", output_dir=tmp_path)
