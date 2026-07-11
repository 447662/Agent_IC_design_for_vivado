import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
ENTRYPOINT_PATH = AGENT_DIR / "agent_entrypoint.py"
DISPATCH_PATH = AGENT_DIR / "agent_cli_dispatch.py"
CLI_PATH = AGENT_DIR / "agent_cli.py"
CLI_PARSER_PATH = AGENT_DIR / "agent_cli_parser.py"


def _function_length(path: Path, function_name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", node.lineno) or node.lineno
            return end_lineno - node.lineno + 1
    raise AssertionError("function not found: {}".format(function_name))


def _oversized_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    oversized = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            end_lineno = getattr(node, "end_lineno", node.lineno) or node.lineno
            length = end_lineno - node.lineno + 1
            if length > 100:
                oversized.append("{}:{} lines={}".format(path.name, node.name, length))
    return oversized


def test_cli_command_dispatch_is_split_from_entrypoint():
    entrypoint_source = ENTRYPOINT_PATH.read_text(encoding="utf-8")

    assert DISPATCH_PATH.is_file()
    assert "from agent_cli_dispatch import dispatch_cli_command" in entrypoint_source
    assert _function_length(ENTRYPOINT_PATH, "run_cli") <= 100


def test_cli_dispatch_functions_stay_within_p1_1_size_budget():
    assert not _oversized_functions(ENTRYPOINT_PATH)
    assert not _oversized_functions(DISPATCH_PATH)


def test_cli_parser_construction_is_split_from_parse_args():
    cli_source = CLI_PATH.read_text(encoding="utf-8")

    assert CLI_PARSER_PATH.is_file()
    assert "from agent_cli_parser import build_parser" in cli_source
    assert _function_length(CLI_PATH, "parse_args") <= 100
