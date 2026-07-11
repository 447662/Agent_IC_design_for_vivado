import importlib
import importlib.util
import json
import pkgutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

from agent_runtime import PluginServiceDenied, PluginServices, TargetHandler


TargetHandlerFactory = Callable[
    [PluginServices, Mapping[str, Any]],
    TargetHandler,
]


def _external_plugin_factory(
    module_name: str,
    handler_id: str,
    search_path: Path,
) -> TargetHandlerFactory:
    def create_external_handler(
        services: PluginServices,
        target: Mapping[str, Any],
    ) -> TargetHandler:
        target_name = str(target["name"])
        target_payload = {
            str(key): value
            for key, value in target.items()
        }
        flows = {
            str(flow): _external_flow_runner(
                module_name,
                handler_id,
                search_path,
                str(flow),
                target_payload,
            )
            for flow in target.get("flows", ())
        }
        return TargetHandler(
            target_name,
            flows,
            plugin={
                "plugin_id": handler_id,
                "module": module_name,
                "isolation": "subprocess",
            },
        )

    return create_external_handler


def _external_flow_runner(
    module_name: str,
    handler_id: str,
    search_path: Path,
    flow: str,
    target: Mapping[str, Any],
) -> Callable[..., Any]:
    def run_external_flow(**kwargs: Any) -> Any:
        module_path = (search_path / Path(*module_name.split("."))).with_suffix(".py")
        agent_runtime_path = Path(__file__).resolve().with_name("agent_runtime.py")
        output_root = Path(kwargs.get("output_dir", "outputs")).resolve()
        payload: dict[str, Any] = {
            "module": module_name,
            "module_path": str(module_path),
            "agent_runtime_path": str(agent_runtime_path),
            "output_root": str(output_root),
            "handler_id": handler_id,
            "flow": flow,
            "target": target,
            "kwargs": {key: str(value) for key, value in kwargs.items()},
        }
        script = (
            "import builtins, importlib.util, json, os, pathlib, subprocess, sys\n"
            "payload=json.loads(sys.stdin.read())\n"
            "allowed_root=pathlib.Path(payload['output_root']).resolve()\n"
            "allowed_reads={pathlib.Path(payload['agent_runtime_path']).resolve(), pathlib.Path(payload['module_path']).resolve()}\n"
            "stdlib_roots={pathlib.Path(path).resolve() for path in sys.path if 'site-packages' not in path and 'dist-packages' not in path and path}\n"
            "def emit_denial(reason, path):\n"
            "    print(json.dumps({'status':'denied','event':{'event':'plugin_service_denied','service':'external_plugin','reason':reason,'path':str(path)}}))\n"
            "    raise SystemExit(13)\n"
            "def deny_command(*args, **kwargs):\n"
            "    command=args[0] if args else kwargs.get('args', '')\n"
            "    emit_denial('unauthorized_command', command)\n"
            "subprocess.run=deny_command\n"
            "subprocess.Popen=deny_command\n"
            "subprocess.call=deny_command\n"
            "subprocess.check_call=deny_command\n"
            "subprocess.check_output=deny_command\n"
            "os.system=deny_command\n"
            "os.popen=deny_command\n"
            "os.spawnl=deny_command\n"
            "os.spawnle=deny_command\n"
            "os.spawnlp=deny_command\n"
            "os.spawnlpe=deny_command\n"
            "os.spawnv=deny_command\n"
            "os.spawnve=deny_command\n"
            "os.spawnvp=deny_command\n"
            "os.spawnvpe=deny_command\n"
            "def is_under(path, root):\n"
            "    try:\n"
            "        pathlib.Path(path).resolve().relative_to(root)\n"
            "        return True\n"
            "    except ValueError:\n"
            "        return False\n"
            "def guard_path(path, mode):\n"
            "    resolved=pathlib.Path(path).resolve()\n"
            "    if any(flag in mode for flag in ('w','a','x','+')):\n"
            "        if not is_under(resolved, allowed_root):\n"
            "            emit_denial('output_dir_outside_allowed_root', resolved)\n"
            "    elif resolved not in allowed_reads and not is_under(resolved, allowed_root) and not any(is_under(resolved, root) for root in stdlib_roots):\n"
            "        emit_denial('read_outside_allowed_root', resolved)\n"
            "real_open=builtins.open\n"
            "def guarded_open(file, mode='r', *args, **kwargs):\n"
            "    if not isinstance(file, int):\n"
            "        guard_path(file, mode)\n"
            "    return real_open(file, mode, *args, **kwargs)\n"
            "builtins.open=guarded_open\n"
            "real_path_open=pathlib.Path.open\n"
            "def guarded_path_open(self, mode='r', *args, **kwargs):\n"
            "    guard_path(self, mode)\n"
            "    return real_path_open(self, mode, *args, **kwargs)\n"
            "pathlib.Path.open=guarded_path_open\n"
            "runtime_spec=importlib.util.spec_from_file_location('agent_runtime', payload['agent_runtime_path'])\n"
            "if runtime_spec is None or runtime_spec.loader is None:\n"
            "    raise SystemExit('invalid agent runtime spec')\n"
            "runtime=importlib.util.module_from_spec(runtime_spec)\n"
            "sys.modules['agent_runtime']=runtime\n"
            "runtime_spec.loader.exec_module(runtime)\n"
            "spec=importlib.util.spec_from_file_location(payload['module'], payload['module_path'])\n"
            "if spec is None or spec.loader is None:\n"
            "    raise SystemExit('invalid external plugin spec')\n"
            "module=importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "if getattr(module, 'HANDLER_ID', None) != payload['handler_id']:\n"
            "    raise SystemExit('handler mismatch')\n"
            "from agent_runtime import PluginServices\n"
            "handler=module.create_handler(PluginServices(operations={}), payload['target'])\n"
            "result=handler.run(payload['flow'], **payload['kwargs'])\n"
            "print(json.dumps({'status':'ok','result':str(result)}))\n"
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            try:
                denial_payload: dict[str, Any] = json.loads(
                    result.stdout.strip().splitlines()[-1]
                )
            except (IndexError, json.JSONDecodeError):
                denial_payload = {}
            if denial_payload.get("status") == "denied":
                event = denial_payload.get("event", {})
                if not isinstance(event, Mapping):
                    event = {}
                raise PluginServiceDenied(
                    str(event.get("service", "external_plugin")),
                    reason=str(event.get("reason", "external_plugin_denied")),
                    path=event.get("path"),
                )
            raise RuntimeError(
                "External target plugin subprocess failed: {}".format(
                    result.stderr.strip()
                )
            )
        return json.loads(result.stdout.strip().splitlines()[-1])["result"]

    return run_external_flow


def _is_target_handler_compatible(handler: Any) -> bool:
    return (
        isinstance(getattr(handler, "target_name", None), str)
        and isinstance(getattr(handler, "flows", None), dict)
        and callable(getattr(handler, "run", None))
    )


class TargetHandlerRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, TargetHandlerFactory] = {}

    def register(
        self,
        handler_id: str,
        factory: TargetHandlerFactory,
        source: str = "",
    ) -> None:
        normalized_id = str(handler_id).strip()
        if not normalized_id:
            raise ValueError("Target handler id must not be empty")
        if normalized_id in self._factories:
            raise ValueError(
                "Duplicate target handler: {}{}".format(
                    normalized_id,
                    " from {}".format(source) if source else "",
                )
            )
        if not callable(factory):
            raise ValueError(
                "Target handler factory is not callable: {}".format(normalized_id)
            )
        self._factories[normalized_id] = factory

    def get(self, handler_id: str) -> TargetHandlerFactory:
        normalized_id = str(handler_id).strip()
        try:
            return self._factories[normalized_id]
        except KeyError as exc:
            raise ValueError(
                "Unknown target handler: {}".format(normalized_id)
            ) from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


