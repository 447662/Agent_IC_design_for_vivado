from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import TypedDict
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROUTING_CASES = ROOT / "tests" / "fixtures" / "agent_routing_cases.json"
DEFAULT_AGENT_EVAL_CASES = ROOT / "tests" / "fixtures" / "agent_eval_cases.json"
DEFAULT_JUNIT_XML = ROOT / ".tmp" / "pytest-results.xml"
DEFAULT_COVERAGE_XML = ROOT / "coverage.xml"
DEFAULT_CAPABILITY_EVIDENCE = (
    ROOT / "docs" / "testing" / "evidence" / "synthpilot_tools_list.json"
)
DEFAULT_AGENT_CONFIG = ROOT / ".trae" / "agent" / "agent.json"
README_START = "<!-- digital-ic-agent:quality:start -->"
README_END = "<!-- digital-ic-agent:quality:end -->"
MIN_ROUTING_CASES = 50
STALE_README_SNIPPETS = (
    "--cov-fail-under=68",
    "当前完整回归：`155 passed`；整体覆盖率为 `75.87%`，CI 门槛为 `68%。",
    "当前完整回归：`155 passed`；整体覆盖率为 `75.87%`，CI 门槛为 `68%`。",
)
VOLATILE_README_METRICS = (
    "Pytest failed",
    "Pytest errors",
    "Pytest skipped",
    "Pytest runtime seconds",
)


class CapabilitySummary(TypedDict):
    name: str
    requirement: str
    failure_impact: str
    captured_at: str
    source_status: str
    status: str


class QualityProvenance(TypedDict):
    source: str
    commit_sha: str
    generated_at: str
    run_id: str
    run_url: str


