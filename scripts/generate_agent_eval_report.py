from __future__ import annotations

import argparse
import io
import json
import sys
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL_CASES = ROOT / "tests" / "fixtures" / "agent_eval_cases.json"
DEFAULT_WORK_DIR = ROOT / ".tmp" / "agent-eval"
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from digital_ic_agent._runtime.agent import DigitalICAgent  # noqa: E402
from digital_ic_agent._runtime.agent_errors import (  # noqa: E402
    AgentError,
    ArtifactValidationError,
)
from digital_ic_agent._runtime.capability_preflight import (  # noqa: E402
    CapabilityCheck,
    PreflightReport,
    PreflightStatus,
)


def load_eval_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Agent eval fixture schema_version must be 1")
    suites = payload.get("suites")
    if not isinstance(suites, list) or not suites:
        raise ValueError("Agent eval fixture must define non-empty suites")
    return payload


def summarize_eval_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    suites = payload["suites"]
    domains: dict[str, dict[str, Any]] = {}
    all_case_ids: list[str] = []
    retained_failure_cases = 0
    targets: set[str] = set()

    for suite in suites:
        domain = str(suite["domain"])
        cases = suite.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError(f"Eval suite must define non-empty cases: {domain}")
        domains[domain] = {
            "case_count": len(cases),
            "description": str(suite.get("description", "")),
        }
        for case in cases:
            case_id = str(case["id"])
            all_case_ids.append(case_id)
            if case.get("retain_failure_case") is True:
                retained_failure_cases += 1
            if "target" in case:
                targets.add(str(case["target"]))
            for target in case.get("targets", []):
                targets.add(str(target))

    duplicate_case_ids = sorted(
        case_id for case_id in set(all_case_ids) if all_case_ids.count(case_id) > 1
    )
    return {
        "schema_version": 1,
        "suite_count": len(suites),
        "case_count": len(all_case_ids),
        "domains": domains,
        "duplicate_case_ids": duplicate_case_ids,
        "retained_failure_cases": retained_failure_cases,
        "targets": sorted(targets),
    }


class RecordingAgent(DigitalICAgent):
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.observed_tools: list[str] = []
        super().__init__(*args, **kwargs)

    def _record(self, name: str) -> None:
        self.observed_tools.append(name)

    def render_target_design_spec(self, *args: object, **kwargs: object) -> Any:
        self._record("render_target_design_spec")
        return super().render_target_design_spec(*args, **kwargs)

    def generate_rtl_project(self, *args: object, **kwargs: object) -> Any:
        self._record("generate_rtl_project")
        return super().generate_rtl_project(*args, **kwargs)

    def record_artifact_run(self, *args: object, **kwargs: object) -> Any:
        self._record("record_artifact_run")
        return super().record_artifact_run(*args, **kwargs)

    def analyze_waveform(self, *args: object, **kwargs: object) -> Any:
        self._record("analyze_waveform")
        return super().analyze_waveform(*args, **kwargs)

    def create_target_scaffold(self, *args: object, **kwargs: object) -> Any:
        self._record("create_target_scaffold")
        return super().create_target_scaffold(*args, **kwargs)

    def resolve_vivado_command(self) -> str | None:
        return None


class MissingCapabilityAgent(RecordingAgent):
    def run_preflight(self, flow: str) -> PreflightReport:
        if flow == "sim-rtl":
            return PreflightReport(
                flow=flow,
                checks=(
                    CapabilityCheck("vivado", PreflightStatus.MISSING_REQUIRED),
                ),
                known_capabilities=("synthpilot", "vivado"),
                required_capabilities=("vivado",),
                optional_capabilities=("synthpilot",),
            )
        return super().run_preflight(flow)


def _check(
    name: str,
    passed: bool,
    *,
    expected: object,
    observed: object,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "observed": observed,
    }


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _latest_manifest_run(work_dir: Path, target: str) -> dict[str, Any]:
    manifest_path = work_dir / target / "artifacts.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return dict(payload["runs"][-1])


