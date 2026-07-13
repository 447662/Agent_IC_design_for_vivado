from __future__ import annotations

import importlib
import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
SOURCE_LEGACY_AGENT_DIR = ROOT / ".trae" / "agent"
PACKAGE_LEGACY_AGENT_DIR = Path(__file__).resolve().parent / "_legacy_agent"
AGENT_DIR = (
    PACKAGE_LEGACY_AGENT_DIR
    if PACKAGE_LEGACY_AGENT_DIR.exists()
    else SOURCE_LEGACY_AGENT_DIR
)


@contextmanager
def _temporary_legacy_import_path() -> Iterator[None]:
    original_path = list(sys.path)
    legacy_path = str(AGENT_DIR)
    if legacy_path not in original_path:
        sys.path[:] = [legacy_path, *original_path]
    try:
        yield
    finally:
        sys.path[:] = original_path


def load_legacy_module(module_name: str, filename: str | None = None) -> ModuleType:
    if PACKAGE_LEGACY_AGENT_DIR.exists():
        legacy_name = "digital_ic_agent._legacy_agent.{}".format(module_name)
        with _temporary_legacy_import_path():
            return importlib.import_module(legacy_name)

    legacy_name = module_name if filename is None else "digital_ic_agent._legacy_{}".format(module_name)
    if legacy_name in sys.modules:
        return sys.modules[legacy_name]

    path = AGENT_DIR / (filename or "{}.py".format(module_name))
    spec = importlib.util.spec_from_file_location(
        legacy_name,
        path,
        submodule_search_locations=[str(AGENT_DIR)] if module_name == "agent" else None,
    )
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load legacy module: {}".format(path))

    module = importlib.util.module_from_spec(spec)
    sys.modules[legacy_name] = module
    try:
        with _temporary_legacy_import_path():
            spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(legacy_name, None)
        raise
    return module
