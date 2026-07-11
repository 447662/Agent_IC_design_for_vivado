from digital_ic_agent._legacy import load_legacy_module


_legacy_cli = load_legacy_module("agent_cli")

parse_args = _legacy_cli.parse_args
parse_seed_list = _legacy_cli.parse_seed_list
build_requirement = _legacy_cli.build_requirement
