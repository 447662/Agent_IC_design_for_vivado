import html
from pathlib import Path
from typing import Any, Protocol


SAMPLE_SPECS = (
    ("VCD", "handshake_trace.vcd"),
    ("FST", "handshake_trace.fst"),
    ("GHW", "time_test.ghw"),
)


class WaveformSampleAgent(Protocol):
    project_root: Path

    def run_waveform_analyzer_json(
        self,
        *args: object,
        backend: str = "auto",
    ) -> dict[str, Any]: ...


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_markdown(samples: list[dict[str, Any]], status: str) -> str:
    lines = [
        "# VCD/FST/GHW 统一波形后端验证",
        "",
        "- 总体状态：`{}`".format(status),
        "- 统一后端：`RWaveAnalyzer / rwave`",
        "- 样例数量：`{}`".format(len(samples)),
        "",
        "| 格式 | 文件 | 状态 | 后端 | 信号数 | Timescale | 时间范围 |",
        "|---|---|---|---|---:|---|---|",
    ]
    for sample in samples:
        lines.append(
            "| {format} | {file} | {status} | {backend} | {signals} | "
            "{timescale} | {time_min} - {time_max} |".format(
                format=_markdown_cell(sample["format"]),
                file=_markdown_cell(sample["file"]),
                status=_markdown_cell(sample["status"]),
                backend=_markdown_cell(sample["backend"]),
                signals=_markdown_cell(sample["signal_count"]),
                timescale=_markdown_cell(sample["timescale"]),
                time_min=_markdown_cell(sample["time_min"]),
                time_max=_markdown_cell(sample["time_max"]),
            )
        )
        if sample.get("error"):
            lines.append(
                "- `{}`：{}".format(
                    _markdown_cell(sample["file"]),
                    _markdown_cell(sample["error"]),
                )
            )
    lines.extend(
        [
            "",
            "## 判定规则",
            "",
            "- VCD、FST、GHW 均必须由 `rwave` 成功解析。",
            "- FST/GHW 不允许降级到仅支持 VCD 的旧分析器。",
            "- 任一样例缺失、解析失败或后端不为 `rwave` 时，总体状态为 `FAIL`。",
            "",
        ]
    )
    return "\n".join(lines)


def _render_html(samples: list[dict[str, Any]], status: str) -> str:
    rows = []
    for sample in samples:
        rows.append(
            "<tr class=\"{row_class}\">"
            "<td>{format}</td><td>{file}</td><td>{status}</td>"
            "<td>{backend}</td><td>{signals}</td><td>{timescale}</td>"
            "<td>{time_min} - {time_max}</td><td>{error}</td></tr>".format(
                row_class="pass" if sample["status"] == "PASS" else "fail",
                format=html.escape(str(sample["format"])),
                file=html.escape(str(sample["file"])),
                status=html.escape(str(sample["status"])),
                backend=html.escape(str(sample["backend"])),
                signals=html.escape(str(sample["signal_count"])),
                timescale=html.escape(str(sample["timescale"])),
                time_min=html.escape(str(sample["time_min"])),
                time_max=html.escape(str(sample["time_max"])),
                error=html.escape(str(sample.get("error") or "")),
            )
        )
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VCD/FST/GHW 统一波形后端验证</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", sans-serif; color: #1f2937; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 24px; }}
    h1 {{ font-size: 28px; }}
    .summary {{ padding: 14px 16px; border-left: 4px solid {status_color}; background: #f3f4f6; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
    th, td {{ padding: 10px 12px; border: 1px solid #d1d5db; text-align: left; }}
    th {{ background: #1f2937; color: #ffffff; }}
    tr.pass td:nth-child(3) {{ color: #166534; font-weight: 700; }}
    tr.fail td:nth-child(3) {{ color: #b91c1c; font-weight: 700; }}
  </style>
</head>
<body>
<main>
  <h1>VCD/FST/GHW 统一波形后端验证</h1>
  <p class="summary">总体状态：<strong>{status}</strong>；统一后端：RWaveAnalyzer / rwave</p>
  <table>
    <thead><tr><th>格式</th><th>文件</th><th>状态</th><th>后端</th><th>信号数</th><th>Timescale</th><th>时间范围</th><th>错误</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</main>
</body>
</html>
""".format(
        status=html.escape(status),
        status_color="#15803d" if status == "PASS" else "#b91c1c",
        rows="".join(rows),
    )


def write_waveform_sample_report(
    agent: WaveformSampleAgent,
    output_dir: str | Path = "outputs",
) -> dict[str, Any]:
    fixture_dir = agent.project_root / "tests" / "fixtures" / "waveforms"
    samples: list[dict[str, Any]] = []

    for format_name, filename in SAMPLE_SPECS:
        waveform_path = fixture_dir / filename
        sample: dict[str, Any] = {
            "format": format_name,
            "file": filename,
            "path": waveform_path,
            "status": "FAIL",
            "backend": "unavailable",
            "signal_count": "unknown",
            "timescale": "unknown",
            "time_min": "unknown",
            "time_max": "unknown",
            "error": None,
        }
        try:
            if not waveform_path.exists():
                raise FileNotFoundError(
                    "Waveform sample not found: {}".format(waveform_path)
                )
            info = agent.run_waveform_analyzer_json(
                "info",
                waveform_path,
                backend="rwave",
            )
            sample["backend"] = info.get("_waveform_backend", "unknown")
            sample["signal_count"] = info.get("signal_count", "unknown")
            sample["timescale"] = info.get("timescale", "unknown")
            sample["time_min"] = info.get("time_min_h", "unknown")
            sample["time_max"] = info.get("time_max_h", "unknown")
            if sample["backend"] != "rwave":
                raise RuntimeError(
                    "Expected rwave backend, got {}".format(sample["backend"])
                )
            sample["status"] = "PASS"
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            sample["error"] = str(exc)
        samples.append(sample)

    status = "PASS" if all(item["status"] == "PASS" for item in samples) else "FAIL"
    report_dir = Path(output_dir) / "waveform-samples"
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / "format_matrix.md"
    html_path = report_dir / "format_matrix.html"
    markdown_path.write_text(_render_markdown(samples, status), encoding="utf-8")
    html_path.write_text(_render_html(samples, status), encoding="utf-8")
    return {
        "status": status,
        "samples": samples,
        "markdown_path": markdown_path,
        "html_path": html_path,
    }
