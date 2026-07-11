import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
ENTRYPOINT_PATH = AGENT_DIR / "agent_entrypoint.py"
DISPATCH_PATH = AGENT_DIR / "agent_cli_dispatch.py"


def _function_length(path: Path, function_name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", node.lineno) or node.lineno
            return end_lineno - node.lineno + 1
    raise AssertionError("function not found: {}".format(function_name))


def test_cli_command_dispatch_is_split_from_entrypoint():
    entrypoint_source = ENTRYPOINT_PATH.read_text(encoding="utf-8")

    assert DISPATCH_PATH.is_file()
    assert "from agent_cli_dispatch import dispatch_cli_command" in entrypoint_source
    assert _function_length(ENTRYPOINT_PATH, "run_cli") <= 100