def load_target_handler_plugins(
    registry: TargetHandlerRegistry,
    module_names: tuple[str, ...],
) -> TargetHandlerRegistry:
    return _load_target_handler_plugin_modules(
        registry,
        tuple((module_name, importlib.import_module(module_name)) for module_name in module_names),
    )


def _load_target_handler_plugin_modules(
    registry: TargetHandlerRegistry,
    modules: tuple[tuple[str, Any], ...],
) -> TargetHandlerRegistry:
    pending_plugins = []
    for module_name, module in modules:
        handler_id = getattr(module, "HANDLER_ID", None)
        factory = getattr(module, "create_handler", None)
        if not handler_id or not callable(factory):
            raise ValueError(
                "Invalid target handler plugin module: {}".format(module_name)
            )
        pending_plugins.append((str(handler_id), factory, module_name))

    staged_registry = TargetHandlerRegistry()
    staged_registry._factories = dict(registry._factories)
    for handler_id, factory, module_name in pending_plugins:
        staged_registry.register(handler_id, factory, source=module_name)
    registry._factories = staged_registry._factories
    return registry


def _load_manifest_target_handler_plugins(
    registry: TargetHandlerRegistry,
    manifest_handlers: Mapping[str, str],
    search_path: Path,
) -> TargetHandlerRegistry:
    staged_registry = TargetHandlerRegistry()
    staged_registry._factories = dict(registry._factories)
    for module_name, handler_id in manifest_handlers.items():
        staged_registry.register(
            handler_id,
            _external_plugin_factory(module_name, handler_id, search_path),
            source=module_name,
        )
    registry._factories = staged_registry._factories
    return registry


