import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
PROJECT_OVERVIEW_PATH = AGENT_DIR / "project_overview.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_local_module(module_name, module_path):
    relative_module = module_path.relative_to(AGENT_DIR).with_suffix("")
    qualified_name = ".".join(relative_module.parts)
    return importlib.import_module(
        "digital_ic_agent._runtime.{}".format(qualified_name)
    )

def run_agent(*args):
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _agent_with_targets():
    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                },
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                },
            ]

    return FakeAgent()


def _write_manifest(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_p5_11_project_overview_aggregates_targets_environment_and_links(tmp_path):
    module = load_local_module("project_overview_split_complete", PROJECT_OVERVIEW_PATH)

    async_dir = tmp_path / "async-fifo"
    sync_dir = tmp_path / "sync-fifo"
    environment_dir = tmp_path / "environment-report"
    for report_path in [
        async_dir / "reports" / "design_spec.html",
        async_dir / "reports" / "sim_report.html",
        async_dir / "reports" / "wave_visibility.html",
        sync_dir / "reports" / "design_spec.html",
        sync_dir / "reports" / "sim_report.html",
        environment_dir / "environment_report.html",
    ]:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("<html lang=\"zh-CN\"></html>\n", encoding="utf-8")

    _write_manifest(
        async_dir / "artifacts.json",
        {
            "schema_version": 1,
            "target": "async-fifo",
            "updated_at": "2026-07-10T12:00:00.000Z",
            "runs": [
                {
                    "flow": "generate-spec",
                    "status": "PASS",
                    "recorded_at": "2026-07-10T10:00:00.000Z",
                    "error": None,
                },
                {
                    "flow": "sim-rtl",
                    "status": "FAIL",
                    "recorded_at": "2026-07-10T12:00:00.000Z",
                    "error": "simulation failed",
                },
            ],
        },
    )
    _write_manifest(
        sync_dir / "artifacts.json",
        {
            "schema_version": 1,
            "target": "sync-fifo",
            "updated_at": "2026-07-10T11:00:00.000Z",
            "runs": [
                {
                    "flow": "sim-rtl",
                    "status": "PASS",
                    "recorded_at": "2026-07-10T11:00:00.000Z",
                    "error": None,
                }
            ],
        },
    )
    _write_manifest(
        environment_dir / "artifacts.json",
        {
            "schema_version": 1,
            "scope": "environment",
            "updated_at": "2026-07-10T09:00:00.000Z",
            "runs": [
                {
                    "flow": "environment-report",
                    "status": "WARN",
                    "recorded_at": "2026-07-10T09:00:00.000Z",
                    "error": None,
                }
            ],
        },
    )

    result = module.write_project_overview(_agent_with_targets(), output_dir=tmp_path)

    assert result["status"] == "FAIL"
    assert result["target_count"] == 2
    assert result["ready_target_count"] == 1
    assert result["failed_target_count"] == 1
    assert result["environment_status"] == "WARN"
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "| async-fifo | Asynchronous FIFO | FAIL | sim-rtl | FAIL |" in markdown
    assert "| sync-fifo | Synchronous FIFO | PASS | sim-rtl | PASS |" in markdown
    assert "simulation failed" in markdown
    assert "environment-report/environment_report.html" in markdown
    assert 'href="async-fifo/reports/design_spec.html"' in html_text
    assert 'href="sync-fifo/reports/design_spec.html"' in html_text
    assert 'class="target-card fail"' in html_text
    assert 'class="target-card pass"' in html_text


def test_p5_11_project_overview_handles_empty_output_as_not_run(tmp_path):
    module = load_local_module("project_overview_split_empty", PROJECT_OVERVIEW_PATH)

    result = module.write_project_overview(_agent_with_targets(), output_dir=tmp_path)

    assert result["status"] == "WARN"
    assert result["target_count"] == 2
    assert result["ready_target_count"] == 0
    assert result["failed_target_count"] == 0
    assert result["environment_status"] == "MISSING"
    assert [item["status"] for item in result["targets"]] == [
        "NOT_RUN",
        "NOT_RUN",
    ]
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "NOT_RUN" in markdown
    for missing_href in [
        "environment-report/artifacts.json",
        "async-fifo/artifacts.json",
        "sync-fifo/artifacts.json",
    ]:
        assert missing_href not in markdown
        assert missing_href not in html_text


def test_p5_11_project_overview_keeps_other_targets_when_manifest_is_invalid(tmp_path):
    module = load_local_module("project_overview_split_invalid", PROJECT_OVERVIEW_PATH)

    async_dir = tmp_path / "async-fifo"
    sync_dir = tmp_path / "sync-fifo"
    async_dir.mkdir(parents=True)
    sync_dir.mkdir(parents=True)
    (async_dir / "artifacts.json").write_text("{broken", encoding="utf-8")
    _write_manifest(
        sync_dir / "artifacts.json",
        {
            "schema_version": 1,
            "target": "sync-fifo",
            "updated_at": "2026-07-10T11:00:00.000Z",
            "runs": [
                {
                    "flow": "generate-rtl",
                    "status": "PASS",
                    "recorded_at": "2026-07-10T11:00:00.000Z",
                    "error": None,
                }
            ],
        },
    )

    result = module.write_project_overview(_agent_with_targets(), output_dir=tmp_path)

    assert result["status"] == "FAIL"
    assert result["targets"][0]["status"] == "INVALID"
    assert result["targets"][1]["status"] == "PASS"
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    assert "artifacts.json" in markdown
    assert "INVALID" in markdown
    assert "sync-fifo" in markdown


def test_p5_11_cli_generates_empty_project_overview(tmp_path):
    result = run_agent(
        "--generate-overview",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "index.html").exists()
    assert "NOT_RUN" in (tmp_path / "index.md").read_text(encoding="utf-8")


def test_p5_11_cli_reports_output_failure_without_traceback(tmp_path):
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("blocked", encoding="utf-8")

    result = run_agent(
        "--generate-overview",
        "--output-dir",
        str(output_file),
    )

    assert result.returncode == 1
    assert "项目总览生成失败" in result.stderr
    assert "Traceback" not in result.stderr


def test_p5_11_target_flow_refreshes_top_level_overview(tmp_path):
    result = run_agent(
        "--generate-rtl",
        "sync-fifo",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    overview_path = tmp_path / "index.md"
    assert overview_path.exists()
    overview = overview_path.read_text(encoding="utf-8")
    assert "| sync-fifo | Synchronous FIFO | PASS | generate-rtl | PASS |" in overview
    assert "| async-fifo | Asynchronous FIFO | NOT_RUN |" in overview


def test_p5_11_environment_report_refreshes_top_level_overview(tmp_path):
    result = run_agent(
        "--environment-report",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    overview_path = tmp_path / "index.md"
    assert overview_path.exists()
    overview = overview_path.read_text(encoding="utf-8")
    assert "environment-report/environment_report.html" in overview
