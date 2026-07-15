from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
BOOTSTRAP_PATH = AGENT_DIR / "agent_bootstrap.py"


def test_runtime_uses_package_imports_without_dynamic_bootstrap():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")

    assert not BOOTSTRAP_PATH.exists()
    assert "load_local_modules" not in agent_source
    assert "LOCAL_MODULES" not in agent_source
    assert "HANDLER_MODULES" not in agent_source
    assert "ADAPTER_MODULES" not in agent_source
    assert "importlib.util" not in agent_source
    assert "digital_ic_agent._runtime" in agent_source
