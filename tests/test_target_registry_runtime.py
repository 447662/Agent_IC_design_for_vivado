import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
TARGET_REGISTRY_PATH = AGENT_DIR / "target_registry.py"
AGENT_TARGETS_DIR = AGENT_DIR / "targets"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_target_registry_runtime_split",
        AGENT_PATH,
    )
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


def test_p5_target_registry_rejects_invalid_target_config(tmp_path):
    module = load_agent_module()
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    (targets_dir / "broken.json").write_text(
        '{"display_name": "Broken"}',
        encoding="utf-8",
    )

    agent = module.DigitalICAgent()

    try:
        agent.load_target_registry(targets_dir)
    except ValueError as exc:
        assert "missing required field: name" in str(exc)
    else:
        raise AssertionError("Expected invalid target config to raise ValueError")


def test_target_registry_module_preserves_sorting_aliases_and_validation(tmp_path):
    assert TARGET_REGISTRY_PATH.exists()

    registry = load_local_module("target_registry_runtime_split", TARGET_REGISTRY_PATH)
    targets = registry.load_target_registry(AGENT_TARGETS_DIR)

    assert [target["name"] for target in registry.list_targets(targets)] == [
        "async-fifo",
        "round-robin-arbiter",
        "sync-fifo",
    ]
    assert registry.get_target(targets, "round_robin_arbiter")["name"] == (
        "round-robin-arbiter"
    )

    broken_dir = tmp_path / "targets"
    broken_dir.mkdir()
    (broken_dir / "broken.json").write_text(
        '{"display_name": "Broken"}',
        encoding="utf-8",
    )
    try:
        registry.load_target_registry(broken_dir)
    except ValueError as exc:
        assert "missing required field: name" in str(exc)
    else:
        raise AssertionError("Expected invalid target config to raise ValueError")


def test_target_handler_registry_matches_declared_flows():
    module = load_agent_module()
    agent = module.DigitalICAgent()

    assert set(agent.target_handlers) == set(agent.targets)
    for target_name, target in agent.targets.items():
        assert set(agent.target_handlers[target_name].flows) == set(target["flows"])


def test_registered_check_rtl_flows_execute_for_all_targets(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    target_artifacts = {
        "sync-fifo": {
            "vcd": "sync_fifo_trace.vcd",
            "wdb": "sync_fifo_smoke.wdb",
            "xpr": "sync_fifo_project.xpr",
        },
        "round-robin-arbiter": {
            "vcd": "round_robin_arbiter_trace.vcd",
            "wdb": "round_robin_arbiter_smoke.wdb",
            "xpr": "round_robin_arbiter_project.xpr",
        },
    }

    for target, names in target_artifacts.items():
        project_dir = agent.generate_rtl_project(target, tmp_path)
        (project_dir / "sim" / names["vcd"]).write_text(
            "$date\nfixture\n$end\n",
            encoding="utf-8",
        )
        (project_dir / "sim" / names["wdb"]).write_text("wdb", encoding="utf-8")
        xpr_path = project_dir / "vivado_project" / names["xpr"]
        xpr_path.parent.mkdir(parents=True, exist_ok=True)
        xpr_path.write_text("<Project />\n", encoding="utf-8")
        report_path = project_dir / "reports" / "sim_report.md"
        report_path.write_text("# Simulation Report\n\n- Status: PASS\n", encoding="utf-8")

        assert module.main(
            [
                "--check-rtl",
                target,
                "--output-dir",
                str(tmp_path),
            ]
        ) == 0


def test_cli_list_targets_outputs_registered_targets(capsys):
    module = load_agent_module()

    assert module.main(["--list-targets"]) == 0

    output = capsys.readouterr().out
    assert "async-fifo" in output
    assert "fifo" in output
    assert "generate-rtl" in output
    assert "uvm-coverage" in output


def test_target_registry_rejects_alias_collisions_between_targets(tmp_path):
    registry = load_local_module(
        "target_registry_alias_collision_split",
        TARGET_REGISTRY_PATH,
    )
    source = json.loads(
        (AGENT_TARGETS_DIR / "sync_fifo.json").read_text(encoding="utf-8")
    )
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    for target_name in ("first-target", "second-target"):
        config = dict(source)
        config["name"] = target_name
        config["display_name"] = target_name
        config["handler"] = target_name
        config["aliases"] = ["shared_alias"]
        (targets_dir / "{}.json".format(target_name)).write_text(
            json.dumps(config, ensure_ascii=False),
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="alias conflict"):
        registry.load_target_registry(targets_dir)
