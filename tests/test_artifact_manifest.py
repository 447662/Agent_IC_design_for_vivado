import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
ARTIFACT_MANIFEST_PATH = AGENT_DIR / "artifact_manifest.py"

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


class FakeArtifactAgent:
    def __init__(self, manifest_entries):
        self.manifest_entries = manifest_entries

    def get_target(self, target):
        return {
            "name": target,
            "artifact_manifest": self.manifest_entries,
        }


def test_p5_8_generate_rtl_writes_runtime_artifact_manifest(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = agent.generate_rtl_project("sync-fifo", tmp_path)

    manifest_path = project_dir / "artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["target"] == "sync-fifo"
    assert manifest["updated_at"].endswith("Z")
    assert len(manifest["runs"]) == 1

    run = manifest["runs"][0]
    assert run["flow"] == "generate-rtl"
    assert run["status"] == "PASS"
    assert run["recorded_at"].endswith("Z")
    assert "--generate-rtl" in run["command"]
    assert "sync-fifo" in run["command"]
    assert run["tools"]["python"]["version"]
    assert run["tools"]["python"]["executable"]

    artifacts = {item["id"]: item for item in run["artifacts"]}
    assert artifacts["rtl"]["path"] == "rtl/sync_fifo.v"
    assert artifacts["rtl"]["exists"] is True
    assert artifacts["rtl"]["status"] == "CURRENT"
    assert artifacts["rtl"]["size_bytes"] > 0
    assert len(artifacts["rtl"]["sha256"]) == 64
    assert artifacts["rtl"]["produced_by_run_id"] == run["run_id"]
    assert artifacts["rtl"]["observed_at"] == run["recorded_at"]
    assert artifacts["wave_vcd"]["exists"] is False
    assert artifacts["wave_vcd"]["status"] == "MISSING"
    assert artifacts["coverage_summary"]["status"] == "N/A"


def test_p5_8_report_generation_appends_manifest_history(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    agent.generate_rtl_project("sync-fifo", tmp_path)
    agent.write_target_design_spec("sync-fifo", output_dir=tmp_path)
    agent.write_target_verification_plan("sync-fifo", output_dir=tmp_path)

    manifest = json.loads(
        (tmp_path / "sync-fifo" / "artifacts.json").read_text(encoding="utf-8")
    )
    assert [run["flow"] for run in manifest["runs"]] == [
        "generate-rtl",
        "generate-spec",
        "generate-verification-plan",
    ]
    assert all(run["status"] == "PASS" for run in manifest["runs"])

    latest_artifacts = {
        item["id"]: item for item in manifest["runs"][-1]["artifacts"]
    }
    assert latest_artifacts["design_spec"]["status"] == "STALE"
    assert latest_artifacts["verification_plan"]["status"] == "CURRENT"


def test_artifact_manifest_marks_unchanged_preexisting_file_stale_on_failure(tmp_path):
    module = load_local_module("artifact_manifest_split_stale", ARTIFACT_MANIFEST_PATH)
    agent = FakeArtifactAgent([
        {"id": "wave_wdb", "path": "sim/example.wdb", "status": "PASS"},
    ])
    project_dir = tmp_path / "sample-target"
    wave_path = project_dir / "sim" / "example.wdb"
    wave_path.parent.mkdir(parents=True)
    wave_path.write_text("old-wave", encoding="utf-8")
    before = module.snapshot_project_artifacts(project_dir)

    module.record_artifact_run(
        agent,
        "sample-target",
        "sim-rtl",
        output_dir=tmp_path,
        project_dir=project_dir,
        status="FAIL",
        artifact_snapshot=before,
        error="simulation failed before producing a new wave",
    )

    manifest = json.loads((project_dir / "artifacts.json").read_text(encoding="utf-8"))
    artifact = manifest["runs"][-1]["artifacts"][0]
    assert artifact["status"] == "STALE"
    assert artifact["produced_by_run_id"] is None
    assert len(artifact["sha256"]) == 64


def test_artifact_manifest_marks_changed_file_current_and_links_run(tmp_path):
    module = load_local_module("artifact_manifest_split_current", ARTIFACT_MANIFEST_PATH)
    agent = FakeArtifactAgent([
        {"id": "rtl", "path": "rtl/example.v", "status": "PASS"},
    ])
    project_dir = tmp_path / "sample-target"
    rtl_path = project_dir / "rtl" / "example.v"
    rtl_path.parent.mkdir(parents=True)
    rtl_path.write_text("module example; endmodule\n", encoding="utf-8")
    before = module.snapshot_project_artifacts(project_dir)
    rtl_path.write_text("module example; wire changed; endmodule\n", encoding="utf-8")

    module.record_artifact_run(
        agent,
        "sample-target",
        "generate-rtl",
        output_dir=tmp_path,
        project_dir=project_dir,
        status="PASS",
        artifact_snapshot=before,
        options={"width": 8},
    )

    manifest = json.loads((project_dir / "artifacts.json").read_text(encoding="utf-8"))
    run = manifest["runs"][-1]
    artifact = run["artifacts"][0]
    assert artifact["status"] == "CURRENT"
    assert artifact["produced_by_run_id"] == run["run_id"]
    assert run["input_digest"]
    assert run["command_digest"]


def test_artifact_manifest_unchanged_file_is_stale_on_later_run(tmp_path):
    module = load_local_module("artifact_manifest_split_reuse", ARTIFACT_MANIFEST_PATH)
    agent = FakeArtifactAgent([
        {"id": "rtl", "path": "rtl/example.v", "status": "PASS"},
    ])
    project_dir = tmp_path / "sample-target"
    rtl_path = project_dir / "rtl" / "example.v"
    rtl_path.parent.mkdir(parents=True)
    rtl_path.write_text("module example; endmodule\n", encoding="utf-8")

    module.record_artifact_run(
        agent,
        "sample-target",
        "generate-rtl",
        output_dir=tmp_path,
        project_dir=project_dir,
        options={"width": 8},
    )
    module.record_artifact_run(
        agent,
        "sample-target",
        "generate-rtl",
        output_dir=tmp_path,
        project_dir=project_dir,
        options={"width": 16},
    )

    manifest = json.loads((project_dir / "artifacts.json").read_text(encoding="utf-8"))
    first, second = manifest["runs"]
    assert first["artifacts"][0]["status"] == "CURRENT"
    assert second["artifacts"][0]["status"] == "STALE"
    assert first["input_digest"] != second["input_digest"]


def test_artifact_manifest_atomic_write_preserves_previous_manifest(
    tmp_path,
    monkeypatch,
):
    module = load_local_module("artifact_manifest_split_atomic", ARTIFACT_MANIFEST_PATH)
    agent = FakeArtifactAgent([])
    project_dir = tmp_path / "sample-target"
    module.record_artifact_run(
        agent,
        "sample-target",
        "generate-rtl",
        output_dir=tmp_path,
        project_dir=project_dir,
    )
    manifest_path = project_dir / "artifacts.json"
    original = manifest_path.read_text(encoding="utf-8")

    def fail_replace(_source, _destination):
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="atomic replace failure"):
        module.record_artifact_run(
            agent,
            "sample-target",
            "generate-spec",
            output_dir=tmp_path,
            project_dir=project_dir,
        )

    assert manifest_path.read_text(encoding="utf-8") == original


def test_history_rotation_archives_target_manifest_runs_and_can_be_disabled(tmp_path):
    module = load_local_module("artifact_manifest_split_rotation", ARTIFACT_MANIFEST_PATH)
    agent = FakeArtifactAgent([])
    project_dir = tmp_path / "sync-fifo"
    for index in range(4):
        module.record_artifact_run(
            agent,
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            project_dir=project_dir,
            options={"sequence": index},
            max_active_runs=2,
        )

    manifest_path = project_dir / "artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [
        run["options"]["sequence"]
        for run in manifest["runs"]
    ] == [2, 3]
    assert manifest["history"] == {
        "active_limit": 2,
        "archive_path": "artifacts.archive.jsonl.gz",
        "archived_runs": 2,
    }

    archive_path = project_dir / "artifacts.archive.jsonl.gz"
    with gzip.open(archive_path, "rt", encoding="utf-8") as stream:
        archived = [
            json.loads(line)
            for line in stream.read().splitlines()
        ]
    assert [
        run["options"]["sequence"]
        for run in archived
    ] == [0, 1]

    unbounded_dir = tmp_path / "unbounded"
    for index in range(3):
        module.record_artifact_run(
            agent,
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            project_dir=unbounded_dir,
            options={"sequence": index},
            max_active_runs=None,
        )
    unbounded = json.loads(
        (unbounded_dir / "artifacts.json").read_text(encoding="utf-8")
    )
    assert len(unbounded["runs"]) == 3
    assert "history" not in unbounded
    assert not (unbounded_dir / "artifacts.archive.jsonl.gz").exists()

    with pytest.raises(ValueError, match="active record limit"):
        module.record_artifact_run(
            agent,
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            project_dir=tmp_path / "invalid-limit",
            max_active_runs=0,
        )


