from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.eval_summary import (  # noqa: E402
    aggregate_eval_reports,
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Eval report must be an object: {path}")
    return payload


def _summary(path: Path) -> dict[str, object]:
    content = Path(path).read_bytes()
    return {
        "path": Path(path).name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    lines = [
        "# P7 Real Eval Summary",
        "",
        f"- Status: **{summary['status']}**",
        f"- Generation: `{totals['generation']}/10`",
        f"- Repair: `{totals['repair']}/10`",
        f"- Negative: `{totals['negative']}/10`",
        f"- Overall: `{totals['overall']}/30`",
        f"- Defects detected: `{totals['defects_detected']}/10`",
        f"- Defects repaired: `{totals['repaired']}/10`",
        "",
        "## Source Reports",
        "",
        "| Report | SHA-256 | Bytes |",
        "| --- | --- | ---: |",
    ]
    for name, report in summary["source_reports"].items():
        lines.append(f"| {name} | `{report['sha256']}` | {report['size_bytes']} |")
    lines.extend(("", "## Issues", ""))
    if summary["issues"]:
        lines.extend(("| Code | Path | Message |", "| --- | --- | --- |"))
        for issue in summary["issues"]:
            lines.append(
                f"| {issue['code']} | `{issue['path']}` | {issue['message']} |"
            )
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate fail-closed P7 eval evidence.")
    parser.add_argument("--generation-report", type=Path, required=True)
    parser.add_argument("--repair-prepare-report", type=Path, required=True)
    parser.add_argument("--repair-report", type=Path, required=True)
    parser.add_argument("--negative-report", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    paths = {
        "generation": args.generation_report,
        "repair_prepare": args.repair_prepare_report,
        "repair": args.repair_report,
        "negative": args.negative_report,
    }
    summary = aggregate_eval_reports(
        generation=_load(paths["generation"]),
        repair_prepare=_load(paths["repair_prepare"]),
        repair=_load(paths["repair"]),
        negative=_load(paths["negative"]),
    )
    summary["source_reports"] = {
        name: _summary(path) for name, path in paths.items()
    }
    for output in (args.json_output, args.markdown_output):
        if output.exists():
            raise ValueError(f"Output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
