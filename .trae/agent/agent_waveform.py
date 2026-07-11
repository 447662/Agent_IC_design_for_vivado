from typing import Any
import os
import shutil
import sys
from pathlib import Path


def resolve_vcd_analyzer_path(project_root: Any) -> Any:
    return (
        Path(project_root)
        / "VCD_ANALYZER-main"
        / "VCD_ANALYZER-main"
        / "vcd_analyzer.py"
    )


def resolve_rwave_source_dir(project_root: Any) -> Any:
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
    project_root: Any,
    env: Any=None,
    which: Any=None,
    source_dir_resolver: Any=None,
) -> Any:
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
    agent: Any,
    waveform_path: Any,
    condition: Any = None,
    show: Any = None,
    limit: Any = 20,
    waveform_backend: Any = "auto",
    report_title: Any = "波形分析报告",
) -> Any:
    waveform_file = Path(waveform_path)
    waveform_format = waveform_file.suffix.lstrip(".").upper()
    if waveform_format not in {"VCD", "FST", "GHW"}:
        print(
            "Unsupported waveform format: {}".format(waveform_file.suffix or "<none>"),
            file=sys.stderr,
        )
        return False
    if not waveform_file.exists():
        print("Waveform file not found: {}".format(waveform_file), file=sys.stderr)
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
        print(str(exc), file=sys.stderr)
        return False

    print(report_title)
    print("=" * 60)
    print("文件: {}".format(waveform_file))
    print("格式: {}".format(waveform_format))
    print("Backend: {}".format(info.get("_waveform_backend", "unknown")))
    print("信号数量: {}".format(info.get("signal_count", "unknown")))
    print(
        "时间范围: {} - {}".format(
            info.get("time_min_h", "unknown"),
            info.get("time_max_h", "unknown"),
        )
    )
    print("持续时间: {}".format(info.get("duration_h", "unknown")))
    print("Timescale: {}".format(info.get("timescale", "unknown")))
    scopes = info.get("scopes") or []
    if scopes:
        print("Scopes: {}".format(", ".join(scopes[:8])))

    if search_result is not None:
        print("\n条件搜索")
        print("- 条件: {}".format(condition))
        if show:
            print("- 观察信号: {}".format(show))
        print("- 模式: {}".format(search_result.get("mode", "unknown")))
        print(
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
        for index, row in enumerate(rows[: int(limit)], start=1):
            begin = (
                row.get("begin_h")
                or row.get("time_h")
                or row.get("at_h")
                or "unknown"
            )
            end = row.get("end_h")
            values = row.get("values") or {}
            if end:
                print("  {}. {} -> {} {}".format(index, begin, end, values))
            else:
                print("  {}. {} {}".format(index, begin, values))

    return True


def analyze_vcd(
    agent: Any,
    vcd_path: Any,
    condition: Any = None,
    show: Any = None,
    limit: Any = 20,
    waveform_backend: Any = "auto",
) -> Any:
    vcd_file = Path(vcd_path)
    if not vcd_file.exists():
        print("VCD file not found: {}".format(vcd_file), file=sys.stderr)
        return False
    return agent.analyze_waveform(
        vcd_file,
        condition=condition,
        show=show,
        limit=limit,
        waveform_backend=waveform_backend,
        report_title="VCD 分析报告",
    )
