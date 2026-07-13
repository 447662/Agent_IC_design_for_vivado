import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_CASES_PATH = ROOT / "tests" / "fixtures" / "agent_eval_cases.json"
ROUTING_CASES_PATH = ROOT / "tests" / "fixtures" / "agent_routing_cases.json"


def _load_eval_cases():
    return json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))


def test_p2_eval_fixture_covers_required_domains_and_keeps_data_decoupled():
    payload = _load_eval_cases()
    domains = {suite["domain"] for suite in payload["suites"]}

    assert payload["schema_version"] == 1
    assert domains == {
        "tool_selection",
        "failure_handling",
        "artifact_authenticity",
        "multi_target_consistency",
    }
    assert "analyze_requirement(" not in EVAL_CASES_PATH.read_text(encoding="utf-8")
    assert "DigitalICAgent" not in EVAL_CASES_PATH.read_text(encoding="utf-8")


def test_p2_eval_fixture_has_unique_case_ids_and_retained_failure_cases():
    payload = _load_eval_cases()
    case_ids = [
        case["id"]
        for suite in payload["suites"]
        for case in suite["cases"]
    ]
    retained_failure_cases = [
        case
        for suite in payload["suites"]
        if suite["domain"] == "failure_handling"
        for case in suite["cases"]
        if case.get("retain_failure_case") is True
    ]

    assert len(case_ids) == len(set(case_ids))
    assert len(retained_failure_cases) >= 3
    assert {case["expected_error_category"] for case in retained_failure_cases} == {
        "artifact_validation",
        "capability",
        "configuration",
    }


def test_p2_eval_fixture_references_existing_routing_fixture_and_targets():
    eval_payload = _load_eval_cases()
    routing_cases = json.loads(ROUTING_CASES_PATH.read_text(encoding="utf-8"))
    target_names = {
        target
        for suite in eval_payload["suites"]
        for case in suite["cases"]
        for target in case.get("targets", [case["target"]] if "target" in case else [])
    }

    assert len(routing_cases) >= 50
    assert target_names == {"async-fifo", "round-robin-arbiter", "sync-fifo"}


def test_p2_eval_fixture_artifact_cases_require_manifest_lineage():
    payload = _load_eval_cases()
    artifact_cases = [
        case
        for suite in payload["suites"]
        if suite["domain"] == "artifact_authenticity"
        for case in suite["cases"]
    ]

    assert artifact_cases
    for case in artifact_cases:
        assert case["required_artifacts"]
        assert {"run_id", "artifacts"} <= set(case["required_manifest_fields"])
