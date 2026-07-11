import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
TARGET_FLOWS_PATH = AGENT_DIR / "target_flows.py"


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
