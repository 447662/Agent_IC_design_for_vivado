import gzip
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
COVERAGE_HISTORY_PATH = AGENT_DIR / "coverage_history.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_coverage_history_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


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


def test_p4_4_appends_coverage_history_and_renders_trend_deltas(tmp_path):
    module = load_local_module("coverage_history_split_p4_4", COVERAGE_HISTORY_PATH)
    reports_dir = tmp_path / "reports"
    common = {
        "target_name": "async-fifo",
        "flow_name": "uvm-coverage",
        "toolchain": {
            "vivado": {
                "version": "2025.2",
                "command": r"D:\vivado\2025.2\Vivado\bin\vivado.bat",
            }
        },
        "coverage_gates": {
            "total": {"result": "PASS", "threshold": 75.0},
            "branch": {"result": "PASS", "threshold": 70.0},
        },
        "status": "PASS",
    }

    first = module.append_coverage_history(
        reports_dir,
        recorded_at="2026-07-10T01:00:00.000Z",
        seed_set=[11],
        coverage_metrics={
            "total": 80.0,
            "statement": 90.0,
            "branch": 75.0,
            "condition": 78.0,
            "toggle": 66.0,
            "functional": None,
        },
        **common,
    )
    second = module.append_coverage_history(
        reports_dir,
        recorded_at="2026-07-10T02:00:00.000Z",
        seed_set=[22],
        coverage_metrics={
            "total": 82.0,
            "statement": 91.0,
            "branch": 74.0,
            "condition": 80.0,
            "toggle": 70.0,
            "functional": 95.0,
        },
        **common,
    )

    history_lines = first["history_path"].read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in history_lines]
    assert len(records) == 2
    assert records[0]["schema_version"] == 1
    assert records[0]["target_name"] == "async-fifo"
    assert records[0]["flow_name"] == "uvm-coverage"
    assert records[0]["toolchain"]["vivado"]["version"] == "2025.2"
    assert records[0]["seed_set"] == [11]
    assert records[1]["coverage_metrics"]["functional"] == 95.0
    assert second["metric_deltas"]["total"] == 2.0
    assert second["metric_deltas"]["branch"] == -1.0

    markdown = second["markdown_path"].read_text(encoding="utf-8")
    html_text = second["html_path"].read_text(encoding="utf-8")
    assert "| Total | 82.0% | +2.0% |" in markdown
    assert "| Branch | 74.0% | -1.0% |" in markdown
    assert "2026-07-10T01:00:00.000Z" in markdown
    assert "2026-07-10T02:00:00.000Z" in markdown
    assert 'data-target="async-fifo"' in html_text
    assert 'class="delta trend-up"' in html_text
    assert 'class="delta trend-down"' in html_text


def test_history_rotation_archives_coverage_records_and_keeps_latest_deltas(
    tmp_path,
):
    module = load_local_module(
        "coverage_history_split_rotation",
        COVERAGE_HISTORY_PATH,
    )
    reports_dir = tmp_path / "reports"
    result = None
    for index in range(4):
        result = module.append_coverage_history(
            reports_dir,
            target_name="async-fifo",
            flow_name="uvm-coverage",
            toolchain={"vivado": {"version": "2025.2"}},
            seed_set=[index],
            coverage_metrics={
                "total": 80.0 + index,
                "statement": 90.0,
                "branch": 75.0,
                "condition": 78.0,
                "toggle": 66.0,
                "functional": 95.0,
            },
            coverage_gates={},
            status="PASS",
            recorded_at="2026-07-11T01:0{}:00.000Z".format(index),
            max_active_records=2,
        )

    assert result is not None
    active_records = module.load_coverage_history(
        reports_dir / "coverage_history.jsonl"
    )
    assert [record["seed_set"] for record in active_records] == [[2], [3]]
    assert result["metric_deltas"]["total"] == 1.0

    archive_path = reports_dir / "coverage_history.archive.jsonl.gz"
    with gzip.open(archive_path, "rt", encoding="utf-8") as stream:
        archived = [json.loads(line) for line in stream.read().splitlines()]
    assert [record["seed_set"] for record in archived] == [[0], [1]]
    assert result["archive_path"] == archive_path
    assert result["archived_records"] == 2

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "coverage_history.archive.jsonl.gz" in markdown
    assert "coverage_history.archive.jsonl.gz" in html_text


def test_p4_4_history_reports_invalid_jsonl_line(tmp_path):
    module = load_local_module(
        "coverage_history_split_invalid_p4_4",
        COVERAGE_HISTORY_PATH,
    )
    history_path = tmp_path / "coverage_history.jsonl"
    history_path.write_text(
        '{"schema_version": 1, "target_name": "async-fifo"}\n'
        "not-json\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="line 2"):
        module.load_coverage_history(history_path)


def test_p4_4_runner_appends_pass_and_fail_history_and_refreshes_index(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    run_count = 0

    monkeypatch.setattr(plugin, "resolve_vivado_command", lambda: vivado_path)

    def fake_run(
        command,
        cwd=None,
        capture_output=False,
        text=False,
        encoding=None,
        errors=None,
        timeout=None,
        check=False,
        env=None,
    ):
        nonlocal run_count
        run_count += 1
        sim_dir = Path(cwd)
        reports_dir = sim_dir.parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n"
            "ASYNC_FIFO_UVM_FCOV_PASS full=1 empty=1 reset=1 mixed=1\n"
            "ASYNC_FIFO_UVM_ASSERT_PASS\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text(
            "wdb placeholder",
            encoding="utf-8",
        )
        cov_dir = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
        cov_dir.mkdir(parents=True, exist_ok=True)
        (cov_dir / "xsim.CCInfo").write_bytes(
            b"xsim.codeCov\x00async_fifo_uvm_cov\x00sbct\x00"
        )
        branch_score = 84.0 if run_count == 1 else 48.0
        total_score = 80.25 if run_count == 1 else 75.0
        (reports_dir / "uvm_coverage_percent.txt").write_text(
            "Statement Coverage : 91.5%\n"
            "Branch Coverage : {:.1f}%\n"
            "Condition Coverage : 79.5%\n"
            "Toggle Coverage : 66.0%\n"
            "Total Coverage : {:.2f}%\n".format(branch_score, total_score),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert plugin.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_thresholds={"branch": 50.0},
        seed=11,
    ) is True
    assert plugin.run_async_fifo_uvm_coverage(
        output_dir=tmp_path,
        coverage_thresholds={"branch": 50.0},
        seed=22,
    ) is False

    reports_dir = tmp_path / "async-fifo" / "reports"
    history_path = reports_dir / "coverage_history.jsonl"
    records = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["PASS", "FAIL"]
    assert [record["seed_set"] for record in records] == [[11], [22]]
    assert records[0]["toolchain"]["vivado"]["version"] == "2025.2"
    assert records[1]["coverage_gates"]["branch"]["result"] == "FAIL"
    trend = (reports_dir / "coverage_trend.md").read_text(encoding="utf-8")
    index = (reports_dir / "index.md").read_text(encoding="utf-8")
    assert "| Total | 75.0% | -5.2% |" in trend
    assert "| Branch | 48.0% | -36.0% |" in trend
    assert "coverage_trend.html" in index
    assert "coverage_history.jsonl" in index


def test_p4_4_coverage_history_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/coverage_history.py"' in pyproject
