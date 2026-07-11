import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
DESIGN_SPEC_PATH = AGENT_DIR / "agent_design_spec.py"


def _class_method_length(path: Path, class_name: str, method_name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    end_lineno = getattr(item, "end_lineno", item.lineno) or item.lineno
                    return end_lineno - item.lineno + 1
    raise AssertionError("method not found: {}.{}".format(class_name, method_name))


def test_default_design_spec_rendering_is_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")

    assert DESIGN_SPEC_PATH.is_file()
    assert "from agent_design_spec import" in agent_source
    assert "render_default_design_spec" in agent_source
    assert "_build_default_project_slug" in agent_source
    assert _class_method_length(AGENT_PATH, "DigitalICAgent", "render_design_spec") <= 20
    assert _class_method_length(AGENT_PATH, "DigitalICAgent", "generate_design_spec") <= 20
    assert "# 数字 IC 设计说明模板" not in agent_source

