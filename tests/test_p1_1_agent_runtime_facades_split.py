import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
RUNTIME_FACADES_PATH = AGENT_DIR / "agent_runtime_facades.py"


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return ast.get_source_segment(source, item) or ""
    raise AssertionError("method not found: {}.{}".format(class_name, method_name))


def test_agent_runtime_facades_are_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")

    assert RUNTIME_FACADES_PATH.is_file()
    assert "from agent_runtime_facades import" in agent_source
    assert "refresh_project_overview as refresh_project_overview_operation" in agent_source
    assert "record_artifact_run as record_artifact_run_operation" in agent_source
    assert "resolve_rwave_command as resolve_rwave_command_operation" in agent_source
    assert "check_rtl_project as check_rtl_project_operation" in agent_source
    assert "run_uvm_coverage as run_uvm_coverage_operation" in agent_source

    for method_name in (
        "refresh_project_overview",
        "record_artifact_run",
        "resolve_vcd_analyzer_path",
        "resolve_rwave_source_dir",
        "resolve_rwave_command",
        "analyze_waveform",
        "analyze_vcd",
        "check_rtl_project",
        "open_rtl_wave",
        "write_smoke_loop_vcd",
        "run_smoke_loop",
        "detect_simulator",
        "write_sim_smoke_sources",
        "run_icarus_sim_smoke",
        "write_vivado_sim_script",
        "open_vivado_wave_gui",
        "run_vivado_sim_smoke",
        "run_sim_smoke",
        "normalize_rtl_target",
        "render_vivado_tclstore_bootstrap",
        "generate_rtl_project",
        "run_rtl_sim",
        "run_uvm_smoke",
        "run_uvm_coverage",
        "run_uvm_random_regression",
        "open_uvm_wave",
        "regress_rtl",
    ):
        method_source = _class_method_source(AGENT_PATH, "DigitalICAgent", method_name)
        assert "print(" not in method_source
        assert method_source.count("return ") == 1
