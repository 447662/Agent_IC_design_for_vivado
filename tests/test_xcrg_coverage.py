import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
XCRG_COVERAGE_PATH = AGENT_DIR / "xcrg_coverage.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_local_module(module_name, module_path):
    relative_module = module_path.relative_to(AGENT_DIR).with_suffix("")
    qualified_name = ".".join(relative_module.parts)
    return importlib.import_module(
        "digital_ic_agent._runtime.{}".format(qualified_name)
    )

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


def test_p4_1_extracts_project_low_coverage_items_from_xcrg(tmp_path):
    module = load_local_module("xcrg_coverage_split_items", XCRG_COVERAGE_PATH)
    project_dir = tmp_path / "async-fifo"
    _write_p4_1_xcrg_fixture(project_dir)

    result = module.extract_low_coverage_items(
        project_dir,
        report_base=tmp_path / "coverage-closure",
        target_threshold=80.0,
    )

    assert result["diagnostics"] == []
    assert len(result["items"]) == 14
    assert [item["score"] for item in result["items"]] == sorted(
        item["score"] for item in result["items"]
    )
    assert all(item["score"] < 80.0 for item in result["items"])
    assert not any(
        "xlnx_uvm_package.sv" in item["source_file"]
        for item in result["items"]
    )
    assert any(
        item["source_file"] == "uvm/async_fifo_uvm_pkg.sv"
        and item["instance"] == "async_fifo_uvm_pkg"
        and item["metric"] == "branch"
        and item["score"] == 18.2
        and item["details"]["scope"] == "module"
        for item in result["items"]
    )
    assert any(
        item["metric"] == "cover_point"
        and item["source_file"] == "uvm/async_fifo_uvm_pkg.sv"
        and item["instance"] == "this.async_fifo_cg"
        and item["score"] == 0.0
        and item["details"]["name"] == "cp_full"
        and item["details"]["uncovered"] == 1
        for item in result["items"]
    )
    assert any(
        item["metric"] == "cross"
        and item["details"]["name"] == "cross_write_full"
        and item["source_report"].endswith("functionalCoverageReport/grp0.html")
        for item in result["items"]
    )


def test_p4_1_reports_missing_and_invalid_xcrg_pages_without_zero_defaults(tmp_path):
    module = load_local_module("xcrg_coverage_split_diagnostics", XCRG_COVERAGE_PATH)
    project_dir = tmp_path / "broken-target"
    code_dir = project_dir / "reports" / "uvm_coverage_xcrg" / "codeCoverageReport"
    code_dir.mkdir(parents=True)
    (code_dir / "files.html").write_text(
        "<html><body>unsupported xcrg layout</body></html>",
        encoding="utf-8",
    )

    result = module.extract_low_coverage_items(
        project_dir,
        report_base=tmp_path / "coverage-closure",
        target_threshold=80.0,
    )

    assert result["items"] == []
    assert {diagnostic["status"] for diagnostic in result["diagnostics"]} == {
        "INVALID",
        "MISSING",
    }
    assert any(
        diagnostic["status"] == "INVALID"
        and diagnostic["source_report"].endswith("codeCoverageReport/files.html")
        for diagnostic in result["diagnostics"]
    )
    assert any(
        diagnostic["status"] == "MISSING"
        and diagnostic["source_report"].endswith("functionalCoverageReport/groups.html")
        for diagnostic in result["diagnostics"]
    )
    assert not any(item["score"] == 0.0 for item in result["items"])


def test_p4_1_xcrg_coverage_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"src/digital_ic_agent"' in pyproject
