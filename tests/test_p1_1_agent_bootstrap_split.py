from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
BOOTSTRAP_PATH = AGENT_DIR / "agent_bootstrap.py"


def test_agent_local_module_bootstrap_is_split_from_core_agent():
    agent_source = AGENT_PATH.read_text(encoding="utf-8")
    bootstrap_source = BOOTSTRAP_PATH.read_text(encoding="utf-8")

    assert BOOTSTRAP_PATH.is_file()
    assert "load_local_modules" in agent_source
    assert "LOCAL_MODULES" not in agent_source
    assert "HANDLER_MODULES" not in agent_source
    assert "ADAPTER_MODULES" not in agent_source
    assert "def _load_local_module" not in agent_source

    assert "LOCAL_MODULES" in bootstrap_source
    assert "ADAPTER_MODULES" in bootstrap_source
    assert "HANDLER_MODULES" in bootstrap_source
    assert "target_examples.async_fifo" in bootstrap_source
