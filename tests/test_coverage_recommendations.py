import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
COVERAGE_CLOSURE_PATH = AGENT_DIR / "coverage_closure.py"
COVERAGE_RECOMMENDATIONS_PATH = AGENT_DIR / "coverage_recommendations.py"

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


def _p4_2_scenario_catalog():
    return [
        {
            "id": "full_boundary",
            "type": "boundary",
            "purpose": "write full boundary",
            "status": "PASS",
            "coverage_match": {
                "tokens": ["full", "write_full"],
                "metrics": ["cover_point", "cross"],
                "priority": "HIGH",
            },
        },
        {
            "id": "empty_boundary",
            "type": "boundary",
            "purpose": "read empty boundary",
            "status": "PASS",
            "coverage_match": {
                "tokens": ["empty", "read_empty"],
                "metrics": ["cover_point", "cross"],
                "priority": "HIGH",
            },
        },
        {
            "id": "reset_recovery",
            "type": "recovery",
            "purpose": "reset recovery",
            "status": "PASS",
            "coverage_match": {
                "tokens": ["reset", "rst"],
                "source_patterns": ["uvm/*sva*.sv"],
                "metrics": ["statement", "branch", "condition", "toggle"],
                "priority": "MEDIUM",
            },
        },
        {
            "id": "clock_ratio_sweep",
            "type": "timing",
            "purpose": "clock ratio sweep",
            "status": "PASS",
            "coverage_match": {
                "tokens": ["clock", "wr_clk", "rd_clk"],
                "source_patterns": ["rtl/async_fifo.v"],
                "metrics": ["toggle"],
                "priority": "MEDIUM",
            },
        },
        {
            "id": "mixed_stress",
            "type": "stress",
            "purpose": "mixed read write stress",
            "status": "PASS",
            "coverage_match": {
                "metrics": [
                    "statement",
                    "branch",
                    "condition",
                    "toggle",
                    "functional_group",
                ],
                "fallback": True,
                "priority": "LOW",
            },
        },
        {
            "id": "disabled_full",
            "type": "boundary",
            "purpose": "disabled full scenario",
            "status": "SKIP",
            "coverage_match": {
                "tokens": ["full"],
                "priority": "HIGH",
            },
        },
    ]


def test_p4_2_maps_low_coverage_items_to_scenario_ids_and_evidence():
    module = load_local_module(
        "coverage_recommendations_split_p4_2",
        COVERAGE_RECOMMENDATIONS_PATH,
    )
    low_coverage_items = [
        {
            "source_file": "uvm/async_fifo_uvm_pkg.sv",
            "instance": "this.async_fifo_cg",
            "metric": "cover_point",
            "score": 0.0,
            "details": {"name": "cp_full", "scope": "cover_point"},
            "source_report": "../reports/grp0.html",
        },
        {
            "source_file": "uvm/async_fifo_uvm_pkg.sv",
            "instance": "this.async_fifo_cg",
            "metric": "cross",
            "score": 0.0,
            "details": {"name": "cross_read_empty", "scope": "cross"},
            "source_report": "../reports/grp0.html",
        },
        {
            "source_file": "uvm/async_fifo_sva.sv",
            "instance": "tb.async_fifo_sva_i",
            "metric": "branch",
            "score": 0.0,
            "details": {"name": "async_fifo_sva", "scope": "module"},
            "source_report": "../reports/mod6.html",
        },
        {
            "source_file": "rtl/async_fifo.v",
            "instance": "tb.dut",
            "metric": "toggle",
            "score": 17.0,
            "details": {"name": "async_fifo_default", "scope": "module"},
            "source_report": "../reports/mod1.html",
        },
        {
            "source_file": "uvm/async_fifo_uvm_pkg.sv",
            "instance": "async_fifo_uvm_pkg",
            "metric": "condition",
            "score": 15.2,
            "details": {"name": "async_fifo_uvm_pkg", "scope": "module"},
            "source_report": "../reports/mod4.html",
        },
    ]

    result = module.recommend_scenarios(
        low_coverage_items,
        _p4_2_scenario_catalog(),
    )

    assert result["recommended_scenarios"] == [
        "full_boundary",
        "empty_boundary",
        "reset_recovery",
        "clock_ratio_sweep",
        "mixed_stress",
    ]
    assert not any(
        item["scenario_id"] == "disabled_full"
        for item in result["recommendations"]
    )
    full_recommendation = result["recommendations"][0]
    assert full_recommendation["scenario_id"] == "full_boundary"
    assert full_recommendation["priority"] == "HIGH"
    assert full_recommendation["matched_items"] == ["cp_full"]
    assert full_recommendation["matched_metrics"] == ["cover_point"]
    assert full_recommendation["evidence_count"] == 1
    assert "cp_full" in full_recommendation["reason"]
    assert module.recommend_scenarios([], _p4_2_scenario_catalog()) == {
        "recommended_scenarios": [],
        "recommendations": [],
    }


def test_p4_2_dashboard_renders_recommendations_and_json(tmp_path):
    module = load_local_module(
        "coverage_closure_split_p4_2_dashboard",
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
                    "scenario_catalog": _p4_2_scenario_catalog(),
                    "coverage_metrics": [
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
    assert target["recommended_scenarios"] == [
        "full_boundary",
        "empty_boundary",
        "clock_ratio_sweep",
        "mixed_stress",
    ]
    assert [
        item["scenario_id"]
        for item in target["scenario_recommendations"]
    ] == target["recommended_scenarios"]
    assert target["scenario_recommendations"][0]["matched_items"] == [
        "cp_full",
        "cross_write_full",
    ]
    assert target["scenario_recommendations"][1]["matched_items"] == [
        "cross_read_empty"
    ]

    payload = json.loads(
        result["low_coverage_items_path"].read_text(encoding="utf-8")
    )
    payload_target = payload["targets"][0]
    assert payload_target["recommended_scenarios"] == (
        target["recommended_scenarios"]
    )
    assert payload_target["scenario_recommendations"]

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    assert "`full_boundary`" in markdown
    assert "cp_full" in markdown
    assert "clock_ratio_sweep" in markdown
    assert "full_boundary" in html_text
    assert "mixed_stress" in html_text


def test_p4_2_async_fifo_catalog_defines_coverage_matching_rules():
    target = json.loads(
        (ROOT / ".trae" / "agent" / "targets" / "async_fifo.json").read_text(
            encoding="utf-8"
        )
    )
    scenarios = {item["id"]: item for item in target["scenario_catalog"]}

    assert "clock_ratio_sweep" in scenarios
    for scenario_id in [
        "full_boundary",
        "empty_boundary",
        "reset_recovery",
        "clock_ratio_sweep",
        "mixed_stress",
    ]:
        coverage_match = scenarios[scenario_id]["coverage_match"]
        assert coverage_match["priority"] in {"HIGH", "MEDIUM", "LOW"}
        assert coverage_match.get("tokens") or coverage_match.get(
            "source_patterns"
        ) or coverage_match.get("fallback")


def test_p4_2_recommendations_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '".trae/agent/coverage_recommendations.py"' in pyproject
