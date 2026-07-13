import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
WAVE_VISIBILITY_PATH = AGENT_DIR / "wave_visibility.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    return importlib.import_module("digital_ic_agent._runtime.agent")

def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


def load_local_module(module_name, module_path):
    relative_module = module_path.relative_to(AGENT_DIR).with_suffix("")
    qualified_name = ".".join(relative_module.parts)
    return importlib.import_module(
        "digital_ic_agent._runtime.{}".format(qualified_name)
    )

def test_async_fifo_wave_visibility_report_validates_gui_preflight(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)
    sim_dir = project_dir / "sim"
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    xpr = project_dir / "vivado_project" / "async_fifo_project.xpr"
    xpr.parent.mkdir(parents=True, exist_ok=True)
    xpr.write_text("<Project />\n", encoding="utf-8")
    (sim_dir / "async_fifo_smoke_20260709_000000.wdb").write_text(
        "wdb",
        encoding="utf-8",
    )
    (sim_dir / "latest_async_fifo_wdb.txt").write_text(
        "async_fifo_smoke_20260709_000000.wdb\n",
        encoding="utf-8",
    )
    (sim_dir / "async_fifo_debug.wcfg").write_text(
        "\n".join(
            [
                '<WVObjectSize size="31" />',
                '<wvobject fp_name="/tb_async_fifo/scenario_id" />',
                '<wvobject fp_name="/tb_async_fifo/wr_clk" />',
                '<wvobject fp_name="/tb_async_fifo/rd_clk" />',
                '<wvobject fp_name="/tb_async_fifo/write_count" />',
                '<wvobject fp_name="/tb_async_fifo/read_count" />',
                '<wvobject fp_name="/tb_async_fifo/dut/full_reg" />',
                '<wvobject fp_name="/tb_async_fifo/dut/empty_reg" />',
            ]
        ),
        encoding="utf-8",
    )
    (reports_dir / "wave_open_check.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_name": "async-fifo",
                "flow_name": "sim-rtl",
                "wave_database": str(sim_dir / "async_fifo_smoke_20260709_000000.wdb"),
                "wdb_opened": True,
                "scope_count": 3,
                "object_count": 48,
                "wave_count": 31,
                "wave_config_count": 1,
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
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

    report = async_fifo_plugin(agent).write_async_fifo_wave_visibility_report(project_dir)
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")

    assert report["visible"] is True
    assert report["runtime_status"] == "PASS"
    assert report["screenshot_status"] == "PASS"
    assert "open_project" in text
    assert "open_wave_database" in text
    assert "WCFG" in text
    assert "Scope" in text
    assert "Object" in text
    assert "Wave" in text
    assert 'class="visibility-card pass"' in html_text


def test_p4_6_wave_open_check_evaluates_runtime_and_screenshot_metrics(tmp_path):
    module = load_local_module("wave_visibility_split_p4_6", WAVE_VISIBILITY_PATH)
    probe_path = tmp_path / "wave_open_check.json"
    metrics_path = tmp_path / "wave_screenshot_metrics.json"
    probe_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_name": "sync-fifo",
                "flow_name": "formal-smoke",
                "wave_database": "sync_fifo.wdb",
                "wdb_opened": True,
                "scope_count": 2,
                "object_count": 18,
                "wave_count": 12,
                "wave_config_count": 1,
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado",
                "width": 1280,
                "height": 720,
                "sampled_pixels": 2048,
                "unique_colors": 64,
                "non_uniform_pixels": 1024,
                "non_uniform_ratio": 0.5,
            }
        ),
        encoding="utf-8",
    )

    result = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )

    assert result["status"] == "PASS"
    assert result["runtime_status"] == "PASS"
    assert result["screenshot_status"] == "PASS"
    assert result["visible"] is True
    assert result["probe"]["target_name"] == "sync-fifo"
    assert result["probe"]["flow_name"] == "formal-smoke"
    assert result["probe"]["scope_count"] == 2
    assert result["probe"]["object_count"] == 18
    assert result["probe"]["wave_count"] == 12
    assert result["screenshot_metrics"]["unique_colors"] == 64


def test_p4_6_wave_open_check_rejects_empty_runtime_and_blank_screenshot(tmp_path):
    module = load_local_module("wave_visibility_split_empty_p4_6", WAVE_VISIBILITY_PATH)
    probe_path = tmp_path / "wave_open_check.json"
    metrics_path = tmp_path / "wave_screenshot_metrics.json"
    probe_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_name": "round-robin-arbiter",
                "flow_name": "sim-rtl",
                "wave_database": "arbiter.wdb",
                "wdb_opened": True,
                "scope_count": 0,
                "object_count": 0,
                "wave_count": 0,
                "wave_config_count": 0,
                "diagnostics": ["get_scopes returned no scopes"],
            }
        ),
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "window_title": "Vivado",
                "width": 1280,
                "height": 720,
                "sampled_pixels": 2048,
                "unique_colors": 1,
                "non_uniform_pixels": 0,
                "non_uniform_ratio": 0.0,
            }
        ),
        encoding="utf-8",
    )

    result = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )

    assert result["status"] == "FAIL"
    assert result["runtime_status"] == "FAIL"
    assert result["screenshot_status"] == "FAIL"
    assert result["visible"] is False
    assert {"scope_count", "object_count", "wave_count", "wave_config_count"} <= {
        item["id"] for item in result["checks"] if item["status"] == "FAIL"
    }
    assert "unique_colors" in {
        item["id"] for item in result["screenshot_checks"] if item["status"] == "FAIL"
    }


