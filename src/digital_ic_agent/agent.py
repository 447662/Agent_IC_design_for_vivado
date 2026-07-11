from typing import Any

from digital_ic_agent._legacy import AGENT_DIR, load_legacy_module


if str(AGENT_DIR) not in __import__("sys").path:
    __import__("sys").path.append(str(AGENT_DIR))

_legacy_agent = load_legacy_module("agent", "agent.py")

DigitalICAgent = _legacy_agent.DigitalICAgent
CommandRunner = _legacy_agent.CommandRunner
TargetHandler = _legacy_agent.TargetHandler
create_agent = _legacy_agent.create_agent


def main(argv: Any = None) -> Any:
    return _legacy_agent.main(argv)
