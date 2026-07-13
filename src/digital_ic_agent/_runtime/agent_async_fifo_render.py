from digital_ic_agent._runtime.agent_async_fifo_render_rtl import (
    AsyncFifoRtlRenderMixin,
)
from digital_ic_agent._runtime.agent_async_fifo_render_uvm import (
    AsyncFifoUvmRenderMixin,
)


class AsyncFifoRenderMixin(
    AsyncFifoUvmRenderMixin,
    AsyncFifoRtlRenderMixin,
):
    pass


__all__ = [
    "AsyncFifoRenderMixin",
    "AsyncFifoRtlRenderMixin",
    "AsyncFifoUvmRenderMixin",
]
