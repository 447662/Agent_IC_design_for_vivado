import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
AGENT_CLI_PATH = AGENT_DIR / "agent_cli.py"
COVERAGE_CLOSURE_PATH = AGENT_DIR / "coverage_closure.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


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


def run_agent(*args):
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _coverage_metrics():
    return [
        {
            "id": "statement",
            "label": "Statement coverage",
            "source": "Vivado xcrg",
            "status": "PASS",
        },
        {
            "id": "branch",
            "label": "Branch coverage",
            "source": "Vivado xcrg",
            "status": "PASS",
        },
        {
            "id": "condition",
            "label": "Condition coverage",
            "source": "Vivado xcrg",
            "status": "PASS",
        },
        {
            "id": "toggle",
            "label": "Toggle coverage",
            "source": "Vivado xcrg",
            "status": "PASS",
        },
        {
            "id": "functional",
            "label": "Functional coverage",
            "source": "UVM covergroup",
            "status": "PASS",
        },
    ]


def test_p4_0_parses_xcrg_scores_and_existing_gate_threshold():
    module = load_local_module("coverage_closure_split_parser", COVERAGE_CLOSURE_PATH)
    score_text = """
Line Coverage Score 60.2041
Branch Coverage Score 23.5294
Condition Coverage Score 22
Toggle Coverage Score 4.84
"""
    summary_text = """
- Current coverage: 27.6%
- Coverage threshold: 1.0%
"""

    scores = module.parse_coverage_scores(score_text, summary_text)

    assert scores == {
        "total": 27.6,
        "statement": 60.2,
        "branch": 23.5,
        "condition": 22.0,
        "toggle": 4.8,
    }
    assert module.parse_gate_threshold(summary_text) == 1.0


def test_p4_0_coverage_dashboard_aggregates_gaps_and_skipped_targets(tmp_path):
    module = load_local_module("coverage_closure_split_dashboard", COVERAGE_CLOSURE_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": [
                        {"id": "full_boundary", "status": "PASS"},
                        {"id": "reset_recovery", "status": "PASS"},
                    ],
                    "coverage_metrics": _coverage_metrics(),
                },
                {
                    "name": "sync-fifo",
                    "display_name": "Synchronous FIFO",
                    "design_family": "fifo",
                    "flows": [],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "statement",
                            "label": "Statement coverage",
                            "source": "not-enabled",
                            "status": "SKIP",
                        },
                        {
                            "id": "functional",
                            "label": "Functional coverage",
                            "source": "no-uvm-flow",
                            "status": "N/A",
                        },
                    ],
                },
                {
                    "name": "round-robin-arbiter",
                    "display_name": "Round-Robin Arbiter",
                    "design_family": "arbiter",
                    "flows": [],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "not-enabled",
                            "status": "SKIP",
                        }
                    ],
                },
            ]

    async_dir = tmp_path / "async-fifo"
    reports_dir = async_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "\n".join(
            [
                "Line Coverage Score 60.2041",
                "Branch Coverage Score 23.5294",
                "Condition Coverage Score 22",
                "Toggle Coverage Score 4.84",
            ]
        ),
        encoding="utf-8",
    )
    (reports_dir / "uvm_coverage_summary.md").write_text(
        "\n".join(
            [
                "# async-fifo UVM coverage summary",
                "- Current coverage: 27.6%",
                "- Coverage threshold: 1.0%",
            ]
        ),
        encoding="utf-8",
    )
    for report_path in [
        reports_dir / "uvm_coverage_summary.html",
        reports_dir / "uvm_coverage_xcrg" / "codeCoverageReport" / "dashboard.html",
        reports_dir
        / "uvm_coverage_xcrg"
        / "functionalCoverageReport"
        / "dashboard.html",
        reports_dir / "xcrg_coverage.log",
        async_dir / "sim" / "async_fifo_uvm_coverage.wdb",
    ]:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("fixture\n", encoding="utf-8")

    result = module.write_coverage_closure_report(
        FakeAgent(),
        output_dir=tmp_path,
        target_threshold=80.0,
    )

    assert result["status"] == "WARN"
    assert result["target_count"] == 3
    assert result["gap_target_count"] == 1
    assert result["skipped_target_count"] == 2
    assert [item["name"] for item in result["targets"]] == [
        "async-fifo",
        "round-robin-arbiter",
        "sync-fifo",
    ]
    async_target = result["targets"][0]
    assert async_target["status"] == "GAP"
    assert async_target["current_total"] == 27.6
    assert async_target["current_threshold"] == 1.0
    assert async_target["target_threshold"] == 80.0
    assert async_target["gap"] == 52.4
    assert [item["id"] for item in async_target["coverage_gaps"]] == [
        "total",
        "statement",
        "branch",
        "condition",
        "toggle",
        "functional",
    ]
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "| async-fifo | fifo | GAP | 27.6% | 80.0% | 52.4% |" in markdown
    assert "| round-robin-arbiter | arbiter | SKIP | - | 80.0% | - |" in markdown
    assert "Statement coverage | 60.2% | 80.0% | GAP" in markdown
    assert "Functional coverage | - | 80.0% | MISSING" in markdown
    assert "../async-fifo/reports/uvm_coverage_summary.html" in markdown
    assert "../async-fifo/sim/async_fifo_uvm_coverage.wdb" in markdown
    assert '<html lang="zh-CN">' in html_text
    assert 'class="target-card gap"' in html_text


