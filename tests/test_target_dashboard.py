import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
PROJECT_OVERVIEW_PATH = AGENT_DIR / "project_overview.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location("digital_ic_agent", AGENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_local_module(module_name, module_path):
    module_dir = str(module_path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_p4_7_target_dashboard_groups_stages_recent_run_and_failure_entry(tmp_path):
    module = load_local_module("target_dashboard_split_complete", PROJECT_OVERVIEW_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                },
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                },
            ]

    project_dir = tmp_path / "async-fifo"
    reports_dir = project_dir / "reports"
    (project_dir / "rtl").mkdir(parents=True)
    (project_dir / "uvm").mkdir()
    reports_dir.mkdir()
    (project_dir / "rtl" / "async_fifo.v").write_text(
        "module async_fifo; endmodule\n",
        encoding="utf-8",
    )
    (project_dir / "uvm" / "tb_async_fifo_uvm.sv").write_text(
        "module tb_async_fifo_uvm; endmodule\n",
        encoding="utf-8",
    )
    (project_dir / "README.md").write_text("# async-fifo\n", encoding="utf-8")
    for relative_path in [
        "design_spec.html",
        "sim_summary.html",
        "uvm_coverage_summary.html",
        "wave_visibility.html",
        "coverage_trend.html",
    ]:
        (reports_dir / relative_path).write_text("<html></html>\n", encoding="utf-8")
    xcrg_dashboard = reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html"
    xcrg_detail = xcrg_dashboard.parent / "modules" / "detail.html"
    xcrg_detail.parent.mkdir(parents=True)
    xcrg_dashboard.write_text("<html>dashboard</html>\n", encoding="utf-8")
    xcrg_detail.write_text("<html>detail</html>\n", encoding="utf-8")
    (project_dir / "artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target": "async-fifo",
                "updated_at": "2026-07-10T12:03:00Z",
                "runs": [
                    {
                        "flow": "sim-rtl",
                        "status": "PASS",
                        "recorded_at": "2026-07-10T12:00:00Z",
                        "command": ["python", "agent.py", "--sim-rtl", "async-fifo"],
                        "error": None,
                    },
                    {
                        "flow": "uvm-coverage",
                        "status": "FAIL",
                        "recorded_at": "2026-07-10T12:01:00Z",
                        "command": ["python", "agent.py", "--uvm-coverage", "async-fifo"],
                        "error": "coverage gate failed",
                    },
                    {
                        "flow": "check-rtl",
                        "status": "PASS",
                        "recorded_at": "2026-07-10T12:03:00Z",
                        "command": ["python", "agent.py", "--check-rtl", "async-fifo"],
                        "error": None,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    failure_manifest = (
        project_dir
        / "failure_archives"
        / "uvm-coverage"
        / "seed_22"
        / "failure_archive.json"
    )
    failure_manifest.parent.mkdir(parents=True)
    failure_manifest.write_text("{}\n", encoding="utf-8")
    (tmp_path / "sync-fifo" / "reports").mkdir(parents=True)

    result = module.write_target_dashboard(FakeAgent(), project_dir)

    assert result["target_count"] == 2
    assert result["stage_count"] == 7
    assert result["ready_stage_count"] == 7
    assert result["latest_run"]["flow"] == "check-rtl"
    assert result["latest_run"]["status"] == "PASS"
    assert result["last_failure"]["flow"] == "uvm-coverage"
    assert result["failure_href"] == (
        "../failure_archives/uvm-coverage/seed_22/failure_archive.json"
    )
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert 'class="target-selector"' in html_text
    assert 'aria-current="page">async-fifo</a>' in html_text
    assert 'class="failure-entry fail"' in html_text
    assert "coverage gate failed" in html_text
    assert "failure_archive.json" in html_text
    assert "uvm_coverage_xcrg/codeCoverageReport/dashboard.html" in html_text
    assert "uvm_coverage_xcrg/codeCoverageReport/modules/detail.html" not in html_text


def test_p4_7_target_dashboard_handles_not_run_without_failure_archive(tmp_path):
    module = load_local_module("target_dashboard_split_empty", PROJECT_OVERVIEW_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                }
            ]

    project_dir = tmp_path / "sync-fifo"
    (project_dir / "rtl").mkdir(parents=True)
    (project_dir / "rtl" / "sync_fifo.v").write_text(
        "module sync_fifo; endmodule\n",
        encoding="utf-8",
    )

    result = module.write_target_dashboard(FakeAgent(), project_dir)

    assert result["status"] == "NOT_RUN"
    assert result["latest_run"] is None
    assert result["last_failure"] is None
    assert result["failure_href"] == "../artifacts.json"
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert 'class="failure-entry clear"' in html_text
    assert 'data-stage="RTL"' in html_text
    assert "NOT_RUN" in html_text


def test_target_dashboard_uses_manifest_freshness_and_detects_modified_artifact(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("sync-fifo", tmp_path)

    initial = agent.write_target_dashboard(project_dir)
    initial_surfaces = {
        surface["id"]: surface
        for surface in initial["surfaces"]
    }
    assert initial_surfaces["RTL"]["status"] == "CURRENT"

    rtl_path = project_dir / "rtl" / "sync_fifo.v"
    rtl_path.write_text(
        rtl_path.read_text(encoding="utf-8") + "\n// modified after run\n",
        encoding="utf-8",
    )

    modified = agent.write_target_dashboard(project_dir)
    modified_surfaces = {
        surface["id"]: surface
        for surface in modified["surfaces"]
    }
    assert modified_surfaces["RTL"]["status"] == "INVALID"


def test_target_dashboard_marks_outputs_stale_when_source_input_changes(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("sync-fifo", tmp_path)
    wave_path = project_dir / "sim" / "sync_fifo_smoke.wdb"
    wave_path.write_text("fresh-wave\n", encoding="utf-8")
    agent.record_artifact_run(
        "sync-fifo",
        "sim-rtl",
        output_dir=tmp_path,
        status="PASS",
    )

    initial = agent.write_target_dashboard(project_dir)
    initial_surfaces = {
        surface["id"]: surface
        for surface in initial["surfaces"]
    }
    assert initial_surfaces["Wave"]["status"] == "CURRENT"

    rtl_path = project_dir / "rtl" / "sync_fifo.v"
    rtl_path.write_text(
        rtl_path.read_text(encoding="utf-8") + "\n// changed input\n",
        encoding="utf-8",
    )

    modified = agent.write_target_dashboard(project_dir)
    modified_surfaces = {
        surface["id"]: surface
        for surface in modified["surfaces"]
    }
    assert modified["status"] == "STALE"
    assert modified_surfaces["Wave"]["status"] == "STALE"


def test_target_dashboard_marks_outputs_stale_when_tool_version_changes(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("sync-fifo", tmp_path)
    wave_path = project_dir / "sim" / "sync_fifo_smoke.wdb"
    wave_path.write_text("fresh-wave\n", encoding="utf-8")
    monkeypatch.setattr(
        agent,
        "resolve_vivado_command",
        lambda: r"D:\vivado\2025.2\Vivado\bin\vivado.bat",
    )
    agent.record_artifact_run(
        "sync-fifo",
        "sim-rtl",
        output_dir=tmp_path,
        status="PASS",
    )

    initial = agent.write_target_dashboard(project_dir)
    assert initial["status"] == "PASS"

    monkeypatch.setattr(
        agent,
        "resolve_vivado_command",
        lambda: r"D:\vivado\2026.1\Vivado\bin\vivado.bat",
    )
    modified = agent.write_target_dashboard(project_dir)
    modified_surfaces = {
        surface["id"]: surface
        for surface in modified["surfaces"]
    }
    assert modified["status"] == "STALE"
    assert modified_surfaces["Wave"]["status"] == "STALE"
