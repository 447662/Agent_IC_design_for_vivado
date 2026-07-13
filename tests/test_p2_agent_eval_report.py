import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "generate_agent_eval_report.py"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "agent_eval_cases.json"


def test_p2_agent_eval_report_generates_machine_readable_summary(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--eval-cases",
            str(FIXTURE_PATH),
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "agent_eval_report.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "agent_eval_report.md").read_text(encoding="utf-8")

    assert report["status"] == "PASS"
    assert report["suite_count"] == 4
    assert report["case_count"] == 10
    assert report["retained_failure_cases"] == 3
    assert report["executed_case_count"] == 10
    assert report["passed_case_count"] == 10
    assert report["failed_case_count"] == 0
    assert report["duplicate_case_ids"] == []
    assert report["targets"] == ["async-fifo", "round-robin-arbiter", "sync-fifo"]
    assert set(report["domains"]) == {
        "artifact_authenticity",
        "failure_handling",
        "multi_target_consistency",
        "tool_selection",
    }
    assert "Agent Evaluation Report" in markdown
    assert "| Tool Selection | 3 |" in markdown
    assert "| Executed cases | 10 |" in markdown
    assert all(case["status"] == "PASS" for case in report["cases"])
    assert all(case["checks"] for case in report["cases"])
    assert all(case["evidence_kind"] for case in report["cases"])


def test_p2_agent_eval_report_fails_on_duplicate_case_ids(tmp_path):
    duplicate_fixture = tmp_path / "duplicate_eval_cases.json"
    duplicate_fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suites": [
                    {
                        "domain": "tool_selection",
                        "cases": [{"id": "dup"}, {"id": "dup"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--eval-cases",
            str(duplicate_fixture),
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 1
    report = json.loads((tmp_path / "agent_eval_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["duplicate_case_ids"] == ["dup"]


def test_agent_eval_report_fails_when_an_expected_tool_is_corrupted(tmp_path):
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["suites"][0]["cases"][0]["expected_tools"] = ["tool-that-does-not-exist"]
    corrupted_fixture = tmp_path / "corrupted_eval_cases.json"
    corrupted_fixture.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--eval-cases",
            str(corrupted_fixture),
            "--output-dir",
            str(tmp_path / "report"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 1
    report = json.loads(
        (tmp_path / "report" / "agent_eval_report.json").read_text(encoding="utf-8")
    )
    failed = next(case for case in report["cases"] if case["id"] == "design_doc_uses_document_generator")
    assert failed["status"] == "FAIL"
    assert failed["observed"]["tools"] == [
        "render_target_design_spec",
        "record_artifact_run",
    ]
