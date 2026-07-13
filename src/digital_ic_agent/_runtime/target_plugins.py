import importlib
import json
import os
import pkgutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import TypedDict, cast

from digital_ic_agent._runtime.agent_errors import ToolExecutionError
from digital_ic_agent._runtime.agent_runtime import PluginServiceDenied, PluginServices, TargetHandler


TargetDefinition = Mapping[str, object]
TargetHandlerFactory = Callable[
    [PluginServices, TargetDefinition],
    TargetHandler,
]
EXTERNAL_PLUGIN_TIMEOUT_SECONDS = 30.0
EXTERNAL_PLUGIN_TRUST = "trusted-local"
EXTERNAL_PLUGIN_ISOLATION = "python-guarded-subprocess"
EXTERNAL_PLUGIN_SANDBOX = "none"
EXTERNAL_PLUGIN_SECURITY_BOUNDARY = "defense-in-depth-only"
EXTERNAL_ENVIRONMENT_KEYS = (
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
)


class ExternalFlowPayload(TypedDict):
    module: str
    module_path: str
    agent_runtime_path: str
    output_root: str
    handler_id: str
    flow: str
    target: dict[str, object]
    kwargs: dict[str, str]


def _declared_flows(target: TargetDefinition) -> tuple[str, ...]:
    raw_flows = target.get("flows", ())
    if not isinstance(raw_flows, list | tuple):
        raise ValueError("Target flows must be a list or tuple")
    return tuple(str(flow) for flow in raw_flows)


def _external_plugin_factory(
    module_name: str,
    handler_id: str,
    search_path: Path,
) -> TargetHandlerFactory:
    def create_external_handler(
        services: PluginServices,
        target: TargetDefinition,
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
            for flow in _declared_flows(target)
        }
        return TargetHandler(
            target_name,
            flows,
            plugin={
                "plugin_id": handler_id,
                "module": module_name,
                "trust": EXTERNAL_PLUGIN_TRUST,
                "isolation": EXTERNAL_PLUGIN_ISOLATION,
                "sandbox": EXTERNAL_PLUGIN_SANDBOX,
                "security_boundary": EXTERNAL_PLUGIN_SECURITY_BOUNDARY,
            },
        )

    return create_external_handler


