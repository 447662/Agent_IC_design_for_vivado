import subprocess
import sys
import json
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
QUALITY_SUMMARY_PATH = ROOT / "docs" / "generated" / "quality_summary.md"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-quality.yml"
GENERATOR_PATH = ROOT / "scripts" / "generate_quality_summary.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("quality_summary_capabilities", GENERATOR_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_capability_inputs(tmp_path: Path, *, required: bool, status: str):
    config_path = tmp_path / "agent.json"
    evidence_path = tmp_path / "synthpilot.json"
    config_path.write_text(
        json.dumps({"mcpServers": {"synthpilot": {"required": required}}}),
        encoding="utf-8",
    )
    evidence_path.write_text(
        json.dumps(
            {
                "capability": {
                    "name": "synthpilot",
                    "requirement": "required" if required else "optional",
                    "failure_impact": (
                        "release-blocking" if required else "degraded-only"
                    ),
                },
                "captured_at": "2026-07-13T10:27:10Z",
                "status": status,
            }
        ),
        encoding="utf-8",
    )
    return config_path, evidence_path


def test_capability_evidence_maps_optional_failure_to_warn(tmp_path):
    generator = _load_generator()
    config_path, evidence_path = _write_capability_inputs(
        tmp_path,
        required=False,
        status="FAIL",
    )

    capability = generator.parse_capability_evidence(evidence_path, config_path)
    summary = generator.build_quality_summary(
        {"tests": 1, "failures": 0, "errors": 0, "skipped": 0, "time": 1.0},
        {"line_rate": 1.0, "branch_rate": 1.0},
        60,
        capability_summary=capability,
    )

    assert capability == {
        "name": "synthpilot",
        "requirement": "optional",
        "failure_impact": "degraded-only",
        "captured_at": "2026-07-13T10:27:10Z",
        "source_status": "FAIL",
        "status": "WARN",
    }
    assert (
        "| Capability synthpilot | WARN "
        "(optional; degraded-only; source FAIL; captured 2026-07-13T10:27:10Z) |"
        in summary
    )


def test_capability_evidence_maps_required_failure_to_blocked(tmp_path):
    generator = _load_generator()
    config_path, evidence_path = _write_capability_inputs(
        tmp_path,
        required=True,
        status="FAIL",
    )

    capability = generator.parse_capability_evidence(evidence_path, config_path)

    assert capability["status"] == "BLOCKED"
    assert generator.has_blocked_capability(capability) is True


