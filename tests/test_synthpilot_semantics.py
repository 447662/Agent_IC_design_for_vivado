import json
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
CONFIG_PATH = AGENT_DIR / "agent.json"
EVIDENCE_PATH = ROOT / "docs" / "testing" / "evidence" / "synthpilot_tools_list.json"
EVIDENCE_SCRIPT_PATH = ROOT / "scripts" / "p0_1_synthpilot_mcp_evidence.py"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent import DigitalICAgent  # noqa: E402
from digital_ic_agent._runtime.capability_preflight import PreflightStatus  # noqa: E402


def test_synthpilot_is_optional_across_config_preflight_diagnostic_and_evidence(
    capsys,
    monkeypatch,
):
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    assert config["mcpServers"]["synthpilot"]["required"] is False
    assert evidence["capability"] == {
        "name": "synthpilot",
        "requirement": "optional",
        "failure_impact": "degraded-only",
    }
    assert evidence["status"] == "FAIL"
    assert evidence["normalized_status"] == "WARN"
    assert evidence["captured_at"].endswith("Z")
    assert evidence["blocker"] == {
        "code": "synthpilot-license-device-limit",
        "fingerprint": "synthpilot-license-device-limit-v1",
        "retry_policy": "external-state-change-only",
        "resume_when": "license slot is freed or activation is reset",
    }
    assert "License Verification Failed" in evidence["error"]["message"]

    agent = DigitalICAgent()
    monkeypatch.setattr(
        agent,
        "check_capability",
        lambda capability: capability == "vivado",
    )
    report = agent.run_preflight("sim-rtl")

    assert report.ok is True
    assert report.status_for("synthpilot") is PreflightStatus.MISSING_OPTIONAL
    assert agent.run_diagnostic(flow="sim-rtl") is True
    diagnostic = capsys.readouterr().out
    assert "synthpilot" in diagnostic
    assert "可选，降级" in diagnostic


def test_synthpilot_evidence_script_skips_unchanged_blocker_without_force():
    spec = importlib.util.spec_from_file_location(
        "synthpilot_evidence_retry_policy",
        EVIDENCE_SCRIPT_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    existing = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert module.should_attempt(existing, force=False) is False
    assert module.should_attempt(existing, force=True) is True


def test_readme_and_evidence_script_use_current_non_sandbox_runtime_terms():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    script = EVIDENCE_SCRIPT_PATH.read_text(encoding="utf-8")
    quality_summary = (ROOT / "docs" / "generated" / "quality_summary.md").read_text(
        encoding="utf-8"
    )
    capability_matrix = (
        ROOT / "docs" / "generated" / "capability_matrix.md"
    ).read_text(encoding="utf-8")

    assert "legacy 模块目录" not in readme
    assert "不构成可运行不可信代码的操作系统安全沙箱" in readme
    assert "digital_ic_agent._runtime.mcp_client" in script
    assert 'ROOT / ".trae" / "agent"' not in script
    for generated_text in (readme, quality_summary, capability_matrix):
        assert "degraded-only" in generated_text
        assert "captured 2026-07-13T10:27:10Z" in generated_text
