from typing import Any

from agent_cli import parse_args
from agent_cli_dispatch import dispatch_cli_command


def run_cli(argv: Any, agent_factory: Any) -> Any:
    args = parse_args(argv)
    agent = agent_factory()
    if agent is None:
        return 1
    return dispatch_cli_command(args, agent)
