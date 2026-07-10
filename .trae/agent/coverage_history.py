import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from artifact_manifest import normalize_json_value, utc_timestamp
from coverage_gates import COVERAGE_METRIC_LABELS, COVERAGE_METRIC_ORDER
from history_rotation import (
    DEFAULT_ACTIVE_RECORD_LIMIT,
    build_rotation_metadata,
    rotate_json_records,
)


SCHEMA_VERSION = 1
VALID_STATUSES = {"PASS", "FAIL"}
ROTATION_METADATA_SCHEMA_VERSION = 1


def _normalize_status(status: str) -> str:
    normalized = str(status).upper()
    if normalized not in VALID_STATUSES:
        raise ValueError("invalid coverage history status: {}".format(status))
    return normalized


def _normalize_metrics(
    coverage_metrics: Mapping[str, float | None],
) -> dict[str, float | None]:
    unsupported = sorted(set(coverage_metrics) - set(COVERAGE_METRIC_ORDER))
    if unsupported:
        raise ValueError(
            "unsupported coverage history metrics: {}".format(
                ", ".join(unsupported)
            )
        )
    normalized: dict[str, float | None] = {}
    for metric in COVERAGE_METRIC_ORDER:
        value = coverage_metrics.get(metric)
        normalized[metric] = None if value is None else float(value)
    return normalized


def build_coverage_history_record(
    *,
    target_name: str,
    flow_name: str,
    toolchain: Mapping[str, Any],
    seed_set: Sequence[int],
    coverage_metrics: Mapping[str, float | None],
    coverage_gates: Mapping[str, Any],
    status: str,
    recorded_at: str | None = None,
    sources: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": recorded_at or utc_timestamp(),
        "target_name": str(target_name),
        "flow_name": str(flow_name),
        "toolchain": normalize_json_value(dict(toolchain)),
        "seed_set": [int(seed) for seed in seed_set],
        "coverage_metrics": _normalize_metrics(coverage_metrics),
        "coverage_gates": normalize_json_value(dict(coverage_gates)),
        "status": _normalize_status(status),
        "sources": normalize_json_value(dict(sources or {})),
    }


def load_coverage_history(history_path: Path) -> list[dict[str, Any]]:
    history_path = Path(history_path)
    if not history_path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        history_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid coverage history JSON at line {}".format(line_number)
            ) from exc
        if not isinstance(record, dict):
            raise ValueError(
                "coverage history line {} must be an object".format(line_number)
            )
        if record.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                "unsupported coverage history schema at line {}".format(
                    line_number
                )
            )
        records.append(record)
    return records


def calculate_metric_deltas(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, float | None]:
    if len(records) < 2:
        return {metric: None for metric in COVERAGE_METRIC_ORDER}

    previous_metrics = records[-2].get("coverage_metrics", {})
    latest_metrics = records[-1].get("coverage_metrics", {})
    deltas: dict[str, float | None] = {}
    for metric in COVERAGE_METRIC_ORDER:
        previous = previous_metrics.get(metric)
        latest = latest_metrics.get(metric)
        if previous is None or latest is None:
            deltas[metric] = None
        else:
            deltas[metric] = round(float(latest) - float(previous), 1)
    return deltas


def _percent(value: Any) -> str:
    return "N/A" if value is None else "{:.1f}%".format(float(value))


def _delta(value: float | None) -> str:
    if value is None:
        return "N/A"
    return "{:+.1f}%".format(value)


def _delta_class(value: float | None) -> str:
    if value is None or value == 0:
        return "trend-flat"
    return "trend-up" if value > 0 else "trend-down"


def _gate_result(record: Mapping[str, Any]) -> str:
    gates = record.get("coverage_gates", {})
    results = [
        str(gate.get("result", "SKIP")).upper()
        for gate in gates.values()
        if isinstance(gate, dict) and gate.get("threshold") is not None
    ]
    if not results:
        return "SKIP"
    if "FAIL" in results:
        return "FAIL"
    if "MISSING" in results:
        return "MISSING"
    return "PASS"


def _vivado_version(record: Mapping[str, Any]) -> str:
    toolchain = record.get("toolchain", {})
    vivado = toolchain.get("vivado", {}) if isinstance(toolchain, dict) else {}
    version = vivado.get("version") if isinstance(vivado, dict) else None
    return str(version or "unknown")


