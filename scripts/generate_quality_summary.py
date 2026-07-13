from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROUTING_CASES = ROOT / "tests" / "fixtures" / "agent_routing_cases.json"
DEFAULT_AGENT_EVAL_CASES = ROOT / "tests" / "fixtures" / "agent_eval_cases.json"
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


def build_quality_summary(
    junit: dict[str, int | float],
    coverage: dict[str, float],
    routing_cases: int,
    eval_case_summary: dict[str, int] | None = None,
    data_scope: str = "CI full quality artifact",
) -> str:
    eval_case_total = sum((eval_case_summary or {}).values())
    return "\n".join(
        [
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
            f"| Pytest runtime seconds | {float(junit['time']):.2f} |",
            f"| Line coverage | {_percent(float(coverage['line_rate']))} |",
            f"| Branch coverage | {_percent(float(coverage['branch_rate']))} |",
            f"| Routing evaluation cases | {routing_cases} |",
            f"| Additional agent evaluation cases | {eval_case_total} |",
            "",
        ]
    )


def build_capability_matrix(
    routing_cases: int,
    eval_case_summary: dict[str, int] | None = None,
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
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "quality_summary.md").write_text(quality_summary, encoding="utf-8")
    (output_dir / "capability_matrix.md").write_text(capability_matrix, encoding="utf-8")


def clean_stale_readme_stats(readme: str) -> str:
    for snippet in STALE_README_SNIPPETS:
        readme = readme.replace(snippet, "")
    return readme


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate quality summary documentation.")
    parser.add_argument("--junitxml", type=Path, required=True)
    parser.add_argument("--coverage-xml", type=Path, required=True)
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "generated")
    parser.add_argument("--routing-cases", type=Path, default=DEFAULT_ROUTING_CASES)
    parser.add_argument("--agent-eval-cases", type=Path, default=DEFAULT_AGENT_EVAL_CASES)
    parser.add_argument("--data-scope", default="CI full quality artifact")
    parser.add_argument("--write-readme", action="store_true")
    args = parser.parse_args()

    junit = parse_junit(args.junitxml)
    coverage = parse_coverage(args.coverage_xml)
    routing_cases = count_routing_cases(args.routing_cases)
    eval_case_summary = summarize_agent_eval_cases(args.agent_eval_cases)
    quality_summary = build_quality_summary(
        junit,
        coverage,
        routing_cases,
        eval_case_summary,
        args.data_scope,
    )
    capability_matrix = build_capability_matrix(routing_cases, eval_case_summary)

    write_outputs(args.output_dir, quality_summary, capability_matrix)

    if args.write_readme:
        readme = clean_stale_readme_stats(args.readme.read_text(encoding="utf-8"))
        updated = replace_marked_block(readme, render_readme_block(quality_summary))
        args.readme.write_text(updated, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
