"""Composition-layer infrastructure adapters (Milestone 4).

These adapters wire runtime and persistence together WITHOUT either layer
knowing about the other's internals:

- RecalculationBridge translates runtime signals into the single
  SchedulerRecalculationRequested topic (refinement 1) so the Scheduler
  subscribes to exactly one event type.
- PersistenceSync (ruling G2) subscribes to the Scheduler/Kernel
  announcement events and writes changed aggregates back through
  repository interfaces — the only non-boot persistence path in PAIOS.
"""

from paios.infrastructure.persistence_sync import PersistenceSync
from paios.infrastructure.recalculation_bridge import RecalculationBridge

__all__ = ["PersistenceSync", "RecalculationBridge"]