def _seed_text(record: Mapping[str, Any]) -> str:
    seeds = record.get("seed_set", [])
    if not seeds:
        return "-"
    return ", ".join(str(seed) for seed in seeds)


def write_coverage_trend_report(
    reports_dir: Path,
    records: Sequence[Mapping[str, Any]],
    *,
    archive_path: Path | None = None,
    archived_records: int = 0,
) -> dict[str, Any]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_dir / "coverage_trend.md"
    html_path = reports_dir / "coverage_trend.html"
    metric_deltas = calculate_metric_deltas(records)
    latest = records[-1] if records else {}
    latest_metrics = latest.get("coverage_metrics", {})
    archive_href = (
        archive_path.name
        if archive_path is not None and archive_path.is_file()
        else None
    )

    lines = [
        "# Coverage 趋势",
        "",
        "- 活动记录数量：{}".format(len(records)),
        "- 已归档记录：{}".format(archived_records),
        "- 压缩归档：{}".format(
            "[{}]({})".format(archive_href, archive_href)
            if archive_href
            else "-"
        ),
        "- 最新目标：{}".format(latest.get("target_name", "-")),
        "- 最新 Flow：{}".format(latest.get("flow_name", "-")),
        "- 最新状态：{}".format(latest.get("status", "-")),
        "- 最新 Gate：{}".format(_gate_result(latest)),
        "- Vivado 版本：{}".format(_vivado_version(latest)),
        "",
        "## 最新变化",
        "",
        "| Metric | Current | Delta |",
        "|---|---:|---:|",
    ]
    for metric in COVERAGE_METRIC_ORDER:
        lines.append(
            "| {} | {} | {} |".format(
                COVERAGE_METRIC_LABELS[metric],
                _percent(latest_metrics.get(metric)),
                _delta(metric_deltas[metric]),
            )
        )

    lines.extend([
        "",
        "## 历史记录",
        "",
        "| Recorded At | Target | Flow | Status | Gate | Seeds | Vivado | Total | Statement/Line | Branch | Condition | Toggle | Functional |",
        "|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for record in records:
        metrics = record.get("coverage_metrics", {})
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                record.get("recorded_at", "-"),
                record.get("target_name", "-"),
                record.get("flow_name", "-"),
                record.get("status", "-"),
                _gate_result(record),
                _seed_text(record),
                _vivado_version(record),
                *(
                    _percent(metrics.get(metric))
                    for metric in COVERAGE_METRIC_ORDER
                ),
            )
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    metric_cards = []
    for metric in COVERAGE_METRIC_ORDER:
        delta = metric_deltas[metric]
        metric_cards.append(
            '<article class="metric-card"><h3>{}</h3><strong>{}</strong>'
            '<span class="delta {}">{}</span></article>'.format(
                html.escape(COVERAGE_METRIC_LABELS[metric]),
                html.escape(_percent(latest_metrics.get(metric))),
                _delta_class(delta),
                html.escape(_delta(delta)),
            )
        )
    history_rows = []
    for record in records:
        metrics = record.get("coverage_metrics", {})
        history_rows.append(
            '<tr data-target="{target}"><td>{recorded_at}</td><td>{target}</td>'
            "<td>{flow}</td><td>{status}</td><td>{gate}</td><td>{seeds}</td>"
            "<td>{vivado}</td>{metrics}</tr>".format(
                target=html.escape(str(record.get("target_name", "-"))),
                recorded_at=html.escape(str(record.get("recorded_at", "-"))),
                flow=html.escape(str(record.get("flow_name", "-"))),
                status=html.escape(str(record.get("status", "-"))),
                gate=html.escape(_gate_result(record)),
                seeds=html.escape(_seed_text(record)),
                vivado=html.escape(_vivado_version(record)),
                metrics="".join(
                    "<td>{}</td>".format(
                        html.escape(_percent(metrics.get(metric)))
                    )
                    for metric in COVERAGE_METRIC_ORDER
                ),
            )
        )
    html_lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Coverage 趋势</title>",
        "<style>",
        "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f4f7fb;color:#172033}",
        ".page{max-width:1280px;margin:0 auto;padding:32px 20px}.hero{padding:26px;border-radius:8px;background:#17324d;color:#fff}",
        ".metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0}",
        ".metric-card{padding:15px;border-radius:8px;background:#fff;border:1px solid #dbe3ee}.metric-card h3{margin:0 0 8px}",
        ".metric-card strong{font-size:25px}.delta{display:block;margin-top:6px;font-weight:700}",
        ".trend-up{color:#0f8a5f}.trend-down{color:#b42318}.trend-flat{color:#64748b}",
        ".table-wrap{overflow-x:auto;background:#fff;border:1px solid #dbe3ee;border-radius:8px}table{border-collapse:collapse;width:100%}",
        "th,td{padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:left;white-space:nowrap}th{background:#eef3f8}",
        "@media(max-width:900px){.metrics{grid-template-columns:1fr}}",
        "</style>",
        "</head>",
        "<body>",
        '<main class="page">',
        (
            '<section class="hero"><h1>Coverage 趋势</h1>'
            "<p>活动记录数量：{} · 已归档记录：{}</p>{}</section>"
        ).format(
            len(records),
            archived_records,
            (
                '<a href="{href}">压缩归档：{label}</a>'.format(
                    href=html.escape(archive_href, quote=True),
                    label=html.escape(archive_href),
                )
                if archive_href
                else "<span>压缩归档：-</span>"
            ),
        ),
        '<section class="metrics">',
        "\n".join(metric_cards),
        "</section>",
        '<section class="table-wrap"><table><thead><tr>',
        "<th>Recorded At</th><th>Target</th><th>Flow</th><th>Status</th><th>Gate</th><th>Seeds</th><th>Vivado</th>",
        "".join(
            "<th>{}</th>".format(html.escape(COVERAGE_METRIC_LABELS[metric]))
            for metric in COVERAGE_METRIC_ORDER
        ),
        "</tr></thead><tbody>",
        "\n".join(history_rows),
        "</tbody></table></section>",
        "</main>",
        "</body>",
        "</html>",
        "",
    ]
    html_path.write_text("\n".join(html_lines), encoding="utf-8")
    return {
        "markdown_path": markdown_path,
        "html_path": html_path,
        "metric_deltas": metric_deltas,
    }


