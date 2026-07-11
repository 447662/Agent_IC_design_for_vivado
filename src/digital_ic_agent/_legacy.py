from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / ".trae" / "agent"


def load_legacy_module(module_name: str, filename: str | None = None) -> ModuleType:
    legacy_name = module_name if filename is None else "digital_ic_agent._legacy_{}".format(
        module_name
    )
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
    spec.loader.exec_module(module)
    return module