def validate_provenance(
    *,
    source: str,
    commit_sha: str,
    generated_at: str,
    run_id: str,
    run_url: str,
) -> QualityProvenance:
    if source not in {"local", "ci"}:
        raise ValueError("provenance source must be local or ci")
    if re.fullmatch(r"[0-9a-f]{40}", commit_sha) is None:
        raise ValueError("provenance commit_sha must be a 40-character lowercase Git SHA")
    if not generated_at.endswith("Z"):
        raise ValueError("provenance generated_at must be an ISO-8601 UTC timestamp")
    try:
        parsed_at = datetime.fromisoformat(generated_at.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError("provenance generated_at must be an ISO-8601 UTC timestamp") from exc
    if parsed_at.tzinfo is None or parsed_at.utcoffset() != UTC.utcoffset(parsed_at):
        raise ValueError("provenance generated_at must be an ISO-8601 UTC timestamp")
    if source == "ci":
        if not run_id or not run_url:
            raise ValueError("CI provenance requires run_id and run_url")
        expected_suffix = "/actions/runs/{}".format(run_id)
        if not run_url.startswith("https://github.com/") or expected_suffix not in run_url:
            raise ValueError("CI provenance run_url must identify its GitHub Actions run_id")
    elif run_id or run_url:
        raise ValueError("local provenance must not claim a CI run_id or run_url")
    return {
        "source": source,
        "commit_sha": commit_sha,
        "generated_at": generated_at,
        "run_id": run_id,
        "run_url": run_url,
    }


def _current_commit_sha(root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git rev-parse HEAD failed")
    return result.stdout.strip().lower()


def _current_utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _read_xml(path: Path) -> ET.Element:
    return ET.fromstring(path.read_text(encoding="utf-8"))


def _parse_int_attr(node: ET.Element, name: str) -> int:
    value = node.attrib.get(name, "0")
    return int(float(value))


def _sum_child_int_attr(node: ET.Element, name: str) -> int:
    return sum(_parse_int_attr(child, name) for child in node.findall("testsuite"))


def _sum_child_time(node: ET.Element) -> float:
    return sum(float(child.attrib.get("time", "0") or 0) for child in node.findall("testsuite"))


def parse_junit(path: Path) -> dict[str, int | float]:
    root = _read_xml(path)
    if root.tag == "testsuites":
        if "tests" not in root.attrib and root.findall("testsuite"):
            return {
                "tests": _sum_child_int_attr(root, "tests"),
                "failures": _sum_child_int_attr(root, "failures"),
                "errors": _sum_child_int_attr(root, "errors"),
                "skipped": _sum_child_int_attr(root, "skipped"),
                "time": _sum_child_time(root),
            }
        return {
            "tests": _parse_int_attr(root, "tests"),
            "failures": _parse_int_attr(root, "failures"),
            "errors": _parse_int_attr(root, "errors"),
            "skipped": _parse_int_attr(root, "skipped"),
            "time": float(root.attrib.get("time", "0") or 0),
        }
    if root.tag == "testsuite":
        return {
            "tests": _parse_int_attr(root, "tests"),
            "failures": _parse_int_attr(root, "failures"),
            "errors": _parse_int_attr(root, "errors"),
            "skipped": _parse_int_attr(root, "skipped"),
            "time": float(root.attrib.get("time", "0") or 0),
        }
    raise ValueError(f"Unsupported JUnit root element: {root.tag}")


def parse_coverage(path: Path) -> dict[str, float]:
    root = _read_xml(path)
    return {
        "line_rate": float(root.attrib.get("line-rate", "0") or 0),
        "branch_rate": float(root.attrib.get("branch-rate", "0") or 0),
    }


def coverage_gate_violations(
    coverage: dict[str, float],
    *,
    minimum_line_rate: float,
    minimum_branch_rate: float,
) -> list[str]:
    violations = []
    if coverage["line_rate"] < minimum_line_rate:
        violations.append(
            "line coverage {:.2%} is below {:.2%}".format(
                coverage["line_rate"],
                minimum_line_rate,
            )
        )
    if coverage["branch_rate"] < minimum_branch_rate:
        violations.append(
            "branch coverage {:.2%} is below {:.2%}".format(
                coverage["branch_rate"],
                minimum_branch_rate,
            )
        )
    return violations


def count_routing_cases(path: Path) -> int:
    if not path.exists():
        raise FileNotFoundError(f"Routing evaluation fixture does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Routing cases must be a JSON list: {path}")
    case_count = len(data)
    if case_count < MIN_ROUTING_CASES:
        raise ValueError(
            f"Routing evaluation fixture must contain at least {MIN_ROUTING_CASES} cases: "
            f"{path} contains {case_count}"
        )
    return case_count


def summarize_agent_eval_cases(path: Path) -> dict[str, int]:
    if not path.exists():
        raise FileNotFoundError(f"Agent evaluation fixture does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(f"Agent evaluation fixture schema_version must be 1: {path}")
    suites = data.get("suites", [])
    if not isinstance(suites, list) or not suites:
        raise ValueError(f"Agent evaluation fixture must define non-empty suites: {path}")
    summary: dict[str, int] = {}
    for suite in suites:
        if not isinstance(suite, dict):
            raise ValueError(f"Agent evaluation suite must be an object: {path}")
        domain = str(suite["domain"])
        if not domain:
            raise ValueError(f"Agent evaluation suite domain must not be empty: {path}")
        if domain in summary:
            raise ValueError(f"Agent evaluation suite domain must be unique: {domain}")
        cases = suite.get("cases", [])
        if not isinstance(cases, list) or not cases:
            raise ValueError(f"Eval suite cases must be a non-empty list: {domain}")
        summary[domain] = len(cases)
    return summary


def parse_capability_evidence(
    evidence_path: Path,
    agent_config_path: Path,
) -> CapabilitySummary:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    config = json.loads(agent_config_path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict) or not isinstance(evidence.get("capability"), dict):
        raise ValueError(f"Capability evidence must contain a capability object: {evidence_path}")
    capability = evidence["capability"]
    name = str(capability.get("name", "")).strip()
    source_status = str(evidence.get("status", "")).strip().upper()
    captured_at = str(evidence.get("captured_at", "")).strip()
    if not name or not source_status or not captured_at.endswith("Z"):
        raise ValueError(f"Capability evidence is incomplete: {evidence_path}")
    if source_status not in {"PASS", "FAIL", "BLOCKED"}:
        raise ValueError(f"Capability evidence has invalid status: {source_status}")
    mcp_servers = config.get("mcpServers") if isinstance(config, dict) else None
    configured = mcp_servers.get(name) if isinstance(mcp_servers, dict) else None
    if not isinstance(configured, dict) or not isinstance(configured.get("required"), bool):
        raise ValueError(f"Capability evidence is not declared in agent config: {name}")
    required = bool(configured["required"])
    requirement = "required" if required else "optional"
    failure_impact = "release-blocking" if required else "degraded-only"
    if capability.get("requirement") != requirement:
        raise ValueError(
            "Capability evidence requirement does not match agent config: {}".format(
                name
            )
        )
    if capability.get("failure_impact") != failure_impact:
        raise ValueError(
            "Capability evidence failure impact does not match agent config: {}".format(
                name
            )
        )
    if source_status == "PASS":
        normalized_status = "PASS"
    elif required:
        normalized_status = "BLOCKED"
    else:
        normalized_status = "WARN"
    declared_normalized = evidence.get("normalized_status")
    if declared_normalized is not None and declared_normalized != normalized_status:
        raise ValueError(
            "Capability evidence normalized status does not match derived status: {}".format(
                name
            )
        )
    return {
        "name": name,
        "requirement": requirement,
        "failure_impact": failure_impact,
        "captured_at": captured_at,
        "source_status": source_status,
        "status": normalized_status,
    }


def has_blocked_capability(capability_summary: CapabilitySummary | None) -> bool:
    return capability_summary is not None and capability_summary["status"] == "BLOCKED"


def build_quality_summary(
    junit: dict[str, int | float],
    coverage: dict[str, float],
    routing_cases: int,
    eval_case_summary: dict[str, int] | None = None,
    data_scope: str = "local quality evidence",
    capability_summary: CapabilitySummary | None = None,
    provenance: QualityProvenance | None = None,
) -> str:
    eval_case_total = sum((eval_case_summary or {}).values())
    lines = [
            "# Quality Summary",
            "",
            "Generated by `python scripts/generate_quality_summary.py` from JUnit XML and coverage XML artifacts.",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Data scope | {data_scope} |",
            f"| Pytest total | {junit['tests']} |",
            f"| Pytest failed | {junit['failures']} |",
            f"| Pytest errors | {junit['errors']} |",
            f"| Pytest skipped | {junit['skipped']} |",
            f"| Line coverage | {_percent(float(coverage['line_rate']))} |",
            f"| Branch coverage | {_percent(float(coverage['branch_rate']))} |",
            f"| Routing evaluation cases | {routing_cases} |",
            f"| Additional agent evaluation cases | {eval_case_total} |",
    ]
    if provenance is not None:
        provenance_rows = [
            f"| {field} | {provenance[field]} |"
            for field in ("source", "commit_sha", "generated_at", "run_id", "run_url")
        ]
        lines[7:7] = provenance_rows
    if capability_summary is not None:
        lines.append(
            "| Capability {name} | {status} ({requirement}; {failure_impact}; "
            "source {source_status}; captured {captured_at}) |".format(
                **capability_summary
            )
        )
    lines.append("")
    return "\n".join(lines)


def build_capability_matrix(
    routing_cases: int,
    eval_case_summary: dict[str, int] | None = None,
    capability_summary: CapabilitySummary | None = None,
) -> str:
    routing_cases_path = DEFAULT_ROUTING_CASES.relative_to(ROOT).as_posix()
    eval_cases_path = DEFAULT_AGENT_EVAL_CASES.relative_to(ROOT).as_posix()
    lines = [
        "# Capability Matrix",
        "",
        "Generated by `python scripts/generate_quality_summary.py` from repository evaluation fixtures and CI artifacts.",
        "",
        "| Capability | Evidence | Status |",
        "| --- | --- | --- |",
        f"| Requirement routing | `{routing_cases_path}` ({routing_cases} cases) | Automated eval fixture |",
    ]
    for domain, count in sorted((eval_case_summary or {}).items()):
        label = domain.replace("_", " ").title()
        lines.append(f"| {label} | `{eval_cases_path}` ({count} cases) | Automated eval fixture |")
    if capability_summary is not None:
        lines.append(
            "| MCP {name} | `docs/testing/evidence/synthpilot_tools_list.json` "
            "({requirement}; {failure_impact}; source {source_status}; "
            "captured {captured_at}) | {status} |".format(
                **capability_summary
            )
        )
    lines.extend(
        [
            "| Agent evaluation report | `docs/generated/agent_eval_report.json` plus Markdown summary | Generated in CI |",
            "| Test module size report | `docs/generated/test_module_report.json` plus Markdown summary | Generated in CI |",
            "| Quality summary | JUnit XML plus coverage XML | Generated in CI |",
            "| README quality block | Marker-delimited generated content | Auto-updated by generator |",
            "",
        ]
    )
    return "\n".join(lines)


def render_readme_block(summary: str) -> str:
    body = summary.splitlines()
    if body and body[0] == "# Quality Summary":
        body[0] = "## 自动质量摘要"
    metrics = {}
    for line in body:
        if line.startswith("|"):
            columns = [column.strip() for column in line.strip("|").split("|")]
            if len(columns) == 2:
                metrics[columns[0]] = columns[1]
    failure_count = int(float(metrics.get("Pytest failed", "0")))
    error_count = int(float(metrics.get("Pytest errors", "0")))
    test_result = "PASS" if failure_count == 0 and error_count == 0 else "FAIL"
    body = [
        line
        for line in body
        if not any(line.startswith(f"| {metric} |") for metric in VOLATILE_README_METRICS)
    ]
    for index, line in enumerate(body):
        if line.startswith("| Data scope |"):
            body.insert(index + 1, f"| Test result | {test_result} |")
            break
    body.insert(
        2,
        "此区块由生成器维护；本地样例运行仅用于验证格式，正式数值以最新 CI 全量产物为准。",
    )
    body.insert(3, "")
    return "\n".join(body).strip() + "\n"


def replace_marked_block(readme: str, block: str) -> str:
    replacement = f"{README_START}\n{block.rstrip()}\n{README_END}"
    if README_START in readme and README_END in readme:
        before, rest = readme.split(README_START, 1)
        _, after = rest.split(README_END, 1)
        return before + replacement + after
    return readme.rstrip() + "\n\n" + replacement + "\n"


def write_outputs(
    output_dir: Path,
    quality_summary: str,
    capability_matrix: str,
    provenance: QualityProvenance,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "quality_summary.md").write_text(quality_summary, encoding="utf-8")
    (output_dir / "capability_matrix.md").write_text(capability_matrix, encoding="utf-8")
    (output_dir / "quality_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def clean_stale_readme_stats(readme: str) -> str:
    for snippet in STALE_README_SNIPPETS:
        readme = readme.replace(snippet, "")
    return readme


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate quality summary documentation.")
    parser.add_argument("--junitxml", type=Path, default=DEFAULT_JUNIT_XML)
    parser.add_argument("--coverage-xml", type=Path, default=DEFAULT_COVERAGE_XML)
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "generated")
    parser.add_argument("--routing-cases", type=Path, default=DEFAULT_ROUTING_CASES)
    parser.add_argument("--agent-eval-cases", type=Path, default=DEFAULT_AGENT_EVAL_CASES)
    parser.add_argument(
        "--capability-evidence",
        type=Path,
        default=DEFAULT_CAPABILITY_EVIDENCE,
    )
    parser.add_argument("--agent-config", type=Path, default=DEFAULT_AGENT_CONFIG)
    parser.add_argument("--data-scope", default="local quality evidence")
    parser.add_argument("--source", choices=("local", "ci"), default="local")
    parser.add_argument("--commit-sha")
    parser.add_argument("--generated-at")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--minimum-line-rate", type=float, default=0.90)
    parser.add_argument("--minimum-branch-rate", type=float, default=0.80)
    parser.add_argument("--write-readme", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    junit = parse_junit(args.junitxml)
    coverage = parse_coverage(args.coverage_xml)
    routing_cases = count_routing_cases(args.routing_cases)
    eval_case_summary = summarize_agent_eval_cases(args.agent_eval_cases)
    capability_summary = parse_capability_evidence(
        args.capability_evidence,
        args.agent_config,
    )
    provenance = validate_provenance(
        source=args.source,
        commit_sha=(args.commit_sha or _current_commit_sha()),
        generated_at=(args.generated_at or _current_utc_timestamp()),
        run_id=args.run_id,
        run_url=args.run_url,
    )
    coverage_violations = coverage_gate_violations(
        coverage,
        minimum_line_rate=args.minimum_line_rate,
        minimum_branch_rate=args.minimum_branch_rate,
    )
    quality_summary = build_quality_summary(
        junit,
        coverage,
        routing_cases,
        eval_case_summary,
        args.data_scope,
        capability_summary,
        provenance,
    )
    capability_matrix = build_capability_matrix(
        routing_cases,
        eval_case_summary,
        capability_summary,
    )

    write_outputs(args.output_dir, quality_summary, capability_matrix, provenance)

    if args.write_readme:
        readme = clean_stale_readme_stats(args.readme.read_text(encoding="utf-8"))
        updated = replace_marked_block(readme, render_readme_block(quality_summary))
        args.readme.write_text(updated, encoding="utf-8")

    for violation in coverage_violations:
        print(f"QUALITY_GATE_ERROR: {violation}", file=sys.stderr)
    if has_blocked_capability(capability_summary):
        return 2
    return 3 if coverage_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
