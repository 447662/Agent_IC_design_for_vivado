import hashlib
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    action: str
    path: Path
    title: str
    content: str
    required_capabilities: tuple[str, ...] = ()
    content_digest: str = ""


@dataclass(frozen=True)
class SkillExecutionRequest:
    skill: SkillDefinition
    user_input: str
    output_dir: Path
    context: Mapping[str, Any] = field(default_factory=dict)


class SkillExecutionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ToolRunRecord:
    name: str
    status: SkillExecutionStatus
    command: tuple[str, ...] = ()
    returncode: int | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillExecutionResult:
    skill_name: str
    action: str
    status: SkillExecutionStatus
    artifacts: tuple[Path, ...] = ()
    validated_artifacts: tuple[Path, ...] = ()
    diagnostics: tuple[str, ...] = ()
    tool_runs: tuple[ToolRunRecord, ...] = ()
    failure_reason: str | None = None
    message: str = ""


class SkillExecutor(Protocol):
    def execute(self, request: SkillExecutionRequest) -> SkillExecutionResult:
        ...


SkillHandler = Callable[[SkillExecutionRequest], SkillExecutionResult]


class SkillResultValidator:
    _RTL_SUFFIXES = {".v", ".sv", ".vhd", ".vhdl"}
    _RTL_CHECK_NAMES = {"rtl-check", "syntax-check", "simulation", "vivado"}

    @staticmethod
    def _inside_root(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    @staticmethod
    def _is_testbench(path: Path) -> bool:
        lowered_parts = {part.lower() for part in path.parts}
        lowered_name = path.name.lower()
        return (
            "tb" in lowered_parts
            or "testbench" in lowered_parts
            or lowered_name.startswith("tb_")
            or "_tb." in lowered_name
        )

    @staticmethod
    def _successful_tool_run(
        tool_runs: tuple[ToolRunRecord, ...],
        accepted_names: set[str],
    ) -> bool:
        for tool_run in tool_runs:
            name = tool_run.name.strip().lower()
            if (
                tool_run.status is SkillExecutionStatus.SUCCEEDED
                and (name in accepted_names or any(item in name for item in accepted_names))
                and tool_run.returncode in (None, 0)
            ):
                return True
        return False

    def _validate_artifact_paths(
        self,
        request: SkillExecutionRequest,
        result: SkillExecutionResult,
    ) -> tuple[Path, ...]:
        output_root = request.output_dir.resolve()
        validated = []
        for raw_path in result.artifacts:
            path = Path(raw_path)
            resolved = (
                path.resolve()
                if path.is_absolute()
                else (output_root / path).resolve()
            )
            if not self._inside_root(resolved, output_root):
                raise ValueError(
                    "Skill result artifact escapes output directory: {}".format(path)
                )
            if not resolved.is_file():
                if result.status in {
                    SkillExecutionStatus.SUCCEEDED,
                    SkillExecutionStatus.PARTIAL,
                }:
                    raise ValueError(
                        "Skill result references missing artifact: {}".format(path)
                    )
                continue
            if resolved.stat().st_size <= 0:
                if result.status in {
                    SkillExecutionStatus.SUCCEEDED,
                    SkillExecutionStatus.PARTIAL,
                }:
                    raise ValueError(
                        "Skill result references empty artifact: {}".format(path)
                    )
                continue
            validated.append(resolved)
        return tuple(validated)

    @staticmethod
    def _validate_design_success(artifacts: tuple[Path, ...]) -> None:
        markdown_files = [path for path in artifacts if path.suffix.lower() == ".md"]
        if not markdown_files:
            raise ValueError("Design skill success requires a Markdown design specification")
        if not any(
            path.read_text(encoding="utf-8", errors="replace").lstrip().startswith("#")
            and "##" in path.read_text(encoding="utf-8", errors="replace")
            for path in markdown_files
        ):
            raise ValueError(
                "Design skill success requires a structured design specification"
            )

    def _validate_rtl_success(
        self,
        artifacts: tuple[Path, ...],
        tool_runs: tuple[ToolRunRecord, ...],
    ) -> None:
        rtl_files = [
            path
            for path in artifacts
            if path.suffix.lower() in self._RTL_SUFFIXES and not self._is_testbench(path)
        ]
        testbenches = [
            path
            for path in artifacts
            if path.suffix.lower() in self._RTL_SUFFIXES and self._is_testbench(path)
        ]
        if not rtl_files:
            raise ValueError("RTL skill success requires an RTL source artifact")
        if not testbenches:
            raise ValueError("RTL skill success requires a testbench artifact")
        if not self._successful_tool_run(tool_runs, self._RTL_CHECK_NAMES):
            raise ValueError(
                "RTL skill success requires a successful syntax or RTL check"
            )

    def _validate_verification_success(
        self,
        artifacts: tuple[Path, ...],
        tool_runs: tuple[ToolRunRecord, ...],
    ) -> None:
        has_uvm_source = any(
            path.suffix.lower() == ".sv" and "uvm" in path.as_posix().lower()
            for path in artifacts
        )
        has_log = any(path.suffix.lower() == ".log" for path in artifacts)
        has_report = any(
            path.suffix.lower() == ".md" and "report" in path.name.lower()
            for path in artifacts
        )
        if not (has_uvm_source and has_log and has_report):
            raise ValueError(
                "Verification success requires UVM source, simulation log, and report"
            )
        if not self._successful_tool_run(
            tool_runs,
            {"uvm", "simulation", "vivado"},
        ):
            raise ValueError(
                "Verification success requires a successful simulator tool run"
            )

    @staticmethod
    def _validate_verification_partial(artifacts: tuple[Path, ...]) -> None:
        if not any(path.name == "verification_plan.md" for path in artifacts):
            raise ValueError(
                "Partial verification result requires verification_plan.md"
            )

    def validate(
        self,
        request: SkillExecutionRequest,
        result: SkillExecutionResult,
    ) -> SkillExecutionResult:
        if result.skill_name != request.skill.name:
            raise ValueError(
                "Skill executor returned mismatched skill name: {}".format(
                    result.skill_name
                )
            )
        if result.action != request.skill.action:
            raise ValueError(
                "Skill executor returned mismatched action: {}".format(result.action)
            )
        if not isinstance(result.status, SkillExecutionStatus):
            raise ValueError(
                "Skill executor returned invalid status: {!r}".format(result.status)
            )
        if (
            result.status in {SkillExecutionStatus.BLOCKED, SkillExecutionStatus.FAILED}
            and not str(result.failure_reason or "").strip()
        ):
            raise ValueError(
                "{} skill result requires failure_reason".format(result.status.value)
            )

        validated_artifacts = self._validate_artifact_paths(request, result)
        if result.status is SkillExecutionStatus.SUCCEEDED:
            if request.skill.action == "design-document":
                self._validate_design_success(validated_artifacts)
            elif request.skill.action == "rtl-implementation":
                self._validate_rtl_success(validated_artifacts, result.tool_runs)
            elif request.skill.action == "verification-plan":
                self._validate_verification_success(
                    validated_artifacts,
                    result.tool_runs,
                )
        elif (
            result.status is SkillExecutionStatus.PARTIAL
            and request.skill.action == "verification-plan"
        ):
            self._validate_verification_partial(validated_artifacts)

        return replace(
            result,
            artifacts=tuple(Path(path).resolve() for path in result.artifacts),
            validated_artifacts=validated_artifacts,
        )


class SkillLoader:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir).resolve()

    def _resolve_path(self, raw_path: object) -> Path:
        relative_path = Path(str(raw_path))
        if relative_path.is_absolute():
            raise ValueError("Skill path must be relative: {}".format(relative_path))
        resolved = (self.root_dir / relative_path).resolve()
        try:
            resolved.relative_to(self.root_dir)
        except ValueError as exc:
            raise ValueError(
                "Skill path escapes configured root: {}".format(relative_path)
            ) from exc
        return resolved

    @staticmethod
    def _title(content: str, fallback: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return fallback

    def load(self, config: Mapping[str, Any]) -> SkillDefinition:
        name = str(config.get("name", "")).strip()
        if not name:
            raise ValueError("Skill config missing name")
        action = str(config.get("action", "")).strip()
        if not action:
            raise ValueError("Skill config missing action: {}".format(name))
        path = self._resolve_path(config.get("path", ""))
        if not path.is_file():
            raise FileNotFoundError("Skill file not found: {}".format(path))
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError("Skill file is empty: {}".format(path))
        raw_capabilities = config.get("requiredCapabilities", ())
        if not isinstance(raw_capabilities, (list, tuple)):
            raise ValueError(
                "Skill requiredCapabilities must be a list: {}".format(name)
            )
        required_capabilities = tuple(
            str(capability).strip()
            for capability in raw_capabilities
            if str(capability).strip()
        )
        description = str(config.get("description", "")).strip()
        return SkillDefinition(
            name=name,
            description=description,
            action=action,
            path=path,
            title=self._title(content, name),
            content=content,
            required_capabilities=required_capabilities,
            content_digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def load_many(
        self,
        configs: list[Mapping[str, Any]],
    ) -> dict[str, SkillDefinition]:
        loaded: dict[str, SkillDefinition] = {}
        for config in configs:
            skill = self.load(config)
            if skill.name in loaded:
                raise ValueError("Duplicate skill name: {}".format(skill.name))
            loaded[skill.name] = skill
        return loaded


class DeterministicSkillExecutor:
    def __init__(
        self,
        handlers: Mapping[str, SkillHandler],
        validator: SkillResultValidator | None = None,
    ):
        self.handlers = dict(handlers)
        self.validator = validator or SkillResultValidator()

    def execute(self, request: SkillExecutionRequest) -> SkillExecutionResult:
        handler = self.handlers.get(request.skill.action)
        if handler is None:
            raise ValueError(
                "No executor registered for skill action: {}".format(
                    request.skill.action
                )
            )
        return self.validator.validate(request, handler(request))
