# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
from typing import Any, TextIO, TypedDict



PathLike = str | os.PathLike[str]


class WaveEventRow(TypedDict, total=False):
    time_h: str
    begin_h: str
    end_h: str
    at_h: str
    values: dict[str, object]


class WaveSearchResult(TypedDict, total=False):
    total: int
    shown: int
    events: list[WaveEventRow]
    segments: list[WaveEventRow]
    intervals: list[WaveEventRow]


class WaveInfo(TypedDict, total=False):
    signal_count: int
    time_min_h: str
    time_max_h: str
    duration_h: str
    timescale: str
    _waveform_backend: str


class AsyncFifoVcdAnalysis(TypedDict):
    vcd_path: Path
    info: WaveInfo
    write_events: WaveSearchResult
    read_events: WaveSearchResult


def build_async_fifo_error_lines(message: str, hint: str | None = None) -> list[str]:
    lines = [message]
    if hint:
        lines.append(hint)
    return lines


def build_async_fifo_vcd_analysis_lines(
    analysis: AsyncFifoVcdAnalysis,
    limit: int = 20,
) -> list[str]:
    vcd_path = analysis["vcd_path"]
    info = analysis["info"]
    write_events = analysis["write_events"]
    read_events = analysis["read_events"]
    lines = [
        "Async FIFO VCD analysis",
        "=" * 60,
        "File: {}".format(vcd_path),
        "Signals: {}".format(info.get("signal_count", "unknown")),
        "Backend: {}".format(info.get("_waveform_backend", "unknown")),
        "Time range: {} - {}".format(
            info.get("time_min_h", "unknown"),
            info.get("time_max_h", "unknown"),
        ),
        "Duration: {}".format(info.get("duration_h", "unknown")),
        "Timescale: {}".format(info.get("timescale", "unknown")),
        "Write handshakes: {}".format(
            write_events.get("total", write_events.get("shown", "unknown"))
        ),
        "Read handshakes: {}".format(
            read_events.get("total", read_events.get("shown", "unknown"))
        ),
    ]

    for title, result in [("Writes", write_events), ("Reads", read_events)]:
        rows = result.get("segments") or result.get("intervals") or result.get("events") or []
        lines.append("\n{}".format(title))
        for index, row in enumerate(rows[: int(limit)], start=1):
            begin = row.get("begin_h") or row.get("time_h") or row.get("at_h") or "unknown"
            end = row.get("end_h")
            values = row.get("values") or {}
            if end:
                lines.append("  {}. {} -> {} {}".format(index, begin, end, values))
            else:
                lines.append("  {}. {} {}".format(index, begin, values))
    return lines


def build_async_fifo_rtl_check_lines(checks: list[tuple[str, bool, Path]]) -> list[str]:
    lines = [
        "Async FIFO RTL check",
        "=" * 60,
    ]
    for label, passed, path in checks:
        lines.append("[{}] {}: {}".format("OK" if passed else "NO", label, path))
    return lines


def build_async_fifo_sim_completed_lines(
    project_dir: Any,
    vcd_path: Any,
    wave_db_path: Any,
    report_path: Any,
) -> list[str]:
    return [
        "Async FIFO simulation completed",
        "Generated VCD: {}".format(vcd_path),
        "Generated WDB: {}".format(wave_db_path),
        "Vivado project: {}".format(project_dir / "vivado_project" / "async_fifo_project.xpr"),
        "Simulation report: {}".format(report_path),
    ]


def build_async_fifo_uvm_smoke_completed_lines(report: dict[str, Any]) -> list[str]:
    return [
        "Async FIFO UVM smoke completed",
        "UVM log: {}".format(report["log_path"]),
        "Generated WDB: {}".format(report["wdb_path"]),
        "UVM smoke report: {}".format(report["markdown_path"]),
    ]


def build_async_fifo_uvm_coverage_completed_lines(
    report: dict[str, Any],
    summary_report: dict[str, Any],
    functional_report: dict[str, Any],
) -> list[str]:
    return [
        "Async FIFO UVM coverage completed",
        "UVM log: {}".format(report["log_path"]),
        "Generated WDB: {}".format(report["wdb_path"]),
        "Coverage DB: {}".format(report["code_cov_dir"]),
        "UVM coverage report: {}".format(report["markdown_path"]),
        "UVM coverage summary: {}".format(summary_report["markdown_path"]),
        "UVM functional coverage report: {}".format(functional_report["markdown_path"]),
    ]


def emit_async_fifo_lines(lines: list[str], stream: TextIO | None = None) -> None:
    target_stream = stream or sys.stdout
    for line in lines:
        print(line, file=target_stream)


class AsyncFifoRegressionCase(TypedDict):
    name: str
    data_width: int
    addr_width: int
