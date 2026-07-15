from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _main() -> object:
    return importlib.import_module("digital_ic_agent._runtime.agent").main


def test_machine_command_registry_covers_codex_workflow() -> None:
    module = importlib.import_module("digital_ic_agent._runtime.agent_machine_cli")

    assert {
        "workspace",
        "spec",
        "reference",
        "verify",
        "diagnose",
        "status",
        "resume",
        "report",
    } == module.MACHINE_COMMANDS


def test_workspace_init_creates_deterministic_non_destructive_layout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "timer-design"
    main = _main()

    assert main(["workspace", "init", "--workspace", str(workspace), "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "PASS"
    assert first["data"]["stage"] == "INITIALIZED"
    for relative in (
        ".digital_ic_agent/state.json",
        "contracts",
        "rtl",
        "uvm",
        "sim",
        "reports",
        "iterations",
    ):
        assert (workspace / relative).exists()
    state_path = workspace / ".digital_ic_agent" / "state.json"
    original = state_path.read_text(encoding="utf-8")
    assert not list(state_path.parent.glob(".*.tmp"))

    assert main(["--json", "workspace", "init", "--workspace", str(workspace)]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["error_code"] is None
    assert second["data"]["already_initialized"] is True
    assert state_path.read_text(encoding="utf-8") == original


def test_spec_validate_emits_ambiguous_without_console_noise(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    design_path = tmp_path / "design_intent.json"
    verification_path = tmp_path / "verification_intent.json"
    design_path.write_text(
        json.dumps(
            {
                "schema_version": "digital-ic-agent.design-intent.v1",
                "module": {"name": "timer", "kind": "sequential"},
                "parameters": [],
                "ports": [],
                "protocols": [],
                "timing": {},
                "exceptional_behavior": [],
                "implementation_constraints": {},
            }
        ),
        encoding="utf-8",
    )
    verification_path.write_text(
        json.dumps(
            {
                "schema_version": "digital-ic-agent.verification-intent.v1",
                "module": "timer",
            }
        ),
        encoding="utf-8",
    )

    assert _main()(
        [
            "spec",
            "validate",
            "--design-intent",
            str(design_path),
            "--verification-intent",
            str(verification_path),
            "--json",
        ]
    ) == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["status"] == "AMBIGUOUS"
    assert payload["ok"] is False
    assert payload["error_code"] == "INTENT_AMBIGUOUS"
    assert {issue["code"] for issue in payload["data"]["issues"]} >= {
        "CLOCK_SEMANTICS_MISSING",
        "RESET_SEMANTICS_MISSING",
        "ACCEPTANCE_CRITERIA_MISSING",
    }
