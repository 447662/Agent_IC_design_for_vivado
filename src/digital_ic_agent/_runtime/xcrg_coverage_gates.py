from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from digital_ic_agent._runtime.xcrg_coverage import (
    _find_table,
    _project_source_file,
    _read_xcrg_page,
    _row_map,
    _score,
)


class CoverageGateEvaluation(TypedDict):
    gates: dict[str, str]
    scores: dict[str, list[float]]
    diagnostics: list[str]


def evaluate_xcrg_coverage_gates(
    project_dir: str | Path,
    xcrg_dir: str | Path,
    *,
    code_thresholds: dict[str, float],
    functional_required: bool,
    functional_threshold: float,
    included_sources: list[str],
) -> CoverageGateEvaluation:
    project_path = Path(project_dir).resolve()
    report_path = Path(xcrg_dir)
    allowed_sources = {Path(source).as_posix() for source in included_sources}
    metric_headers = {
        "statement": "statement coverage score",
        "branch": "branch coverage score",
        "condition": "condition coverage score",
        "toggle": "toggle coverage score",
    }
    unsupported_metrics = set(code_thresholds) - set(metric_headers)
    if unsupported_metrics:
        raise ValueError(
            "unsupported coverage metrics: {}".format(
                ", ".join(sorted(unsupported_metrics))
            )
        )
    for metric, threshold in code_thresholds.items():
        if not 0.0 <= float(threshold) <= 100.0:
            raise ValueError(f"invalid {metric} coverage threshold")
    if not 0.0 <= float(functional_threshold) <= 100.0:
        raise ValueError("invalid functional coverage threshold")

    scores: dict[str, list[float]] = {metric: [] for metric in code_thresholds}
    diagnostics: list[str] = []
    files_path = report_path / "codeCoverageReport" / "files.html"
    if code_thresholds:
        if not files_path.is_file():
            diagnostics.append(f"missing code coverage report: {files_path}")
        else:
            try:
                parser = _read_xcrg_page(files_path)
                table = _find_table(
                    parser.tables,
                    {"file path", *metric_headers.values()},
                )
                if table is None:
                    raise ValueError("unsupported files.html layout")
                for row in _row_map(table):
                    source_cell = row.get("file path")
                    if source_cell is None:
                        continue
                    source = _project_source_file(source_cell["text"], project_path)
                    if source is None or Path(source).as_posix() not in allowed_sources:
                        continue
                    for metric in code_thresholds:
                        cell = row.get(metric_headers[metric])
                        if cell is None:
                            diagnostics.append(f"missing {metric} score for {source}")
                            continue
                        scores[metric].append(_score(cell["text"]))
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                diagnostics.append(f"invalid code coverage report: {exc}")

    if functional_required:
        scores["functional"] = []
        groups_path = report_path / "functionalCoverageReport" / "groups.html"
        if not groups_path.is_file():
            diagnostics.append(f"missing functional coverage report: {groups_path}")
        else:
            try:
                parser = _read_xcrg_page(groups_path)
                table = _find_table(parser.tables, {"score", "goal"})
                if table is None:
                    raise ValueError("unsupported groups.html layout")
                for row in _row_map(table):
                    cell = row.get("score")
                    if cell is not None:
                        scores["functional"].append(_score(cell["text"]))
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                diagnostics.append(f"invalid functional coverage report: {exc}")

    thresholds = dict(code_thresholds)
    if functional_required:
        thresholds["functional"] = float(functional_threshold)
    gates = {
        metric: (
            "MISSING"
            if not values
            else "PASS"
            if min(values) >= float(thresholds[metric])
            else "FAIL"
        )
        for metric, values in sorted(scores.items())
    }
    return {
        "gates": gates,
        "scores": {
            metric: sorted(values)
            for metric, values in sorted(scores.items())
        },
        "diagnostics": diagnostics,
    }
