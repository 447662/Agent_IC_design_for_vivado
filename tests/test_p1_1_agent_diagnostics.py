import ast
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any, get_type_hints


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
DIAGNOSTICS_PATH = AGENT_DIR / "agent_diagnostics.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from digital_ic_agent._runtime.capability_preflight import PreflightStatus  # noqa: E402


def _class_method_names(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, ast.FunctionDef)
            }
    raise AssertionError("class not found: {}".format(class_name))


def _function_node(path: Path, function_name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return node
    raise AssertionError("function not found: {}".format(function_name))


def _load_diagnostics_module():
    module_dir = str(DIAGNOSTICS_PATH.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(
        "agent_diagnostics_p1_3_contract",
        DIAGNOSTICS_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_agent_diagnostics_are_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")
    method_names = _class_method_names(AGENT_PATH, "DigitalICAgent")

    assert DIAGNOSTICS_PATH.is_file()
    assert (
        "from digital_ic_agent._runtime.agent_diagnostics import run_agent_diagnostic"
        in agent_source
    )
    assert "_diagnostic_status_text" not in method_names
    assert "_capability_diagnostic" not in method_names
    assert "def run_diagnostic" in agent_source


def test_agent_diagnostics_expose_typed_render_contracts():
    diagnostics = _load_diagnostics_module()

    status_hints = get_type_hints(diagnostics.diagnostic_status_text)
    capability_hints = get_type_hints(diagnostics.capability_diagnostic)
    lines_hints = get_type_hints(diagnostics.build_diagnostic_report_lines)
    emit_hints = get_type_hints(diagnostics.emit_diagnostic_lines)
    run_hints = get_type_hints(diagnostics.run_agent_diagnostic)

    assert status_hints["status"] is PreflightStatus
    assert status_hints["requirement"] is str
    assert status_hints["return"] is str
    assert capability_hints["capability"] is str
    assert capability_hints["flow"] == str | None
    assert capability_hints["return"] == tuple[PreflightStatus, str]
    assert lines_hints["flow"] == str | None
    assert lines_hints["return"] == tuple[bool, list[str]]
    assert emit_hints["lines"] == list[str]
    assert emit_hints["return"] is type(None)
    assert run_hints["flow"] == str | None
    assert run_hints["return"] is bool

    for hints in (status_hints, capability_hints, lines_hints, emit_hints, run_hints):
        assert Any not in hints.values()


def test_run_agent_diagnostic_uses_renderer_without_direct_print():
    diagnostics_source = DIAGNOSTICS_PATH.read_text(encoding="utf-8")
    assert "def build_diagnostic_report_lines(" in diagnostics_source

    run_node = _function_node(DIAGNOSTICS_PATH, "run_agent_diagnostic")
    direct_print_calls = [
        node
        for node in ast.walk(run_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    called_names = {
        node.func.id
        for node in ast.walk(run_node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert direct_print_calls == []
    assert "build_diagnostic_report_lines" in called_names
    assert "emit_diagnostic_lines" in called_names


def test_build_diagnostic_report_lines_preserves_cli_text():
    diagnostics = _load_diagnostics_module()

    class FakePreflight:
        @staticmethod
        def required_flows(capability: str):
            return ("sim-rtl",) if capability == "vivado" else ()

        @staticmethod
        def optional_flows(capability: str):
            return ("sim-rtl",) if capability == "synthpilot" else ()

    class FakeAgent:
        OK = "[OK]"
        WARN = "[WARN]"
        NO = "[NO]"
        preflight = FakePreflight()
        cli_tools = [{"name": "vivado"}]
        mcp_servers = {"synthpilot": {"installGuide": "install synthpilot"}}
        agent_config = {"skills": [{"name": "digital-ic-designer"}]}

        @staticmethod
        def check_capability(_capability: str) -> bool:
            return False

        @staticmethod
        def get_install_guide(_kind: str, name: str) -> str:
            return "install {}".format(name)

        @staticmethod
        def resolve_skill_path(_skill):
            return Path("missing-skill-file")

    all_ok, lines = diagnostics.build_diagnostic_report_lines(FakeAgent(), flow=None)

    assert all_ok is False
    rendered = "\n".join(lines)
    assert "Agent" in rendered
    assert "CLI" in rendered
    assert "vivado" in rendered
    assert "install vivado" in rendered
    assert "MCP" in rendered
    assert "synthpilot" in rendered
    assert "digital-ic-designer" in rendered


def test_run_agent_diagnostic_accepts_injected_output_stream():
    diagnostics = _load_diagnostics_module()

    class FakePreflight:
        @staticmethod
        def required_flows(_capability: str):
            return ()

        @staticmethod
        def optional_flows(_capability: str):
            return ()

    class FakeAgent:
        OK = "[OK]"
        WARN = "[WARN]"
        preflight = FakePreflight()
        cli_tools = []
        mcp_servers = {}
        agent_config = {"skills": []}

    output = io.StringIO()

    assert diagnostics.run_agent_diagnostic(FakeAgent(), output=output) is True
    assert "Agent" in output.getvalue()
    assert "=" * 60 in output.getvalue()
