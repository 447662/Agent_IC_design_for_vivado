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
4. As a manifest consumer, I want missing artifacts to omit fingerprint fields
   rather than receive placeholder hashes, so `MISSING` entries remain distinct
   from observed files.

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

### ArtifactEntry Required/Optional Slice Evidence

The next P1-2 slice fixed a contract mismatch in `ArtifactEntry`: runtime
entries always include artifact identity/status fields, while fingerprint fields
exist only when the file is present. The previous `TypedDict` inheritance made
fingerprint fields required and runtime identity fields optional.

RED command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py --basetemp .tmp-pytest-p1-2-artifact-entry-red -p no:cacheprovider -q
```

RED result:

```text
1 failed, 1 passed in 0.15s
```

The intended failure showed `ArtifactEntry.__required_keys__` did not contain
`id`, `path`, `declared_status`, `status`, `exists`, `observed_at`, or
`produced_by_run_id`.

GREEN command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py --basetemp .tmp-pytest-p1-2-artifact-entry-green2 -p no:cacheprovider -q
```

GREEN result:

```text
2 passed in 0.10s
```

Regression and quality commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_3_error_model.py tests/test_p1_3_async_fifo_typed_contracts.py tests/test_agent.py -k artifact_manifest --basetemp .tmp-pytest-p1-2-artifact-entry-regression -p no:cacheprovider -q
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/artifact_manifest.py tests/test_p1_2_artifact_manifest_typed_contract.py
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

Regression and quality results:

```text
8 passed, 208 deselected in 4.65s
All checks passed!
Success: no issues found in 61 source files
```

### Artifact Manifest Pure Function Signature Slice Evidence

The follow-on P1-2 slice tightened low-risk pure-function boundaries in
`artifact_manifest.py` without changing runtime manifest behavior:

- `snapshot_project_inputs(project_dir: str | Path) -> dict[str, ArtifactFingerprint]`
- `build_replay_command(...) -> list[str]`
- `extract_tool_version(...) -> str | None`
- `json_digest(...) -> str`
- `normalize_artifact_path(...) -> Path`
- `build_run_input_digest(...) -> str`

RED command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py --basetemp .tmp-pytest-p1-2-artifact-pure-fns-red -p no:cacheprovider -q
```

RED result:

```text
1 failed, 1 passed in 0.14s
```

The intended failure showed `snapshot_project_inputs` still accepted
`typing.Any` for `project_dir`, proving the pure-function boundary was not yet
typed.

GREEN and quality commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py --basetemp .tmp-pytest-p1-2-artifact-pure-fns-green2 -p no:cacheprovider -q
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/artifact_manifest.py tests/test_p1_2_artifact_manifest_typed_contract.py
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

GREEN and quality results:

```text
2 passed in 2.85s
All checks passed!
Success: no issues found in 61 source files
```

### Artifact Manifest Builder/Snapshot Signature Slice Evidence

The next P1-2 slice tightened artifact builder, extra artifact normalization,
latest snapshot extraction, and atomic JSON write boundaries:

- `build_artifact_entry(...) -> ArtifactEntry`
- `normalize_extra_artifact(...) -> ExtraArtifactEntry`
- `collect_artifacts(target_info: TargetArtifactInfo, ...) -> list[ArtifactEntry]`
- `_latest_artifact_snapshot(manifest: RuntimeManifest) -> dict[str, ArtifactSnapshotEntry]`
- `atomic_write_json(path: str | Path, value: object) -> None`

RED command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py --basetemp .tmp-pytest-p1-2-artifact-builders-red -p no:cacheprovider -q
```

RED result:

```text
1 failed, 1 passed in 0.16s
```

The intended failure showed `build_artifact_entry` still accepted `typing.Any`
for `project_dir`, proving the builder boundary was not yet typed.

GREEN and quality commands:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_p1_2_artifact_manifest_typed_contract.py --basetemp .tmp-pytest-p1-2-artifact-builders-green2 -p no:cacheprovider -q
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen ruff check .trae/agent/artifact_manifest.py tests/test_p1_2_artifact_manifest_typed_contract.py
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen mypy
```

GREEN and quality results:

```text
2 passed in 3.63s
All checks passed!
Success: no issues found in 61 source files
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
| 7 | Artifact entry identity/status fields are required while fingerprint fields are optional | `tests/test_p1_2_artifact_manifest_typed_contract.py` | structure/unit | PASS | `2 passed in 0.10s` |
| 8 | Missing artifact entries do not emit placeholder fingerprint fields | `tests/test_p1_2_artifact_manifest_typed_contract.py::test_missing_artifact_entry_keeps_fingerprint_fields_absent` | behavior/unit | PASS | `2 passed in 0.10s` |
| 9 | Artifact manifest pure helpers expose concrete path, digest, replay, and version return types | `tests/test_p1_2_artifact_manifest_typed_contract.py` | structure/unit | PASS | `2 passed in 2.85s` |
| 10 | Tightened pure-function signatures remain accepted by Ruff and project Mypy scope | quality commands above | quality/typecheck | PASS | Ruff PASS, Mypy PASS |
| 11 | Artifact builder, extra artifact, snapshot, and atomic write helpers expose concrete contracts | `tests/test_p1_2_artifact_manifest_typed_contract.py` | structure/unit | PASS | `2 passed in 3.63s` |
| 12 | Builder/snapshot signature tightening remains accepted by Ruff and project Mypy scope | quality commands above | quality/typecheck | PASS | Ruff PASS, Mypy PASS |

## Known Gaps

- This is the second P1-2 typed slice. It does not yet satisfy the full P1-2
  acceptance criteria of reducing `Any` by at least 80%, raising coverage to
  85%, or enabling the full Ruff `I/B/UP/SIM/C90` rule set.
- Remaining P1-2 work should continue through entrypoint, plugin boundary,
  runtime facade, and broader artifact contract internals before tightening
  global quality gates.
