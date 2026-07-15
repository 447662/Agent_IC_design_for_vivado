from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.design_eval import (  # noqa: E402
    evaluate_negative_cases,
    load_eval_manifest,
    summarize_negative_cases,
    validate_eval_manifest,
)


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Digital IC Negative Eval",
        "",
        f"- Status: **{summary['status']}**",
        f"- Executed: `{summary['executed']}`",
        f"- Passed: `{summary['passed']}`",
        f"- Failed: `{summary['failed']}`",
        f"- Vivado invoked: `{str(summary['vivado_invoked']).lower()}`",
        "- Evidence: `contract-negative`",
        "",
        "| Case | Expected | Observed | Required code | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in summary["cases"]:
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                case["id"],
                case["expected_status"],
                case["observed_status"],
                case["expected_code"],
                case["status"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_report(output_dir: Path, summary: dict[str, Any]) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    json_path = output_dir / "negative_design_eval.json"
    markdown_path = output_dir / "negative_design_eval.md"
    if json_path.exists() or markdown_path.exists():
        raise ValueError(f"Eval report already exists in: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ten contract-negative evals before Vivado invocation."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "evals" / "digital_ic" / "manifest.json",
    )
    parser.add_argument(
        "--eval-root",
        type=Path,
        default=ROOT / "evals" / "digital_ic",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = load_eval_manifest(args.manifest)
    validation = validate_eval_manifest(manifest, root=args.eval_root)
    if validation["status"] != "PASS":
        print(json.dumps(validation, ensure_ascii=False, sort_keys=True))
        return 2
    results = evaluate_negative_cases(
        manifest,
        root=args.eval_root,
        tool_observer=lambda command: None,
    )
    summary = summarize_negative_cases(results)
    paths = write_report(args.output_dir, summary)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "executed": summary["executed"],
                "passed": summary["passed"],
                "failed": summary["failed"],
                "vivado_invoked": summary["vivado_invoked"],
                "reports": [str(path) for path in paths],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
