import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime import agent_waveform as waveform  # noqa: E402


def test_waveform_report_renders_scope_and_all_search_row_shapes():
    info = {
        "_waveform_backend": "fixture",
        "signal_count": 4,
        "scopes": ("tb", "tb.dut"),
    }
    segments = {
        "mode": "condition",
        "shown": 3,
        "segments": [
            {"begin_h": "1 ns", "end_h": "2 ns", "values": {"data": "aa"}},
            {"time_h": "3 ns", "values": {"data": "55"}},
            "ignored-row",
        ],
    }

    lines = waveform.build_waveform_report_lines(
        "Report",
        "trace.vcd",
        "VCD",
        info,
        search_result=segments,
        condition="valid=1",
        show="data",
    )

    assert "Scopes: tb, tb.dut" in lines
    assert "- 观察信号: data" in lines
    assert any("1 ns -> 2 ns" in line for line in lines)
    assert any("3 ns" in line and "->" not in line for line in lines)


@pytest.mark.parametrize(
    ("search_result", "expected"),
    [
        ({"intervals": [{"at_h": "4 ns"}]}, "4 ns"),
        ({"events": [{"values": {"ready": 1}}]}, "unknown"),
        ({"segments": "invalid"}, "命中数量"),
    ],
)
def test_waveform_report_handles_search_fallbacks(search_result, expected):
    lines = waveform.build_waveform_report_lines(
        "Report",
        "trace.fst",
        "FST",
        {"scopes": "not-a-list"},
        search_result=search_result,
        condition="ready=1",
    )

    assert any(expected in line for line in lines)


def test_rwave_resolution_uses_environment_path_and_path_lookup(tmp_path):
    env_binary = tmp_path / "env-rwave.exe"
    env_binary.write_text("binary", encoding="utf-8")

    assert waveform.resolve_rwave_command(
        tmp_path,
        env={"RWAVE_BIN": str(env_binary)},
        which=lambda _name: None,
    ) == str(env_binary)
    assert waveform.resolve_rwave_command(
        tmp_path,
        env={"RWAVE_BIN": str(tmp_path / "missing")},
        which=lambda name: "path-rwave" if name == "rwave" else None,
    ) == "path-rwave"


def test_rwave_resolution_handles_archive_binary_and_missing_source(tmp_path):
    archive = (
        tmp_path
        / "docs"
        / "tools_archive"
        / "RWaveAnalyzer-main"
        / "RWaveAnalyzer-main"
    )
    (archive / "crates" / "rwave").mkdir(parents=True)
    (archive / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    binary = archive / "dist" / "rwave-linux-amd64"
    binary.parent.mkdir()
    binary.write_text("binary", encoding="utf-8")

    assert waveform.resolve_rwave_source_dir(tmp_path) == archive
    assert waveform.resolve_rwave_command(
        tmp_path,
        env={},
        which=lambda _name: None,
    ) == str(binary)
    assert waveform.resolve_rwave_command(
        tmp_path,
        env={},
        which=lambda _name: None,
        source_dir_resolver=lambda: None,
    ) is None


class Analyzer:
    def __init__(self):
        self.calls: list[tuple[tuple[object, ...], str]] = []

    def run_waveform_analyzer_json(self, *args: object, backend: str = "auto"):
        self.calls.append((args, backend))
        if args[0] == "info":
            return {"signal_count": 2, "scopes": []}
        return {"events": [{"time_h": "1 ns", "values": {"data": "aa"}}]}

    def analyze_waveform(self, *_args: object, **_kwargs: object) -> bool:
        return True


def test_analyze_waveform_rejects_unsupported_and_missing_inputs(tmp_path, capsys):
    analyzer = Analyzer()

    assert waveform.analyze_waveform(analyzer, tmp_path / "trace.bin") is False
    assert waveform.analyze_waveform(analyzer, tmp_path / "missing.fst") is False
    errors = capsys.readouterr().err
    assert "Unsupported waveform format" in errors
    assert "Waveform file not found" in errors


def test_analyze_waveform_runs_info_and_condition_search(tmp_path, capsys):
    analyzer = Analyzer()
    trace = tmp_path / "trace.ghw"
    trace.write_text("fixture", encoding="utf-8")

    assert waveform.analyze_waveform(
        analyzer,
        trace,
        condition="valid=1",
        show="data",
        limit=3,
        waveform_backend="rwave",
    ) is True

    assert analyzer.calls[0] == (("info", trace), "rwave")
    assert analyzer.calls[1][0][-2:] == ("--show", "data")
    assert "条件搜索" in capsys.readouterr().out


def test_analyze_vcd_delegates_only_for_existing_file(tmp_path, capsys):
    analyzer = Analyzer()
    trace = tmp_path / "trace.vcd"

    assert waveform.analyze_vcd(analyzer, trace) is False
    assert "VCD file not found" in capsys.readouterr().err
    trace.write_text("fixture", encoding="utf-8")
    assert waveform.analyze_vcd(analyzer, trace, condition="valid=1") is True
