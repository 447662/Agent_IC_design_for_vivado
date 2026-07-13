from pathlib import Path
from typing import Protocol, TypedDict


AGENT_MODULE_DIR = Path(__file__).resolve().parent
PathLike = str | Path


class CompletedProcessLike(Protocol):
    returncode: int


class AsyncFifoWcfgSummary(TypedDict):
    path: Path
    exists: bool
    object_count: int
    required_objects: list[str]
    present_required: list[str]
    missing_required: list[str]
    valid: bool