def test_p4_6_wave_open_check_handles_missing_corrupt_and_invalid_values(tmp_path):
    module = load_local_module("wave_visibility_split_edges_p4_6", WAVE_VISIBILITY_PATH)
    probe_path = tmp_path / "wave_open_check.json"
    metrics_path = tmp_path / "wave_screenshot_metrics.json"

    pending = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )
    assert pending["status"] == "PENDING"
    assert pending["runtime_status"] == "PENDING"
    assert pending["screenshot_status"] == "PENDING"
    assert pending["visible"] is False

    probe_path.write_text("{bad json", encoding="utf-8")
    corrupt_probe = module.evaluate_wave_open_check(probe_path)
    assert corrupt_probe["runtime_status"] == "FAIL"
    assert "invalid wave probe JSON" in corrupt_probe["diagnostics"][0]

    probe_path.write_text("[]", encoding="utf-8")
    non_object_probe = module.evaluate_wave_open_check(probe_path)
    assert "wave probe must be a JSON object" in non_object_probe["diagnostics"][0]

    probe_path.write_text('{"schema_version": 2}', encoding="utf-8")
    unsupported_probe = module.evaluate_wave_open_check(probe_path)
    assert "unsupported wave probe schema" in unsupported_probe["diagnostics"][0]

    probe_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "wdb_opened": False,
                "scope_count": "invalid",
                "object_count": None,
                "wave_count": "invalid",
                "wave_config_count": False,
                "diagnostics": "not-a-list",
            }
        ),
        encoding="utf-8",
    )
    metrics_path.write_text("{bad metrics", encoding="utf-8")
    invalid_values = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )
    assert invalid_values["runtime_status"] == "FAIL"
    assert invalid_values["screenshot_status"] == "FAIL"
    assert invalid_values["visible"] is False
    assert any(
        "invalid wave screenshot metrics JSON" in item
        for item in invalid_values["diagnostics"]
    )

    metrics_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "width": "invalid",
                "height": None,
                "sampled_pixels": False,
                "unique_colors": "invalid",
                "non_uniform_ratio": "invalid",
            }
        ),
        encoding="utf-8",
    )
    invalid_metrics = module.evaluate_wave_open_check(
        probe_path,
        screenshot_metrics_path=metrics_path,
    )
    assert invalid_metrics["screenshot_status"] == "FAIL"
    assert {
        "width",
        "height",
        "sampled_pixels",
        "unique_colors",
        "non_uniform_ratio",
    } == {
        item["id"]
        for item in invalid_metrics["screenshot_checks"]
        if item["status"] == "FAIL"
    }


def test_p4_6_wave_probe_and_capture_scripts_are_flow_agnostic():
    module = load_local_module("wave_visibility_split_scripts_p4_6", WAVE_VISIBILITY_PATH)

    probe_tcl = module.render_wave_open_probe_tcl(
        "../reports/wave_open_check.json",
        target_name="sync-fifo",
        flow_name="formal-smoke",
    )
    capture_script = module.render_window_capture_script(
        screenshot_name="formal_wave.png",
        metrics_name="formal_wave_metrics.json",
    )

    assert "get_scopes" in probe_tcl
    assert "get_objects" in probe_tcl
    assert "get_waves" in probe_tcl
    assert "wave_config_count" in probe_tcl
    assert "formal-smoke" in probe_tcl
    assert "GetForegroundWindow" in capture_script
    assert "GetWindowRect" in capture_script
    assert "unique_colors" in capture_script
    assert "non_uniform_ratio" in capture_script
    source = WAVE_VISIBILITY_PATH.read_text(encoding="utf-8")
    assert "tb_async_fifo" not in source
    assert "async_fifo" not in source


def test_p4_6_async_fifo_gui_script_ignores_stale_latest_wdb_pointer():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    script = async_fifo_plugin(agent).render_async_fifo_open_project_gui_script()

    assert "set latest_candidate [file normalize [file join $script_dir $latest_wdb]]" in script
    assert 'if {$latest_wdb ne "" && [file exists $latest_candidate]}' in script
    assert "set wave_db $latest_candidate" in script


def test_p4_6_wave_visibility_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"src/digital_ic_agent"' in pyproject
