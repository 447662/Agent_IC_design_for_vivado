import os
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, TypeGuard, cast, runtime_checkable


_PLUGIN_OUTPUT_ROOT: ContextVar[Path | None] = ContextVar(
    "plugin_output_root",
    default=None,
)
CommandPart = str | os.PathLike[str]
FlowHandler = Callable[..., object]
PluginOperation = Callable[..., object]


def _is_path_value(value: object) -> TypeGuard[str | os.PathLike[str]]:
    return isinstance(value, str | os.PathLike)


class ProcessHandle(Protocol):
    pid: int
    returncode: int | None

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


@dataclass
class ManagedProcess:
    process: ProcessHandle
    command: tuple[str, ...]
    cwd: Path | None
    started_at: datetime
    mode: str
    preserve: bool
    termination_grace_period: float = 5.0
    diagnostics: list[str] = field(default_factory=list)

    @property
    def pid(self) -> int:
        return int(self.process.pid)

    @property
    def returncode(self) -> int | None:
        value = getattr(self.process, "returncode", None)
        return None if value is None else int(value)

    def poll(self) -> int | None:
        value = self.process.poll()
        return None if value is None else int(value)

    def wait(self, timeout: float | None = None) -> int:
        try:
            return int(self.process.wait(timeout=timeout))
        except subprocess.TimeoutExpired:
            self.diagnostics.append(
                "wait timed out after {} seconds".format(timeout)
            )
            if self.mode == "automation" and not self.preserve:
                self.close(force=True)
            raise

    def terminate(self) -> None:
        if self.poll() is None:
            self.diagnostics.append("terminate requested")
            self.process.terminate()

    def kill(self) -> None:
        if self.poll() is None:
            self.diagnostics.append("kill requested")
            self.process.kill()

    def close(self, *, force: bool = False) -> None:
        if self.preserve and not force:
            return
        if self.poll() is not None:
            return

        self.terminate()
        try:
            self.process.wait(timeout=self.termination_grace_period)
        except subprocess.TimeoutExpired:
            self.diagnostics.append(
                "terminate timed out after {} seconds".format(
                    self.termination_grace_period
                )
            )
            self.kill()
            try:
                self.process.wait(timeout=self.termination_grace_period)
            except subprocess.TimeoutExpired:
                self.diagnostics.append(
                    "kill timed out after {} seconds".format(
                        self.termination_grace_period
                    )
                )

    def __enter__(self) -> "ManagedProcess":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class CommandRunner:
    def __init__(
        self,
        default_timeout: float = 120,
        process_grace_period: float = 5.0,
    ) -> None:
        self.default_timeout = int(default_timeout)
        self.process_grace_period = float(process_grace_period)
        self._launched_processes: list[ManagedProcess] = []

    @property
    def launched_processes(self) -> tuple[ManagedProcess, ...]:
        return tuple(self._launched_processes)

    @property
    def active_processes(self) -> tuple[ManagedProcess, ...]:
        return tuple(
            process
            for process in self._launched_processes
            if process.poll() is None
        )

    @staticmethod
    def _coerce_text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def run(
        self,
        command: Sequence[str | Path],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        options = dict(kwargs)
        timeout = options.pop("timeout", None)
        if timeout is not None and not isinstance(timeout, int | float):
            raise TypeError("timeout must be numeric or None")
        effective_timeout = self.default_timeout if timeout is None else int(timeout)
        options["timeout"] = effective_timeout
        if options.get("text") or options.get("universal_newlines"):
            options.setdefault("encoding", "utf-8")
            options.setdefault("errors", "replace")
        try:
            return cast(
                subprocess.CompletedProcess[str],
                subprocess.run(command, **cast(Any, options)),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = self._coerce_text(exc.stdout or exc.output)
            timeout_message = "Command timed out after {} seconds: {}".format(
                effective_timeout,
                " ".join(str(part) for part in command),
            )
            stderr = self._coerce_text(exc.stderr)
            if stderr:
                timeout_message = "{}\n{}".format(timeout_message, stderr)
            return subprocess.CompletedProcess(
                command,
                124,
                stdout=stdout,
                stderr=timeout_message,
            )

    def launch(
        self,
        command: Sequence[CommandPart],
        *,
        mode: str = "automation",
        preserve: bool | None = None,
        startup_timeout: float = 0.5,
        **kwargs: Any,
    ) -> ManagedProcess:
        if mode not in {"automation", "interactive"}:
            raise ValueError("Unsupported process launch mode: {}".format(mode))
        effective_startup_timeout = float(startup_timeout)
        if effective_startup_timeout < 0:
            raise ValueError("startup_timeout must be non-negative")

        preserve_process = mode == "interactive" if preserve is None else preserve
        process = subprocess.Popen(command, **kwargs)
        raw_cwd = kwargs.get("cwd")
        cwd = None if raw_cwd is None else Path(raw_cwd)
        handle = ManagedProcess(
            process=process,
            command=tuple(str(part) for part in command),
            cwd=cwd,
            started_at=datetime.now(UTC),
            mode=mode,
            preserve=bool(preserve_process),
            termination_grace_period=self.process_grace_period,
        )
        self._launched_processes.append(handle)

        deadline = time.monotonic() + effective_startup_timeout
        while True:
            return_code = handle.poll()
            if return_code is not None:
                handle.diagnostics.append(
                    "startup exit code {}".format(return_code)
                )
                raise RuntimeError(
                    "Process exited during startup with code {}: {}".format(
                        return_code,
                        " ".join(handle.command),
                    )
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.05, remaining))

        return handle

    def cleanup(self, *, include_preserved: bool = False) -> None:
        for process in self.active_processes:
            if process.preserve and not include_preserved:
                continue
            process.close(force=include_preserved)

    def __enter__(self) -> "CommandRunner":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.cleanup()


@dataclass
class PluginServiceDenied(ValueError):
    service: str
    reason: str = "undeclared_service"
    path: str | None = None

    @property
    def event(self) -> dict[str, str]:
        event = {
            "event": "plugin_service_denied",
            "service": self.service,
            "reason": self.reason,
        }
        if self.path is not None:
            event["path"] = self.path
        return event

    def __str__(self) -> str:
        return "Plugin service is not available: {}".format(self.service)


@dataclass(frozen=True)
class PluginServiceFacade:
    services: "PluginServices"
    domain: str

    def call(self, name: str, *args: object, **kwargs: object) -> object:
        return self.services.call(name, *args, **kwargs)


@dataclass(frozen=True)
class VivadoService(PluginServiceFacade):
    pass


@dataclass(frozen=True)
class WaveformService(PluginServiceFacade):
    pass


@dataclass(frozen=True)
class ArtifactService(PluginServiceFacade):
    pass


@dataclass(frozen=True)
class PluginServices:
    operations: Mapping[str, PluginOperation]
    _denials: tuple[dict[str, str], ...] = field(default_factory=tuple)

    @property
    def vivado(self) -> VivadoService:
        return VivadoService(self, "vivado")

    @property
    def waveform(self) -> WaveformService:
        return WaveformService(self, "waveform")

    @property
    def artifacts(self) -> ArtifactService:
        return ArtifactService(self, "artifacts")

    @property
    def denials(self) -> tuple[dict[str, str], ...]:
        return self._denials

    @staticmethod
    def _looks_like_output_path(
        name: str,
        value: object,
    ) -> TypeGuard[str | os.PathLike[str]]:
        if not _is_path_value(value):
            return False
        return name == "output_dir" or name in {"project_dir", "artifact_path"}

    @staticmethod
    def _positional_output_path_indices(name: str) -> tuple[int, ...]:
        if name in {"launch_vivado_gui", "run_vivado_batch"}:
            return (2,)
        if name.startswith(("analyze_", "check_", "open_", "write_")):
            return (0,)
        return ()

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _record_denial(self, denial: PluginServiceDenied) -> None:
        object.__setattr__(self, "_denials", (*self._denials, denial.event))

    def _validate_output_paths(
        self,
        service_name: str,
        args: tuple[object, ...],
        kwargs: Mapping[str, object],
    ) -> None:
        output_root = _PLUGIN_OUTPUT_ROOT.get()
        if output_root is None:
            return
        candidates: list[Path] = []
        for key, value in kwargs.items():
            if self._looks_like_output_path(str(key), value) and _is_path_value(value):
                candidates.append(Path(value))
        for index in self._positional_output_path_indices(service_name):
            if len(args) > index:
                value = args[index]
                if _is_path_value(value):
                    candidates.append(Path(value))
        for candidate in candidates:
            if not self._is_relative_to(candidate, output_root):
                denied = PluginServiceDenied(
                    service_name,
                    reason="output_dir_outside_allowed_root",
                    path=str(candidate),
                )
                self._record_denial(denied)
                raise denied

    def require(self, name: str) -> PluginOperation:
        try:
            return self.operations[name]
        except KeyError as exc:
            denied = PluginServiceDenied(name)
            self._record_denial(denied)
            raise denied from exc

    def call(self, name: str, *args: object, **kwargs: object) -> object:
        operation = self.require(name)
        self._validate_output_paths(name, args, kwargs)
        return operation(*args, **kwargs)

    def restrict(self, names: tuple[str, ...]) -> "PluginServices":
        allowed = {}
        for name in names:
            allowed[name] = self.require(name)
        return PluginServices(
            operations=allowed,
            _denials=self._denials,
        )


@runtime_checkable
class TargetPlugin(Protocol):
    plugin_id: str
    target_name: str
    supported_flows: tuple[str, ...]
    services: PluginServices

    def execute(self, flow: str, request: Mapping[str, object]) -> object:
        ...


class TargetHandler:
    def __init__(
        self,
        target_name: str,
        flows: Mapping[str, FlowHandler],
        extension_methods: Iterable[str] = (),
        plugin: object | None = None,
    ) -> None:
        self.target_name = target_name
        self.flows = dict(flows)
        self.extension_methods = tuple(extension_methods)
        self.plugin = plugin

    def run(self, flow: str, **kwargs: object) -> object:
        handler = self.flows.get(flow)
        if handler is None:
            raise ValueError(
                "Target {} does not support flow: {}".format(self.target_name, flow)
            )
        raw_output_dir = kwargs.get("output_dir", "outputs")
        if not _is_path_value(raw_output_dir):
            raise TypeError("output_dir must be path-like")
        output_dir = Path(raw_output_dir).resolve()
        token = _PLUGIN_OUTPUT_ROOT.set(output_dir)
        try:
            return handler(**kwargs)
        finally:
            _PLUGIN_OUTPUT_ROOT.reset(token)
