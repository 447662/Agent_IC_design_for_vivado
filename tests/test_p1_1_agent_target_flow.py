import ast
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any, get_type_hints


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
TARGET_FLOWS_PATH = AGENT_DIR / "target_flows.py"
LEGACY_FACADES_PATH = AGENT_DIR / "agent_legacy_target_facades.py"


TARGET_FLOW_METHODS = {
    "build_target_registry",
    "load_target_registry",
    "list_targets",
    "get_target",
    "print_targets",
    "build_target_handlers",
    "validate_target_handlers",
    "run_target_flow",
}

LEGACY_TARGET_FACADE_METHODS = {
    "open_sync_fifo_project_gui",
    "run_sync_fifo_vivado_sim",
    "analyze_sync_fifo_vcd",
    "collect_sync_fifo_vcd_analysis",
    "open_round_robin_arbiter_project_gui",
    "run_round_robin_arbiter_vivado_sim",
    "analyze_round_robin_arbiter_vcd",
    "collect_round_robin_arbiter_vcd_analysis",
}

LEGACY_MODULE_EXPORTS = {
    "get_vcd_analyzer_path": "resolve_vcd_analyzer_path",
    "get_rwave_source_dir": "resolve_rwave_source_dir",
    "get_rwave_command": "resolve_rwave_command",
    "run_rtl_project_checks": "check_rtl_project",
}


def _class_methods(path: Path, class_name: str) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            result = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    end_lineno = getattr(item, "end_lineno", item.lineno) or item.lineno
                    result[item.name] = end_lineno - item.lineno + 1
            return result
    raise AssertionError("class not found: {}".format(class_name))


