"""PAIOS Windows installer (Milestone 19).

The logic inside PAIOSSetup.exe. Mirrors the M16 `install.ps1`
contract — private venv, pip install, config + directory skeleton,
health check — and adds the product finish: PAIOS.exe placement,
Desktop / Start Menu shortcuts, logon startup registration, and an
optional Task Scheduler runtime task. Pure stdlib; every side effect
goes through an injectable port (process runner, registry, filesystem
paths) so the behaviour is testable without touching the machine.
"""

from paios_installer.steps import (
    Installer,
    InstallerError,
    InstallLog,
    InstallOptions,
    Uninstaller,
)

__all__ = [
    "Installer",
    "InstallerError",
    "InstallLog",
    "InstallOptions",
    "Uninstaller",
]
