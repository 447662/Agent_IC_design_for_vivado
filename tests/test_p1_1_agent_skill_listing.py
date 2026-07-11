import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
SKILL_LISTING_PATH = AGENT_DIR / "agent_skill_listing.py"


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return ast.get_source_segment(source, item) or ""
    raise AssertionError("method not found: {}.{}".format(class_name, method_name))


def test_agent_skill_listing_is_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")

    assert SKILL_LISTING_PATH.is_file()
    assert "from agent_skill_listing import" in agent_source
    assert "list_skills as list_skills_operation" in agent_source
    assert "recommend_skills as recommend_skills_operation" in agent_source
    assert "resolve_skill_path as resolve_skill_path_operation" in agent_source

    for method_name in ("list_skills", "recommend_skills", "resolve_skill_path"):
        method_source = _class_method_source(AGENT_PATH, "DigitalICAgent", method_name)
        assert "print(" not in method_source
        assert method_source.count("return ") == 1

