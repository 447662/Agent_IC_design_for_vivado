import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
AGENT_CLI_PATH = AGENT_DIR / "agent_cli.py"
WAVEFORM_SAMPLES_PATH = AGENT_DIR / "waveform_samples.py"
WAVEFORM_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "waveforms"
P5_12_VCD_PATH = WAVEFORM_FIXTURES_DIR / "handshake_trace.vcd"
P5_12_FST_PATH = WAVEFORM_FIXTURES_DIR / "handshake_trace.fst"
P5_12_GHW_PATH = WAVEFORM_FIXTURES_DIR / "time_test.ghw"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_local_module(module_name, module_path):
    relative_module = module_path.relative_to(AGENT_DIR).with_suffix("")
    qualified_name = ".".join(relative_module.parts)
    return importlib.import_module(
        "digital_ic_agent._runtime.{}".format(qualified_name)
    )

def load_agent_module():
    return importlib.import_module("digital_ic_agent._runtime.agent")

@pytest.mark.parametrize(
    ("waveform_path", "expected_suffix"),
    [
        (P5_12_VCD_PATH, ".vcd"),
        (P5_12_FST_PATH, ".fst"),
        (P5_12_GHW_PATH, ".ghw"),
    ],
)
def test_p5_12_cli_accepts_generic_waveform_formats(waveform_path, expected_suffix):
    cli_module = load_local_module("agent_cli_split_p5_12_waveform", AGENT_CLI_PATH)

    args = cli_module.parse_args(["--analyze-waveform", str(waveform_path)])

    assert Path(args.analyze_waveform).suffix == expected_suffix
    assert args.analyze_vcd is None


def test_p5_12_cli_exposes_waveform_sample_verification_mode():
    cli_module = load_local_module("agent_cli_split_p5_12_samples", AGENT_CLI_PATH)

    args = cli_module.parse_args(["--verify-waveform-samples"])

    assert args.verify_waveform_samples is True
    assert args.analyze_waveform is None


@pytest.mark.parametrize("waveform_path", [P5_12_FST_PATH, P5_12_GHW_PATH])
def test_p5_12_binary_waveforms_never_fall_back_to_vcd_analyzer(
    monkeypatch,
    waveform_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    fallback_calls = []

    monkeypatch.setattr(
        agent,
        "run_rwave_json",
        lambda *args: (_ for _ in ()).throw(
            FileNotFoundError("RWaveAnalyzer rwave binary not found")
        ),
    )
    monkeypatch.setattr(
        agent,
        "run_vcd_analyzer_json",
        lambda *args: fallback_calls.append(args),
    )

    with pytest.raises(FileNotFoundError, match="requires RWaveAnalyzer"):
        agent.run_waveform_analyzer_json("info", waveform_path, backend="auto")

    with pytest.raises(ValueError, match="only supports VCD"):
        agent.run_waveform_analyzer_json(
            "info",
            waveform_path,
            backend="vcd-analyzer",
        )

    assert fallback_calls == []


def test_p5_12_generic_waveform_report_uses_detected_format(monkeypatch, capsys):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    calls = []

    def fake_run(*args, backend="auto"):
        calls.append((args, backend))
        return {
            "signal_count": 3,
            "time_min_h": "0s",
            "time_max_h": "30ns",
            "duration_h": "30ns",
            "timescale": "1ns",
            "scopes": ["tb"],
            "_waveform_backend": "rwave",
        }

    monkeypatch.setattr(agent, "run_waveform_analyzer_json", fake_run)

    assert agent.analyze_waveform(P5_12_FST_PATH, waveform_backend="auto") is True

    captured = capsys.readouterr()
    assert "格式: FST" in captured.out or "鏍煎紡: FST" in captured.out
    assert "Backend: rwave" in captured.out
    assert calls == [(("info", P5_12_FST_PATH), "auto")]


def test_p5_12_waveform_sample_matrix_covers_vcd_fst_and_ghw(tmp_path):
    module = load_local_module("waveform_samples_split_p5_12", WAVEFORM_SAMPLES_PATH)

    class FakeAgent:
        project_root = ROOT

        def run_waveform_analyzer_json(self, *args, backend="auto"):
            waveform_path = Path(args[1])
            if waveform_path.suffix == ".ghw":
                return {
                    "signal_count": 3,
                    "time_min_h": "0s",
                    "time_max_h": "10ns",
                    "duration_h": "10ns",
                    "timescale": "1fs",
                    "scopes": ["time_test"],
                    "_waveform_backend": "rwave",
                }
            return {
                "signal_count": 3,
                "time_min_h": "0s",
                "time_max_h": "30ns",
                "duration_h": "30ns",
                "timescale": "1ns",
                "scopes": ["tb"],
                "_waveform_backend": "rwave",
            }

    result = module.write_waveform_sample_report(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "PASS"
    assert [item["format"] for item in result["samples"]] == ["VCD", "FST", "GHW"]
    assert all(item["backend"] == "rwave" for item in result["samples"])
    assert all(item["status"] == "PASS" for item in result["samples"])
    assert result["markdown_path"] == (
        tmp_path / "waveform-samples" / "format_matrix.md"
    )
    assert result["html_path"] == (
        tmp_path / "waveform-samples" / "format_matrix.html"
    )

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "| VCD | handshake_trace.vcd | PASS | rwave | 3 | 1ns | 0s - 30ns |" in markdown
    assert "| FST | handshake_trace.fst | PASS | rwave | 3 | 1ns | 0s - 30ns |" in markdown
    assert "| GHW | time_test.ghw | PASS | rwave | 3 | 1fs | 0s - 10ns |" in markdown
    assert '<html lang="zh-CN">' in html_text
    assert "VCD" in html_text
    assert "FST" in html_text
    assert "GHW" in html_text
    assert "\ufffd" not in markdown
    assert "\ufffd" not in html_text


def test_p5_12_waveform_samples_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"src/digital_ic_agent"' in pyproject
