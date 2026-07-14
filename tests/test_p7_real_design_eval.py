from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
EVAL_ROOT = ROOT / "evals" / "digital_ic"
MANIFEST_PATH = EVAL_ROOT / "manifest.json"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.design_eval import (  # noqa: E402
    evaluate_negative_cases,
    load_eval_manifest,
    validate_eval_manifest,
)
from digital_ic_agent._runtime.intent_contract import (  # noqa: E402
    validate_intent_files,
)


def _manifest() -> dict[str, object]:
    return load_eval_manifest(MANIFEST_PATH)


def test_p7_manifest_defines_thirty_unique_non_synthetic_evals() -> None:
    manifest = _manifest()
    validation = validate_eval_manifest(manifest, root=EVAL_ROOT)

    assert validation["status"] == "PASS"
    suites = {suite["kind"]: suite["cases"] for suite in manifest["suites"]}
    assert {kind: len(cases) for kind, cases in suites.items()} == {
        "generation": 10,
        "repair": 10,
        "negative": 10,
    }
    cases = [case for suite in manifest["suites"] for case in suite["cases"]]
    assert len({case["id"] for case in cases}) == 30
    assert len({case["spec_sha256"] for case in cases}) == 30
    assert all("synthetic" not in case["evidence_kind"] for case in cases)


def test_p7_generation_cases_are_unseen_real_vivado_and_reference_disjoint() -> None:
    generation_cases = next(
        suite["cases"]
        for suite in _manifest()["suites"]
        if suite["kind"] == "generation"
    )

    assert all(case["unseen"] is True for case in generation_cases)
    assert all(case["evidence_kind"] == "real-vivado" for case in generation_cases)
    assert all(case["reference_fingerprints"] == [] for case in generation_cases)
    assert len({case["design_template"] for case in generation_cases}) == 10


def test_p7_all_generation_templates_have_valid_executable_contracts() -> None:
    manifest = _manifest()
    generation_cases = next(
        suite["cases"]
        for suite in manifest["suites"]
        if suite["kind"] == "generation"
    )

    for case in generation_cases:
        design_dir = EVAL_ROOT / "designs" / case["design_template"]
        design_intent = design_dir / "contracts" / "design_intent.json"
        verification_intent = design_dir / "contracts" / "verification_intent.json"
        result = validate_intent_files(design_intent, verification_intent)
        assert result.status == "PASS", (case["id"], result.to_dict())
        verification = __import__("json").loads(
            verification_intent.read_text(encoding="utf-8")
        )
        assert all((design_dir / source).is_file() for source in verification["source_files"])
        formal_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in design_dir.rglob("*.sv")
        )
        assert "TODO" not in formal_text


def test_p7_three_core_designs_include_complete_uvm_sva_and_coverage() -> None:
    for design_name in ("timer", "apb-register-block", "priority-encoder"):
        design_dir = EVAL_ROOT / "designs" / design_name
        verification = __import__("json").loads(
            (design_dir / "contracts" / "verification_intent.json").read_text(
                encoding="utf-8"
            )
        )
        source_names = {Path(source).name for source in verification["source_files"]}
        assert any(name.endswith("_if.sv") for name in source_names)
        assert any(name.endswith("_sva.sv") for name in source_names)
        assert any(name.endswith("_pkg.sv") for name in source_names)
        assert any(name.startswith("tb_") for name in source_names)
        assert verification["uvm_enabled"] is True
        assert verification["scoreboard"]["enabled"] is True
        assert verification["assertions"]
        assert verification["functional_coverage"]
        assert verification["coverage_strategy"]["code_coverage"] is True
        assert verification["coverage_strategy"]["functional_coverage"] is True


def test_p7_repair_cases_are_bounded_and_cover_ten_distinct_defects() -> None:
    repair_cases = next(
        suite["cases"]
        for suite in _manifest()["suites"]
        if suite["kind"] == "repair"
    )

    assert all(case["max_repair_iterations"] <= 3 for case in repair_cases)
    assert len({case["defect"]["id"] for case in repair_cases}) == 10
    assert all(case["defect"]["expected_reason_codes"] for case in repair_cases)
    assert {case["design_template"] for case in repair_cases} >= {
        "timer",
        "apb-register-block",
        "priority-encoder",
    }


def test_p7_negative_cases_fail_before_any_vivado_tool_call() -> None:
    manifest = _manifest()
    calls: list[list[str]] = []

    results = evaluate_negative_cases(
        manifest,
        root=EVAL_ROOT,
        tool_observer=calls.append,
    )

    assert len(results) == 10
    assert all(result["status"] == "PASS" for result in results)
    assert {result["observed_status"] for result in results} == {
        "FAIL",
        "AMBIGUOUS",
    }
    assert calls == []
