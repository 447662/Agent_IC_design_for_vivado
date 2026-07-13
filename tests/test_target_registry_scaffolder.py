import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = ROOT / ".trae" / "agent" / "agent.py"
TARGET_REGISTRY_PATH = ROOT / ".trae" / "agent" / "target_registry.py"
TARGET_SCAFFOLDER_PATH = ROOT / ".trae" / "agent" / "target_scaffolder.py"
AGENT_TARGETS_DIR = ROOT / ".trae" / "agent" / "targets"

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


def run_agent(*args):
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_p5_target_registry_lists_async_fifo_metadata():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    target_config = json.loads((AGENT_TARGETS_DIR / "async_fifo.json").read_text(encoding="utf-8"))
    targets = agent.list_targets()
    target_names = [target["name"] for target in targets]
    async_fifo = agent.get_target("async_fifo")

    assert target_config["name"] == "async-fifo"
    assert target_names == ["async-fifo", "round-robin-arbiter", "sync-fifo"]
    assert async_fifo["name"] == "async-fifo"
    assert async_fifo["display_name"] == "Asynchronous FIFO"
    assert async_fifo["design_family"] == "fifo"
    assert "async_fifo" in async_fifo["aliases"]
    assert "generate-rtl" in async_fifo["flows"]
    assert "sim-rtl" in async_fifo["flows"]
    assert "uvm-coverage" in async_fifo["flows"]
    assert agent.normalize_rtl_target("async_fifo") == "async-fifo"


def test_p5_2_target_registry_lists_sync_fifo_metadata():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    target_config = json.loads((AGENT_TARGETS_DIR / "sync_fifo.json").read_text(encoding="utf-8"))
    targets = agent.list_targets()
    target_names = [target["name"] for target in targets]
    sync_fifo = agent.get_target("sync_fifo")

    assert target_config["name"] == "sync-fifo"
    assert target_names == ["async-fifo", "round-robin-arbiter", "sync-fifo"]
    assert sync_fifo["name"] == "sync-fifo"
    assert sync_fifo["display_name"] == "Synchronous FIFO"
    assert sync_fifo["design_family"] == "fifo"
    assert "sync_fifo" in sync_fifo["aliases"]
    assert "generate-rtl" in sync_fifo["flows"]
    assert "sim-rtl" in sync_fifo["flows"]
    assert "analyze-rtl-vcd" in sync_fifo["flows"]
    assert agent.normalize_rtl_target("sync_fifo") == "sync-fifo"


def test_p5_3_target_registry_lists_round_robin_arbiter_metadata():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    target_config = json.loads(
        (AGENT_TARGETS_DIR / "round_robin_arbiter.json").read_text(encoding="utf-8")
    )
    targets = agent.list_targets()
    target_names = [target["name"] for target in targets]
    arbiter = agent.get_target("round_robin_arbiter")

    assert target_config["name"] == "round-robin-arbiter"
    assert target_names == ["async-fifo", "round-robin-arbiter", "sync-fifo"]
    assert arbiter["name"] == "round-robin-arbiter"
    assert arbiter["display_name"] == "Round-Robin Arbiter"
    assert arbiter["design_family"] == "arbiter"
    assert "round_robin_arbiter" in arbiter["aliases"]
    assert "rr-arbiter" in arbiter["aliases"]
    assert "generate-rtl" in arbiter["flows"]
    assert "sim-rtl" in arbiter["flows"]
    assert "analyze-rtl-vcd" in arbiter["flows"]
    assert "open-wave" in arbiter["flows"]
    assert agent.normalize_rtl_target("round_robin_arbiter") == "round-robin-arbiter"


def test_p5_6_target_registry_exposes_common_capability_metadata():
    module = load_agent_module()
    agent = module.DigitalICAgent()
    allowed_statuses = {"PASS", "SKIP", "N/A"}

    for target in agent.list_targets():
        assert target["parameters"]
        assert target["interfaces"]
        assert target["checks"]
        assert target["scenario_catalog"]
        assert target["coverage_metrics"]
        assert target["artifact_manifest"]

        scenario_ids = [item["id"] for item in target["scenario_catalog"]]
        metric_ids = [item["id"] for item in target["coverage_metrics"]]
        artifact_ids = [item["id"] for item in target["artifact_manifest"]]
        assert len(scenario_ids) == len(set(scenario_ids))
        assert len(metric_ids) == len(set(metric_ids))
        assert len(artifact_ids) == len(set(artifact_ids))

        for item in (
            target["scenario_catalog"]
            + target["coverage_metrics"]
            + target["artifact_manifest"]
        ):
            assert item["status"] in allowed_statuses