def _load_rotation_metadata(metadata_path: Path) -> dict[str, Any] | None:
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "invalid coverage history rotation metadata: {}".format(
                metadata_path
            )
        ) from exc
    if not isinstance(metadata, dict):
        raise ValueError("coverage history rotation metadata must be an object")
    if metadata.get("schema_version") != ROTATION_METADATA_SCHEMA_VERSION:
        raise ValueError("unsupported coverage history rotation metadata schema")
    return metadata


def append_coverage_history(
    reports_dir: Path,
    *,
    target_name: str,
    flow_name: str,
    toolchain: Mapping[str, Any],
    seed_set: Sequence[int],
    coverage_metrics: Mapping[str, float | None],
    coverage_gates: Mapping[str, Any],
    status: str,
    recorded_at: str | None = None,
    sources: Mapping[str, Any] | None = None,
    max_active_records: int | None = DEFAULT_ACTIVE_RECORD_LIMIT,
) -> dict[str, Any]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    history_path = reports_dir / "coverage_history.jsonl"
    metadata_path = reports_dir / "coverage_history.meta.json"
    existing_records = load_coverage_history(history_path)
    existing_metadata = _load_rotation_metadata(metadata_path)
    record = build_coverage_history_record(
        target_name=target_name,
        flow_name=flow_name,
        toolchain=toolchain,
        seed_set=seed_set,
        coverage_metrics=coverage_metrics,
        coverage_gates=coverage_gates,
        status=status,
        recorded_at=recorded_at,
        sources=sources,
    )
    records, archive_path, newly_archived = rotate_json_records(
        [*existing_records, record],
        history_path,
        active_limit=max_active_records,
    )
    history_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    rotation = build_rotation_metadata(
        existing_metadata,
        active_limit=max_active_records,
        archive_path=archive_path,
        newly_archived=newly_archived,
        count_key="archived_records",
    )
    archived_records = 0
    if rotation is not None:
        archived_records = int(rotation["archived_records"])
        metadata_path.write_text(
            json.dumps(
                {
                    "schema_version": ROTATION_METADATA_SCHEMA_VERSION,
                    **rotation,
                    "updated_at": record["recorded_at"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    trend_report = write_coverage_trend_report(
        reports_dir,
        records,
        archive_path=archive_path,
        archived_records=archived_records,
    )
    return {
        "history_path": history_path,
        "metadata_path": metadata_path,
        "archive_path": archive_path,
        "archived_records": archived_records,
        "record": record,
        "records": records,
        **trend_report,
    }
