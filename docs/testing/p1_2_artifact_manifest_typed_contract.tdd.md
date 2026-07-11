# P1-2 Artifact Manifest Typed Contract TDD Evidence

## Source

No upgrade plan file was read for this work. The scope was derived from the
P1-2 requirement to replace generic dictionaries and `Any` with typed contracts,
starting with the runtime artifact contract because it is shared by release
gates, dashboards, target flows, and artifact freshness checks.

SynthPilot real MCP validation remains deferred and is tracked separately in:

```text
docs/testing/p0_1_synthpilot_follow_up.md
```

## User Journeys

1. As a release owner, I want runtime artifact manifests to expose typed
   contracts, so artifact freshness and manifest consumers do not rely only on
   unstructured dictionaries.
2. As a maintainer, I want run and artifact statuses represented as `Literal`
   unions, so invalid status values are visible in the Python type surface.
3. As a reviewer, I want existing artifact-manifest behavior tests to remain
   green while typing is introduced incrementally.

## Task Report

### RED Evidence

A new structure test was added to require exported typed runtime contracts.

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py --basetemp .tmp-pytest-p1-2-artifact-types-red -p no:cacheprovider -q
```

Result:

```text
1 failed in 0.09s
```

The failure was the intended RED signal: `artifact_manifest` did not yet expose
`RunStatus`, `ArtifactStatus`, `ArtifactFingerprint`, `ArtifactEntry`, or
`RuntimeManifest`.

### GREEN Evidence

`artifact_manifest.py` now exports typed runtime contracts:

- `RunStatus = Literal["PASS", "FAIL"]`
- `ArtifactStatus = Literal["CURRENT", "MISSING", "N/A", "STALE"]`
- `ArtifactFingerprint`, `ArtifactEntry`, `RuntimeRun`, `RotationHistory`, and
  `RuntimeManifest` as `TypedDict` contracts
- `load_runtime_manifest(manifest_path: Path, target_name: str) -> RuntimeManifest`
- `snapshot_project_artifacts(project_dir: str | Path) -> dict[str, ArtifactFingerprint]`
- `artifact_status(...) -> ArtifactStatus`

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py --basetemp .tmp-pytest-p1-2-artifact-types-green-3 -p no:cacheprovider -q; uv run --offline --frozen mypy .trae/agent/artifact_manifest.py
```

Result:

```text
1 passed in 0.05s
Success: no issues found in 1 source file
```

### Regression Evidence

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py tests/test_agent.py::test_p5_8_generate_rtl_writes_runtime_artifact_manifest tests/test_agent.py::test_artifact_manifest_marks_unchanged_preexisting_file_stale_on_failure tests/test_agent.py::test_artifact_manifest_marks_changed_file_current_and_links_run tests/test_agent.py::test_artifact_manifest_unchanged_file_is_stale_on_later_run tests/test_agent.py::test_artifact_manifest_atomic_write_preserves_previous_manifest tests/test_agent.py::test_history_rotation_archives_target_manifest_runs_and_can_be_disabled tests/test_agent.py::test_p5_8_manifest_rejects_invalid_status_external_path_and_corrupt_json tests/test_agent.py::test_artifact_manifest_rejects_relative_path_escape tests/test_agent.py::test_artifact_manifest_records_input_file_lineage --basetemp .tmp-pytest-p1-2-artifact-types-regression-2 -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent/artifact_manifest.py tests/test_p1_2_artifact_manifest_typed_contract.py; uv run --offline --frozen mypy
```

Result:

```text
10 passed in 0.91s
All checks passed!
Success: no issues found in 60 source files
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Runtime run status is represented by a `Literal` union | `tests/test_p1_2_artifact_manifest_typed_contract.py` | structure/unit | PASS | `RunStatus` args asserted |
| 2 | Artifact status is represented by a `Literal` union | `tests/test_p1_2_artifact_manifest_typed_contract.py` | structure/unit | PASS | `ArtifactStatus` args asserted |
| 3 | Artifact fingerprints and entries expose `TypedDict` fields | `tests/test_p1_2_artifact_manifest_typed_contract.py` | structure/unit | PASS | annotations asserted |
| 4 | Runtime manifests expose typed top-level fields | `tests/test_p1_2_artifact_manifest_typed_contract.py` | structure/unit | PASS | `RuntimeManifest.__annotations__` asserted |
| 5 | Existing artifact manifest freshness and failure behavior remains compatible | selected `tests/test_agent.py` manifest tests | regression | PASS | `10 passed in 0.91s` |
| 6 | Artifact manifest stays covered by Ruff and Mypy | quality command above | quality/typecheck | PASS | Ruff PASS, Mypy PASS |

## Known Gaps

- This is the second P1-2 typed slice. It does not yet satisfy the full P1-2
  acceptance criteria of reducing `Any` by at least 80%, raising coverage to
  85%, or enabling the full Ruff `I/B/UP/SIM/C90` rule set.
- Remaining P1-2 work should continue through entrypoint, plugin boundary,
  runtime facade, and broader artifact contract internals before tightening
  global quality gates.
