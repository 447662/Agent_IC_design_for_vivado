from __future__ import annotations

import json
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from digital_ic_agent._runtime.design_workspace import (
    load_workspace_state,
    record_workspace_verification,
)
from digital_ic_agent._runtime.generic_verification_evidence import (
    SourceRecord,
    atomic_write_json as _atomic_write_json,
    atomic_write_text as _atomic_write_text,
    collect_intent_hashes as _intent_hashes,
    existing_iteration as _existing_iteration,
    file_summary as _file_summary,
    progress_signature as _progress_signature,
    same_failed_progress_count as _same_failed_progress_count,
    sha256 as _sha256,
    timestamp as _timestamp,
    write_source_snapshot_and_diff as _write_source_snapshot_and_diff,
)
from digital_ic_agent._runtime.generic_verification_vivado import (
    ExecutionConfig,
    VivadoLaunchMode,
    VivadoToolError,
    copy_project_artifact as _copy_project_artifact,
    project_artifact as _project_artifact,
    render_project_verification_tcl as _render_project_verification_tcl,
    resolve_tools as _resolve_tools,
)
from digital_ic_agent._runtime.intent_contract import (
    IntentFileError,
    load_intent_json,
    validate_intents,
)
from digital_ic_agent._runtime.verification_verdict import (
    ProcessResult,
    VerificationVerdict,
    evaluate_process_results,
    failed_verdict,
    write_verification_verdict,
)
from digital_ic_agent._runtime.xcrg_coverage_gates import (
    CoverageGateEvaluation,
    evaluate_xcrg_coverage_gates,
)


ToolRunner = Callable[..., subprocess.CompletedProcess[str]]
IntentStatus = Literal["FAIL", "AMBIGUOUS"]
MAX_SOURCE_BYTES = 16 * 1024 * 1024
ITERATION_SCHEMA_VERSION = "digital-ic-agent.iteration.v1"


class GenericVerificationError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: IntentStatus = "FAIL",
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.data = dict(data or {})


def _as_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise GenericVerificationError("INTENT_INVALID", f"{name} must be an object")
    return value


def _load_config(verification: Mapping[str, object]) -> ExecutionConfig:
    coverage_strategy = _as_mapping(
        verification["coverage_strategy"],
        "coverage_strategy",
    )
    iteration_limits = _as_mapping(
        verification["iteration_limits"],
        "iteration_limits",
    )
    code_thresholds = _as_mapping(
        verification["code_coverage"],
        "code_coverage",
    )
    return {
        "module": cast(str, verification["module"]),
        "testbench_top": cast(str, verification["testbench_top"]),
        "source_files": [str(item) for item in cast(list[object], verification["source_files"])],
        "include_dirs": [str(item) for item in cast(list[object], verification["include_dirs"])],
        "uvm_enabled": cast(bool, verification["uvm_enabled"]),
        "timescale": cast(str, verification["timescale"]),
        "pass_markers": [str(item) for item in cast(list[object], verification["pass_markers"])],
        "code_thresholds": {
            metric: float(cast(int | float, code_thresholds[metric]))
            for metric in ("statement", "branch", "condition", "toggle")
        },
        "code_coverage": cast(bool, coverage_strategy["code_coverage"]),
        "functional_coverage": cast(bool, coverage_strategy["functional_coverage"]),
        "functional_threshold": float(
            cast(int | float, coverage_strategy["functional_threshold"])
        ),
        "max_iterations": cast(int, iteration_limits["max_iterations"]),
        "max_time_seconds": cast(int, iteration_limits["max_time_seconds"]),
        "no_progress_limit": cast(int, iteration_limits["no_progress_limit"]),
    }


def _resolve_workspace_path(workspace: Path, relative: str, *, kind: str) -> Path:
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise GenericVerificationError(
            f"{kind.upper()}_PATH_INVALID",
            f"{kind} path escapes the workspace: {relative}",
        ) from exc
    return candidate


