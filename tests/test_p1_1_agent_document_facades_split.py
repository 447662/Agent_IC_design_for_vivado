import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
DOCUMENT_FACADES_PATH = AGENT_DIR / "agent_document_facades.py"


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return ast.get_source_segment(source, item) or ""
    raise AssertionError("method not found: {}.{}".format(class_name, method_name))


def test_agent_document_facades_are_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")

    assert DOCUMENT_FACADES_PATH.is_file()
    assert "import agent_document_facades as document_facades" in agent_source
    assert "document_facades.build_project_slug(" in agent_source
    assert "document_facades.render_design_spec(" in agent_source
    assert "document_facades.generate_design_spec(" in agent_source
    assert "document_facades.render_markdown_document_html(" in agent_source

    for method_name in (
        "build_project_slug",
        "render_design_spec",
        "generate_design_spec",
        "render_markdown_document_html",
    ):
        method_source = _class_method_source(AGENT_PATH, "DigitalICAgent", method_name)
        assert "render_default_design_spec(" not in method_source
        assert "write_default_design_spec(" not in method_source
        assert "render_markdown_html_document(" not in method_source
        assert method_source.count("return ") == 1
