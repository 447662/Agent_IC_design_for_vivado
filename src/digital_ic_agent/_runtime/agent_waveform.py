from collections.abc import Callable, Mapping
import os
import shutil
import sys
from pathlib import Path
from typing import Protocol, TextIO


class WaveformAnalysisAgent(Protocol):
    def run_waveform_analyzer_json(
        self,
        *args: object,
        backend: str = "auto",
    ) -> Mapping[str, object]:
        ...

    def analyze_waveform(
        self,
        waveform_path: str | Path,
        condition: str | None = None,
        show: str | None = None,
        limit: int = 20,
        waveform_backend: str = "auto",
        report_title: str = "波形分析报告",
    ) -> bool:
        ...


def build_waveform_report_lines(
    report_title: str,
    waveform_file: str | Path,
    waveform_format: str,
    info: Mapping[str, object],
    search_result: Mapping[str, object] | None = None,
    condition: str | None = None,
    show: str | None = None,
    limit: int = 20,
) -> list[str]:
    lines = [
        str(report_title),
        "=" * 60,
        "文件: {}".format(waveform_file),
        "格式: {}".format(waveform_format),
        "Backend: {}".format(info.get("_waveform_backend", "unknown")),
        "信号数量: {}".format(info.get("signal_count", "unknown")),
        "时间范围: {} - {}".format(
            info.get("time_min_h", "unknown"),
            info.get("time_max_h", "unknown"),
        ),
        "持续时间: {}".format(info.get("duration_h", "unknown")),
        "Timescale: {}".format(info.get("timescale", "unknown")),
    ]
    scopes = info.get("scopes") or []
    if isinstance(scopes, list | tuple):
        lines.append("Scopes: {}".format(", ".join(str(scope) for scope in scopes[:8])))

    if search_result is not None:
        lines.append("")
        lines.append("条件搜索")
        lines.append("- 条件: {}".format(condition))
        if show:
            lines.append("- 观察信号: {}".format(show))
        lines.append("- 模式: {}".format(search_result.get("mode", "unknown")))
        lines.append(
            "- 命中数量: {}".format(
                search_result.get("total", search_result.get("shown", "unknown"))
            )
        )

        rows = (
            search_result.get("segments")
            or search_result.get("intervals")
            or search_result.get("events")
            or []
        )
        if not isinstance(rows, list | tuple):
            rows = []
        for index, row in enumerate(rows[: int(limit)], start=1):
            if not isinstance(row, Mapping):
                continue
            begin = (
                row.get("begin_h")
                or row.get("time_h")
                or row.get("at_h")
                or "unknown"
            )
            end = row.get("end_h")
            values = row.get("values") or {}
            if end:
                lines.append("  {}. {} -> {} {}".format(index, begin, end, values))
            else:
                lines.append("  {}. {} {}".format(index, begin, values))
    return lines


def build_waveform_error_lines(message: str) -> list[str]:
    return [message]


def emit_waveform_lines(lines: list[str], stream: TextIO | None = None) -> None:
    target_stream = stream or sys.stdout
    for line in lines:
        print(line, file=target_stream)


def resolve_vcd_analyzer_path(project_root: str | Path) -> Path:
    return (
        Path(project_root)
        / "VCD_ANALYZER-main"
        / "VCD_ANALYZER-main"
        / "vcd_analyzer.py"
    )


def resolve_rwave_source_dir(project_root: str | Path) -> Path | None:
    project_root = Path(project_root)
    candidates = [
        project_root / "RWaveAnalyzer-main" / "RWaveAnalyzer-main",
        (
            project_root
            / "docs"
            / "tools_archive"
            / "RWaveAnalyzer-main"
            / "RWaveAnalyzer-main"
        ),
    ]
    for candidate in candidates:
        if (
            (candidate / "Cargo.toml").exists()
            and (candidate / "crates" / "rwave").exists()
        ):
            return candidate
    return None


def resolve_rwave_command(
    project_root: str | Path,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
    source_dir_resolver: Callable[[], Path | None] | None = None,
) -> str | None:
    env = os.environ if env is None else env
    which = shutil.which if which is None else which

    env_path = env.get("RWAVE_BIN")
    if env_path:
        env_candidate = Path(env_path)
        if env_candidate.exists():
            return str(env_candidate)

    path_candidate = which("rwave")
    if path_candidate:
        return path_candidate

    source_dir = (
        source_dir_resolver()
        if source_dir_resolver is not None
        else resolve_rwave_source_dir(project_root)
    )
    if source_dir:
        built_candidates = [
            source_dir / "target" / "release" / "rwave.exe",
            source_dir / "target" / "release" / "rwave",
            source_dir / "dist" / "rwave-windows-amd64.exe",
            source_dir / "dist" / "rwave-linux-amd64",
        ]
        for candidate in built_candidates:
            if candidate.exists():
                return str(candidate)
    return None


def analyze_waveform(
    agent: WaveformAnalysisAgent,
    waveform_path: str | Path,
    condition: str | None = None,
    show: str | None = None,
    limit: int = 20,
    waveform_backend: str = "auto",
    report_title: str = "波形分析报告",
) -> bool:
    waveform_file = Path(waveform_path)
    waveform_format = waveform_file.suffix.lstrip(".").upper()
    if waveform_format not in {"VCD", "FST", "GHW"}:
        emit_waveform_lines(
            build_waveform_error_lines(
                "Unsupported waveform format: {}".format(waveform_file.suffix or "<none>")
            ),
            stream=sys.stderr,
        )
        return False
    if not waveform_file.exists():
        emit_waveform_lines(
            build_waveform_error_lines("Waveform file not found: {}".format(waveform_file)),
            stream=sys.stderr,
        )
        return False

    try:
        info = agent.run_waveform_analyzer_json(
            "info",
            waveform_file,
            backend=waveform_backend,
        )
        search_result = None
        if condition:
            search_args = [
                "search",
                waveform_file,
                "--condition",
                condition,
                "--limit",
                limit,
            ]
            if show:
                search_args.extend(["--show", show])
            search_result = agent.run_waveform_analyzer_json(
                *search_args,
                backend=waveform_backend,
            )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        emit_waveform_lines(build_waveform_error_lines(str(exc)), stream=sys.stderr)
        return False

    emit_waveform_lines(
        build_waveform_report_lines(
            report_title,
            waveform_file,
            waveform_format,
            info,
            search_result=search_result,
            condition=condition,
            show=show,
            limit=limit,
        )
    )

    return True


def analyze_vcd(
    agent: WaveformAnalysisAgent,
    vcd_path: str | Path,
    condition: str | None = None,
    show: str | None = None,
    limit: int = 20,
    waveform_backend: str = "auto",
) -> bool:
    vcd_file = Path(vcd_path)
    if not vcd_file.exists():
        emit_waveform_lines(
            build_waveform_error_lines("VCD file not found: {}".format(vcd_file)),
            stream=sys.stderr,
        )
        return False
    return agent.analyze_waveform(
        vcd_file,
        condition=condition,
        show=show,
        limit=limit,
        waveform_backend=waveform_backend,
        report_title="VCD 分析报告",
    )
