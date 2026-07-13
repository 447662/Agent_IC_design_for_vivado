import inspect
import sys
from pathlib import Path
from typing import get_args, get_type_hints

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


import artifact_manifest  # noqa: E402


def test_artifact_manifest_exposes_typed_runtime_contracts():
    load_hints = get_type_hints(artifact_manifest.load_runtime_manifest)
    status_hints = get_type_hints(artifact_manifest.artifact_status)
    snapshot_hints = get_type_hints(artifact_manifest.snapshot_project_artifacts)
    input_snapshot_hints = get_type_hints(artifact_manifest.snapshot_project_inputs)
    build_entry_hints = get_type_hints(artifact_manifest.build_artifact_entry)
    collect_hints = get_type_hints(artifact_manifest.collect_artifacts)
    extra_hints = get_type_hints(artifact_manifest.normalize_extra_artifact)
    latest_hints = get_type_hints(artifact_manifest._latest_artifact_snapshot)
    atomic_hints = get_type_hints(artifact_manifest.atomic_write_json)
    replay_hints = get_type_hints(artifact_manifest.build_replay_command)
    version_hints = get_type_hints(artifact_manifest.extract_tool_version)
    digest_hints = get_type_hints(artifact_manifest.json_digest)
    path_hints = get_type_hints(artifact_manifest.normalize_artifact_path)
    input_digest_hints = get_type_hints(artifact_manifest.build_run_input_digest)

    assert artifact_manifest.RunStatus.__name__ == "Literal"
    assert set(get_args(artifact_manifest.RunStatus)) == {"PASS", "FAIL"}
    assert artifact_manifest.ArtifactStatus.__name__ == "Literal"
    assert set(get_args(artifact_manifest.ArtifactStatus)) == {
        "CURRENT",
        "MISSING",
        "N/A",
        "STALE",
    }
    assert set(artifact_manifest.ArtifactFingerprint.__annotations__) == {
        "sha256",
        "size_bytes",
        "created_at",
        "modified_at",
    }
    assert set(artifact_manifest.ArtifactEntry.__annotations__) >= {
        "id",
        "path",
        "declared_status",
        "status",
        "exists",
        "observed_at",
        "produced_by_run_id",
    }
    assert artifact_manifest.ArtifactEntry.__required_keys__ >= {
        "id",
        "path",
        "declared_status",
        "status",
        "exists",
        "observed_at",
        "produced_by_run_id",
    }
    assert artifact_manifest.ArtifactEntry.__optional_keys__ >= {
        "sha256",
        "size_bytes",
        "created_at",
        "modified_at",
    }
    assert {
        "sha256",
        "size_bytes",
        "created_at",
        "modified_at",
    }.isdisjoint(artifact_manifest.ArtifactEntry.__required_keys__)
    assert set(artifact_manifest.RuntimeManifest.__annotations__) == {
        "schema_version",
        "target",
        "updated_at",
        "runs",
        "history",
    }
    assert load_hints["manifest_path"] == Path
    assert load_hints["target_name"] is str
    assert load_hints["return"] is artifact_manifest.RuntimeManifest
    assert inspect.signature(artifact_manifest.load_runtime_manifest).return_annotation == (
        "RuntimeManifest"
    )
    assert status_hints["return"] == artifact_manifest.ArtifactStatus
    assert snapshot_hints["return"] == dict[str, artifact_manifest.ArtifactFingerprint]
    assert input_snapshot_hints["project_dir"] == str | Path
    assert input_snapshot_hints["return"] == dict[str, artifact_manifest.ArtifactFingerprint]
    assert build_entry_hints["project_dir"] == str | Path
    assert build_entry_hints["artifact_id"] is str
    assert build_entry_hints["relative_path"] == str | Path
    assert build_entry_hints["declared_status"] is str
    assert build_entry_hints["run_id"] is str
    assert build_entry_hints["observed_at"] is str
    assert build_entry_hints["return"] is artifact_manifest.ArtifactEntry
    assert extra_hints["return"] is artifact_manifest.ExtraArtifactEntry
    assert collect_hints["target_info"] is artifact_manifest.TargetArtifactInfo
    assert collect_hints["return"] == list[artifact_manifest.ArtifactEntry]
    assert latest_hints["manifest"] is artifact_manifest.RuntimeManifest
    assert latest_hints["return"] == dict[str, artifact_manifest.ArtifactSnapshotEntry]
    assert atomic_hints["path"] == str | Path
    assert atomic_hints["value"] is object
    assert atomic_hints["return"] is type(None)
    assert replay_hints["flow"] is str
    assert replay_hints["target_name"] is str
    assert replay_hints["output_dir"] == str | Path
    assert replay_hints["return"] == list[str]
    assert version_hints["return"] == str | None
    assert digest_hints["return"] is str
    assert path_hints["return"] is Path
    assert input_digest_hints["return"] is str


def test_missing_artifact_entry_keeps_fingerprint_fields_absent(tmp_path):
    entry = artifact_manifest.build_artifact_entry(
        tmp_path,
        "missing-report",
        "reports/missing.md",
        "CURRENT",
        "run-1",
        "2026-07-12T00:00:00.000Z",
    )

    assert entry["status"] == "MISSING"
    assert entry["exists"] is False
    assert entry["produced_by_run_id"] is None
    assert {
        "sha256",
        "size_bytes",
        "created_at",
        "modified_at",
    }.isdisjoint(entry)