def test_p4_0_coverage_dashboard_marks_enabled_target_without_data_not_run(tmp_path):
    module = load_local_module("coverage_closure_split_not_run", COVERAGE_CLOSURE_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "enabled-target",
                    "display_name": "Enabled Target",
                    "design_family": "custom",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "xcrg",
                            "status": "PASS",
                        }
                    ],
                }
            ]

    result = module.write_coverage_closure_report(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "WARN"
    assert result["targets"][0]["status"] == "NOT_RUN"
    assert result["targets"][0]["current_total"] is None
    assert result["targets"][0]["gap"] is None
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    assert "| enabled-target | custom | NOT_RUN | 0.0% |" not in markdown


def test_p4_0_coverage_dashboard_isolates_invalid_target_report(tmp_path):
    module = load_local_module("coverage_closure_split_invalid", COVERAGE_CLOSURE_PATH)

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "broken-target",
                    "display_name": "Broken Target",
                    "design_family": "custom",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "xcrg",
                            "status": "PASS",
                        }
                    ],
                },
                {
                    "name": "skipped-target",
                    "display_name": "Skipped Target",
                    "design_family": "custom",
                    "flows": [],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": "branch",
                            "label": "Branch coverage",
                            "source": "not-enabled",
                            "status": "SKIP",
                        }
                    ],
                },
            ]

    report_path = tmp_path / "broken-target" / "reports" / "uvm_coverage_percent.txt"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("xcrg completed without score rows\n", encoding="utf-8")

    result = module.write_coverage_closure_report(FakeAgent(), output_dir=tmp_path)

    assert result["status"] == "FAIL"
    assert result["targets"][0]["status"] == "INVALID"
    assert result["targets"][1]["status"] == "SKIP"
    assert "coverage score" in result["targets"][0]["error"]


def test_p4_0_cli_accepts_coverage_closure_target():
    cli_module = load_local_module("agent_cli_split_p4_0", AGENT_CLI_PATH)

    args = cli_module.parse_args(["--coverage-closure", "--coverage-target", "85"])

    assert args.coverage_closure is True
    assert args.coverage_target == 85.0


def test_p4_0_cli_generates_empty_coverage_dashboard(tmp_path):
    result = run_agent(
        "--coverage-closure",
        "--coverage-target",
        "80",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "coverage-closure" / "index.md").exists()
    assert (tmp_path / "coverage-closure" / "index.html").exists()
    markdown = (tmp_path / "coverage-closure" / "index.md").read_text(encoding="utf-8")
    assert "| async-fifo | fifo | NOT_RUN | - | 80.0% | - |" in markdown
    assert "| sync-fifo | fifo | SKIP | - | 80.0% | - |" in markdown


