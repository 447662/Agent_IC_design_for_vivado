from __future__ import annotations

import copy
import hashlib
import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from digital_ic_agent._runtime.intent_contract import (
    load_intent_json,
    validate_intents,
)
from digital_ic_agent._runtime.design_workspace import initialize_workspace
from digital_ic_agent._runtime.design_workspace import diagnose_workspace
from digital_ic_agent._runtime.generic_verification import (
    VivadoLaunchMode,
    verify_workspace,
)


EVAL_SCHEMA_VERSION = "digital-ic-agent.eval.v1"
EXPECTED_SUITE_COUNTS = {
    "generation": 10,
    "repair": 10,
    "negative": 10,
}
MAX_EVAL_MANIFEST_BYTES = 2 * 1024 * 1024
ToolObserver = Callable[[list[str]], None]
WorkspaceVerifier = Callable[..., dict[str, Any]]
WorkspaceDiagnoser = Callable[[Path], dict[str, Any]]
REQUIRED_REPAIR_PASSES = 7


class DesignEvalError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def load_eval_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise DesignEvalError("EVAL_MANIFEST_NOT_FOUND", f"Eval manifest not found: {path}")
    if path.stat().st_size > MAX_EVAL_MANIFEST_BYTES:
        raise DesignEvalError("EVAL_MANIFEST_TOO_LARGE", f"Eval manifest is too large: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DesignEvalError("EVAL_MANIFEST_INVALID", f"Invalid eval manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise DesignEvalError("EVAL_MANIFEST_INVALID", "Eval manifest must be an object")
    return payload


def _safe_relative_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return Path(*path.parts)


def _sequence(value: object) -> Sequence[object] | None:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    return None


def _case_hash(specification: str) -> str:
    return hashlib.sha256(specification.encode("utf-8")).hexdigest()


def _issue(issues: list[dict[str, str]], code: str, path: str, message: str) -> None:
    candidate = {"code": code, "path": path, "message": message}
    if candidate not in issues:
        issues.append(candidate)


def validate_eval_manifest(
    manifest: object,
    *,
    root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(manifest, Mapping):
        return {
            "status": "FAIL",
            "issues": [
                {
                    "code": "EVAL_MANIFEST_INVALID",
                    "path": "manifest",
                    "message": "Eval manifest must be an object",
                }
            ],
        }
    if manifest.get("schema_version") != EVAL_SCHEMA_VERSION:
        _issue(
            issues,
            "EVAL_SCHEMA_VERSION_INVALID",
            "schema_version",
            f"Expected {EVAL_SCHEMA_VERSION}",
        )
    suites = _sequence(manifest.get("suites"))
    if suites is None:
        _issue(issues, "EVAL_SUITES_INVALID", "suites", "Suites must be an array")
        suites = []

    seen_suite_kinds: set[str] = set()
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for suite_index, raw_suite in enumerate(suites):
        suite_path = f"suites.{suite_index}"
        if not isinstance(raw_suite, Mapping):
            _issue(issues, "EVAL_SUITE_INVALID", suite_path, "Suite must be an object")
            continue
        kind = raw_suite.get("kind")
        if kind not in EXPECTED_SUITE_COUNTS:
            _issue(issues, "EVAL_SUITE_KIND_INVALID", f"{suite_path}.kind", "Unknown suite kind")
            continue
        kind = str(kind)
        if kind in seen_suite_kinds:
            _issue(issues, "EVAL_SUITE_DUPLICATE", f"{suite_path}.kind", f"Duplicate suite: {kind}")
        seen_suite_kinds.add(kind)
        cases = _sequence(raw_suite.get("cases"))
        if cases is None or len(cases) != EXPECTED_SUITE_COUNTS[kind]:
            _issue(
                issues,
                "EVAL_CASE_COUNT_INVALID",
                f"{suite_path}.cases",
                f"{kind} must define exactly {EXPECTED_SUITE_COUNTS[kind]} cases",
            )
            cases = cases or []
        for case_index, raw_case in enumerate(cases):
            case_path = f"{suite_path}.cases.{case_index}"
            if not isinstance(raw_case, Mapping):
                _issue(issues, "EVAL_CASE_INVALID", case_path, "Case must be an object")
                continue
            case_id = raw_case.get("id")
            if not isinstance(case_id, str) or not case_id.strip():
                _issue(issues, "EVAL_CASE_ID_INVALID", f"{case_path}.id", "Case id is required")
            elif case_id in seen_ids:
                _issue(issues, "EVAL_CASE_ID_DUPLICATE", f"{case_path}.id", case_id)
            else:
                seen_ids.add(case_id)
            specification = raw_case.get("specification")
            spec_hash = raw_case.get("spec_sha256")
            if not isinstance(specification, str) or not specification.strip():
                _issue(
                    issues,
                    "EVAL_SPECIFICATION_INVALID",
                    f"{case_path}.specification",
                    "Specification is required",
                )
            elif spec_hash != _case_hash(specification):
                _issue(
                    issues,
                    "EVAL_SPEC_HASH_MISMATCH",
                    f"{case_path}.spec_sha256",
                    "Specification hash does not match UTF-8 content",
                )
            elif spec_hash in seen_hashes:
                _issue(issues, "EVAL_SPEC_HASH_DUPLICATE", f"{case_path}.spec_sha256", str(spec_hash))
            else:
                seen_hashes.add(str(spec_hash))
            evidence_kind = raw_case.get("evidence_kind")
            if not isinstance(evidence_kind, str) or "synthetic" in evidence_kind:
                _issue(
                    issues,
                    "EVAL_EVIDENCE_KIND_INVALID",
                    f"{case_path}.evidence_kind",
                    "Synthetic evidence is forbidden",
                )

            template_key = "base_template" if kind == "negative" else "design_template"
            template = _safe_relative_path(raw_case.get(template_key))
            if template is None or len(template.parts) != 1:
                _issue(
                    issues,
                    "EVAL_TEMPLATE_INVALID",
                    f"{case_path}.{template_key}",
                    "Design template must be a simple relative name",
                )
            elif not (Path(root) / "designs" / template).is_dir():
                _issue(
                    issues,
                    "EVAL_TEMPLATE_NOT_FOUND",
                    f"{case_path}.{template_key}",
                    f"Design template not found: {template.as_posix()}",
                )
            if kind == "generation":
                if raw_case.get("unseen") is not True:
                    _issue(issues, "EVAL_NOT_UNSEEN", f"{case_path}.unseen", "Generation case must be unseen")
                if raw_case.get("evidence_kind") != "real-vivado":
                    _issue(
                        issues,
                        "EVAL_REAL_VIVADO_REQUIRED",
                        f"{case_path}.evidence_kind",
                        "Generation cases require real-vivado evidence",
                    )
                fingerprints = _sequence(raw_case.get("reference_fingerprints"))
                if fingerprints is None:
                    _issue(
                        issues,
                        "EVAL_REFERENCE_FINGERPRINTS_INVALID",
                        f"{case_path}.reference_fingerprints",
                        "Reference fingerprints must be an array",
                    )
            elif kind == "repair":
                maximum = raw_case.get("max_repair_iterations")
                defect = raw_case.get("defect")
                if not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= 3:
                    _issue(
                        issues,
                        "EVAL_REPAIR_LIMIT_INVALID",
                        f"{case_path}.max_repair_iterations",
                        "Repair limit must be between one and three",
                    )
                if not isinstance(defect, Mapping) or not _sequence(defect.get("expected_reason_codes")):
                    _issue(
                        issues,
                        "EVAL_DEFECT_INVALID",
                        f"{case_path}.defect",
                        "Defect and expected reason codes are required",
                    )
                else:
                    defect_file = _safe_relative_path(defect.get("file"))
                    injection = defect.get("injection")
                    if (
                        template is None
                        or defect_file is None
                        or len(defect_file.parts) < 2
                        or not (Path(root) / "designs" / template / defect_file).is_file()
                    ):
                        _issue(
                            issues,
                            "EVAL_DEFECT_FILE_INVALID",
                            f"{case_path}.defect.file",
                            "Defect file must resolve inside the design template",
                        )
                    if (
                        not isinstance(injection, Mapping)
                        or injection.get("operation") != "replace_once"
                        or not isinstance(injection.get("find"), str)
                        or not injection.get("find")
                        or not isinstance(injection.get("replace"), str)
                        or injection.get("find") == injection.get("replace")
                    ):
                        _issue(
                            issues,
                            "EVAL_DEFECT_INJECTION_INVALID",
                            f"{case_path}.defect.injection",
                            "Repair defects require one exact replace_once injection",
                        )
            else:
                mutation = raw_case.get("mutation")
                if not isinstance(mutation, Mapping):
                    _issue(
                        issues,
                        "EVAL_MUTATION_INVALID",
                        f"{case_path}.mutation",
                        "Negative case mutation is required",
                    )
                if raw_case.get("expected_status") not in {"FAIL", "AMBIGUOUS"}:
                    _issue(
                        issues,
                        "EVAL_EXPECTED_STATUS_INVALID",
                        f"{case_path}.expected_status",
                        "Negative status must be FAIL or AMBIGUOUS",
                    )
    if seen_suite_kinds != set(EXPECTED_SUITE_COUNTS):
        _issue(issues, "EVAL_SUITE_SET_INVALID", "suites", "All three eval suites are required")
    return {"status": "FAIL" if issues else "PASS", "issues": issues}


def _resolve_mutation(document: Any, path: str) -> tuple[Any, str | int]:
    parts = path.split(".")
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    leaf: str | int = int(parts[-1]) if isinstance(current, list) else parts[-1]
    return current, leaf


def _apply_mutation(document: dict[str, Any], mutation: Mapping[str, object]) -> None:
    parent, leaf = _resolve_mutation(document, str(mutation["path"]))
    operation = mutation.get("operation")
    if operation == "delete":
        del parent[leaf]
    elif operation == "set":
        parent[leaf] = copy.deepcopy(mutation.get("value"))
    else:
        raise DesignEvalError("EVAL_MUTATION_INVALID", f"Unsupported mutation: {operation}")


def evaluate_negative_cases(
    manifest: Mapping[str, object],
    *,
    root: Path,
    tool_observer: ToolObserver,
) -> list[dict[str, Any]]:
    del tool_observer
    suites = _sequence(manifest.get("suites")) or []
    negative_suite = next(
        (
            suite
            for suite in suites
            if isinstance(suite, Mapping) and suite.get("kind") == "negative"
        ),
        None,
    )
    if not isinstance(negative_suite, Mapping):
        raise DesignEvalError("EVAL_NEGATIVE_SUITE_MISSING", "Negative eval suite is missing")
    cases = _sequence(negative_suite.get("cases")) or []
    results: list[dict[str, Any]] = []
    for raw_case in cases:
        if not isinstance(raw_case, Mapping):
            continue
        design_dir = Path(root) / "designs" / str(raw_case["base_template"])
        design = copy.deepcopy(
            load_intent_json(design_dir / "contracts" / "design_intent.json")
        )
        verification = copy.deepcopy(
            load_intent_json(design_dir / "contracts" / "verification_intent.json")
        )
        if not isinstance(design, dict) or not isinstance(verification, dict):
            raise DesignEvalError("EVAL_TEMPLATE_INVALID", "Template intents must be objects")
        mutation = raw_case["mutation"]
        if not isinstance(mutation, Mapping):
            raise DesignEvalError("EVAL_MUTATION_INVALID", "Mutation must be an object")
        target = design if mutation.get("document") == "design" else verification
        _apply_mutation(target, mutation)
        validation = validate_intents(design, verification)
        codes = {issue.code for issue in validation.issues}
        expected_status = str(raw_case["expected_status"])
        expected_code = str(raw_case["expected_code"])
        passed = validation.status == expected_status and expected_code in codes
        results.append(
            {
                "id": str(raw_case["id"]),
                "status": "PASS" if passed else "FAIL",
                "observed_status": validation.status,
                "observed_codes": sorted(codes),
                "expected_status": expected_status,
                "expected_code": expected_code,
                "vivado_invoked": False,
            }
        )
    return results


def summarize_negative_cases(
    results: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    cases = [dict(result) for result in results]
    passed_count = sum(case.get("status") == "PASS" for case in cases)
    vivado_invoked = any(case.get("vivado_invoked") is not False for case in cases)
    failed_count = len(cases) - passed_count
    return {
        "schema_version": "digital-ic-agent.eval-report.v1",
        "suite": "negative",
        "evidence_kind": "contract-negative",
        "executed": len(cases),
        "passed": passed_count,
        "failed": failed_count,
        "vivado_invoked": vivado_invoked,
        "status": (
            "PASS"
            if len(cases) == EXPECTED_SUITE_COUNTS["negative"]
            and failed_count == 0
            and not vivado_invoked
            else "FAIL"
        ),
        "cases": cases,
    }


def materialize_design_workspace(
    template_dir: Path,
    workspace: Path,
) -> dict[str, Any]:
    template_dir = Path(template_dir).resolve()
    workspace = Path(workspace).resolve()
    if not template_dir.is_dir():
        raise DesignEvalError(
            "EVAL_TEMPLATE_NOT_FOUND",
            f"Design template not found: {template_dir}",
        )
    if workspace.exists():
        raise DesignEvalError(
            "EVAL_WORKSPACE_EXISTS",
            f"Eval workspace already exists: {workspace}",
        )
    for path in template_dir.rglob("*"):
        if path.is_symlink():
            raise DesignEvalError(
                "EVAL_TEMPLATE_SYMLINK_FORBIDDEN",
                f"Template symlinks are forbidden: {path}",
            )
    workspace.mkdir(parents=True)
    for directory in ("contracts", "rtl", "uvm"):
        source = template_dir / directory
        if not source.is_dir():
            raise DesignEvalError(
                "EVAL_TEMPLATE_INVALID",
                f"Template directory is missing: {source}",
            )
        shutil.copytree(source, workspace / directory)
    return initialize_workspace(workspace)


def run_generation_cases(
    manifest: Mapping[str, object],
    *,
    root: Path,
    work_root: Path,
    vivado_bin: Path | None,
    vivado_launch_mode: VivadoLaunchMode = "direct",
    verifier: WorkspaceVerifier = verify_workspace,
) -> dict[str, Any]:
    root = Path(root).resolve()
    work_root = Path(work_root).resolve()
    if work_root.exists():
        raise DesignEvalError(
            "EVAL_WORK_ROOT_EXISTS",
            f"Eval work root already exists: {work_root}",
        )
    work_root.mkdir(parents=True)
    suites = _sequence(manifest.get("suites")) or []
    generation_suite = next(
        (
            suite
            for suite in suites
            if isinstance(suite, Mapping) and suite.get("kind") == "generation"
        ),
        None,
    )
    if not isinstance(generation_suite, Mapping):
        raise DesignEvalError(
            "EVAL_GENERATION_SUITE_MISSING",
            "Generation eval suite is missing",
        )
    cases = _sequence(generation_suite.get("cases")) or []
    results: list[dict[str, Any]] = []
    for raw_case in cases:
        if not isinstance(raw_case, Mapping):
            continue
        case_id = str(raw_case["id"])
        workspace = work_root / case_id
        try:
            materialize_design_workspace(
                root / "designs" / str(raw_case["design_template"]),
                workspace,
            )
            verification = verifier(
                workspace,
                vivado_bin=vivado_bin,
                vivado_launch_mode=vivado_launch_mode,
            )
            verdict = verification.get("verdict")
            passed = isinstance(verdict, Mapping) and verdict.get("status") == "PASS"
            results.append(
                {
                    "id": case_id,
                    "spec_sha256": str(raw_case["spec_sha256"]),
                    "design_template": str(raw_case["design_template"]),
                    "evidence_kind": str(raw_case["evidence_kind"]),
                    "status": "PASS" if passed else "FAIL",
                    "workspace": str(workspace),
                    "iteration": verification.get("iteration"),
                    "coverage": verification.get("coverage", {}),
                    "verdict": verdict,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": case_id,
                    "spec_sha256": str(raw_case["spec_sha256"]),
                    "design_template": str(raw_case["design_template"]),
                    "evidence_kind": str(raw_case["evidence_kind"]),
                    "status": "FAIL",
                    "workspace": str(workspace),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    passed_count = sum(result["status"] == "PASS" for result in results)
    failed_count = sum(result["status"] == "FAIL" for result in results)
    return {
        "schema_version": "digital-ic-agent.eval-report.v1",
        "suite": "generation",
        "evidence_kind": "real-vivado",
        "vivado_launch_mode": vivado_launch_mode,
        "executed": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "status": (
            "PASS"
            if len(results) == EXPECTED_SUITE_COUNTS["generation"] and failed_count == 0
            else "FAIL"
        ),
        "cases": results,
    }


def _suite_cases(
    manifest: Mapping[str, object],
    kind: str,
) -> Sequence[object]:
    suites = _sequence(manifest.get("suites")) or []
    suite = next(
        (
            item
            for item in suites
            if isinstance(item, Mapping) and item.get("kind") == kind
        ),
        None,
    )
    if not isinstance(suite, Mapping):
        raise DesignEvalError(
            f"EVAL_{kind.upper()}_SUITE_MISSING",
            f"{kind.capitalize()} eval suite is missing",
        )
    return _sequence(suite.get("cases")) or []


def _repair_parts(
    raw_case: Mapping[str, object],
) -> tuple[Path, Mapping[str, object], Sequence[object]]:
    defect = raw_case.get("defect")
    if not isinstance(defect, Mapping):
        raise DesignEvalError("EVAL_DEFECT_INVALID", "Repair defect must be an object")
    relative_file = _safe_relative_path(defect.get("file"))
    injection = defect.get("injection")
    expected_codes = _sequence(defect.get("expected_reason_codes"))
    if relative_file is None or not isinstance(injection, Mapping) or expected_codes is None:
        raise DesignEvalError("EVAL_DEFECT_INVALID", "Repair defect is incomplete")
    return relative_file, injection, expected_codes


def _injected_bytes(
    source: Path,
    injection: Mapping[str, object],
) -> bytes:
    try:
        original = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DesignEvalError("EVAL_DEFECT_FILE_INVALID", f"Cannot read defect file: {source}") from exc
    find = injection.get("find")
    replace = injection.get("replace")
    if (
        injection.get("operation") != "replace_once"
        or not isinstance(find, str)
        or not find
        or not isinstance(replace, str)
        or find == replace
    ):
        raise DesignEvalError("EVAL_DEFECT_INJECTION_INVALID", "Invalid replace_once injection")
    occurrences = original.count(find)
    if occurrences != 1:
        raise DesignEvalError(
            "EVAL_DEFECT_ANCHOR_INVALID",
            f"Defect anchor must occur exactly once in {source}; observed {occurrences}",
        )
    return original.replace(find, replace, 1).encode("utf-8")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _reason_codes(payload: object) -> set[str]:
    if not isinstance(payload, Mapping):
        return set()
    reasons = _sequence(payload.get("reasons")) or []
    return {
        str(reason["code"])
        for reason in reasons
        if isinstance(reason, Mapping) and isinstance(reason.get("code"), str)
    }


def inject_repair_defect(
    workspace: Path,
    raw_case: Mapping[str, object],
) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    relative_file, injection, _ = _repair_parts(raw_case)
    target = workspace / relative_file
    if not target.is_file():
        raise DesignEvalError("EVAL_DEFECT_FILE_INVALID", f"Defect file not found: {target}")
    original = target.read_bytes()
    injected = _injected_bytes(target, injection)
    target.write_bytes(injected)
    return {
        "file": relative_file.as_posix(),
        "original_sha256": _sha256_bytes(original),
        "injected_sha256": _sha256_bytes(injected),
    }


def prepare_repair_cases(
    manifest: Mapping[str, object],
    *,
    root: Path,
    work_root: Path,
    vivado_bin: Path | None,
    vivado_launch_mode: VivadoLaunchMode = "direct",
    verifier: WorkspaceVerifier = verify_workspace,
    diagnoser: WorkspaceDiagnoser = diagnose_workspace,
) -> dict[str, Any]:
    root = Path(root).resolve()
    work_root = Path(work_root).resolve()
    if work_root.exists():
        raise DesignEvalError("EVAL_WORK_ROOT_EXISTS", f"Eval work root already exists: {work_root}")
    work_root.mkdir(parents=True)
    results: list[dict[str, Any]] = []
    for raw_case in _suite_cases(manifest, "repair"):
        if not isinstance(raw_case, Mapping):
            continue
        case_id = str(raw_case["id"])
        workspace = work_root / case_id
        try:
            materialize_design_workspace(
                root / "designs" / str(raw_case["design_template"]),
                workspace,
            )
            injection = inject_repair_defect(workspace, raw_case)
            verification = verifier(
                workspace,
                vivado_bin=vivado_bin,
                vivado_launch_mode=vivado_launch_mode,
            )
            diagnosis_result = diagnoser(workspace)
            verdict = verification.get("verdict")
            diagnosis = diagnosis_result.get("diagnosis")
            observed_codes = _reason_codes(verdict)
            diagnosis_codes = _reason_codes(diagnosis)
            _, _, raw_expected_codes = _repair_parts(raw_case)
            expected_codes = {str(code) for code in raw_expected_codes}
            initial_status = verdict.get("status") if isinstance(verdict, Mapping) else None
            diagnosis_status = (
                diagnosis.get("status") if isinstance(diagnosis, Mapping) else None
            )
            detected = (
                initial_status == "FAIL"
                and diagnosis_status == "FAIL"
                and expected_codes.issubset(observed_codes)
                and expected_codes.issubset(diagnosis_codes)
            )
            results.append(
                {
                    "id": case_id,
                    "design_template": str(raw_case["design_template"]),
                    "evidence_kind": str(raw_case["evidence_kind"]),
                    "status": "PASS" if detected else "FAIL",
                    "workspace": str(workspace),
                    "initial_status": initial_status,
                    "diagnosis_status": diagnosis_status,
                    "expected_reason_codes": sorted(expected_codes),
                    "observed_reason_codes": sorted(observed_codes),
                    "diagnosis_reason_codes": sorted(diagnosis_codes),
                    "iteration": verification.get("iteration"),
                    "injection": injection,
                    "verdict": verdict,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": case_id,
                    "design_template": str(raw_case.get("design_template", "")),
                    "evidence_kind": str(raw_case.get("evidence_kind", "")),
                    "status": "FAIL",
                    "workspace": str(workspace),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    detected_count = sum(result["status"] == "PASS" for result in results)
    return {
        "schema_version": "digital-ic-agent.eval-report.v1",
        "suite": "repair-prepare",
        "evidence_kind": "real-vivado-repair",
        "vivado_launch_mode": vivado_launch_mode,
        "executed": len(results),
        "detected": detected_count,
        "failed_detection": len(results) - detected_count,
        "status": (
            "PASS"
            if len(results) == EXPECTED_SUITE_COUNTS["repair"]
            and detected_count == len(results)
            else "FAIL"
        ),
        "cases": results,
    }


def verify_repaired_cases(
    manifest: Mapping[str, object],
    *,
    root: Path,
    work_root: Path,
    vivado_bin: Path | None,
    vivado_launch_mode: VivadoLaunchMode = "direct",
    verifier: WorkspaceVerifier = verify_workspace,
) -> dict[str, Any]:
    root = Path(root).resolve()
    work_root = Path(work_root).resolve()
    if not work_root.is_dir():
        raise DesignEvalError("EVAL_WORK_ROOT_NOT_FOUND", f"Eval work root not found: {work_root}")
    results: list[dict[str, Any]] = []
    for raw_case in _suite_cases(manifest, "repair"):
        if not isinstance(raw_case, Mapping):
            continue
        case_id = str(raw_case["id"])
        workspace = work_root / case_id
        try:
            relative_file, injection, _ = _repair_parts(raw_case)
            template_file = root / "designs" / str(raw_case["design_template"]) / relative_file
            injected_sha256 = _sha256_bytes(_injected_bytes(template_file, injection))
            repaired_source = (workspace / relative_file).read_bytes()
            repaired_sha256 = _sha256_bytes(repaired_source)
            repair_changed_source = repaired_sha256 != injected_sha256
            verification = verifier(
                workspace,
                vivado_bin=vivado_bin,
                vivado_launch_mode=vivado_launch_mode,
            )
            verdict = verification.get("verdict")
            iteration = verification.get("iteration")
            repair_iterations = iteration - 1 if isinstance(iteration, int) else None
            maximum = raw_case.get("max_repair_iterations")
            bounded = (
                isinstance(maximum, int)
                and isinstance(repair_iterations, int)
                and 1 <= repair_iterations <= maximum
            )
            passed = (
                repair_changed_source
                and bounded
                and isinstance(verdict, Mapping)
                and verdict.get("status") == "PASS"
            )
            results.append(
                {
                    "id": case_id,
                    "design_template": str(raw_case["design_template"]),
                    "evidence_kind": str(raw_case["evidence_kind"]),
                    "status": "PASS" if passed else "FAIL",
                    "workspace": str(workspace),
                    "repair_changed_source": repair_changed_source,
                    "injected_sha256": injected_sha256,
                    "repaired_sha256": repaired_sha256,
                    "iteration": iteration,
                    "repair_iterations": repair_iterations,
                    "max_repair_iterations": maximum,
                    "coverage": verification.get("coverage", {}),
                    "verdict": verdict,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": case_id,
                    "design_template": str(raw_case.get("design_template", "")),
                    "evidence_kind": str(raw_case.get("evidence_kind", "")),
                    "status": "FAIL",
                    "workspace": str(workspace),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    repaired_count = sum(result["status"] == "PASS" for result in results)
    return {
        "schema_version": "digital-ic-agent.eval-report.v1",
        "suite": "repair-verify",
        "evidence_kind": "real-vivado-repair",
        "vivado_launch_mode": vivado_launch_mode,
        "executed": len(results),
        "repaired": repaired_count,
        "failed_repair": len(results) - repaired_count,
        "required_repaired": REQUIRED_REPAIR_PASSES,
        "status": (
            "PASS"
            if len(results) == EXPECTED_SUITE_COUNTS["repair"]
            and repaired_count >= REQUIRED_REPAIR_PASSES
            else "FAIL"
        ),
        "cases": results,
    }
