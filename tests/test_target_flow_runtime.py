import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent import DigitalICAgent  # noqa: E402


def test_target_flow_preflight_blocks_before_handler_execution(
    tmp_path,
    monkeypatch,
):
    agent = DigitalICAgent()
    calls = []
    monkeypatch.setattr(agent, "check_capability", lambda _name: False)
    monkeypatch.setattr(agent, "record_artifact_run", lambda *_args, **_kwargs: None)
    agent.target_handlers["sync-fifo"].flows["generate-rtl"] = (
        lambda **_kwargs: calls.append("generate-rtl") or True
    )
    agent.target_handlers["sync-fifo"].flows["sim-rtl"] = (
        lambda **_kwargs: calls.append("sim-rtl") or True
    )

    assert agent.run_target_flow(
        "sync-fifo",
        "generate-rtl",
        output_dir=tmp_path,
    )
    assert (
        agent.run_target_flow(
            "sync-fifo",
            "sim-rtl",
            output_dir=tmp_path,
        )
        is False
    )
    assert calls == ["generate-rtl"]