def test_p5_6_target_registry_rejects_invalid_capability_status(tmp_path):
    module = load_agent_module()
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    config = {
        "name": "demo",
        "display_name": "Demo",
        "design_family": "demo",
        "aliases": [],
        "flows": [],
        "description": "Demo target",
        "parameters": [
            {"name": "WIDTH", "default": "8", "description": "Data width"},
        ],
        "interfaces": [
            {
                "name": "clk",
                "direction": "input",
                "width": "1",
                "description": "Clock",
            },
        ],
        "checks": ["Clock is present"],
        "scenario_catalog": [
            {
                "id": "smoke",
                "type": "functional",
                "purpose": "Smoke scenario",
                "status": "BROKEN",
            },
        ],
        "coverage_metrics": [
            {
                "id": "line",
                "label": "Line coverage",
                "source": "xcrg",
                "status": "SKIP",
            },
        ],
        "artifact_manifest": [
            {"id": "rtl", "path": "rtl/demo.v", "status": "PASS"},
        ],
        "notes": [],
    }
    (targets_dir / "demo.json").write_text(
        json.dumps(config, ensure_ascii=False),
        encoding="utf-8",
    )

    agent = module.DigitalICAgent()
    try:
        agent.load_target_registry(targets_dir)
    except ValueError as exc:
        assert "invalid status" in str(exc)
    else:
        raise AssertionError("Expected invalid capability status to raise ValueError")


def test_p5_6_spec_and_plan_surface_capability_statuses():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    spec_text = agent.render_target_design_spec("sync-fifo")
    plan_text = agent.render_target_verification_plan("sync-fifo")

    assert "## Artifact Manifest" in spec_text
    assert "| SKIP |" in spec_text
    assert "coverage_metrics" in plan_text


def test_p5_7_target_scaffolder_generates_valid_candidate_project(tmp_path):
    assert TARGET_SCAFFOLDER_PATH.exists()

    module = load_agent_module()
    registry = load_local_module("target_registry", TARGET_REGISTRY_PATH)
    agent = module.DigitalICAgent()

    result = agent.create_target_scaffold(
        "packet_router",
        output_dir=tmp_path,
        description="Configurable packet router target",
    )

    project_dir = tmp_path / "packet-router"
    config_path = project_dir / "target" / "packet_router.json"
    assert result["project_dir"] == project_dir
    assert result["config_path"] == config_path

    target = registry.get_target(
        registry.load_target_registry(project_dir / "target"),
        "packet_router",
    )
    assert target["name"] == "packet-router"
    assert target["display_name"] == "Packet Router"
    assert target["design_family"] == "custom"
    assert target["aliases"] == ["packet_router"]
    assert target["flows"] == []
    assert target["description"] == "Configurable packet router target"
    assert target["parameters"][0]["name"] == "DATA_WIDTH"
    assert target["interfaces"][0]["name"] == "clk"
    assert target["scenario_catalog"][0]["status"] == "SKIP"
    assert target["coverage_metrics"][-1]["status"] == "N/A"
    assert target["artifact_manifest"][0]["status"] == "SKIP"

    rtl_path = project_dir / "rtl" / "packet_router.v"
    tb_path = project_dir / "tb" / "tb_packet_router.v"
    design_spec_path = project_dir / "reports" / "design_spec.md"
    verification_plan_path = project_dir / "reports" / "verification_plan.md"
    sim_report_path = project_dir / "reports" / "sim_report.md"
    todo_path = project_dir / "TODO.md"
    readme_path = project_dir / "README.md"
    for path in [
        rtl_path,
        tb_path,
        design_spec_path,
        verification_plan_path,
        sim_report_path,
        todo_path,
        readme_path,
    ]:
        assert path.exists()

    assert "module packet_router" in rtl_path.read_text(encoding="utf-8")
    assert "TODO" in rtl_path.read_text(encoding="utf-8")
    assert "module tb_packet_router" in tb_path.read_text(encoding="utf-8")
    assert "- [ ]" in todo_path.read_text(encoding="utf-8")
    assert ".trae/agent/targets/packet_router.json" in readme_path.read_text(
        encoding="utf-8"
    )


def test_p5_7_target_scaffolder_rejects_invalid_duplicate_and_overwrite(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    with pytest.raises(ValueError, match="invalid target name"):
        agent.create_target_scaffold("../escape", output_dir=tmp_path)

    with pytest.raises(ValueError, match="already registered"):
        agent.create_target_scaffold("async_fifo", output_dir=tmp_path)

    first = agent.create_target_scaffold("packet-router", output_dir=tmp_path)
    assert first["project_dir"].exists()
    with pytest.raises(FileExistsError, match="already exists"):
        agent.create_target_scaffold("packet-router", output_dir=tmp_path)


def test_p5_7_cli_create_target_generates_scaffold(tmp_path):
    result = run_agent(
        "--create-target",
        "packet_router",
        "--output-dir",
        str(tmp_path),
        "Configurable packet router target",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Created target scaffold" in result.stdout
    assert "packet_router.json" in result.stdout
    assert (tmp_path / "packet-router" / "target" / "packet_router.json").exists()
    assert (tmp_path / "packet-router" / "TODO.md").exists()
