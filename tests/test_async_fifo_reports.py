import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_async_fifo_reports_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


def _write_valid_wcfg(path):
    required_objects = [
        "/tb_async_fifo/scenario_id",
        "/tb_async_fifo/wr_clk",
        "/tb_async_fifo/rd_clk",
        "/tb_async_fifo/write_count",
        "/tb_async_fifo/read_count",
        "/tb_async_fifo/dut/full_reg",
        "/tb_async_fifo/dut/empty_reg",
    ]
    path.write_text(
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                "<wave_config>",
                '<WVObjectSize size="31" />',
                *[f'<wvobject fp_name="{name}" />' for name in required_objects],
                "</wave_config>",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_async_fifo_wcfg_validation_detects_required_wave_objects(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    wcfg_path = project_dir / "sim" / "async_fifo_debug.wcfg"
    _write_valid_wcfg(wcfg_path)

    summary = async_fifo_plugin(agent).parse_async_fifo_wcfg_summary(project_dir)

    assert summary["exists"] is True
    assert summary["object_count"] == 31
    assert summary["valid"] is True
    assert summary["missing_required"] == []
    assert "/tb_async_fifo/scenario_id" in summary["required_objects"]


def test_async_fifo_wcfg_validation_rejects_empty_wave_config(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    wcfg_path = project_dir / "sim" / "async_fifo_debug.wcfg"
    wcfg_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<WVObjectSize size="0" />\n',
        encoding="utf-8",
    )

    summary = async_fifo_plugin(agent).parse_async_fifo_wcfg_summary(project_dir)

    assert summary["exists"] is True
    assert summary["object_count"] == 0
    assert summary["valid"] is False
    assert "/tb_async_fifo/scenario_id" in summary["missing_required"]


def test_async_fifo_wave_screenshot_report_embeds_png_and_capture_script(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = reports_dir / "wave_visibility.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-png")
    (reports_dir / "wave_screenshot_metrics.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado 2025.2",
                "width": 1600,
                "height": 900,
                "sampled_pixels": 4096,
                "unique_colors": 128,
                "non_uniform_pixels": 3011,
                "non_uniform_ratio": 0.7351,
            }
        ),
        encoding="utf-8",
    )

    report = async_fifo_plugin(agent).write_async_fifo_wave_screenshot_report(project_dir)
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    script_text = report["capture_script_path"].read_text(encoding="utf-8")

    assert report["captured"] is True
    assert report["screenshot_status"] == "PASS"
    assert "PASS" in text
    assert "wave_visibility.png" in text
    assert "CopyFromScreen" in script_text
    assert "GetForegroundWindow" in script_text
    assert "wave_screenshot_metrics.json" in script_text
    assert 'class="screenshot-card pass"' in html_text
    assert "<img" in html_text
    assert "wave_visibility.png" in html_text


def test_async_fifo_reports_index_links_core_reports_and_lessons(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "sim_summary.html",
        "regression_summary.html",
        "wave_visibility.html",
        "wave_screenshot.html",
        "uvm_coverage_summary.html",
    ]:
        (reports_dir / name).write_text("<html></html>\n", encoding="utf-8")
    xcrg_code_report = (
        reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html"
    )
    xcrg_func_report = (
        reports_dir
        / "uvm_coverage_xcrg"
        / "functionalCoverageReport"
        / "dashboard.html"
    )
    xcrg_code_report.parent.mkdir(parents=True, exist_ok=True)
    xcrg_func_report.parent.mkdir(parents=True, exist_ok=True)
    xcrg_code_report.write_text("<html>code</html>\n", encoding="utf-8")
    xcrg_func_report.write_text("<html>functional</html>\n", encoding="utf-8")
    (reports_dir / "xcrg_coverage.log").write_text("xcrg ok\n", encoding="utf-8")
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "Line Coverage Score 60.2041\n"
        "Branch Coverage Score 23.5294\n"
        "Condition Coverage Score 22\n"
        "Toggle Coverage Score 4.84\n",
        encoding="utf-8",
    )

    report = async_fifo_plugin(agent).write_async_fifo_reports_index(project_dir)
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")

    assert report["ready_count"] >= 4
    assert "sim_summary.html" in text
    assert "regression_summary.html" in text
    assert "wave_visibility.html" in text
    assert "wave_screenshot.html" in text
    assert "docs/vivado_async_fifo_lessons_learned.md" in text
    assert "uvm_coverage_summary.html" in text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in text
    assert "uvm_coverage_xcrg/functionalCoverageReport/dashboard.html" in text
    assert "xcrg_coverage.log" in text
    assert "uvm_coverage_percent.txt" in text
    assert 'class="report-card ready"' in html_text
    assert 'class="target-selector"' in html_text
    assert 'href="../../index.html"' in html_text
    assert 'data-stage="Simulation"' in html_text
    assert 'data-stage="Coverage"' in html_text


def test_async_fifo_summary_report_includes_wcfg_scenarios_and_commands(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    sim_dir = project_dir / "sim"
    vcd_path = sim_dir / "async_fifo_trace.vcd"
    wdb_path = sim_dir / "async_fifo_smoke_20260709_000000.wdb"
    vcd_path.write_text("$date\nasync fifo\n$end\n", encoding="utf-8")
    wdb_path.write_text("wdb", encoding="utf-8")
    (sim_dir / "latest_async_fifo_wdb.txt").write_text(wdb_path.name + "\n", encoding="utf-8")
    _write_valid_wcfg(sim_dir / "async_fifo_debug.wcfg")
    monkeypatch.setattr(
        plugin,
        "collect_async_fifo_vcd_analysis",
        lambda output_dir="outputs", limit=20: {
            "info": {
                "signal_count": 48,
                "time_min_h": "0 ns",
                "time_max_h": "1200 ns",
                "duration_h": "1200 ns",
                "timescale": "1 ns",
            },
            "write_events": {"total": 70, "events": []},
            "read_events": {"total": 70, "events": []},
        },
    )

    report_path = plugin.write_async_fifo_sim_report(project_dir, vcd_path, wdb_path)
    summary_path = project_dir / "reports" / "sim_summary.md"
    html_path = project_dir / "reports" / "sim_summary.html"
    summary_text = summary_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")

    assert report_path.exists()
    assert "basic_ordered" in summary_text
    assert "mixed_stress" in summary_text
    assert "`python .trae/agent/agent.py --open-wave async-fifo --output-dir outputs`" in summary_text
    assert "regression_matrix.md" in summary_text
    assert "<html lang=\"zh-CN\">" in html_text
    assert 'class="metric-card"' in html_text
    assert 'class="status-pill pass"' in html_text
    assert "font-family:" in html_text
    mojibake_tokens = ["娴犺法婀", "閹芥", "闂傤", "閸︾", "閿"]
    assert not any(token in summary_text for token in mojibake_tokens)
    assert not any(token in html_text for token in mojibake_tokens)


def test_cli_sim_rtl_async_fifo_invokes_runner(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_rtl_sim(self, target, output_dir="outputs", open_wave_gui=True):
        calls.append((target, output_dir, open_wave_gui))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "run_rtl_sim", fake_run_rtl_sim)

    assert module.main(
        ["--sim-rtl", "async-fifo", "--no-wave-gui", "--output-dir", str(tmp_path)]
    ) == 0
    assert calls == [("async-fifo", str(tmp_path), False)]
