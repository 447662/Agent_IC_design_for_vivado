import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
WORKFLOW_PATH = AGENT_DIR / "agent_workflow.py"


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return ast.get_source_segment(source, item) or ""
    raise AssertionError("method not found: {}.{}".format(class_name, method_name))


def test_agent_default_workflow_is_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")

    assert WORKFLOW_PATH.is_file()
    assert "import agent_workflow as workflow" in agent_source
    assert "workflow.execute_workflow(" in agent_source

    method_source = _class_method_source(AGENT_PATH, "DigitalICAgent", "execute_workflow")
    assert "AgentRequest(" not in method_source
    assert "agent_execution_engine.run" not in method_source
    assert "print(" not in method_source
    assert method_source.count("return ") == 1