def _function_node(path: Path, function_name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return node
    raise AssertionError("function not found: {}".format(function_name))


def _load_target_flows_module():
    module_dir = str(TARGET_FLOWS_PATH.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(
        "target_flows_p1_2_contract",
        TARGET_FLOWS_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_target_flow_orchestration_is_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")
    target_flow_source = TARGET_FLOWS_PATH.read_text(encoding="utf-8")
    method_lengths = _class_methods(AGENT_PATH, "DigitalICAgent")

    assert "run_target_flow as run_target_flow_operation" in agent_source
    assert "validate_target_handlers as validate_target_handlers_operation" in agent_source
    assert "def run_target_flow(" in target_flow_source
    assert "def validate_target_handlers(" in target_flow_source
    assert "Target handler registry mismatch" not in agent_source
    assert "flow returned a false result" not in agent_source
    assert "Digital IC Agent registered targets" not in agent_source
    for method_name in TARGET_FLOW_METHODS:
        assert method_lengths[method_name] <= 20, method_name


def test_target_flow_public_entrypoints_expose_typed_contracts():
    target_flows = _load_target_flows_module()

    plugin_hints = get_type_hints(target_flows.build_plugin_services)
    handlers_hints = get_type_hints(target_flows.build_target_handlers)
    registry_hints = get_type_hints(target_flows.build_target_registry)
    validation_hints = get_type_hints(target_flows.validate_target_handlers)
    render_hints = get_type_hints(target_flows.render_targets)
    print_hints = get_type_hints(target_flows.print_targets)
    list_hints = get_type_hints(target_flows.list_targets)
    get_hints = get_type_hints(target_flows.get_target)
    run_hints = get_type_hints(target_flows.run_target_flow)

    assert plugin_hints["return"].__name__ == "PluginServices"
    assert handlers_hints["return"] == dict[str, target_flows.TargetHandlerLike]
    assert registry_hints["return"] == target_flows.TargetMap
    assert validation_hints["return"] is bool
    assert render_hints["return"] is str
    assert print_hints["return"] is bool
    assert list_hints["return"] == list[target_flows.TargetInfo]
    assert get_hints["target"] is str
    assert get_hints["return"] is target_flows.TargetInfo
    assert run_hints["target"] is str
    assert run_hints["flow"] is str
    assert run_hints["kwargs"] is object
    assert run_hints["return"] is object

    for hints in (
        plugin_hints,
        handlers_hints,
        registry_hints,
        validation_hints,
        render_hints,
        print_hints,
        list_hints,
        get_hints,
        run_hints,
    ):
        assert Any not in hints.values()


def test_print_targets_renders_through_helper_without_direct_print():
    print_targets_node = _function_node(TARGET_FLOWS_PATH, "print_targets")
    direct_print_calls = [
        node
        for node in ast.walk(print_targets_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]

    assert direct_print_calls == []

    called_names = {
        node.func.id
        for node in ast.walk(print_targets_node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "render_targets" in called_names


def test_render_targets_preserves_cli_list_target_text():
    target_flows = _load_target_flows_module()
    targets = [
        {
            "name": "async-fifo",
            "display_name": "Asynchronous FIFO",
            "design_family": "fifo",
            "aliases": ["async_fifo", "afifo"],
            "flows": ["generate-rtl", "uvm-coverage"],
            "description": "CDC FIFO",
        },
        {
            "name": "minimal",
            "display_name": "Minimal Target",
            "design_family": "demo",
        },
    ]

    assert target_flows.render_targets(targets) == (
        "Digital IC Agent registered targets\n"
        "============================================================\n"
        "async-fifo (Asynchronous FIFO)\n"
        "  family: fifo\n"
        "  aliases: async_fifo, afifo\n"
        "  flows: generate-rtl, uvm-coverage\n"
        "  note: CDC FIFO\n"
        "minimal (Minimal Target)\n"
        "  family: demo\n"
        "  aliases: -\n"
        "  flows: \n"
        "  note: \n"
    )


def test_print_targets_accepts_injected_output_stream():
    target_flows = _load_target_flows_module()

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                    "flows": ["generate-rtl"],
                },
            ]

    output = io.StringIO()

    assert target_flows.print_targets(FakeAgent(), output=output) is True
    assert "sync-fifo (Synchronous FIFO)" in output.getvalue()
    assert output.getvalue().endswith("  note: \n")


def test_legacy_target_facades_are_thin_delegates_without_mixin_inheritance():
    tree = ast.parse(AGENT_PATH.read_text(encoding="utf-8"))
    legacy_tree = ast.parse(LEGACY_FACADES_PATH.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "DigitalICAgent"
    )
    base_names = {
        base.id
        for base in class_node.bases
        if isinstance(base, ast.Name)
    }

    assert "SyncFifoMixin" not in base_names
    assert "RoundRobinArbiterMixin" not in base_names

    install_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "install_legacy_target_facades"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "legacy_target_facades"
    ]
    assert len(install_calls) == 1
    assert isinstance(install_calls[0].args[0], ast.Name)
    assert install_calls[0].args[0].id == "DigitalICAgent"

    install_function = next(
        node
        for node in ast.walk(legacy_tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "install_legacy_target_facades"
    )
    methods_assignment = next(
        item
        for item in install_function.body
        if isinstance(item, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "methods"
            for target in item.targets
        )
    )
    assert isinstance(methods_assignment.value, ast.Dict)
    installed_methods = {
        key.value
        for key in methods_assignment.value.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert installed_methods >= LEGACY_TARGET_FACADE_METHODS


def test_legacy_module_exports_are_reexported_from_split_modules():
    tree = ast.parse(AGENT_PATH.read_text(encoding="utf-8"))
    assignments = {}
    for item in tree.body:
        if isinstance(item, ast.Assign) and len(item.targets) == 1:
            target = item.targets[0]
            if isinstance(target, ast.Name) and isinstance(item.value, ast.Attribute):
                assignments[target.id] = item.value

    for exported_name, source_name in LEGACY_MODULE_EXPORTS.items():
        value = assignments[exported_name]
        assert isinstance(value.value, ast.Name)
        assert value.value.id in {"agent_waveform", "target_checks"}
        assert value.attr == source_name
