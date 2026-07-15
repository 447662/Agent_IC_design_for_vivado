import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
CAPABILITIES_PATH = AGENT_DIR / "agent_capabilities.py"


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return ast.get_source_segment(source, item) or ""
    raise AssertionError("method not found: {}.{}".format(class_name, method_name))


def test_agent_capability_checks_are_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")

    assert CAPABILITIES_PATH.is_file()
    assert "import agent_capabilities as capabilities" in agent_source
    assert "capabilities.check_capability(" in agent_source
    assert "capabilities.check_cli_tool(" in agent_source
    assert "capabilities.check_mcp_server(" in agent_source
    assert "capabilities.get_install_guide(" in agent_source
    assert "capabilities.run_preflight(" in agent_source

    for method_name in (
        "check_capability",
        "run_preflight",
        "normalize_command",
        "check_cli_tool",
        "check_mcp_server",
        "get_install_guide",
    ):
        method_source = _class_method_source(AGENT_PATH, "DigitalICAgent", method_name)
        assert "subprocess" not in method_source
        assert "re.search" not in method_source
        assert method_source.count("return ") == 1