def _collect_sources(
    workspace: Path,
    config: ExecutionConfig,
) -> tuple[list[Path], list[Path], list[SourceRecord], dict[str, bytes]]:
    source_paths: list[Path] = []
    records: list[SourceRecord] = []
    contents: dict[str, bytes] = {}
    for relative in config["source_files"]:
        path = _resolve_workspace_path(workspace, relative, kind="source")
        if not path.is_file():
            raise GenericVerificationError(
                "SOURCE_FILE_NOT_FOUND",
                f"Declared source file was not found: {relative}",
            )
        content = path.read_bytes()
        if len(content) > MAX_SOURCE_BYTES:
            raise GenericVerificationError(
                "SOURCE_FILE_TOO_LARGE",
                f"Declared source exceeds {MAX_SOURCE_BYTES} bytes: {relative}",
            )
        normalized = Path(relative).as_posix()
        source_paths.append(path)
        records.append(
            {
                "path": normalized,
                "sha256": _sha256(content),
                "size_bytes": len(content),
            }
        )
        contents[normalized] = content

    include_paths: list[Path] = []
    for relative in config["include_dirs"]:
        path = _resolve_workspace_path(workspace, relative, kind="include")
        if not path.is_dir():
            raise GenericVerificationError(
                "INCLUDE_DIR_NOT_FOUND",
                f"Declared include directory was not found: {relative}",
            )
        include_paths.append(path)
    return source_paths, include_paths, records, contents


def _run_stage(
    runner: ToolRunner,
    command: list[str],
    *,
    cwd: Path,
    deadline: float,
    stage: str,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Path]]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        result = subprocess.CompletedProcess(command, 124, "", "verification time limit reached")
    else:
        try:
            result = runner(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=remaining,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            result = subprocess.CompletedProcess(
                command,
                124,
                stdout,
                f"{stderr}\nverification time limit reached".strip(),
            )
        except FileNotFoundError as exc:
            result = subprocess.CompletedProcess(command, 127, "", str(exc))
        except OSError as exc:
            result = subprocess.CompletedProcess(command, 126, "", str(exc))
    stdout_path = cwd / "logs" / f"{stage}.stdout.log"
    stderr_path = cwd / "logs" / f"{stage}.stderr.log"
    _atomic_write_text(stdout_path, result.stdout or "")
    _atomic_write_text(stderr_path, result.stderr or "")
    return result, {f"{stage}.stdout": stdout_path, f"{stage}.stderr": stderr_path}


def _tool_version(result: subprocess.CompletedProcess[str]) -> str:
    for line in f"{result.stdout or ''}\n{result.stderr or ''}".splitlines():
        if line.strip():
            return line.strip()
    return "UNKNOWN"


def _load_manifest(workspace: Path, module: str) -> dict[str, Any]:
    path = workspace / "artifacts.json"
    if not path.is_file():
        return {
            "schema_version": 1,
            "target": module,
            "updated_at": _timestamp(),
            "runs": [],
        }
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenericVerificationError("MANIFEST_INVALID", f"Invalid artifacts manifest: {exc}") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or not isinstance(manifest.get("runs"), list)
    ):
        raise GenericVerificationError("MANIFEST_INVALID", "Invalid artifacts manifest structure")
    target = manifest.get("target")
    if target not in {None, module}:
        raise GenericVerificationError(
            "MANIFEST_TARGET_MISMATCH",
            f"Manifest target {target!r} does not match {module!r}",
        )
    manifest["target"] = module
    return manifest


def _append_manifest(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    iteration: int,
    iteration_dir: Path | None,
    verdict: VerificationVerdict,
) -> Path:
    runs = cast(list[object], manifest["runs"])
    runs.append(
        {
            "run_id": f"generic-{iteration:04d}-{uuid.uuid4().hex[:8]}",
            "flow": "generic-vivado",
            "status": verdict.status,
            "iteration": iteration,
            "iteration_dir": None if iteration_dir is None else str(iteration_dir),
            "verification_verdict": verdict.to_dict(),
        }
    )
    manifest["updated_at"] = _timestamp()
    path = workspace / "artifacts.json"
    _atomic_write_json(path, manifest)
    return path