def _evaluate_tool_selection(
    case: dict[str, Any],
    work_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    scenario = dict(case["scenario"])
    operation = str(scenario["operation"])
    succeeded = False
    with RecordingAgent() as agent:
        if operation == "generate-spec":
            report = agent.write_target_design_spec(
                str(scenario["target"]),
                output_dir=work_dir,
                requirement=str(case["input"]),
            )
            succeeded = all(Path(str(path)).is_file() for path in report.values())
        elif operation == "generate-rtl":
            project_dir = agent.generate_rtl_project(
                str(scenario["target"]),
                output_dir=work_dir,
            )
            succeeded = Path(project_dir).is_dir()
        elif operation == "analyze-waveform":
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                succeeded = bool(
                    agent.analyze_waveform(
                        ROOT / str(scenario["fixture"]),
                        waveform_backend="vcd-analyzer",
                    )
                )
        else:
            raise ValueError("Unsupported tool selection operation: {}".format(operation))
        observed_tools = _unique(agent.observed_tools)

    expected_tools = [str(name) for name in case.get("expected_tools", [])]
    forbidden_tools = [str(name) for name in case.get("forbidden_tools", [])]
    checks = [
        _check(
            "operation_succeeded",
            succeeded,
            expected=True,
            observed=succeeded,
        ),
        _check(
            "expected_tools",
            set(expected_tools) <= set(observed_tools),
            expected=expected_tools,
            observed=observed_tools,
        ),
        _check(
            "forbidden_tools",
            not (set(forbidden_tools) & set(observed_tools)),
            expected=[],
            observed=sorted(set(forbidden_tools) & set(observed_tools)),
        ),
    ]
    return {"tools": observed_tools, "operation": operation}, checks, "runtime"


def _evaluate_failure(
    case: dict[str, Any],
    work_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    scenario = dict(case["scenario"])
    operation = str(scenario["operation"])
    observed_category: str | None = None
    observed_exit_code: int | None = None

    if operation == "missing-capability":
        target = str(scenario["target"])
        with MissingCapabilityAgent() as agent:
            agent.run_target_flow(target, "sim-rtl", output_dir=work_dir)
        run = _latest_manifest_run(work_dir, target)
        observed_category = run.get("error_category")
        observed_exit_code = run.get("error_exit_code")
    elif operation == "broken-config":
        config_path = work_dir / "broken-agent.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text('{"name":""}\n', encoding="utf-8")
        try:
            DigitalICAgent(config_path=config_path)
        except AgentError as exc:
            observed_category = exc.category
            observed_exit_code = exc.exit_code
    elif operation == "stale-artifact":
        target = str(scenario["target"])
        with RecordingAgent() as agent:
            agent.generate_rtl_project(target, output_dir=work_dir)
            agent.record_artifact_run(
                target,
                "generate-rtl",
                output_dir=work_dir,
                status="FAIL",
                error=ArtifactValidationError("pre-existing artifact is stale"),
            )
        run = _latest_manifest_run(work_dir, target)
        if any(item.get("status") == "STALE" for item in run["artifacts"]):
            error = ArtifactValidationError("pre-existing artifact is stale")
            observed_category = error.category
            observed_exit_code = error.exit_code
    else:
        raise ValueError("Unsupported failure operation: {}".format(operation))

    expected_category = str(case["expected_error_category"])
    expected_exit_code = int(case["expected_exit_code"])
    observed = {
        "error_category": observed_category,
        "exit_code": observed_exit_code,
        "operation": operation,
    }
    checks = [
        _check(
            "expected_error_category",
            observed_category == expected_category,
            expected=expected_category,
            observed=observed_category,
        ),
        _check(
            "expected_exit_code",
            observed_exit_code == expected_exit_code,
            expected=expected_exit_code,
            observed=observed_exit_code,
        ),
    ]
    return observed, checks, "runtime-error-contract"


def _write_synthetic_artifacts(
    agent: RecordingAgent,
    target: str,
    required_ids: set[str],
    work_dir: Path,
) -> None:
    target_info = agent.targets[target]
    project_dir = work_dir / target
    for artifact in target_info["artifact_manifest"]:
        if artifact["id"] not in required_ids:
            continue
        path = project_dir / str(artifact["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic executable eval artifact\n", encoding="utf-8")


def _evaluate_artifact_authenticity(
    case: dict[str, Any],
    work_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    target = str(case["target"])
    flow = str(case["flow"])
    required_artifacts = {str(value) for value in case["required_artifacts"]}
    with RecordingAgent() as agent:
        agent.generate_rtl_project(target, output_dir=work_dir)
        evidence_kind = "runtime"
        if flow != "generate-rtl":
            _write_synthetic_artifacts(agent, target, required_artifacts, work_dir)
            agent.record_artifact_run(target, flow, output_dir=work_dir, status="PASS")
            evidence_kind = "synthetic-runtime-contract"

    run = _latest_manifest_run(work_dir, target)
    current_artifacts = sorted(
        str(item["id"])
        for item in run["artifacts"]
        if item.get("status") == "CURRENT" and item.get("exists") is True
    )
    manifest_fields = sorted(run)
    required_fields = {str(value) for value in case["required_manifest_fields"]}
    observed = {
        "artifacts": current_artifacts,
        "manifest_fields": manifest_fields,
        "run_id_present": bool(run.get("run_id")),
    }
    checks = [
        _check(
            "required_artifacts",
            required_artifacts <= set(current_artifacts),
            expected=sorted(required_artifacts),
            observed=current_artifacts,
        ),
        _check(
            "required_manifest_fields",
            required_fields <= set(manifest_fields),
            expected=sorted(required_fields),
            observed=manifest_fields,
        ),
    ]
    return observed, checks, evidence_kind


def _evaluate_multi_target(
    case: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    targets = [str(target) for target in case["targets"]]
    with RecordingAgent() as agent:
        observed_targets = {
            target: {
                "design_family": agent.targets[target].get("design_family"),
                "flows": sorted(str(flow) for flow in agent.targets[target].get("flows", [])),
                "metadata": sorted(agent.targets[target]),
            }
            for target in targets
        }

    checks: list[dict[str, Any]] = []
    required_flows = {str(value) for value in case.get("required_flows", [])}
    required_metadata = {str(value) for value in case.get("required_metadata", [])}
    if required_flows:
        checks.append(
            _check(
                "required_flows",
                all(
                    required_flows <= set(observed_targets[target]["flows"])
                    for target in targets
                ),
                expected=sorted(required_flows),
                observed={target: observed_targets[target]["flows"] for target in targets},
            )
        )
    checks.append(
        _check(
            "required_metadata",
            all(
                required_metadata <= set(observed_targets[target]["metadata"])
                for target in targets
            ),
            expected=sorted(required_metadata),
            observed={target: observed_targets[target]["metadata"] for target in targets},
        )
    )
    expected_family = case.get("expected_design_family")
    if expected_family is not None:
        checks.append(
            _check(
                "expected_design_family",
                all(
                    observed_targets[target]["design_family"] == expected_family
                    for target in targets
                ),
                expected=expected_family,
                observed={
                    target: observed_targets[target]["design_family"] for target in targets
                },
            )
        )
    return {"targets": observed_targets}, checks, "runtime-config-contract"


def execute_case(
    domain: str,
    case: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    try:
        if domain == "tool_selection":
            observed, checks, evidence_kind = _evaluate_tool_selection(case, work_dir)
        elif domain == "failure_handling":
            observed, checks, evidence_kind = _evaluate_failure(case, work_dir)
        elif domain == "artifact_authenticity":
            observed, checks, evidence_kind = _evaluate_artifact_authenticity(case, work_dir)
        elif domain == "multi_target_consistency":
            observed, checks, evidence_kind = _evaluate_multi_target(case)
        else:
            raise ValueError("Unsupported evaluation domain: {}".format(domain))
        passed = all(check["status"] == "PASS" for check in checks)
        return {
            "id": str(case["id"]),
            "domain": domain,
            "status": "PASS" if passed else "FAIL",
            "evidence_kind": evidence_kind,
            "checks": checks,
            "observed": observed,
        }
    except Exception as exc:
        return {
            "id": str(case.get("id", "unknown")),
            "domain": domain,
            "status": "FAIL",
            "evidence_kind": "execution-error",
            "checks": [
                _check(
                    "case_execution",
                    False,
                    expected="successful execution",
                    observed="{}: {}".format(type(exc).__name__, exc),
                )
            ],
            "observed": {},
        }


def build_executable_summary(
    payload: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    summary = summarize_eval_fixture(payload)
    results: list[dict[str, Any]] = []
    if not summary["duplicate_case_ids"]:
        for suite in payload["suites"]:
            domain = str(suite["domain"])
            for case in suite["cases"]:
                case_work_dir = work_dir / str(case["id"])
                case_work_dir.mkdir(parents=True, exist_ok=True)
                results.append(execute_case(domain, dict(case), case_work_dir))

    passed_case_count = sum(case["status"] == "PASS" for case in results)
    failed_case_count = sum(case["status"] == "FAIL" for case in results)
    for domain, domain_summary in summary["domains"].items():
        domain_results = [case for case in results if case["domain"] == domain]
        domain_summary["passed"] = sum(case["status"] == "PASS" for case in domain_results)
        domain_summary["failed"] = sum(case["status"] == "FAIL" for case in domain_results)
    summary.update(
        {
            "executed_case_count": len(results),
            "passed_case_count": passed_case_count,
            "failed_case_count": failed_case_count,
            "cases": results,
            "status": (
                "PASS"
                if not summary["duplicate_case_ids"]
                and len(results) == summary["case_count"]
                and failed_case_count == 0
                else "FAIL"
            ),
        }
    )
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Agent Evaluation Report",
        "",
        "Generated by `python scripts/generate_agent_eval_report.py` from decoupled eval fixtures.",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Suites | {summary['suite_count']} |",
        f"| Cases | {summary['case_count']} |",
        f"| Executed cases | {summary['executed_case_count']} |",
        f"| Passed cases | {summary['passed_case_count']} |",
        f"| Failed cases | {summary['failed_case_count']} |",
        f"| Retained failure cases | {summary['retained_failure_cases']} |",
        f"| Targets | {len(summary['targets'])} |",
        "",
        "| Domain | Cases | Description |",
        "| --- | ---: | --- |",
    ]
    for domain, domain_summary in sorted(summary["domains"].items()):
        lines.append(
            "| {} | {} | {} |".format(
                domain.replace("_", " ").title(),
                domain_summary["case_count"],
                domain_summary["description"],
            )
        )
    lines.extend(
        [
            "",
            "| Case | Domain | Evidence | Status |",
            "| --- | --- | --- | --- |",
        ]
    )
    for case in summary["cases"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                case["id"],
                case["domain"],
                case["evidence_kind"],
                case["status"],
            )
        )
    lines.extend(["", f"Status: `{summary['status']}`", ""])
    return "\n".join(lines)


def write_report(output_dir: Path, summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "agent_eval_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "agent_eval_report.md").write_text(
        render_markdown(summary),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate machine-readable agent eval report.")
    parser.add_argument("--eval-cases", type=Path, default=DEFAULT_EVAL_CASES)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "generated")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    args = parser.parse_args()

    payload = load_eval_fixture(args.eval_cases)
    run_work_dir = args.work_dir / uuid.uuid4().hex
    summary = build_executable_summary(payload, run_work_dir)
    write_report(args.output_dir, summary)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
