from typing import Any
import os
import shutil
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
