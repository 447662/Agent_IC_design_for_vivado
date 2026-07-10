import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, runtime_checkable


@dataclass
class ManagedProcess:
    process: Any
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
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:
        self.close()


class CommandRunner:
    def __init__(
        self,
        default_timeout: Any = 120,
        process_grace_period: Any = 5.0,
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
    def _coerce_text(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def run(self, command: Any, timeout: Any=None, **kwargs: Any) -> Any:
        effective_timeout = self.default_timeout if timeout is None else int(timeout)
        kwargs["timeout"] = effective_timeout
        if kwargs.get("text") or kwargs.get("universal_newlines"):
            kwargs.setdefault("encoding", "utf-8")
            kwargs.setdefault("errors", "replace")
        try:
            return subprocess.run(command, **kwargs)
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
        command: Any,
        *,
        mode: str = "automation",
        preserve: bool | None = None,
        startup_timeout: Any = 0.5,
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
            started_at=datetime.now(timezone.utc),
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
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:
        self.cleanup()


@dataclass(frozen=True)
class PluginServices:
    command_runner: CommandRunner
    project_root: Path
    operations: Mapping[str, Callable[..., Any]]

    def require(self, name: str) -> Callable[..., Any]:
        try:
            return self.operations[name]
        except KeyError as exc:
            raise ValueError(
                "Plugin service is not available: {}".format(name)
            ) from exc

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        return self.require(name)(*args, **kwargs)

    def restrict(self, names: tuple[str, ...]) -> "PluginServices":
        allowed = {}
        for name in names:
            allowed[name] = self.require(name)
        return PluginServices(
            command_runner=self.command_runner,
            project_root=self.project_root,
            operations=allowed,
        )


@runtime_checkable
class TargetPlugin(Protocol):
    plugin_id: str
    target_name: str
    supported_flows: tuple[str, ...]
    services: PluginServices

    def execute(self, flow: str, request: Mapping[str, Any]) -> Any:
        ...


class TargetHandler:
    def __init__(
        self,
        target_name: Any,
        flows: Any,
        extension_methods: Any=(),
        plugin: Any=None,
    ) -> None:
        self.target_name = target_name
        self.flows = dict(flows)
        self.extension_methods = tuple(extension_methods)
        self.plugin = plugin

    def run(self, flow: Any, **kwargs: Any) -> Any:
        handler = self.flows.get(flow)
        if handler is None:
            raise ValueError(
                "Target {} does not support flow: {}".format(self.target_name, flow)
            )
        return handler(**kwargs)
