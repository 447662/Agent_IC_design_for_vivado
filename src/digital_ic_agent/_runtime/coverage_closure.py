import json
from pathlib import Path
from typing import Any

from digital_ic_agent._runtime.coverage_closure_core import (
    CoverageClosureAgent,
    collect_coverage_targets,
    coverage_closure_status,
    parse_coverage_scores,
    parse_gate_threshold,
    _utc_timestamp,
)
from digital_ic_agent._runtime.coverage_closure_render import (
    render_coverage_closure_html,
    render_coverage_closure_markdown,
)


__all__ = [
    "CoverageClosureAgent",
    "collect_coverage_targets",
    "coverage_closure_status",
    "parse_coverage_scores",
    "parse_gate_threshold",
    "render_coverage_closure_html",
    "render_coverage_closure_markdown",
    "write_coverage_closure_report",
]


def write_coverage_closure_report(
    agent: CoverageClosureAgent,
    output_dir: str | Path = "outputs",
    target_threshold: float = 80.0,
) -> dict[str, Any]:
    targets = collect_coverage_targets(
        agent,
        output_dir=output_dir,
        target_threshold=target_threshold,
    )
    status = coverage_closure_status(targets)
    generated_at = _utc_timestamp()
    report_dir = Path(output_dir) / "coverage-closure"
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / "index.md"
    html_path = report_dir / "index.html"
    markdown_path.write_text(
        render_coverage_closure_markdown(
            targets,
            status,
            float(target_threshold),
            generated_at,
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        render_coverage_closure_html(
            targets,
            status,
            float(target_threshold),
            generated_at,
        ),
        encoding="utf-8",
    )
    low_coverage_items_path = report_dir / "low_coverage_items.json"
    low_coverage_items_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "target_threshold": float(target_threshold),
                "targets": [
                    {
                        "name": target["name"],
                        "low_coverage_items": target["low_coverage_items"],
                        "diagnostics": target["low_coverage_diagnostics"],
                        "recommended_scenarios": target[
                            "recommended_scenarios"
                        ],
                        "scenario_recommendations": target[
                            "scenario_recommendations"
                        ],
                    }
                    for target in targets
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "status": status,
        "target_count": len(targets),
        "gap_target_count": sum(
            target["status"] in {"GAP", "MISSING"}
            for target in targets
        ),
        "skipped_target_count": sum(
            target["status"] == "SKIP"
            for target in targets
        ),
        "not_run_target_count": sum(
            target["status"] == "NOT_RUN"
            for target in targets
        ),
        "targets": targets,
        "markdown_path": markdown_path,
        "html_path": html_path,
        "low_coverage_items_path": low_coverage_items_path,
    }
