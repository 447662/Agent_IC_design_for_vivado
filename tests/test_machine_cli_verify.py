from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCHEMA_PATH = SRC_DIR / "digital_ic_agent" / "schemas" / "cli-response.schema.json"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _payload(status: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "passed": status == "PASS",
        "reasons": (
            []
            if status == "PASS"
            else [
                {
                    "code": "SIMULATION_FAILED",
                    "message": "simulation failed",
                    "source": "xsim.log",
                }
            ]
        ),
        "evidence": {},
    }


def _project(tmp_path: Path, status: str = "PASS") -> Path:
    project_dir = tmp_path / "sample-target"
    verdict = _payload(status)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "verification_verdict.json").write_text(
        json.dumps(verdict),
        encoding="utf-8",
    )
    (project_dir / "artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target": "sample-target",
                "updated_at": verdict["generated_at"],
                "runs": [
                    {
                        "run_id": "run-1",
                        "flow": "sim-rtl",
                        "status": status,
                        "verification_verdict": verdict,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return project_dir


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda project: ["verify", "--project-dir", str(project), "--json"],
        lambda project: ["--json", "verify", "--project-dir", str(project)],
    ],
)
def test_machine_verify_emits_pure_canonical_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argv_builder: object,
) -> None:
    module = importlib.import_module("digital_ic_agent._runtime.agent")
    project_dir = _project(tmp_path)

    assert module.main(argv_builder(project_dir)) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "digital-ic-agent.cli.v1"
    assert payload["command"] == "verify"
    assert payload["status"] == "PASS"
    assert payload["ok"] is True
    assert payload["error_code"] is None
    assert payload["data"]["verdict"]["status"] == "PASS"
    assert payload["data"]["manifest_status"] == "PASS"


def test_machine_verify_returns_stable_failure_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = importlib.import_module("digital_ic_agent._runtime.agent")
    project_dir = _project(tmp_path, status="FAIL")

    assert module.main(["verify", "--project-dir", str(project_dir), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "FAIL"
    assert payload["ok"] is False
    assert payload["error_code"] == "VERIFICATION_FAILED"
    assert payload["data"]["verdict"]["reasons"][0]["code"] == "SIMULATION_FAILED"


def test_machine_verify_rejects_missing_or_mismatched_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = importlib.import_module("digital_ic_agent._runtime.agent")
    missing_project = tmp_path / "missing"

    assert module.main(
        ["verify", "--project-dir", str(missing_project), "--json"]
    ) == 1
    missing = json.loads(capsys.readouterr().out)
    assert missing["error_code"] == "VERDICT_NOT_FOUND"

    project_dir = _project(tmp_path / "mismatch")
    manifest_path = project_dir / "artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runs"][-1]["status"] = "FAIL"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert module.main(
        ["verify", "--project-dir", str(project_dir), "--json"]
    ) == 1
    mismatch = json.loads(capsys.readouterr().out)
    assert mismatch["error_code"] == "VERDICT_MANIFEST_MISMATCH"


def test_machine_verify_checks_expected_flow(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = importlib.import_module("digital_ic_agent._runtime.agent")
    project_dir = _project(tmp_path)

    assert module.main(
        [
            "verify",
            "--project-dir",
            str(project_dir),
            "--expected-flow",
            "uvm-smoke",
            "--json",
        ]
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "FLOW_MISMATCH"


def test_machine_verify_executes_workspace_and_emits_canonical_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    machine_cli = importlib.import_module(
        "digital_ic_agent._runtime.agent_machine_cli"
    )
    workspace = tmp_path / "workspace"
    verdict = _payload("PASS")

    def fake_verify_workspace(
        received_workspace: Path,
        *,
        vivado_bin: Path | None,
    ) -> dict[str, object]:
        assert received_workspace == workspace
        assert vivado_bin == tmp_path / "vivado-bin"
        return {
            "workspace": str(workspace),
            "iteration": 1,
            "iteration_dir": str(workspace / "iterations" / "0001"),
            "verdict": verdict,
        }

    monkeypatch.setattr(machine_cli, "verify_workspace", fake_verify_workspace)
    module = importlib.import_module("digital_ic_agent._runtime.agent")

    assert module.main(
        [
            "verify",
            "--workspace",
            str(workspace),
            "--vivado-bin",
            str(tmp_path / "vivado-bin"),
            "--json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "verify"
    assert payload["status"] == "PASS"
    assert payload["data"]["iteration"] == 1
    assert payload["data"]["verdict"]["status"] == "PASS"


def test_machine_cli_response_schema_is_packaged_and_strict() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "command",
        "status",
        "ok",
        "error_code",
        "message",
        "data",
    }
    assert schema["properties"]["schema_version"]["const"] == (
        "digital-ic-agent.cli.v1"
    )
