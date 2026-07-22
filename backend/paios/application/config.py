"""Application configuration: the only knobs composition needs.

Clock selection (Manual/System) happens HERE and nowhere else — the one
composition-time decision the architecture allows about time.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from paios.runtime.clock import Clock

if TYPE_CHECKING:  # type-only: composition supplies the instance
    from paios.scheduler.planner import Planner


@dataclass(frozen=True)
class ApplicationConfig:
    #: Storage location per ENTITY_RELATIONSHIPS.md - Local Data Storage.
    data_dir: Path | str = ".data"
    #: None selects SystemClock (the sole OS-clock site); inject a
    #: ManualClock for deterministic runs and tests.
    clock: Clock | None = None
    #: Milestone 20 additive knob (approved 5.2): a Planner injected
    #: through the Scheduler's existing R3 constructor seam. None keeps
    #: the Milestone 4 DeterministicPlanner — fully backward compatible.
    planner: "Planner | None" = None
