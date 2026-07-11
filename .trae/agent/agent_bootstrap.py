from pathlib import Path
from typing import Any
import importlib.util
import sys


LOCAL_MODULES = (
    "history_rotation",
    "agent_contracts",
    "intent_router",
    "mcp_client",
    "agent_runtime",
    "agent_provider",
    "agent_execution",
    "agent_config",
    "skill_runtime",
    "agent_skill_tool",
    "agent_skill_execution",
    "agent_capabilities",
    "agent_skill_listing",
    "agent_workflow",
    "agent_cli_parser",
    "agent_cli",
    "agent_cli_dispatch",
    "agent_design_spec",
    "capability_preflight",
    "agent_diagnostics",
    "agent_composition",
    "agent_entrypoint",
    "report_templates",
    "agent_reports",
    "agent_document_facades",
    "agent_waveform",
    "agent_sim_smoke",
    "coverage_gates",
    "artifact_manifest",
    "xcrg_coverage",
    "coverage_recommendations",
    "coverage_closure",
    "coverage_history",
    "environment_report",
    "failure_archive",
    "intent_router",
    "project_overview",
    "skill_runtime",
    "waveform_samples",
    "wave_visibility",
    "target_checks",
    "agent_runtime_facades",
    "target_plugins",
    "target_registry",
    "target_scaffolder",
    "agent_sync_fifo",
    "agent_round_robin_arbiter",
    "agent_async_fifo_render",
    "agent_async_fifo_reports",
    "agent_async_fifo_runtime",
    "target_service_host",
    "target_flows",
)

ADAPTER_MODULES = ("report", "vivado", "waveform")
HANDLER_MODULES = ("async_fifo", "round_robin_arbiter", "sync_fifo")
TARGET_EXAMPLE_MODULE = ("target_examples.async_fifo", "target_examples/async_fifo.py")


def load_module(
    module_name: str,
    agent_module_dir: Path,
    relative_path: str | None = None,
) -> Any:
    if module_name in sys.modules:
        return sys.modules[module_name]
    module_path = agent_module_dir / (relative_path or "{}.py".format(module_name))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load local agent module: {}".format(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_local_modules(agent_module_dir: Path) -> None:
    for module_name in LOCAL_MODULES:
        load_module(module_name, agent_module_dir)
    for adapter_module_name in ADAPTER_MODULES:
        load_module(
            "adapters.{}".format(adapter_module_name),
            agent_module_dir,
            "adapters/{}.py".format(adapter_module_name),
        )
    load_module(
        TARGET_EXAMPLE_MODULE[0],
        agent_module_dir,
        TARGET_EXAMPLE_MODULE[1],
    )
    for handler_module_name in HANDLER_MODULES:
        load_module(
            "target_handlers.{}".format(handler_module_name),
            agent_module_dir,
            "target_handlers/{}.py".format(handler_module_name),
        )