def test_capability_evidence_rejects_requirement_drift(tmp_path):
    generator = _load_generator()
    config_path, evidence_path = _write_capability_inputs(
        tmp_path,
        required=False,
        status="FAIL",
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["capability"]["requirement"] = "required"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(ValueError, match="requirement does not match"):
        generator.parse_capability_evidence(evidence_path, config_path)


def test_p2_readme_uses_generated_quality_block_without_stale_stats():
    readme = README_PATH.read_text(encoding="utf-8")
    quality_summary = QUALITY_SUMMARY_PATH.read_text(encoding="utf-8")
    quality_block = readme.split(
        "<!-- digital-ic-agent:quality:start -->",
        1,
    )[1].split("<!-- digital-ic-agent:quality:end -->", 1)[0]

    assert "<!-- digital-ic-agent:quality:start -->" in readme
    assert "<!-- digital-ic-agent:quality:end -->" in readme
    assert "自动质量摘要" in readme
    assert "此区块由生成器维护" in readme
    assert "155 passed" not in readme
    assert "75.87%" not in readme
    assert "--cov-fail-under=68" not in readme
    assert "| Test result | PASS |" in quality_block
    for metric in ("Pytest total", "Line coverage", "Branch coverage"):
        summary_row = next(
            line for line in quality_summary.splitlines() if line.startswith(f"| {metric} |")
        )
        assert summary_row in quality_block
    assert "| Pytest failed |" not in quality_block
    assert "| Pytest errors |" not in quality_block
    assert "| Pytest skipped |" not in quality_block
    assert "| Pytest runtime seconds |" not in quality_block


def test_p2_quality_workflow_generates_quality_summary_and_matrix():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "--junitxml .tmp/pytest-results.xml" in workflow
    assert "--cov-report=xml:coverage.xml" in workflow
    assert "--minimum-line-rate 0.90" in workflow
    assert "--minimum-branch-rate 0.80" in workflow
    assert "scripts/generate_quality_summary.py" in workflow
    assert "--write-readme" not in workflow
    assert "Verify generated quality reports" in workflow
    assert "test -s .tmp/generated-quality/quality_summary.md" in workflow
    assert "test -s .tmp/generated-quality/capability_matrix.md" in workflow
    assert "test -s .tmp/generated-quality/quality_provenance.json" in workflow
    assert "test -s .tmp/generated-quality/agent_eval_report.json" in workflow
    assert "test -s .tmp/generated-quality/test_module_report.json" in workflow
    assert "Upload generated quality reports" in workflow
    assert ".tmp/generated-quality" in workflow
    assert "if-no-files-found: error" in workflow
    assert workflow.count("if: ${{ !cancelled() }}") >= 5


def test_p2_quality_summary_generator_updates_readme_from_test_artifacts(tmp_path):
    junit_path = tmp_path / "pytest-results.xml"
    coverage_path = tmp_path / "coverage.xml"
    readme_path = tmp_path / "README.md"
    output_dir = tmp_path / "generated"

    junit_path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" tests="5" failures="1" errors="0" skipped="1" time="1.23" />
</testsuites>
""",
        encoding="utf-8",
    )
    coverage_path.write_text(
        """<?xml version="1.0" ?>
<coverage line-rate="0.875" branch-rate="0.75" version="coverage.py">
  <packages />
</coverage>
""",
        encoding="utf-8",
    )
    readme_path.write_text(
        "# Demo\n\n<!-- digital-ic-agent:quality:start -->\nold\n<!-- digital-ic-agent:quality:end -->\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(GENERATOR_PATH),
            "--junitxml",
            str(junit_path),
            "--coverage-xml",
            str(coverage_path),
            "--readme",
            str(readme_path),
            "--output-dir",
            str(output_dir),
            "--data-scope",
            "local fixture sample",
            "--minimum-line-rate",
            "0",
            "--minimum-branch-rate",
            "0",
            "--write-readme",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    quality_summary = (output_dir / "quality_summary.md").read_text(encoding="utf-8")
    capability_matrix = (output_dir / "capability_matrix.md").read_text(encoding="utf-8")
    updated_readme = readme_path.read_text(encoding="utf-8")

    assert "Pytest total | 5" in quality_summary
    assert "Pytest failed | 1" in quality_summary
    assert "Data scope | local fixture sample" in quality_summary
    assert "Line coverage | 87.5%" in quality_summary
    assert "Branch coverage | 75.0%" in quality_summary
    assert "Routing evaluation cases" in quality_summary
    assert "Additional agent evaluation cases" in quality_summary
    assert "| Requirement routing |" in capability_matrix
    assert "| Tool Selection |" in capability_matrix
    assert "| Failure Handling |" in capability_matrix
    assert "| Artifact Authenticity |" in capability_matrix
    assert "| Multi Target Consistency |" in capability_matrix
    assert "| Agent evaluation report |" in capability_matrix
    assert "| Test module size report |" in capability_matrix
    assert "Data scope | local fixture sample" in updated_readme
    assert "Generated by `python scripts/generate_quality_summary.py`" in updated_readme
    assert "| Test result | FAIL |" in updated_readme
    assert "| Pytest total | 5 |" in updated_readme
    assert "| Line coverage | 87.5% |" in updated_readme
    assert "| Branch coverage | 75.0% |" in updated_readme
    assert "| Pytest failed |" not in updated_readme
    assert "| Pytest errors |" not in updated_readme
    assert "| Pytest skipped |" not in updated_readme
    assert "| Pytest runtime seconds |" not in updated_readme
    assert "old" not in updated_readme


def test_p2_quality_summary_rejects_missing_or_insufficient_eval_fixtures(tmp_path):
    junit_path = tmp_path / "pytest-results.xml"
    coverage_path = tmp_path / "coverage.xml"
    readme_path = tmp_path / "README.md"
    valid_routing_path = tmp_path / "routing.json"
    insufficient_routing_path = tmp_path / "routing-small.json"
    valid_eval_path = tmp_path / "agent-eval.json"

    junit_path.write_text(
        '<testsuite tests="1" failures="0" errors="0" skipped="0" time="0.1" />',
        encoding="utf-8",
    )
    coverage_path.write_text(
        '<coverage line-rate="1" branch-rate="1" />',
        encoding="utf-8",
    )
    readme_path.write_text("# Demo\n", encoding="utf-8")
    valid_routing_path.write_text(
        json.dumps([{"id": f"route-{index}"} for index in range(50)]),
        encoding="utf-8",
    )
    insufficient_routing_path.write_text(
        json.dumps([{"id": "only-one"}]),
        encoding="utf-8",
    )
    valid_eval_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suites": [
                    {
                        "domain": "tool_selection",
                        "cases": [{"id": "tool-1"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cases = [
        (tmp_path / "missing-routing.json", valid_eval_path),
        (insufficient_routing_path, valid_eval_path),
        (valid_routing_path, tmp_path / "missing-agent-eval.json"),
    ]
    for index, (routing_path, eval_path) in enumerate(cases):
        output_dir = tmp_path / f"generated-{index}"
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR_PATH),
                "--junitxml",
                str(junit_path),
                "--coverage-xml",
                str(coverage_path),
                "--readme",
                str(readme_path),
                "--output-dir",
                str(output_dir),
                "--routing-cases",
                str(routing_path),
                "--agent-eval-cases",
                str(eval_path),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        assert result.returncode != 0
        assert not output_dir.exists()
