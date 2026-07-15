import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_PATH = AGENT_DIR / "agent.py"
FAILURE_ARCHIVE_PATH = AGENT_DIR / "failure_archive.py"

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

def test_p4_5_archives_failed_run_materials_with_generic_manifest(tmp_path):
    module = load_local_module("failure_archive_split_p4_5", FAILURE_ARCHIVE_PATH)
    source_dir = tmp_path / "run"
    log_path = source_dir / "sim" / "failed.log"
    wdb_path = source_dir / "sim" / "failed.wdb"
    coverage_db = source_dir / "sim" / "coverage" / "xsim.codeCov"
    tcl_path = source_dir / "sim" / "run_failed.tcl"
    config_path = source_dir / "config" / "target.json"
    log_path.parent.mkdir(parents=True)
    coverage_db.mkdir(parents=True)
    config_path.parent.mkdir(parents=True)
    log_path.write_text("simulation failed\n", encoding="utf-8")
    wdb_path.write_text("wdb", encoding="utf-8")
    (coverage_db / "xsim.CCInfo").write_text("coverage", encoding="utf-8")
    tcl_path.write_text("puts failed\n", encoding="utf-8")
    config_path.write_text('{"name": "sync-fifo"}\n', encoding="utf-8")

    result = module.archive_failed_run(
        tmp_path / "failure_archives",
        target_name="sync-fifo",
        flow_name="formal-smoke",
        run_id="seed_22",
        status="FAIL",
        seed=22,
        artifacts=[
            {"role": "log", "path": log_path},
            {"role": "waveform", "path": wdb_path},
            {"role": "coverage_db", "path": coverage_db},
            {"role": "tcl", "path": tcl_path},
            {"role": "target_config", "path": config_path},
        ],
        reproduce_command=[
            "python",
            ".trae/agent/agent.py",
            "--uvm-random-regress",
            "sync-fifo",
            "--uvm-seeds",
            "22",
        ],
        wave_open_command=["vivado", "-mode", "gui", str(wdb_path)],
    )

    archive_dir = tmp_path / "failure_archives" / "formal-smoke" / "seed_22"
    assert result["archive_dir"] == archive_dir
    assert result["manifest_path"] == archive_dir / "failure_archive.json"
    assert result["reproduce_script_path"] == archive_dir / "reproduce.ps1"
    manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["target_name"] == "sync-fifo"
    assert manifest["flow_name"] == "formal-smoke"
    assert manifest["run_id"] == "seed_22"
    assert manifest["status"] == "FAIL"
    assert manifest["seed"] == 22
    assert manifest["reproduce_command"][-2:] == ["--uvm-seeds", "22"]
    assert manifest["wave_open_command"][:3] == ["vivado", "-mode", "gui"]
    assert {item["role"] for item in manifest["artifacts"]} == {
        "log",
        "waveform",
        "coverage_db",
        "tcl",
        "target_config",
    }
    for item in manifest["artifacts"]:
        assert item["available"] is True
        assert (archive_dir / item["archive_path"]).exists()
    assert "--uvm-seeds 22" in result["reproduce_script_path"].read_text(
        encoding="utf-8"
    )
    assert "formal-smoke" in result["readme_path"].read_text(encoding="utf-8")
    source = FAILURE_ARCHIVE_PATH.read_text(encoding="utf-8")
    assert "async_fifo" not in source
    assert "uvm_coverage" not in source


def test_p4_5_random_regression_archives_only_failed_seed_and_links_report(
    monkeypatch,
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    plugin = async_fifo_plugin(agent)

    def fake_run(
        output_dir="outputs",
        data_width=8,
        addr_width=4,
        coverage_threshold=None,
        coverage_percent=None,
        coverage_thresholds=None,
        seed=None,
    ):
        project_dir = Path(output_dir) / "async-fifo"
        sim_dir = project_dir / "sim"
        coverage_db = sim_dir / "coverage" / "xsim.codeCov" / "async_fifo_uvm_cov"
        coverage_db.mkdir(parents=True, exist_ok=True)
        (sim_dir / "async_fifo_uvm_coverage.log").write_text(
            "PASS\n" if seed == 11 else "FAIL\n",
            encoding="utf-8",
        )
        (sim_dir / "async_fifo_uvm_coverage.wdb").write_text("wdb", encoding="utf-8")
        (coverage_db / "xsim.CCInfo").write_text("coverage", encoding="utf-8")
        (sim_dir / "run_vivado_async_fifo_uvm_coverage.tcl").write_text(
            "puts run\n",
            encoding="utf-8",
        )
        return seed == 11

    monkeypatch.setattr(plugin, "run_async_fifo_uvm_coverage", fake_run)

    assert plugin.run_async_fifo_uvm_random_regression(
        output_dir=tmp_path,
        seeds=[11, 22],
    ) is False

    archive_root = tmp_path / "async-fifo" / "failure_archives" / "uvm-coverage"
    assert not (archive_root / "seed_11").exists()
    failed_archive = archive_root / "seed_22"
    assert (failed_archive / "failure_archive.json").exists()
    assert (failed_archive / "reproduce.ps1").exists()
    archived_roles = {
        item["role"]
        for item in json.loads(
            (failed_archive / "failure_archive.json").read_text(encoding="utf-8")
        )["artifacts"]
    }
    assert archived_roles == {
        "log",
        "waveform",
        "coverage_db",
        "tcl",
        "target_config",
    }
    report = (
        tmp_path / "async-fifo" / "reports" / "uvm_random_regression.md"
    ).read_text(encoding="utf-8")
    html_report = (
        tmp_path / "async-fifo" / "reports" / "uvm_random_regression.html"
    ).read_text(encoding="utf-8")
    assert "Failure Archive" in report
    assert "reproduce.ps1" in report
    assert "failure_archives" in report
    assert "Open WDB" in report
    assert "failure_archives" in html_report
    assert "reproduce.ps1" in html_report


def test_p4_5_failure_archive_module_is_in_mypy_scope():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"src/digital_ic_agent"' in pyproject