def _finalize(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    iteration: int,
    iteration_dir: Path | None,
    intent_hashes: dict[str, str],
    intent_sha256: str,
    progress_signature: str,
    sources: list[SourceRecord],
    source_diff: Path | None,
    started_at: str,
    tool_version: str,
    commands: list[list[str]],
    log_paths: dict[str, Path],
    coverage: CoverageGateEvaluation,
    verdict: VerificationVerdict,
    vivado_launch_mode: VivadoLaunchMode,
    stopped_reason: str | None = None,
) -> dict[str, Any]:
    root_verdict_paths = write_verification_verdict(workspace, verdict)
    iteration_verdict_paths: tuple[Path, Path] | None = None
    if iteration_dir is not None:
        iteration_verdict_paths = write_verification_verdict(iteration_dir, verdict)
        metadata = {
            "schema_version": ITERATION_SCHEMA_VERSION,
            "iteration": iteration,
            "started_at": started_at,
            "completed_at": _timestamp(),
            "intent_hashes": intent_hashes,
            "intent_sha256": intent_sha256,
            "progress_signature": progress_signature,
            "sources": sources,
            "source_diff": None if source_diff is None else _file_summary(source_diff),
            "tool_version": tool_version,
            "vivado_launch_mode": vivado_launch_mode,
            "commands": commands,
            "logs": {
                name: _file_summary(path)
                for name, path in sorted(log_paths.items())
                if path.is_file()
            },
            "coverage_gates": coverage["gates"],
            "coverage_scores": coverage["scores"],
            "coverage_diagnostics": coverage["diagnostics"],
            "verdict": verdict.to_dict(),
            "stopped_reason": stopped_reason,
        }
        _atomic_write_json(iteration_dir / "iteration.json", metadata)

    manifest_path = _append_manifest(
        workspace,
        manifest,
        iteration=iteration,
        iteration_dir=iteration_dir,
        verdict=verdict,
    )
    state = record_workspace_verification(
        workspace,
        iteration=iteration,
        iteration_dir=iteration_dir,
        verdict_status=verdict.status,
        stopped_reason=stopped_reason,
    )
    return {
        "workspace": str(workspace),
        "iteration": iteration,
        "iteration_dir": None if iteration_dir is None else str(iteration_dir),
        "manifest_path": str(manifest_path),
        "verdict_paths": [str(path) for path in root_verdict_paths],
        "iteration_verdict_paths": (
            []
            if iteration_verdict_paths is None
            else [str(path) for path in iteration_verdict_paths]
        ),
        "coverage": coverage,
        "vivado_launch_mode": vivado_launch_mode,
        "state": state,
        "verdict": verdict.to_dict(),
    }


