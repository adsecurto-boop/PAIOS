"""Application configuration: the only knobs composition needs.

Clock selection (Manual/System) happens HERE and nowhere else — the one
composition-time decision the architecture allows about time.
"""

from dataclasses import dataclass
from pathlib import Path

from paios.runtime.clock import Clock


@dataclass(frozen=True)
class ApplicationConfig:
    #: Storage location per ENTITY_RELATIONSHIPS.md - Local Data Storage.
    data_dir: Path | str = ".data"
    #: None selects SystemClock (the sole OS-clock site); inject a
    #: ManualClock for deterministic runs and tests.
    clock: Clock | None = None
