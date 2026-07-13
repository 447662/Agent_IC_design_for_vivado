import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


class FakeRunningGuiProcess:
    pid = 4321
    returncode = None

    @staticmethod
    def poll():
        return None


def load_agent_module():
    return importlib.import_module("digital_ic_agent._runtime.agent")

def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


def test_open_async_fifo_uvm_wave_gui_uses_uvm_wdb(monkeypatch, tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    sim_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb", encoding="utf-8")
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: vivado_path)
    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda command, cwd=None: (
            calls.append(([str(part) for part in command], Path(cwd))),
            FakeRunningGuiProcess(),
        )[1],
    )

    assert plugin.open_async_fifo_uvm_wave_gui(project_dir, wave_kind="coverage") is True

    script = sim_dir / "open_async_fifo_uvm_coverage_wave.tcl"
    script_text = script.read_text(encoding="utf-8")
    assert "async_fifo_uvm_coverage.wdb" in script_text
    assert "open_wave_database $wave_db" in script_text
    assert "add_wave -r /tb_async_fifo_uvm" in script_text
    assert "uvm_coverage_wave_open_check.json" in script_text
    assert "get_scopes" in script_text
    assert "get_objects" in script_text
    assert "get_waves" in script_text
    assert calls == [([vivado_path, "-mode", "gui", "-source", script.name], sim_dir)]


def test_async_fifo_uvm_wave_screenshot_report_embeds_png_and_capture_script(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    reports_dir = project_dir / "reports"
    sim_dir = project_dir / "sim"
    reports_dir.mkdir(parents=True)
    sim_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb", encoding="utf-8")
    (reports_dir / "uvm_wave_visibility.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (reports_dir / "uvm_coverage_wave_open_check.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_name": "async-fifo",
                "flow_name": "uvm-coverage",
                "wave_database": str(sim_dir / "async_fifo_uvm_coverage.wdb"),
                "wdb_opened": True,
                "scope_count": 2,
                "object_count": 40,
                "wave_count": 40,
                "wave_config_count": 1,
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    (reports_dir / "uvm_wave_screenshot_metrics.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado 2025.2",
                "width": 1600,
                "height": 900,
                "sampled_pixels": 4096,
                "unique_colors": 96,
                "non_uniform_pixels": 2440,
                "non_uniform_ratio": 0.5957,
            }
        ),
        encoding="utf-8",
    )

    report = async_fifo_plugin(agent).write_async_fifo_uvm_wave_screenshot_report(
        project_dir,
        wave_kind="coverage",
    )

    assert report["captured"] is True
    assert report["runtime_status"] == "PASS"
    assert report["screenshot_status"] == "PASS"
    assert report["markdown_path"].name == "uvm_wave_screenshot.md"
    assert report["html_path"].name == "uvm_wave_screenshot.html"
    assert report["capture_script_path"].name == "capture_uvm_wave_screenshot.ps1"
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    script_text = report["capture_script_path"].read_text(encoding="utf-8")
    assert "--open-uvm-wave async-fifo --uvm-wave-kind coverage" in text
    assert "uvm_wave_visibility.png" in text
    assert "Scope" in text
    assert "uvm_wave_visibility.png" in html_text
    assert "capture_uvm_wave_screenshot.ps1" in script_text
    assert "GetForegroundWindow" in script_text
    assert "uvm_wave_screenshot_metrics.json" in script_text


def test_cli_uvm_random_regress_and_open_uvm_wave(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_random(self, target, output_dir="outputs", seeds=None):
        calls.append(("random", target, output_dir, seeds))
        return True

    def fake_open(self, target, output_dir="outputs", wave_kind="coverage"):
        calls.append(("open", target, output_dir, wave_kind))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "run_uvm_random_regression", fake_random)
    monkeypatch.setattr(module.DigitalICAgent, "open_uvm_wave", fake_open)

    assert module.main(
        [
            "--uvm-random-regress",
            "async-fifo",
            "--uvm-seeds",
            "1,2,3",
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    assert module.main(
        [
            "--open-uvm-wave",
            "async-fifo",
            "--uvm-wave-kind",
            "smoke",
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    assert calls == [
        ("random", "async-fifo", str(tmp_path), [1, 2, 3]),
        ("open", "async-fifo", str(tmp_path), "smoke"),
    ]


def test_cli_open_wave_async_fifo_invokes_gui(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_open_rtl_wave(self, target, output_dir="outputs"):
        calls.append((target, output_dir))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "open_rtl_wave", fake_open_rtl_wave)

    assert (
        module.main(
            [
                "--open-wave",
                "async-fifo",
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert calls == [("async-fifo", str(tmp_path))]
