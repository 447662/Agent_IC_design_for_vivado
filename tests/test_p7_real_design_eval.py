from __future__ import annotations

import shutil
import sys
import copy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
EVAL_ROOT = ROOT / "evals" / "digital_ic"
MANIFEST_PATH = EVAL_ROOT / "manifest.json"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.design_eval import (  # noqa: E402
    DesignEvalError,
    evaluate_negative_cases,
    load_eval_manifest,
    materialize_design_workspace,
    prepare_repair_cases,
    run_generation_cases,
    summarize_negative_cases,
    validate_eval_manifest,
    verify_repaired_cases,
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

    timer_scoreboard = (
        EVAL_ROOT / "designs" / "timer" / "uvm" / "timer_pkg.sv"
    ).read_text(encoding="utf-8")
    assert "expected_remaining" in timer_scoreboard
    assert "expired mismatch" in timer_scoreboard


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


def test_p7_negative_summary_requires_ten_pre_vivado_rejections() -> None:
    results = evaluate_negative_cases(
        _manifest(),
        root=EVAL_ROOT,
        tool_observer=lambda command: None,
    )

    summary = summarize_negative_cases(results)

    assert summary["schema_version"] == "digital-ic-agent.eval-report.v1"
    assert summary["suite"] == "negative"
    assert summary["evidence_kind"] == "contract-negative"
    assert summary["status"] == "PASS"
    assert summary["executed"] == 10
    assert summary["passed"] == 10
    assert summary["failed"] == 0
    assert summary["vivado_invoked"] is False

    results[0]["vivado_invoked"] = True
    assert summarize_negative_cases(results)["status"] == "FAIL"


def test_p7_materialization_is_non_destructive_and_initializes_state(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "timer"

    result = materialize_design_workspace(
        EVAL_ROOT / "designs" / "timer",
        workspace,
    )

    assert result["stage"] == "INITIALIZED"
    assert (workspace / "contracts" / "design_intent.json").is_file()
    assert (workspace / "rtl" / "timer.sv").is_file()
    assert (workspace / ".digital_ic_agent" / "state.json").is_file()
    try:
        materialize_design_workspace(EVAL_ROOT / "designs" / "timer", workspace)
    except DesignEvalError as exc:
        assert exc.code == "EVAL_WORKSPACE_EXISTS"
    else:  # pragma: no cover - fail-closed contract
        raise AssertionError("existing eval workspace was overwritten")


def test_p7_generation_runner_requires_ten_passing_verdicts(tmp_path: Path) -> None:
    observed: list[str] = []

    def fake_verifier(
        workspace: Path,
        *,
        vivado_bin: Path | None,
        vivado_launch_mode: str,
    ) -> dict[str, object]:
        assert vivado_bin == Path("D:/vivado/bin")
        assert vivado_launch_mode == "project"
        assert (workspace / "contracts" / "design_intent.json").is_file()
        observed.append(workspace.name)
        return {
            "workspace": str(workspace),
            "iteration": 1,
            "verdict": {"status": "PASS", "reasons": []},
            "coverage": {"gates": {"statement": "PASS"}},
        }

    summary = run_generation_cases(
        _manifest(),
        root=EVAL_ROOT,
        work_root=tmp_path / "generation",
        vivado_bin=Path("D:/vivado/bin"),
        vivado_launch_mode="project",
        verifier=fake_verifier,
    )

    assert summary["status"] == "PASS"
    assert summary["executed"] == 10
    assert summary["passed"] == 10
    assert summary["failed"] == 0
    assert len(observed) == 10
    assert all(case["evidence_kind"] == "real-vivado" for case in summary["cases"])


def test_p7_timer_reset_defect_uses_observable_scoreboard_diagnostics() -> None:
    repair_cases = next(
        suite["cases"] for suite in _manifest()["suites"] if suite["kind"] == "repair"
    )
    timer_reset = next(
        case for case in repair_cases if case["id"] == "repair-timer-reset"
    )

    assert timer_reset["defect"]["type"] == "behavior"
    assert set(timer_reset["defect"]["expected_reason_codes"]) == {
        "FAIL_MARKER_FOUND",
        "UVM_ERROR_FOUND",
    }


def test_p7_repair_runner_separates_injection_diagnosis_and_codex_repair(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    expected_codes = {
        case["id"]: list(case["defect"]["expected_reason_codes"])
        for suite in manifest["suites"]
        if suite["kind"] == "repair"
        for case in suite["cases"]
    }

    def failing_verifier(
        workspace: Path,
        *,
        vivado_bin: Path | None,
        vivado_launch_mode: str,
    ) -> dict[str, object]:
        assert vivado_bin == Path("D:/vivado/bin")
        assert vivado_launch_mode == "direct"
        return {
            "iteration": 1,
            "verdict": {
                "status": "FAIL",
                "reasons": [
                    {"code": code, "message": code, "source": "xsim.log"}
                    for code in expected_codes[workspace.name]
                ],
            },
        }

    def fake_diagnoser(workspace: Path) -> dict[str, object]:
        return {
            "diagnosis": {
                "status": "FAIL",
                "reasons": [
                    {"code": code, "message": code, "source": "xsim.log"}
                    for code in expected_codes[workspace.name]
                ],
            }
        }

    work_root = tmp_path / "repair"
    prepared = prepare_repair_cases(
        manifest,
        root=EVAL_ROOT,
        work_root=work_root,
        vivado_bin=Path("D:/vivado/bin"),
        verifier=failing_verifier,
        diagnoser=fake_diagnoser,
    )

    assert prepared["status"] == "PASS"
    assert prepared["executed"] == 10
    assert prepared["detected"] == 10
    assert all(case["initial_status"] == "FAIL" for case in prepared["cases"])
    assert all(case["diagnosis_status"] == "FAIL" for case in prepared["cases"])

    repair_cases = next(
        suite["cases"] for suite in manifest["suites"] if suite["kind"] == "repair"
    )
    for case in repair_cases:
        relative_file = Path(case["defect"]["file"])
        shutil.copyfile(
            EVAL_ROOT / "designs" / case["design_template"] / relative_file,
            work_root / case["id"] / relative_file,
        )

    def passing_verifier(
        workspace: Path,
        *,
        vivado_bin: Path | None,
        vivado_launch_mode: str,
    ) -> dict[str, object]:
        assert vivado_bin == Path("D:/vivado/bin")
        assert vivado_launch_mode == "direct"
        return {
            "iteration": 2,
            "verdict": {"status": "PASS", "reasons": []},
            "coverage": {"gates": {"statement": "PASS"}},
        }

    repaired = verify_repaired_cases(
        manifest,
        root=EVAL_ROOT,
        work_root=work_root,
        vivado_bin=Path("D:/vivado/bin"),
        verifier=passing_verifier,
    )

    assert repaired["status"] == "PASS"
    assert repaired["executed"] == 10
    assert repaired["repaired"] == 10
    assert repaired["required_repaired"] == 7
    assert all(case["repair_iterations"] == 1 for case in repaired["cases"])
    assert all(case["repair_changed_source"] is True for case in repaired["cases"])


def test_p7_manifest_validation_reports_all_governance_boundaries() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["schema_version"] = "invalid"
    suites = manifest["suites"]
    generation = next(suite for suite in suites if suite["kind"] == "generation")
    repair = next(suite for suite in suites if suite["kind"] == "repair")
    negative = next(suite for suite in suites if suite["kind"] == "negative")

    generation["cases"][0].update(
        {
            "id": "",
            "specification": "",
            "evidence_kind": "synthetic-runtime-contract",
            "design_template": "../escape",
            "unseen": False,
            "reference_fingerprints": "invalid",
        }
    )
    generation["cases"][2]["id"] = generation["cases"][1]["id"]
    generation["cases"][3]["spec_sha256"] = "wrong-hash"
    generation["cases"][4]["specification"] = generation["cases"][1]["specification"]
    generation["cases"][4]["spec_sha256"] = generation["cases"][1]["spec_sha256"]
    generation["cases"][5]["design_template"] = "missing-template"

    repair["cases"][0]["max_repair_iterations"] = True
    repair["cases"][0]["defect"] = None
    repair["cases"][1]["defect"] = {
        "file": "rtl/missing.sv",
        "expected_reason_codes": ["NONZERO_EXIT"],
        "injection": {
            "operation": "append",
            "find": "same",
            "replace": "same",
        },
    }
    negative["cases"][0]["mutation"] = None
    negative["cases"][0]["expected_status"] = "PASS"

    suites.extend(
        [
            None,
            {"kind": "unknown", "cases": []},
            {"kind": "generation", "cases": "invalid"},
            {"kind": "generation", "cases": [None] * 10},
        ]
    )
    result = validate_eval_manifest(manifest, root=EVAL_ROOT)

    assert result["status"] == "FAIL"
    codes = {issue["code"] for issue in result["issues"]}
    assert {
        "EVAL_SCHEMA_VERSION_INVALID",
        "EVAL_SUITE_INVALID",
        "EVAL_SUITE_KIND_INVALID",
        "EVAL_SUITE_DUPLICATE",
        "EVAL_CASE_COUNT_INVALID",
        "EVAL_CASE_INVALID",
        "EVAL_CASE_ID_INVALID",
        "EVAL_CASE_ID_DUPLICATE",
        "EVAL_SPECIFICATION_INVALID",
        "EVAL_SPEC_HASH_MISMATCH",
        "EVAL_SPEC_HASH_DUPLICATE",
        "EVAL_EVIDENCE_KIND_INVALID",
        "EVAL_TEMPLATE_INVALID",
        "EVAL_TEMPLATE_NOT_FOUND",
        "EVAL_NOT_UNSEEN",
        "EVAL_REAL_VIVADO_REQUIRED",
        "EVAL_REFERENCE_FINGERPRINTS_INVALID",
        "EVAL_REPAIR_LIMIT_INVALID",
        "EVAL_DEFECT_INVALID",
        "EVAL_DEFECT_FILE_INVALID",
        "EVAL_DEFECT_INJECTION_INVALID",
        "EVAL_MUTATION_INVALID",
        "EVAL_EXPECTED_STATUS_INVALID",
    } <= codes
    assert validate_eval_manifest(None, root=EVAL_ROOT)["status"] == "FAIL"
    missing_suites = validate_eval_manifest(
        {"schema_version": "digital-ic-agent.eval.v1", "suites": "invalid"},
        root=EVAL_ROOT,
    )
    assert {issue["code"] for issue in missing_suites["issues"]} == {
        "EVAL_SUITES_INVALID",
        "EVAL_SUITE_SET_INVALID",
    }


def test_p7_manifest_loader_and_workspace_runners_fail_closed(tmp_path: Path) -> None:
    paths = {
        "missing": tmp_path / "missing.json",
        "invalid": tmp_path / "invalid.json",
        "array": tmp_path / "array.json",
        "large": tmp_path / "large.json",
    }
    paths["invalid"].write_text("{", encoding="utf-8")
    paths["array"].write_text("[]", encoding="utf-8")
    paths["large"].write_bytes(b" " * (2 * 1024 * 1024 + 1))
    expected = {
        "missing": "EVAL_MANIFEST_NOT_FOUND",
        "invalid": "EVAL_MANIFEST_INVALID",
        "array": "EVAL_MANIFEST_INVALID",
        "large": "EVAL_MANIFEST_TOO_LARGE",
    }
    for name, path in paths.items():
        try:
            load_eval_manifest(path)
        except DesignEvalError as exc:
            assert exc.code == expected[name]
        else:  # pragma: no cover - fail-closed contract
            raise AssertionError(f"invalid manifest was accepted: {name}")

    boundary_calls = (
        lambda: materialize_design_workspace(tmp_path / "no-template", tmp_path / "workspace"),
        lambda: run_generation_cases(
            _manifest(),
            root=EVAL_ROOT,
            work_root=tmp_path,
            vivado_bin=None,
        ),
        lambda: prepare_repair_cases(
            _manifest(),
            root=EVAL_ROOT,
            work_root=tmp_path,
            vivado_bin=None,
        ),
        lambda: verify_repaired_cases(
            _manifest(),
            root=EVAL_ROOT,
            work_root=tmp_path / "missing-repair-root",
            vivado_bin=None,
        ),
        lambda: evaluate_negative_cases({}, root=EVAL_ROOT, tool_observer=lambda _: None),
    )
    expected_codes = (
        "EVAL_TEMPLATE_NOT_FOUND",
        "EVAL_WORK_ROOT_EXISTS",
        "EVAL_WORK_ROOT_EXISTS",
        "EVAL_WORK_ROOT_NOT_FOUND",
        "EVAL_NEGATIVE_SUITE_MISSING",
    )
    for call, code in zip(boundary_calls, expected_codes, strict=True):
        try:
            call()
        except DesignEvalError as exc:
            assert exc.code == code
        else:  # pragma: no cover - fail-closed contract
            raise AssertionError(f"boundary did not fail closed: {code}")
