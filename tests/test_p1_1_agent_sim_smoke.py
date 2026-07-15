import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
SIM_SMOKE_PATH = AGENT_DIR / "agent_sim_smoke.py"


SIM_SMOKE_METHODS = {
    "write_smoke_loop_vcd",
    "run_smoke_loop",
    "detect_simulator",
    "write_sim_smoke_sources",
    "run_icarus_sim_smoke",
    "write_vivado_sim_script",
    "open_vivado_wave_gui",
    "run_vivado_sim_smoke",
    "run_sim_smoke",
    "render_vivado_tclstore_bootstrap",
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


def test_sim_smoke_flows_are_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")
    method_lengths = _class_methods(AGENT_PATH, "DigitalICAgent")

    assert SIM_SMOKE_PATH.is_file()
    assert "from digital_ic_agent._runtime.agent_sim_smoke import" in agent_source
    assert "run_sim_smoke as run_sim_smoke_flow" in agent_source
    assert "module handshake_passthrough" not in agent_source
    assert "DigitalICAgent built-in handshake smoke loop" not in agent_source
    for method_name in SIM_SMOKE_METHODS:
        assert method_lengths[method_name] <= 20, method_name