def test_artifact_manifest_rejects_relative_path_escape(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    outside_path = tmp_path / "outside.log"
    outside_path.write_text("outside", encoding="utf-8")
    relative_escape = Path("..") / outside_path.name

    with pytest.raises(ValueError, match="inside project directory"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="PASS",
            extra_artifacts=[
                {"id": "outside", "path": relative_escape, "status": "PASS"},
            ],
        )

    target_info = dict(agent.get_target("sync-fifo"))
    target_info["artifact_manifest"] = [
        {"id": "outside", "path": relative_escape, "status": "PASS"},
    ]
    with pytest.raises(ValueError, match="inside project directory"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="PASS",
            target_info=target_info,
        )


def test_artifact_manifest_records_input_file_lineage(tmp_path):
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

    manifest = json.loads((project_dir / "artifacts.json").read_text(encoding="utf-8"))
    run = manifest["runs"][-1]
    assert run["input_digest"]
    assert run["input_files"]["rtl/sync_fifo.v"]["sha256"]
    assert run["input_files"]["tb/tb_sync_fifo.v"]["size_bytes"] > 0
    assert "sim/sync_fifo_smoke.wdb" not in run["input_files"]
    assert "reports/index.html" not in run["input_files"]


def test_p5_8_failed_target_flow_records_failure(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    class FailingHandler:
        def run(self, _flow, **_kwargs):
            raise RuntimeError("simulated manifest failure path")

    agent.target_handlers["sync-fifo"] = FailingHandler()

    with pytest.raises(RuntimeError, match="simulated manifest failure path"):
        agent.run_target_flow(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
        )

    manifest = json.loads(
        (tmp_path / "sync-fifo" / "artifacts.json").read_text(encoding="utf-8")
    )
    run = manifest["runs"][-1]
    assert run["flow"] == "generate-rtl"
    assert run["status"] == "FAIL"
    assert "simulated manifest failure path" in run["error"]
    assert "--generate-rtl" in run["command"]


def test_failed_target_flow_marks_preexisting_artifact_stale(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    project_dir = tmp_path / "sync-fifo"
    rtl_path = project_dir / "rtl" / "sync_fifo.v"
    rtl_path.parent.mkdir(parents=True)
    rtl_path.write_text("module sync_fifo; endmodule\n", encoding="utf-8")
    agent.target_handlers["sync-fifo"].flows["generate-rtl"] = (
        lambda **_kwargs: False
    )

    assert (
        agent.run_target_flow(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
        )
        is False
    )

    manifest = json.loads(
        (project_dir / "artifacts.json").read_text(encoding="utf-8")
    )
    artifacts = {
        item["id"]: item
        for item in manifest["runs"][-1]["artifacts"]
    }
    assert artifacts["rtl"]["status"] == "STALE"
    assert artifacts["rtl"]["produced_by_run_id"] is None


def test_async_fifo_manifest_declares_uvm_flow_artifacts(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()
    target_info = agent.get_target("async-fifo")

    artifact_paths = {
        item["path"]
        for item in target_info["artifact_manifest"]
    }

    assert "reports/uvm_smoke_report.md" in artifact_paths
    assert "sim/async_fifo_uvm_smoke.wdb" in artifact_paths
    assert "reports/uvm_coverage_summary.md" in artifact_paths
    assert "sim/async_fifo_uvm_coverage.wdb" in artifact_paths


def test_p5_8_create_target_scaffold_writes_runtime_manifest(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    scaffold = agent.create_target_scaffold("packet_router", output_dir=tmp_path)
    manifest = json.loads(
        (scaffold["project_dir"] / "artifacts.json").read_text(encoding="utf-8")
    )
    run = manifest["runs"][-1]

    assert manifest["target"] == "packet-router"
    assert run["flow"] == "create-target"
    assert run["status"] == "PASS"
    assert "--create-target" in run["command"]
    assert any(
        item["path"] == "target/packet_router.json"
        and item["exists"] is True
        and item["status"] == "CURRENT"
        and item["produced_by_run_id"] == run["run_id"]
        for item in run["artifacts"]
    )


def test_p5_8_manifest_rejects_invalid_status_external_path_and_corrupt_json(
    tmp_path,
):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    with pytest.raises(ValueError, match="invalid runtime flow status"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="BROKEN",
        )

    outside_path = tmp_path / "outside.log"
    outside_path.write_text("outside", encoding="utf-8")
    with pytest.raises(ValueError, match="inside project directory"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="PASS",
            extra_artifacts=[
                {"id": "outside", "path": outside_path, "status": "PASS"},
            ],
        )

    manifest_path = tmp_path / "sync-fifo" / "artifacts.json"
    manifest_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid runtime artifact manifest JSON"):
        agent.record_artifact_run(
            "sync-fifo",
            "generate-rtl",
            output_dir=tmp_path,
            status="PASS",
        )
