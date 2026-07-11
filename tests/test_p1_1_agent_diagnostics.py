import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
DIAGNOSTICS_PATH = AGENT_DIR / "agent_diagnostics.py"


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


def test_agent_diagnostics_are_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")
    method_names = _class_method_names(AGENT_PATH, "DigitalICAgent")

    assert DIAGNOSTICS_PATH.is_file()
    assert "from agent_diagnostics import run_agent_diagnostic" in agent_source
    assert "_diagnostic_status_text" not in method_names
    assert "_capability_diagnostic" not in method_names
    assert "def run_diagnostic" in agent_source

