import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
SKILL_EXECUTION_PATH = AGENT_DIR / "agent_skill_execution.py"


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return ast.get_source_segment(source, item) or ""
    raise AssertionError("method not found: {}.{}".format(class_name, method_name))


def test_agent_skill_execution_handlers_are_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")

    assert SKILL_EXECUTION_PATH.is_file()
    assert "import agent_skill_execution as skill_execution" in agent_source
    assert "skill_execution.build_skill_action_handlers(" in agent_source
    assert "skill_execution.skill_result(" in agent_source
    assert "skill_execution.write_skill_execution_brief(" in agent_source
    assert "skill_execution.execute_design_document_skill(" in agent_source
    assert "skill_execution.execute_rtl_implementation_skill(" in agent_source
    assert "skill_execution.execute_verification_plan_skill(" in agent_source

    for method_name in (
        "build_skill_action_handlers",
        "_skill_result",
        "_write_skill_execution_brief",
        "execute_design_document_skill",
        "execute_rtl_implementation_skill",
        "execute_verification_plan_skill",
    ):
        method_source = _class_method_source(AGENT_PATH, "DigitalICAgent", method_name)
        assert "SkillExecutionResult(" not in method_source
        assert "write_text(" not in method_source
        assert method_source.count("return ") == 1
