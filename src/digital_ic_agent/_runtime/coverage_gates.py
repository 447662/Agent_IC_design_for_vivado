from typing import Mapping, TypedDict


COVERAGE_METRIC_LABELS = {
    "total": "Total",
    "statement": "Statement/Line",
    "branch": "Branch",
    "condition": "Condition",
    "toggle": "Toggle",
    "functional": "Functional",
}
COVERAGE_METRIC_ORDER = tuple(COVERAGE_METRIC_LABELS)


class CoverageGateResult(TypedDict):
    metric: str
    label: str
    current: float | None
    threshold: float | None
    gap: float | None
    result: str
    diagnostic: str


def _normalize_percent(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    normalized = float(value)
    if normalized < 0.0 or normalized > 100.0:
        raise ValueError("{} must be between 0 and 100".format(field_name))
    return normalized


def evaluate_coverage_gates(
    scores: Mapping[str, float | None],
    thresholds: Mapping[str, float | None],
) -> tuple[dict[str, CoverageGateResult], bool]:
    unsupported = sorted(set(thresholds) - set(COVERAGE_METRIC_LABELS))
    if unsupported:
        raise ValueError(
            "Unsupported coverage gate metrics: {}".format(", ".join(unsupported))
        )

    results: dict[str, CoverageGateResult] = {}
    configured_results: list[str] = []
    for metric in COVERAGE_METRIC_ORDER:
        label = COVERAGE_METRIC_LABELS[metric]
        current = _normalize_percent(scores.get(metric), "{} score".format(metric))
        threshold = _normalize_percent(
            thresholds.get(metric),
            "{} threshold".format(metric),
        )
        gap = None
        result = "SKIP"
        diagnostic = "未设置阈值"
        if threshold is not None:
            if current is None:
                result = "MISSING"
                diagnostic = "数据源缺失"
            else:
                gap = round(threshold - current, 1)
                if current >= threshold:
                    result = "PASS"
                    diagnostic = "达到阈值，余量 {:.1f}%".format(abs(gap))
                else:
                    result = "FAIL"
                    diagnostic = "低于阈值，差距 {:.1f}%".format(gap)
            configured_results.append(result)

        results[metric] = {
            "metric": metric,
            "label": label,
            "current": current,
            "threshold": threshold,
            "gap": gap,
            "result": result,
            "diagnostic": diagnostic,
        }

    passed = all(result == "PASS" for result in configured_results)
    return results, passed
