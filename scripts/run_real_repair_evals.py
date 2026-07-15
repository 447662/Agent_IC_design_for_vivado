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
    load_eval_manifest,
    prepare_repair_cases,
    validate_eval_manifest,
    verify_repaired_cases,
)


def render_markdown(summary: dict[str, Any]) -> str:
    phase = str(summary["suite"])
    lines = [
        "# Real Digital IC Repair Eval",
        "",
        f"- Phase: `{phase}`",
        f"- Status: **{summary['status']}**",
        f"- Executed: `{summary['executed']}`",
        "- Evidence: `real-vivado-repair`",
    ]
    if phase == "repair-prepare":
        lines.extend(
            (
                f"- Detected: `{summary['detected']}`",
                f"- Failed detection: `{summary['failed_detection']}`",
            )
        )
    else:
        lines.extend(
            (
                f"- Repaired: `{summary['repaired']}`",
                f"- Required repaired: `{summary['required_repaired']}`",
                f"- Failed repair: `{summary['failed_repair']}`",
            )
        )
    lines.extend(("", "| Case | Design | Iteration | Status |", "| --- | --- | ---: | --- |"))
    for case in summary["cases"]:
        iteration = case.get("iteration", "")
        lines.append(
            f"| {case['id']} | {case['design_template']} | {iteration} | {case['status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(output_dir: Path, summary: dict[str, Any]) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    stem = "real_design_repair_prepare" if summary["suite"] == "repair-prepare" else "real_design_repair_eval"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
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
        description="Prepare or verify ten bounded real Vivado repair evals."
    )
    parser.add_argument("phase", choices=("prepare", "verify"))
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
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--vivado-bin", type=Path, required=True)
    parser.add_argument(
        "--vivado-launch-mode",
        choices=("direct", "project"),
        default="direct",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = load_eval_manifest(args.manifest)
    validation = validate_eval_manifest(manifest, root=args.eval_root)
    if validation["status"] != "PASS":
        print(json.dumps(validation, ensure_ascii=False, sort_keys=True))
        return 2
    if args.phase == "prepare":
        summary = prepare_repair_cases(
            manifest,
            root=args.eval_root,
            work_root=args.work_root,
            vivado_bin=args.vivado_bin,
            vivado_launch_mode=args.vivado_launch_mode,
        )
    else:
        summary = verify_repaired_cases(
            manifest,
            root=args.eval_root,
            work_root=args.work_root,
            vivado_bin=args.vivado_bin,
            vivado_launch_mode=args.vivado_launch_mode,
        )
    paths = write_report(args.output_dir, summary)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "suite": summary["suite"],
                "executed": summary["executed"],
                "passed": (
                    summary.get("detected")
                    if args.phase == "prepare"
                    else summary.get("repaired")
                ),
                "reports": [str(path) for path in paths],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
