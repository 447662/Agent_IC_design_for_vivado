import fnmatch
import re
from typing import Any, TypedDict

from xcrg_coverage import CoverageItem


PRIORITY_ORDER = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2,
}
GENERIC_SCENARIO_TOKENS = {
    "boundary",
    "functional",
    "recovery",
    "scenario",
    "stress",
    "sweep",
    "test",
}


class ScenarioRecommendation(TypedDict):
    scenario_id: str
    scenario_type: str
    purpose: str
    priority: str
    evidence_count: int
    matched_items: list[str]
    matched_metrics: list[str]
    source_reports: list[str]
    reason: str


class ScenarioRecommendationResult(TypedDict):
    recommended_scenarios: list[str]
    recommendations: list[ScenarioRecommendation]


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [
            _clean_text(item)
            for item in value
            if _clean_text(item)
        ]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _priority(value: object) -> str:
    priority = _clean_text(value).upper()
    return priority if priority in PRIORITY_ORDER else "MEDIUM"


def _scenario_tokens(
    scenario: dict[str, Any],
    coverage_match: dict[str, Any],
) -> list[str]:
    explicit_tokens = _string_list(coverage_match.get("tokens", []))
    if explicit_tokens:
        return [token.casefold() for token in explicit_tokens]
    return [
        token
        for token in re.split(
            r"[^a-z0-9]+",
            _clean_text(scenario.get("id", "")).casefold(),
        )
        if token and token not in GENERIC_SCENARIO_TOKENS
    ]


def _item_name(item: CoverageItem) -> str:
    details = item.get("details", {})
    detail_name = (
        _clean_text(details.get("name", ""))
        if isinstance(details, dict)
        else ""
    )
    return (
        detail_name
        or _clean_text(item.get("instance", ""))
        or _clean_text(item.get("source_file", ""))
        or _clean_text(item.get("metric", ""))
    )


def _item_text(item: CoverageItem) -> str:
    details = item.get("details", {})
    detail_values = (
        [_clean_text(value) for value in details.values()]
        if isinstance(details, dict)
        else [_clean_text(details)]
    )
    return " ".join(
        [
            _clean_text(item.get("source_file", "")),
            _clean_text(item.get("instance", "")),
            _clean_text(item.get("metric", "")),
            *detail_values,
        ]
    ).casefold()


def _matches_source(source_file: str, patterns: list[str]) -> bool:
    source = source_file.replace("\\", "/").casefold()
    return any(
        fnmatch.fnmatchcase(source, pattern.replace("\\", "/").casefold())
        for pattern in patterns
    )


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _reason(matched_items: list[str]) -> str:
    preview = ", ".join(matched_items[:3])
    if len(matched_items) > 3:
        preview += " 等 {} 项".format(len(matched_items))
    return "匹配低覆盖项：{}".format(preview)


def recommend_scenarios(
    low_coverage_items: list[CoverageItem],
    scenario_catalog: list[dict[str, Any]],
) -> ScenarioRecommendationResult:
    ranked: list[tuple[int, int, ScenarioRecommendation]] = []
    for catalog_index, scenario in enumerate(scenario_catalog):
        if _clean_text(scenario.get("status", "")).upper() != "PASS":
            continue
        scenario_id = _clean_text(scenario.get("id", ""))
        if not scenario_id:
            continue

        raw_coverage_match = scenario.get("coverage_match", {})
        coverage_match = (
            raw_coverage_match
            if isinstance(raw_coverage_match, dict)
            else {}
        )
        tokens = _scenario_tokens(scenario, coverage_match)
        metrics = {
            metric.casefold()
            for metric in _string_list(
                coverage_match.get("metrics", [])
            )
        }
        source_patterns = _string_list(
            coverage_match.get("source_patterns", [])
        )
        fallback = bool(coverage_match.get("fallback", False))
        priority = _priority(coverage_match.get("priority", "MEDIUM"))

        matched: list[CoverageItem] = []
        for item in low_coverage_items:
            metric = _clean_text(item.get("metric", "")).casefold()
            if metrics and metric not in metrics:
                continue
            token_match = any(
                token in _item_text(item)
                for token in tokens
            )
            source_match = _matches_source(
                _clean_text(item.get("source_file", "")),
                source_patterns,
            )
            if token_match or source_match or fallback:
                matched.append(item)

        if not matched:
            continue

        matched_items = _unique([_item_name(item) for item in matched])
        matched_metrics = _unique(
            [_clean_text(item.get("metric", "")) for item in matched]
        )
        source_reports = _unique(
            [
                _clean_text(item.get("source_report", ""))
                for item in matched
                if _clean_text(item.get("source_report", ""))
            ]
        )
        recommendation: ScenarioRecommendation = {
            "scenario_id": scenario_id,
            "scenario_type": _clean_text(scenario.get("type", "")),
            "purpose": _clean_text(scenario.get("purpose", "")),
            "priority": priority,
            "evidence_count": len(matched),
            "matched_items": matched_items,
            "matched_metrics": matched_metrics,
            "source_reports": source_reports,
            "reason": _reason(matched_items),
        }
        ranked.append(
            (
                PRIORITY_ORDER[priority],
                catalog_index,
                recommendation,
            )
        )

    recommendations = [
        recommendation
        for _, _, recommendation in sorted(
            ranked,
            key=lambda item: (item[0], item[1]),
        )
    ]
    return {
        "recommended_scenarios": [
            item["scenario_id"]
            for item in recommendations
        ],
        "recommendations": recommendations,
    }
