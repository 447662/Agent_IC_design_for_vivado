from typing import Any

from agent_round_robin_arbiter import RoundRobinArbiterMixin
from agent_sync_fifo import SyncFifoMixin


class TargetServiceHost(
    SyncFifoMixin,
    RoundRobinArbiterMixin,
):
    def __init__(self, agent: Any) -> None:
        self._agent = agent

    def __getattr__(self, name: str) -> Any:
        return getattr(self._agent, name)
