"""Dependency composition: build every subsystem, wire nothing twice.

Pure construction — no side effects (no directory creation, no boot, no
subscriptions). Attachment and boot happen in Application.start(), in the
canonical order, so startup is deterministic and inspectable.
"""

from dataclasses import dataclass

from paios.decision_engine.engine import DecisionEngine
from paios.infrastructure.persistence_sync import PersistenceSync
from paios.infrastructure.recalculation_bridge import RecalculationBridge
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import Clock, SystemClock
from paios.runtime.kernel import RuntimeKernel
from paios.scheduler.scheduler import Scheduler
from paios.application.config import ApplicationConfig
from paios.application.domain_operations import DomainOperations


@dataclass(frozen=True)
class Components:
    """Everything the application composes, held together in one place."""

    config: ApplicationConfig
    clock: Clock
    repositories: RepositoryFactory
    kernel: RuntimeKernel
    scheduler: Scheduler
    engine: DecisionEngine
    bridge: RecalculationBridge
    sync: PersistenceSync
    operations: DomainOperations


def build_components(config: ApplicationConfig) -> Components:
    """Construct the full dependency graph (DIP: everything injected)."""
    clock = config.clock if config.clock is not None else SystemClock()
    repositories = RepositoryFactory(config.data_dir)
    kernel = RuntimeKernel(repositories=repositories, clock=clock)
    scheduler = Scheduler(kernel)
    engine = DecisionEngine()
    bridge = RecalculationBridge(kernel)
    sync = PersistenceSync(kernel, repositories)
    operations = DomainOperations(repositories=repositories, now=clock.now)
    return Components(
        config=config,
        clock=clock,
        repositories=repositories,
        kernel=kernel,
        scheduler=scheduler,
        engine=engine,
        bridge=bridge,
        sync=sync,
        operations=operations,
    )
