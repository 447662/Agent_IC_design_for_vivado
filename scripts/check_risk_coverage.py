from __future__ import annotations

import argparse
from pathlib import Path
from collections.abc import Mapping
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
RISK_MODULE_THRESHOLDS: dict[str, dict[str, float]] = {
    "_runtime/agent_provider.py": {"line": 0.85, "branch": 0.75},
    "_runtime/mcp_client.py": {"line": 0.93, "branch": 0.87},
    "_runtime/plugin_guard_runner.py": {"line": 0.87, "branch": 0.78},
    "_runtime/agent_execution.py": {"line": 0.94, "branch": 0.90},
    "_runtime/agent_cli_dispatch.py": {"line": 0.82, "branch": 0.75},
    "_runtime/agent_async_fifo_flows.py": {"line": 0.70, "branch": 0.80},
}


def _coverage_rates(path: Path) -> dict[str, dict[str, float]]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    rates: dict[str, dict[str, float]] = {}
    for class_node in root.findall("./packages/package/classes/class"):
        filename = class_node.attrib.get("filename", "").replace("\\", "/")
        if not filename:
            continue
        rates[filename] = {
            "line": float(class_node.attrib.get("line-rate", "0") or 0),
            "branch": float(class_node.attrib.get("branch-rate", "0") or 0),
        }
    return rates


def find_coverage_violations(
    coverage_xml: Path,
    thresholds: Mapping[str, Mapping[str, float]] = RISK_MODULE_THRESHOLDS,
) -> list[str]:
    actual_rates = _coverage_rates(coverage_xml)
    violations: list[str] = []
    for module, required_rates in thresholds.items():
        matches = [rates for filename, rates in actual_rates.items() if filename.endswith(module)]
        if len(matches) != 1:
            violations.append("{} missing coverage data".format(module))
            continue
        actual = matches[0]
        for metric in ("line", "branch"):
            required = required_rates[metric]
            if actual[metric] < required:
                violations.append(
                    "{} {} coverage {:.2%} is below {:.2%}".format(
                        module,
                        metric,
                        actual[metric],
                        required,
                    )
                )
    return violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enforce risk-oriented module coverage gates.")
    parser.add_argument("--coverage-xml", type=Path, default=ROOT / "coverage.xml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    violations = find_coverage_violations(args.coverage_xml)
    for violation in violations:
        print("RISK_COVERAGE_ERROR: {}".format(violation), file=sys.stderr)
    if violations:
        return 1
    print("Risk-oriented module coverage: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
