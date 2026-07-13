from __future__ import annotations

import builtins
import importlib.util
import json
import os
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn, TextIO, TypedDict, cast


class GuardPayload(TypedDict):
    module: str
    module_path: str
    agent_runtime_path: str
    output_root: str
    handler_id: str
    flow: str
    target: dict[str, object]
    kwargs: dict[str, str]


@dataclass(frozen=True)
class GuardContext:
    output_root: Path
    allowed_reads: frozenset[Path]
    stdlib_roots: tuple[Path, ...]


def read_payload(stream: TextIO = sys.stdin) -> GuardPayload:
    raw: object = json.loads(stream.read())
    if not isinstance(raw, dict):
        raise ValueError("External plugin payload must be an object")

    for field in (
        "module",
        "module_path",
        "agent_runtime_path",
        "output_root",
        "handler_id",
        "flow",
    ):
        if not isinstance(raw.get(field), str) or not raw[field]:
            raise ValueError("External plugin payload field must be a non-empty string: {}".format(field))
    if not isinstance(raw.get("target"), dict):
        raise ValueError("External plugin payload target must be an object")
    if not isinstance(raw.get("kwargs"), dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in raw["kwargs"].items()
    ):
        raise ValueError("External plugin payload kwargs must contain string values")
    return cast(GuardPayload, raw)


def _stdlib_roots() -> tuple[Path, ...]:
    roots = {
        Path(path).resolve()
        for name in ("stdlib", "platstdlib")
        if (path := sysconfig.get_path(name))
    }
    return tuple(sorted(roots, key=str))


def build_context(payload: GuardPayload) -> GuardContext:
    return GuardContext(
        output_root=Path(payload["output_root"]).resolve(),
        allowed_reads=frozenset(
            {
                Path(payload["agent_runtime_path"]).resolve(),
                Path(payload["module_path"]).resolve(),
            }
        ),
        stdlib_roots=_stdlib_roots(),
    )


def _emit_payload(payload: dict[str, object]) -> None:
    print(json.dumps(payload))


def _emit_denial(reason: str, path: object) -> NoReturn:
    _emit_payload(
        {
            "status": "denied",
            "event": {
                "event": "plugin_service_denied",
                "service": "external_plugin",
                "reason": reason,
                "path": str(path),
            },
        }
    )
    raise SystemExit(13)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def guard_path(context: GuardContext, path: str | os.PathLike[str], mode: str) -> None:
    resolved = Path(path).resolve()
    if any(flag in mode for flag in ("w", "a", "x", "+")):
        if not _is_under(resolved, context.output_root):
            _emit_denial("output_dir_outside_allowed_root", resolved)
        return
    if (
        resolved not in context.allowed_reads
        and not _is_under(resolved, context.output_root)
        and not any(_is_under(resolved, root) for root in context.stdlib_roots)
    ):
        _emit_denial("read_outside_allowed_root", resolved)


def install_command_guards() -> None:
    def deny_command(*args: object, **kwargs: object) -> NoReturn:
        command = args[0] if args else kwargs.get("args", "")
        _emit_denial("unauthorized_command", command)

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        setattr(subprocess, name, deny_command)
    for name in (
        "system",
        "popen",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
    ):
        setattr(os, name, deny_command)


def install_file_guards(context: GuardContext) -> None:
    real_open = builtins.open
    real_path_open = Path.open

    def guarded_open(
        file: int | str | bytes | os.PathLike[str],
        mode: str = "r",
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not isinstance(file, int):
            guard_path(context, os.fsdecode(file), mode)
        return real_open(file, mode, *args, **kwargs)

    def guarded_path_open(
        path: Path,
        mode: str = "r",
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        guard_path(context, path, mode)
        return real_path_open(path, mode, *args, **kwargs)

    setattr(builtins, "open", guarded_open)
    setattr(Path, "open", guarded_path_open)


def load_module(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load external plugin module: {}".format(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def run(payload: GuardPayload) -> str:
    context = build_context(payload)
    install_command_guards()
    install_file_guards(context)

    load_module("agent_runtime", Path(payload["agent_runtime_path"]))
    module = load_module(payload["module"], Path(payload["module_path"]))
    if getattr(module, "HANDLER_ID", None) != payload["handler_id"]:
        raise ValueError("External plugin handler mismatch")

    from agent_runtime import PluginServices

    handler = module.create_handler(PluginServices(operations={}), payload["target"])
    return str(handler.run(payload["flow"], **payload["kwargs"]))


def main() -> int:
    result = run(read_payload())
    _emit_payload({"status": "ok", "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