def verify_workspace(
    workspace: Path,
    *,
    vivado_bin: Path | None = None,
    vivado_launch_mode: VivadoLaunchMode = "direct",
    runner: ToolRunner = subprocess.run,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    if vivado_launch_mode not in {"direct", "project"}:
        raise GenericVerificationError(
            "VIVADO_LAUNCH_MODE_INVALID",
            f"Unsupported Vivado launch mode: {vivado_launch_mode}",
        )
    state = load_workspace_state(workspace)
    design_path = workspace / "contracts" / "design_intent.json"
    verification_path = workspace / "contracts" / "verification_intent.json"
    try:
        design = load_intent_json(design_path)
        verification = load_intent_json(verification_path)
    except IntentFileError as exc:
        raise GenericVerificationError(exc.code, str(exc)) from exc
    validation = validate_intents(design, verification)
    if not validation.passed:
        status: IntentStatus = "AMBIGUOUS" if validation.status == "AMBIGUOUS" else "FAIL"
        raise GenericVerificationError(
            "INTENT_AMBIGUOUS" if status == "AMBIGUOUS" else "INTENT_INVALID",
            "Intent contracts require clarification or correction",
            status=status,
            data={"issues": [issue.to_dict() for issue in validation.issues]},
        )
    verification_document = _as_mapping(verification, "VerificationIntent")
    config = _load_config(verification_document)
    source_paths, include_paths, source_records, source_contents = _collect_sources(
        workspace,
        config,
    )
    intent_hashes, intent_sha256 = _intent_hashes(workspace)
    signature = _progress_signature(intent_sha256, source_records)
    current_iteration = _existing_iteration(workspace, state.get("iteration"))
    manifest = _load_manifest(workspace, config["module"])
    empty_coverage: CoverageGateEvaluation = {
        "gates": {},
        "scores": {},
        "diagnostics": [],
    }
    if current_iteration >= config["max_iterations"]:
        verdict = failed_verdict(
            "MAX_ITERATIONS_REACHED",
            f"Maximum iteration count reached: {config['max_iterations']}",
        )
        return _finalize(
            workspace,
            manifest,
            iteration=current_iteration,
            iteration_dir=None,
            intent_hashes=intent_hashes,
            intent_sha256=intent_sha256,
            progress_signature=signature,
            sources=source_records,
            source_diff=None,
            started_at=_timestamp(),
            tool_version="NOT_RUN",
            commands=[],
            log_paths={},
            coverage=empty_coverage,
            verdict=verdict,
            vivado_launch_mode=vivado_launch_mode,
            stopped_reason="MAX_ITERATIONS_REACHED",
        )

    same_failed_progress = _same_failed_progress_count(workspace, signature)
    iteration = current_iteration + 1
    iteration_dir = workspace / "iterations" / f"{iteration:04d}"
    if iteration_dir.exists():
        raise GenericVerificationError(
            "ITERATION_DIRECTORY_EXISTS",
            f"Iteration directory already exists: {iteration_dir}",
        )
    iteration_dir.mkdir(parents=True)
    source_diff = _write_source_snapshot_and_diff(
        workspace,
        iteration_dir,
        iteration,
        source_records,
        source_contents,
    )
    started_at_text = _timestamp()
    if same_failed_progress >= config["no_progress_limit"]:
        verdict = failed_verdict(
            "NO_PROGRESS_LIMIT_REACHED",
            "No source or intent progress was detected after the configured failure limit",
        )
        return _finalize(
            workspace,
            manifest,
            iteration=iteration,
            iteration_dir=iteration_dir,
            intent_hashes=intent_hashes,
            intent_sha256=intent_sha256,
            progress_signature=signature,
            sources=source_records,
            source_diff=source_diff,
            started_at=started_at_text,
            tool_version="NOT_RUN",
            commands=[],
            log_paths={},
            coverage=empty_coverage,
            verdict=verdict,
            vivado_launch_mode=vivado_launch_mode,
            stopped_reason="NO_PROGRESS_LIMIT_REACHED",
        )

    coverage_required = config["code_coverage"] or config["functional_coverage"]
    try:
        tools = _resolve_tools(
            vivado_bin,
            coverage_required=coverage_required,
            vivado_launch_mode=vivado_launch_mode,
        )
    except VivadoToolError as exc:
        verdict = failed_verdict(exc.code, str(exc), cast(str | None, exc.data.get("tool")))
        return _finalize(
            workspace,
            manifest,
            iteration=iteration,
            iteration_dir=iteration_dir,
            intent_hashes=intent_hashes,
            intent_sha256=intent_sha256,
            progress_signature=signature,
            sources=source_records,
            source_diff=source_diff,
            started_at=started_at_text,
            tool_version="NOT_FOUND",
            commands=[],
            log_paths={},
            coverage=empty_coverage,
            verdict=verdict,
            vivado_launch_mode=vivado_launch_mode,
        )

    started_at = datetime.now(UTC)
    deadline = time.monotonic() + config["max_time_seconds"]
    commands: list[list[str]] = []
    log_paths: dict[str, Path] = {}
    process_results: dict[str, ProcessResult] = {}
    coverage_name = f"{config['module']}_cov"
    project_required_artifacts: list[Path] = []
    if vivado_launch_mode == "project":
        project_name = f"{config['module']}_verification"
        project_dir = iteration_dir / "vivado_project"
        project_script = iteration_dir / "run_vivado_project.tcl"
        _atomic_write_text(
            project_script,
            _render_project_verification_tcl(
                project_dir=project_dir,
                config=config,
                source_paths=source_paths,
                include_paths=include_paths,
                coverage_required=coverage_required,
            ),
        )
        vivado_log = iteration_dir / "logs" / "vivado.log"
        vivado_journal = iteration_dir / "logs" / "vivado.jou"
        vivado_log.parent.mkdir(parents=True, exist_ok=True)
        project_command = [
            str(tools["vivado"]),
            "-mode",
            "batch",
            "-source",
            str(project_script),
            "-journal",
            str(vivado_journal),
            "-log",
            str(vivado_log),
        ]
        commands.append(project_command)
        project_result, project_logs = _run_stage(
            runner,
            project_command,
            cwd=iteration_dir,
            deadline=deadline,
            stage="vivado_project",
        )
        process_results["vivado"] = cast(ProcessResult, project_result)
        log_paths.update(project_logs)
        if vivado_log.is_file():
            log_paths["vivado.log"] = vivado_log
        version = _tool_version(project_result)

        compile_log = _copy_project_artifact(
            _project_artifact(project_dir, "compile.log"),
            iteration_dir / "logs" / "compile.log",
        )
        elaborate_log = _copy_project_artifact(
            _project_artifact(project_dir, "elaborate.log"),
            iteration_dir / "logs" / "elaborate.log",
        )
        xsim_log = _copy_project_artifact(
            _project_artifact(project_dir, "simulate.log"),
            iteration_dir / "xsim.log",
        )
        wave_db = _copy_project_artifact(
            _project_artifact(project_dir, "*_behav.wdb"),
            iteration_dir / "simulation.wdb",
        )
        log_paths.update(
            {
                "compile.log": compile_log,
                "elaborate.log": elaborate_log,
                "simulate.log": xsim_log,
            }
        )
        project_file = project_dir / f"{project_name}.xpr"
        project_required_artifacts.extend(
            (project_file, compile_log, elaborate_log)
        )
        discovered_coverage_info = _project_artifact(project_dir, "xsim.CCInfo")
        if discovered_coverage_info is None:
            coverage_db_dir = project_dir / "coverage"
            coverage_info = (
                coverage_db_dir
                / "xsim.codeCov"
                / coverage_name
                / "xsim.CCInfo"
            )
        else:
            coverage_info = discovered_coverage_info
            coverage_db_dir = coverage_info.parents[2]
        coverage_db_argument = str(coverage_db_dir)
        simulation_result = project_result
    else:
        version_command = [str(tools["xvlog"]), "--version"]
        commands.append(version_command)
        version_result, version_logs = _run_stage(
            runner,
            version_command,
            cwd=iteration_dir,
            deadline=deadline,
            stage="version",
        )
        log_paths.update(version_logs)
        version = _tool_version(version_result)

        compile_command = [str(tools["xvlog"]), "-sv"]
        if config["uvm_enabled"]:
            compile_command.extend(("-L", "uvm"))
        for include_path in include_paths:
            compile_command.extend(("-i", str(include_path)))
        compile_command.extend(str(path) for path in source_paths)
        commands.append(compile_command)
        compile_result, compile_logs = _run_stage(
            runner,
            compile_command,
            cwd=iteration_dir,
            deadline=deadline,
            stage="compile",
        )
        process_results["xvlog"] = cast(ProcessResult, compile_result)
        log_paths.update(compile_logs)

        snapshot = f"{config['module']}_snapshot"
        if compile_result.returncode == 0:
            elaborate_command = [
                str(tools["xelab"]),
                config["testbench_top"],
                "-debug",
                "typical",
                "-timescale",
                config["timescale"],
                "-s",
                snapshot,
            ]
            if config["uvm_enabled"]:
                elaborate_command.extend(("-L", "uvm"))
            if coverage_required:
                elaborate_command.extend(
                    ("-cov_db_dir", "coverage", "-cov_db_name", coverage_name)
                )
            if config["code_coverage"]:
                elaborate_command.extend(("-cc_type", "sbct"))
            commands.append(elaborate_command)
            elaborate_result, elaborate_logs = _run_stage(
                runner,
                elaborate_command,
                cwd=iteration_dir,
                deadline=deadline,
                stage="elaborate",
            )
            process_results["xelab"] = cast(ProcessResult, elaborate_result)
            log_paths.update(elaborate_logs)
        else:
            elaborate_result = subprocess.CompletedProcess([], 1, "", "compile failed")

        xsim_log = iteration_dir / "xsim.log"
        wave_db = iteration_dir / "simulation.wdb"
        run_script = iteration_dir / "run_all.tcl"
        _atomic_write_text(run_script, "log_wave -r /\nrun all\nexit\n")
        if elaborate_result.returncode == 0:
            simulation_command = [
                str(tools["xsim"]),
                snapshot,
                "-wdb",
                wave_db.name,
                "-tclbatch",
                run_script.name,
                "-log",
                xsim_log.name,
            ]
            commands.append(simulation_command)
            simulation_result, simulation_logs = _run_stage(
                runner,
                simulation_command,
                cwd=iteration_dir,
                deadline=deadline,
                stage="simulate",
            )
            process_results["xsim"] = cast(ProcessResult, simulation_result)
            log_paths.update(simulation_logs)
        else:
            simulation_result = subprocess.CompletedProcess([], 1, "", "elaboration failed")

        coverage_info = (
            iteration_dir
            / "coverage"
            / "xsim.codeCov"
            / coverage_name
            / "xsim.CCInfo"
        )
        coverage_db_argument = "coverage"

    xcrg_dir = iteration_dir / "reports" / "coverage"
    xcrg_log = iteration_dir / "logs" / "xcrg.log"
    if simulation_result.returncode == 0 and coverage_required:
        coverage_command = [
            str(tools["xcrg"]),
            "-cov_db_dir",
            coverage_db_argument,
            "-cov_db_name",
            coverage_name,
            "-report_dir",
            str(xcrg_dir),
            "-report_format",
            "html",
            "-log",
            str(xcrg_log),
        ]
        commands.append(coverage_command)
        coverage_result, coverage_logs = _run_stage(
            runner,
            coverage_command,
            cwd=iteration_dir,
            deadline=deadline,
            stage="coverage",
        )
        process_results["xcrg"] = cast(ProcessResult, coverage_result)
        log_paths.update(coverage_logs)

    if coverage_required:
        coverage = evaluate_xcrg_coverage_gates(
            workspace,
            xcrg_dir,
            code_thresholds=(config["code_thresholds"] if config["code_coverage"] else {}),
            functional_required=config["functional_coverage"],
            functional_threshold=config["functional_threshold"],
            included_sources=[
                record["path"]
                for record in source_records
                if record["path"].startswith("rtl/")
            ],
        )
    else:
        coverage = empty_coverage

    evidence_paths = dict(log_paths)
    evidence_paths["xsim.log"] = xsim_log
    if xcrg_log.is_file():
        evidence_paths["xcrg.log"] = xcrg_log
    required_artifacts = [xsim_log, wave_db, *project_required_artifacts]
    if coverage_required:
        required_artifacts.append(coverage_info)
        if config["code_coverage"]:
            required_artifacts.append(xcrg_dir / "codeCoverageReport" / "files.html")
        if config["functional_coverage"]:
            required_artifacts.append(xcrg_dir / "functionalCoverageReport" / "groups.html")
        required_artifacts.append(xcrg_log)
    verdict = evaluate_process_results(
        process_results=process_results,
        evidence_paths=evidence_paths,
        required_pass_markers=config["pass_markers"],
        required_artifact_paths=required_artifacts,
        started_at=started_at,
        coverage_required=coverage_required,
        coverage_gates=coverage["gates"],
    )
    return _finalize(
        workspace,
        manifest,
        iteration=iteration,
        iteration_dir=iteration_dir,
        intent_hashes=intent_hashes,
        intent_sha256=intent_sha256,
        progress_signature=signature,
        sources=source_records,
        source_diff=source_diff,
        started_at=started_at_text,
        tool_version=version,
        commands=commands,
        log_paths=evidence_paths,
        coverage=coverage,
        verdict=verdict,
        vivado_launch_mode=vivado_launch_mode,
    )
