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