def test_p4_0_coverage_closure_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/coverage_closure.py"' in pyproject


def _write_p4_1_xcrg_fixture(project_dir):
    code_dir = (
        project_dir
        / "reports"
        / "uvm_coverage_xcrg"
        / "codeCoverageReport"
    )
    functional_dir = (
        project_dir
        / "reports"
        / "uvm_coverage_xcrg"
        / "functionalCoverageReport"
    )
    code_dir.mkdir(parents=True)
    functional_dir.mkdir(parents=True)
    project_path = project_dir.as_posix()

    (code_dir / "files.html").write_text(
        f"""
<table class="fileInfosTable">
<tr>
<td>File ID</td><td>File Path</td><td>Modules Count</td>
<td>Total Instances Count</td><td>Statement Coverage Score</td>
<td>Lines Count</td><td>Statements Count</td>
<td>Branch Coverage Score</td><td>Condition Coverage Score</td>
<td>Toggle Coverage Score</td>
</tr>
<tr>
<td>1</td><td><a href="file1.html">{project_path}/rtl/async_fifo.v</a></td>
<td>1</td><td>1</td><td>100</td><td>30</td><td>30</td>
<td>100</td><td>100</td><td>17.01</td>
</tr>
<tr>
<td>2</td><td><a href="file2.html">{project_path}/uvm/async_fifo_uvm_pkg.sv</a></td>
<td>1</td><td>1</td><td>54.7337</td><td>20</td><td>20</td>
<td>18.1818</td><td>15.2174</td><td>0</td>
</tr>
<tr>
<td>3</td><td><a href="file3.html">D:/Vivado/data/system_verilog/uvm_1.2/xlnx_uvm_package.sv</a></td>
<td>1</td><td>1</td><td>0</td><td>20</td><td>20</td>
<td>0</td><td>0</td><td>0</td>
</tr>
</table>
""",
        encoding="utf-8",
    )
    (code_dir / "modules.html").write_text(
        f"""
<table class="moduleInfosTable">
<tr>
<td>Module ID</td><td>Module Name</td><td>Instance[s] Count</td>
<td>Hierarchical Instance[s]</td><td>Statement Score</td>
<td>Branch Score</td><td>Condition Score</td><td>Toggle Score</td>
<td>Module definition in File</td><td>File ID</td>
</tr>
<tr>
<td>1</td><td><a href="mod1.html">async_fifo_default</a></td><td>1</td>
<td>tb_async_fifo_uvm.dut</td><td>100</td><td>100</td><td>100</td>
<td>17.01</td>
<td><span class="tooltiptext">{project_path}/rtl/async_fifo.v</span></td><td>1</td>
</tr>
<tr>
<td>2</td><td><a href="mod2.html">async_fifo_uvm_pkg</a></td><td>1</td>
<td>async_fifo_uvm_pkg</td><td>54.7337</td><td>18.1818</td>
<td>15.2174</td><td>0</td>
<td><span class="tooltiptext">{project_path}/uvm/async_fifo_uvm_pkg.sv</span></td>
<td>2</td>
</tr>
</table>
""",
        encoding="utf-8",
    )
    (functional_dir / "groups.html").write_text(
        """
<table>
<tr><td>Name</td><td>Score</td><td>Num Insts</td>
<td>Avg Instances Score</td><td>Weight</td><td>Goal</td></tr>
<tr>
<td><a href="grp0.html">async_fifo_uvm_pkg::async_fifo_monitor::async_fifo_cg</a></td>
<td>57.1429</td><td>1</td><td>57.1429</td><td>1</td><td>100</td>
</tr>
</table>
""",
        encoding="utf-8",
    )
    (functional_dir / "grp0.html").write_text(
        f"""
<a href="dashboard.html">Dashboard</a>
<a href="groups.html">Groups</a>
<span>Source File(s) :</span>
<a href="file:{project_path}/uvm/async_fifo_uvm_pkg.sv">
{project_path}/uvm/async_fifo_uvm_pkg.sv
</a>
<table id="sortable0">
<tr><td>Name</td><td>Score</td><td>Weight</td><td>Goal</td></tr>
<tr><td><span class="tooltiptext1">\this .async_fifo_cg</span></td>
<td>57.1429</td><td>1</td><td>100</td></tr>
</table>
<table id="sortable1">
<tr><td>Name</td><td>Expected</td><td>Uncovered</td>
<td>Covered</td><td>Percent</td><td>Goal</td></tr>
<tr><td>cp_write</td><td>1</td><td>0</td><td>1</td><td>100</td><td>100</td></tr>
<tr><td>cp_full</td><td>1</td><td>1</td><td>0</td><td>0</td><td>100</td></tr>
</table>
<table id="sortable2">
<tr><td>Name</td><td>Expected</td><td>Uncovered</td>
<td>Covered</td><td>Percent</td><td>Goal</td></tr>
<tr><td><span class="tooltiptext5">cross_write_full</span></td>
<td>1</td><td>1</td><td>0</td><td>0</td><td>100</td></tr>
<tr><td><span class="tooltiptext5">cross_read_empty</span></td>
<td>1</td><td>1</td><td>0</td><td>0</td><td>100</td></tr>
</table>
""",
        encoding="utf-8",
    )