def _external_flow_runner(
    module_name: str,
    handler_id: str,
    search_path: Path,
    flow: str,
    target: TargetDefinition,
) -> Callable[..., object]:
    def run_external_flow(**kwargs: object) -> object:
        package_name = module_name.split(".", 1)[0]
        _, module_path = _resolve_external_module_path(
            search_path,
            package_name,
            module_name,
        )
        agent_runtime_path = Path(__file__).resolve().with_name("agent_runtime.py")
        raw_output_root = kwargs.get("output_dir", "outputs")
        if not isinstance(raw_output_root, str | Path):
            raise TypeError("output_dir must be path-like")
        output_root = Path(raw_output_root).resolve()
        payload: ExternalFlowPayload = {
            "module": module_name,
            "module_path": str(module_path),
            "agent_runtime_path": str(agent_runtime_path),
            "output_root": str(output_root),
            "handler_id": handler_id,
            "flow": flow,
            "target": dict(target),
            "kwargs": {key: str(value) for key, value in kwargs.items()},
        }
        guard_runner_path = Path(__file__).resolve().with_name("plugin_guard_runner.py")
        try:
            result = subprocess.run(
                [sys.executable, "-B", str(guard_runner_path)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=EXTERNAL_PLUGIN_TIMEOUT_SECONDS,
                env=_external_plugin_environment(),
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolExecutionError(
                "External target plugin timed out after {} seconds".format(
                    EXTERNAL_PLUGIN_TIMEOUT_SECONDS
                ),
                stage="external_plugin",
                details={
                    "flow": flow,
                    "handler_id": handler_id,
                    "module": module_name,
                    "reason": "timeout",
                    "timeout_seconds": EXTERNAL_PLUGIN_TIMEOUT_SECONDS,
                },
            ) from exc
        if result.returncode != 0:
            try:
                raw_denial: object = json.loads(result.stdout.strip().splitlines()[-1])
                denial_payload = (
                    {str(key): value for key, value in raw_denial.items()}
                    if isinstance(raw_denial, dict)
                    else {}
                )
            except (IndexError, json.JSONDecodeError):
                denial_payload = {}
            if denial_payload.get("status") == "denied":
                event = denial_payload.get("event", {})
                if not isinstance(event, Mapping):
                    event = {}
                denied_path = event.get("path")
                raise PluginServiceDenied(
                    str(event.get("service", "external_plugin")),
                    reason=str(event.get("reason", "external_plugin_denied")),
                    path=None if denied_path is None else str(denied_path),
                )
            raise ToolExecutionError(
                "External target plugin subprocess failed: {}".format(
                    result.stderr.strip() or "no stderr"
                ),
                stage="external_plugin",
                details={
                    "flow": flow,
                    "handler_id": handler_id,
                    "module": module_name,
                    "reason": "nonzero_exit",
                    "returncode": result.returncode,
                },
            )
        try:
            response: object = json.loads(result.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise ToolExecutionError(
                "External target plugin returned non-JSON output",
                stage="external_plugin",
                details={
                    "flow": flow,
                    "handler_id": handler_id,
                    "module": module_name,
                    "reason": "invalid_response",
                },
            ) from exc
        if not isinstance(response, dict) or "result" not in response:
            raise ToolExecutionError(
                "External target plugin returned an invalid response",
                stage="external_plugin",
                details={
                    "flow": flow,
                    "handler_id": handler_id,
                    "module": module_name,
                    "reason": "invalid_response",
                },
            )
        return response["result"]

    return run_external_flow


def _is_target_handler_compatible(handler: object) -> bool:
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
    modules: tuple[tuple[str, ModuleType], ...],
) -> TargetHandlerRegistry:
    pending_plugins = []
    for module_name, module in modules:
        handler_id = getattr(module, "HANDLER_ID", None)
        factory = getattr(module, "create_handler", None)
        if not handler_id or not callable(factory):
            raise ValueError(
                "Invalid target handler plugin module: {}".format(module_name)
            )
        pending_plugins.append(
            (str(handler_id), cast(TargetHandlerFactory, factory), module_name)
        )

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


def _validate_external_manifest_modules(
    package_name: str,
    module_names: tuple[str, ...],
) -> None:
    package_prefix = package_name + "."
    for module_name in module_names:
        if not module_name.startswith(package_prefix):
            raise ValueError(
                "External target plugin module must belong to package {}: {}".format(
                    package_name,
                    module_name,
                )
            )
        if not all(part.isidentifier() for part in module_name.split(".")):
            raise ValueError(
                "External target plugin module must be a valid qualified name: {}".format(
                    module_name
                )
            )


def _resolve_external_module_path(
    search_path: str | Path,
    package_name: str,
    module_name: str,
) -> tuple[Path, Path]:
    try:
        root = Path(search_path).resolve(strict=True)
        package_dir = (root / package_name).resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            "Target handler plugin package not found: {}".format(package_name)
        ) from exc
    try:
        module_path = (
            root / Path(*module_name.split("."))
        ).with_suffix(".py").resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            "External target plugin module path does not exist: {}".format(module_name)
        ) from exc
    try:
        package_dir.relative_to(root)
        module_path.relative_to(package_dir)
    except ValueError as exc:
        raise ValueError(
            "External target plugin module resolves outside external plugin root: {}".format(
                module_name
            )
        ) from exc
    if not package_dir.is_dir():
        raise ValueError(
            "External target plugin package is not a directory: {}".format(package_name)
        )
    if not module_path.is_file():
        raise ValueError(
            "External target plugin module must be a regular file: {}".format(module_name)
        )
    return root, module_path


def _external_plugin_environment() -> dict[str, str]:
    environment = {
        key: os.environ[key]
        for key in EXTERNAL_ENVIRONMENT_KEYS
        if key in os.environ
    }
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    return environment


def discover_target_handler_plugins(
    registry: TargetHandlerRegistry,
    package_name: str = "target_handlers",
    search_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    allowed_modules: tuple[str, ...] | None = None,
) -> TargetHandlerRegistry:
    if search_path is not None and manifest_path is None:
        raise ValueError("External target plugin search_path requires a manifest")
    if search_path is not None and allowed_modules is None:
        raise ValueError(
            "External target plugin search_path requires an explicit allowlist"
        )

    manifest_modules: tuple[str, ...] | None = None
    manifest_handlers: dict[str, str] = {}
    if manifest_path is not None:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("Target handler plugin manifest must be an object")
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

        if search_path is not None and manifest.get("trust") != EXTERNAL_PLUGIN_TRUST:
            raise ValueError(
                "External target plugin manifest trust must be trusted-local; "
                "Python subprocess guards are defense-in-depth only and do not "
                "sandbox untrusted code"
            )

    if search_path is not None and manifest_modules is not None:
        _validate_external_manifest_modules(package_name, manifest_modules)

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
        resolved_search_path = Path(search_path).resolve(strict=True)
        for module_name in manifest_modules or ():
            _resolve_external_module_path(
                resolved_search_path,
                package_name,
                module_name,
            )
        return _load_manifest_target_handler_plugins(
            registry,
            manifest_handlers,
            resolved_search_path,
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
        module = importlib.import_module(module_name)
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
    targets: Mapping[str, TargetDefinition],
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
        declared_flows = set(_declared_flows(target))
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
