"""Runtime Status — the queryable answer to "what state is the runtime in".

Pure reporting: no behavior, no mutation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from paios.runtime.lifecycle import KernelState
from paios.runtime.runtime_state import ExecutionContext


@dataclass(frozen=True)
class RuntimeStatus:
    state: KernelState
    is_operational: bool
    booted_at: datetime | None
    execution_context: ExecutionContext | None
    registered_services: tuple[str, ...]
    aggregate_counts: Mapping[str, int] = field(default_factory=dict)
    latest_snapshot_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "aggregate_counts", MappingProxyType(dict(self.aggregate_counts))
        )
