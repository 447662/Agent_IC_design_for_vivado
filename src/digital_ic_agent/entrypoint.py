from digital_ic_agent._legacy import load_legacy_module


_legacy_entrypoint = load_legacy_module("agent_entrypoint")

run_cli = _legacy_entrypoint.run_cli
