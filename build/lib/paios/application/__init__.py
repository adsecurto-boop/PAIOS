"""PAIOS Application / Composition Layer (Milestone 6).

Connects the completed subsystems into one runnable application:
dependency composition, canonical startup/shutdown, the runtime loop
pass, and a delegating facade. It owns WIRING only — zero business,
scheduling, decision, persistence, or kernel logic. Every layer below
remains independently testable.
"""

from paios.application.application import Application
from paios.application.bootstrap import Components, build_components
from paios.application.config import ApplicationConfig
from paios.application.exceptions import (
    ApplicationAlreadyStartedError,
    ApplicationError,
    ApplicationNotStartedError,
)

__all__ = [
    "Application",
    "ApplicationAlreadyStartedError",
    "ApplicationConfig",
    "ApplicationError",
    "ApplicationNotStartedError",
    "Components",
    "build_components",
]