def discover_target_handler_plugins(
    registry: TargetHandlerRegistry,
    package_name: str = "target_handlers",
    search_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    allowed_modules: tuple[str, ...] | None = None,
) -> TargetHandlerRegistry:
    manifest_modules: tuple[str, ...] | None = None
    manifest_handlers: dict[str, str] = {}
    if manifest_path is not None:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        raw_plugins = manifest.get("plugins")
        if not isinstance(raw_plugins, list):
            raise ValueError("Target handler plugin manifest plugins must be a list")
        parsed_modules = []
        for index, raw_plugin in enumerate(raw_plugins):
            if not isinstance(raw_plugin, dict):
                raise ValueError(
                    "Target handler plugin manifest entry {} must be an object".format(
                        index
                    )
                )
            module_name = str(raw_plugin.get("module", "")).strip()
            handler_id = str(raw_plugin.get("handler_id", "")).strip()
            if not module_name or not handler_id:
                raise ValueError(
                    "Target handler plugin manifest entry {} is incomplete".format(
                        index
                    )
                )
            parsed_modules.append(module_name)
            manifest_handlers[module_name] = handler_id
        manifest_modules = tuple(parsed_modules)

    if allowed_modules is not None and manifest_modules is not None:
        allowed = set(allowed_modules)
        for module_name in manifest_modules:
            if module_name not in allowed:
                raise ValueError(
                    "Target handler plugin module not allowlisted: {}".format(
                        module_name
                    )
                )

    module_names: tuple[str, ...]
    package_paths: tuple[str, ...]
    if search_path is not None:
        resolved_search_path = Path(search_path)
        package_dir = Path(search_path) / package_name
        if not package_dir.is_dir():
            raise ValueError(
                "Target handler plugin package not found: {}".format(package_name)
            )
        if manifest_modules is not None:
            return _load_manifest_target_handler_plugins(
                registry,
                manifest_handlers,
                resolved_search_path,
            )
        else:
            package_paths = (str(package_dir),)
            module_names = tuple(
                sorted(
                    "{}.{}".format(package_name, item.name)
                    for item in pkgutil.iter_modules(package_paths)
                )
            )
    else:
        importlib.invalidate_caches()
        package = importlib.import_module(package_name)
        package_paths_value = getattr(package, "__path__", None)
        if package_paths_value is None:
            raise ValueError(
                "Target handler plugin package has no __path__: {}".format(
                    package_name
                )
            )
        package_paths = tuple(str(path) for path in package_paths_value)
        module_names = tuple(
            sorted(
                item.name
                for item in pkgutil.iter_modules(
                    package_paths,
                    package.__name__ + ".",
                )
            )
        )

    plugin_modules = []
    for module_name in module_names:
        if search_path is not None:
            module_path = (
                Path(search_path)
                / Path(*module_name.split("."))
            ).with_suffix(".py")
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ValueError(
                    "Invalid target handler plugin module: {}".format(module_name)
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            module = importlib.import_module(module_name)
            module_handler_id = getattr(module, "HANDLER_ID", None)
            module_factory = getattr(module, "create_handler", None)
            if module_handler_id is None and module_factory is None:
                continue
        module_handler_id = getattr(module, "HANDLER_ID", None)
        module_factory = getattr(module, "create_handler", None)
        if module_handler_id is None and module_factory is None:
            continue
        if module_name in manifest_handlers:
            actual_handler = str(getattr(module, "HANDLER_ID", "")).strip()
            expected_handler = manifest_handlers[module_name]
            if actual_handler != expected_handler:
                raise ValueError(
                    "Target handler plugin manifest handler mismatch: {}".format(
                        module_name
                    )
                )
        plugin_modules.append((module_name, module))
    return _load_target_handler_plugin_modules(
        registry,
        tuple(plugin_modules),
    )


def build_target_handlers(
    services: PluginServices,
    targets: Mapping[str, Mapping[str, Any]],
    registry: TargetHandlerRegistry,
) -> dict[str, TargetHandler]:
    handlers: dict[str, TargetHandler] = {}
    for target_name, target in targets.items():
        handler_id = str(target.get("handler", "")).strip()
        if not handler_id:
            raise ValueError(
                "Target {} missing handler declaration".format(target_name)
            )
        factory = registry.get(handler_id)
        handler = factory(services, target)
        if not _is_target_handler_compatible(handler):
            raise ValueError(
                "Target handler factory {} did not return TargetHandler".format(
                    handler_id
                )
            )
        declared_flows = set(str(flow) for flow in target.get("flows", ()))
        implemented_flows = set(handler.flows)
        if declared_flows != implemented_flows:
            missing = sorted(declared_flows - implemented_flows)
            undeclared = sorted(implemented_flows - declared_flows)
            raise ValueError(
                "Target {} flow mismatch: missing={}, undeclared={}".format(
                    target_name,
                    missing,
                    undeclared,
                )
            )
        handlers[target_name] = handler
    return handlers
