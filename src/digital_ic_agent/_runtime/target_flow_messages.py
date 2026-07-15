from __future__ import annotations

import sys
from typing import Any, TextIO

def build_sync_fifo_error_lines(message: str, hint: str | None = None) -> list[str]:
    lines = [message]
    if hint:
        lines.append(hint)
    return lines


def build_sync_fifo_vcd_analysis_lines(analysis: dict[str, Any], limit: int = 20) -> list[str]:
    vcd_path = analysis["vcd_path"]
    info = analysis["info"]
    write_events = analysis["write_events"]
    read_events = analysis["read_events"]
    lines = [
        "Sync FIFO VCD analysis",
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


def build_sync_fifo_sim_completed_lines(
    project_dir: Any,
    vcd_path: Any,
    wave_db_path: Any,
    project_warning: str | None,
    report_path: Any,
) -> list[str]:
    lines = [
        "Sync FIFO simulation completed",
        "Generated VCD: {}".format(vcd_path),
        "Generated WDB: {}".format(wave_db_path),
    ]
    if project_warning is None:
        lines.append("Vivado project: {}".format(project_dir / "vivado_project" / "sync_fifo_project.xpr"))
    lines.append("Simulation report: {}".format(report_path))
    return lines


def emit_sync_fifo_lines(lines: list[str], stream: TextIO | None = None) -> None:
    target_stream = stream or sys.stdout
    for line in lines:
        print(line, file=target_stream)
def build_round_robin_arbiter_error_lines(message: str, hint: str | None = None) -> list[str]:
    lines = [message]
    if hint:
        lines.append(hint)
    return lines


def build_round_robin_arbiter_vcd_analysis_lines(
    analysis: dict[str, Any],
    limit: int = 20,
    report_path: Any = None,
) -> list[str]:
    vcd_path = analysis["vcd_path"]
    info = analysis["info"]
    grant_events = analysis["grant_events"]
    fairness_events = analysis["fairness_events"]
    lines = [
        "Round-Robin Arbiter VCD analysis",
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
        "Grant events: {}".format(
            grant_events.get("total", grant_events.get("shown", "unknown"))
        ),
        "Fairness checkpoints: {}".format(
            fairness_events.get("total", fairness_events.get("shown", "unknown"))
        ),
    ]

    for title, result in [("Grants", grant_events), ("Fairness", fairness_events)]:
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

    if report_path is not None:
        lines.append("Simulation report refreshed: {}".format(report_path))
    return lines


def build_round_robin_arbiter_sim_completed_lines(
    project_dir: Any,
    vcd_path: Any,
    wave_db_path: Any,
    project_warning: str | None,
    report_path: Any,
) -> list[str]:
    lines = [
        "Round-Robin Arbiter simulation completed",
        "Generated VCD: {}".format(vcd_path),
        "Generated WDB: {}".format(wave_db_path),
    ]
    if project_warning is None:
        lines.append(
            "Vivado project: {}".format(
                project_dir / "vivado_project" / "round_robin_arbiter_project.xpr"
            )
        )
    lines.append("Simulation report: {}".format(report_path))
    return lines


def emit_round_robin_arbiter_lines(lines: list[str], stream: TextIO | None = None) -> None:
    target_stream = stream or sys.stdout
    for line in lines:
        print(line, file=target_stream)
