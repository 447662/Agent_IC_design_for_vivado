import importlib
import pkgutil
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

from agent_runtime import PluginServices, TargetHandler


TargetHandlerFactory = Callable[
    [PluginServices, Mapping[str, Any]],
    TargetHandler,
]


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
    pending_plugins = []
    for module_name in module_names:
        module = importlib.import_module(module_name)
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


def discover_target_handler_plugins(
    registry: TargetHandlerRegistry,
    package_name: str = "target_handlers",
    search_path: str | Path | None = None,
) -> TargetHandlerRegistry:
    inserted_path: str | None = None
    if search_path is not None:
        inserted_path = str(Path(search_path))
        if inserted_path not in sys.path:
            sys.path.insert(0, inserted_path)
    try:
        importlib.invalidate_caches()
        package = importlib.import_module(package_name)
        package_paths = getattr(package, "__path__", None)
        if package_paths is None:
            raise ValueError(
                "Target handler plugin package has no __path__: {}".format(
                    package_name
                )
            )
        module_names = sorted(
            item.name
            for item in pkgutil.iter_modules(
                package_paths,
                package.__name__ + ".",
            )
        )
        plugin_modules = []
        for module_name in module_names:
            module = importlib.import_module(module_name)
            handler_id = getattr(module, "HANDLER_ID", None)
            factory = getattr(module, "create_handler", None)
            if handler_id is None and factory is None:
                continue
            plugin_modules.append(module_name)
        return load_target_handler_plugins(
            registry,
            tuple(plugin_modules),
        )
    finally:
        if inserted_path is not None and sys.path[:1] == [inserted_path]:
            sys.path.pop(0)


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
