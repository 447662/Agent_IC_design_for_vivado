import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_uvm_smoke_regression_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def async_fifo_plugin(agent):
    return agent.target_plugins["async-fifo"]


def test_generate_async_fifo_uvm_smoke_creates_minimal_environment(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    uvm_dir = async_fifo_plugin(agent).write_async_fifo_uvm_smoke_project(project_dir)

    expected_files = [
        uvm_dir / "async_fifo_if.sv",
        uvm_dir / "async_fifo_uvm_pkg.sv",
        uvm_dir / "tb_async_fifo_uvm.sv",
        project_dir / "sim" / "run_vivado_async_fifo_uvm.tcl",
    ]
    for path in expected_files:
        assert path.exists()

    pkg = (uvm_dir / "async_fifo_uvm_pkg.sv").read_text(encoding="utf-8")
    top = (uvm_dir / "tb_async_fifo_uvm.sv").read_text(encoding="utf-8")
    script = (project_dir / "sim" / "run_vivado_async_fifo_uvm.tcl").read_text(
        encoding="utf-8"
    )

    assert "import uvm_pkg::*;" in pkg
    assert "`include \"uvm_macros.svh\"" in pkg
    assert "class async_fifo_driver extends uvm_driver" in pkg
    assert "class async_fifo_monitor extends uvm_component" in pkg
    assert "read_pending = vif.rd_en && !vif.empty" in pkg
    assert "class async_fifo_scoreboard extends uvm_component" in pkg
    assert "class async_fifo_env extends uvm_env" in pkg
    assert "class async_fifo_basic_test extends uvm_test" in pkg
    assert "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in pkg
    assert "module tb_async_fifo_uvm" in top
    assert ".wr_rst_n(fifo_if.wr_rst_n)" in top
    assert ".rd_rst_n(fifo_if.rd_rst_n)" in top
    assert ".rst_n(" not in top
    assert "run_test(\"async_fifo_basic_test\")" in top
    assert "ASYNC_FIFO_UVM_TEST_DONE" in top
    assert "uvm_pkg" in script
    assert "-l uvm" in script.lower()
    assert "-timescale 1ns/1ps" in script
    assert "async_fifo_uvm_smoke" in script


def test_run_async_fifo_uvm_smoke_writes_report_and_can_skip_gui(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    vivado_path = r"D:\vivado\2025.2\Vivado\bin\vivado.bat"
    calls = []

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
    ):
        calls.append(([str(part) for part in command], Path(cwd)))
        Path(cwd, "async_fifo_uvm_smoke.log").write_text(
            "UVM_INFO async FIFO smoke\n"
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n",
            encoding="utf-8",
        )
        Path(cwd, "async_fifo_uvm_smoke.wdb").write_text(
            "wdb placeholder",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="ASYNC_FIFO_UVM_SCOREBOARD_PASS\nASYNC_FIFO_UVM_TEST_DONE\n",
            stderr="",
        )

    def fail_if_gui_opens(*args, **kwargs):
        raise AssertionError("GUI should be skipped")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(plugin, "open_async_fifo_project_gui", fail_if_gui_opens)

    assert plugin.run_async_fifo_uvm_smoke(
        output_dir=tmp_path,
        open_wave_gui=False,
    ) is True

    project_dir = tmp_path / "async-fifo"
    report = project_dir / "reports" / "uvm_smoke_report.md"
    html_report = project_dir / "reports" / "uvm_smoke_report.html"
    assert report.exists()
    assert html_report.exists()
    text = report.read_text(encoding="utf-8")
    html_text = html_report.read_text(encoding="utf-8")
    assert "ASYNC_FIFO_UVM_SCOREBOARD_PASS" in text
    assert "ASYNC_FIFO_UVM_TEST_DONE" in text
    assert "class=\"uvm-card pass\"" in html_text
    assert calls == [
        (
            [vivado_path, "-mode", "batch", "-source", "run_vivado_async_fifo_uvm.tcl"],
            project_dir / "sim",
        )
    ]


def test_cli_uvm_smoke_async_fifo_invokes_runner(monkeypatch, tmp_path):
    module = load_agent_module()
    calls = []

    monkeypatch.setattr(module, "create_agent", lambda: module.DigitalICAgent())

    def fake_run_uvm_smoke(self, target, output_dir="outputs", open_wave_gui=True):
        calls.append((target, output_dir, open_wave_gui))
        return True

    monkeypatch.setattr(module.DigitalICAgent, "run_uvm_smoke", fake_run_uvm_smoke)

    assert module.main(
        ["--uvm-smoke", "async-fifo", "--no-wave-gui", "--output-dir", str(tmp_path)]
    ) == 0
    assert calls == [("async-fifo", str(tmp_path), False)]


def test_generate_async_fifo_uvm_environment_includes_functional_coverage_and_sva(
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("async-fifo", tmp_path)

    async_fifo_plugin(agent).write_async_fifo_uvm_coverage_project(project_dir)

    pkg = (project_dir / "uvm" / "async_fifo_uvm_pkg.sv").read_text(
        encoding="utf-8"
    )
    sva = (project_dir / "uvm" / "async_fifo_sva.sv").read_text(encoding="utf-8")
    top = (project_dir / "uvm" / "tb_async_fifo_uvm.sv").read_text(
        encoding="utf-8"
    )
    script = (project_dir / "sim" / "run_vivado_async_fifo_uvm_coverage.tcl").read_text(
        encoding="utf-8"
    )

    assert "covergroup async_fifo_cg" in pkg
    assert "ASYNC_FIFO_UVM_FCOV_SAMPLE" in pkg
    assert "ASYNC_FIFO_UVM_FCOV_PASS" in pkg
    assert "ASYNC_FIFO_UVM_FCOV summary" in pkg
    assert "module async_fifo_sva" in sva
    assert "p_no_write_when_full" in sva
    assert "p_no_read_when_empty" in sva
    assert "ASYNC_FIFO_SVA_BOUND" in top
    assert "async_fifo_sva.sv" in script


def test_write_async_fifo_uvm_functional_coverage_report(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "async-fifo"
    sim_dir = project_dir / "sim"
    sim_dir.mkdir(parents=True)
    (sim_dir / "async_fifo_uvm_coverage.log").write_text(
        "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
        "ASYNC_FIFO_UVM_FCOV_SAMPLE full=1 empty=1 reset=1 mixed=1\n"
        "ASYNC_FIFO_UVM_FCOV_PASS samples=18\n"
        "ASYNC_FIFO_UVM_ASSERT_PASS\n",
        encoding="utf-8",
    )

    report = async_fifo_plugin(agent).write_async_fifo_uvm_functional_coverage_report(
        project_dir
    )

    assert report["passed"] is True
    assert report["markdown_path"].name == "uvm_functional_coverage.md"
    assert report["html_path"].name == "uvm_functional_coverage.html"
    text = report["markdown_path"].read_text(encoding="utf-8")
    html_text = report["html_path"].read_text(encoding="utf-8")
    assert "full_boundary" in text
    assert "empty_boundary" in text
    assert "reset_recovery" in text
    assert "mixed_traffic" in text
    assert "FOUND" in text
    assert "functional-card pass" in html_text


def test_run_async_fifo_uvm_random_regression_writes_seed_report(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)
    calls = []

    def fake_run(
        output_dir="outputs",
        data_width=8,
        addr_width=4,
        coverage_threshold=None,
        coverage_percent=None,
        seed=None,
    ):
        calls.append((seed, Path(output_dir)))
        project_dir = Path(output_dir) / "async-fifo"
        sim_dir = project_dir / "sim"
        sim_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=8 reads=8\n"
            "ASYNC_FIFO_UVM_TEST_DONE\n"
            "ASYNC_FIFO_UVM_FCOV_PASS samples=18\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text(
            "wdb",
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr(plugin, "run_async_fifo_uvm_coverage", fake_run)

    assert plugin.run_async_fifo_uvm_random_regression(
        output_dir=tmp_path,
        seeds=[11, 22, 33],
    ) is True

    report = tmp_path / "async-fifo" / "reports" / "uvm_random_regression.md"
    html_report = tmp_path / "async-fifo" / "reports" / "uvm_random_regression.html"
    assert calls == [
        (11, tmp_path / "async-fifo" / "uvm_regression" / "seed_11"),
        (22, tmp_path / "async-fifo" / "uvm_regression" / "seed_22"),
        (33, tmp_path / "async-fifo" / "uvm_regression" / "seed_33"),
    ]
    assert report.exists()
    assert html_report.exists()
    text = report.read_text(encoding="utf-8")
    assert "Seed | Status" in text
    assert "| 11 | PASS |" in text
    assert "| 22 | PASS |" in text
    assert "| 33 | PASS |" in text
    assert "uvm_regression" in text
    assert "seed_11" in text
    assert (
        tmp_path
        / "async-fifo"
        / "uvm_regression"
        / "seed_11"
        / "async-fifo"
        / "sim"
        / "async_fifo_uvm_coverage.log"
    ).exists()