def test_p4_1_dashboard_renders_concrete_items_and_writes_json(tmp_path):
    module = load_local_module(
        "coverage_closure_p4_1_dashboard_split",
        COVERAGE_CLOSURE_PATH,
    )

    class FakeAgent:
        def list_targets(self):
            return [
                {
                    "name": "async-fifo",
                    "display_name": "Asynchronous FIFO",
                    "design_family": "fifo",
                    "flows": ["uvm-coverage"],
                    "scenario_catalog": [],
                    "coverage_metrics": [
                        {
                            "id": metric_id,
                            "label": label,
                            "source": source,
                            "status": "PASS",
                        }
                        for metric_id, label, source in (
                            ("statement", "Statement coverage", "Vivado xcrg"),
                            ("branch", "Branch coverage", "Vivado xcrg"),
                            ("condition", "Condition coverage", "Vivado xcrg"),
                            ("toggle", "Toggle coverage", "Vivado xcrg"),
                            ("functional", "Functional coverage", "UVM covergroup"),
                        )
                    ],
                }
            ]

    async_dir = tmp_path / "async-fifo"
    reports_dir = async_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "uvm_coverage_percent.txt").write_text(
        "\n".join(
            [
                "Line Coverage Score 60.2041",
                "Branch Coverage Score 23.5294",
                "Condition Coverage Score 22",
                "Toggle Coverage Score 4.84",
            ]
        ),
        encoding="utf-8",
    )
    (reports_dir / "uvm_coverage_summary.md").write_text(
        "- Total Coverage: 27.6%\n- Coverage threshold: 1.0%\n",
        encoding="utf-8",
    )
    _write_p4_1_xcrg_fixture(async_dir)

    result = module.write_coverage_closure_report(
        FakeAgent(),
        output_dir=tmp_path,
        target_threshold=80.0,
    )

    target = result["targets"][0]
    assert target["coverage_gaps"]
    assert len(target["low_coverage_items"]) == 14
    assert target["low_coverage_diagnostics"] == []
    assert target["recommended_scenarios"] == []
    assert result["low_coverage_items_path"] == (
        tmp_path / "coverage-closure" / "low_coverage_items.json"
    )
    payload = json.loads(
        result["low_coverage_items_path"].read_text(encoding="utf-8")
    )
    assert payload["targets"][0]["name"] == "async-fifo"
    assert len(payload["targets"][0]["low_coverage_items"]) == 14

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "### 低覆盖项" in markdown
    assert "uvm/async_fifo_uvm_pkg.sv" in markdown
    assert "this.async_fifo_cg" in markdown
    assert "cp_full" in markdown
    assert "functionalCoverageReport/grp0.html" in markdown
    assert "低覆盖项" in html_text
    assert "cross_write_full" in html_text
