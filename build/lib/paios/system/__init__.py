"""PAIOS system tier (Milestone 16): deployment-time composition.

Configuration files, structured logging, backups, health checks, and
the daemon process runner. Everything here composes existing layers
through their public surfaces — no business logic, no frozen-layer
imports beyond the facade and the bus vocabulary.
"""

from paios.system.config import (
    SystemConfig,
    generate_default_config,
    load_system_config,
)
from paios.system.backup import BackupManager
from paios.system.health import HealthCheck, run_health_checks
from paios.system.logs import BusLogObserver, LogProvider, setup_logging

__all__ = [
    "BackupManager",
    "BusLogObserver",
    "HealthCheck",
    "LogProvider",
    "SystemConfig",
    "generate_default_config",
    "load_system_config",
    "run_health_checks",
    "setup_logging",
]
