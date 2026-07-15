import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
WAVEFORM_PATH = AGENT_DIR / "agent_waveform.py"


WAVEFORM_ANALYSIS_METHODS = {
    "analyze_waveform",
    "analyze_vcd",
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


def test_waveform_analysis_flows_are_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")
    waveform_source = WAVEFORM_PATH.read_text(encoding="utf-8")
    method_lengths = _class_methods(AGENT_PATH, "DigitalICAgent")

    assert "analyze_waveform as analyze_waveform_flow" in agent_source
    assert "def analyze_waveform(" in waveform_source
    assert "def analyze_vcd(" in waveform_source
    assert "Unsupported waveform format" not in agent_source
    assert "Waveform file not found" not in agent_source
    assert "VCD file not found" not in agent_source
    assert "Backend:" not in agent_source
    for method_name in WAVEFORM_ANALYSIS_METHODS:
        assert method_lengths[method_name] <= 20, method_name
