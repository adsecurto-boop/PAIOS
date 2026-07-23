"""PAIOS product launcher (Milestone 19).

PAIOS.exe: one process that owns the product — it starts the daemon,
the REST API and the desktop dashboard as supervised child processes,
keeps them alive, shows a system tray with runtime controls, and shuts
everything down gracefully. Frozen layers are reached only through the
public `paios` CLI surfaces the children run.
"""

from paios_launcher.single_instance import (
    AlreadyRunningError,
    SingleInstance,
)
from paios_launcher.supervisor import (
    ChildSpec,
    ChildState,
    ManagedChild,
    RestartPolicy,
    Supervisor,
)

__all__ = [
    "AlreadyRunningError",
    "SingleInstance",
    "ChildSpec",
    "ChildState",
    "ManagedChild",
    "RestartPolicy",
    "Supervisor",
]
