"""PAIOSSetup.exe entry: parse options, run the installer (or the
uninstaller), leave a log either way.

When frozen by PyInstaller the payload is unpacked under
``sys._MEIPASS/payload``. A payload with an ``app/`` tree triggers the
standalone consumer install (copy files; no Python needed); a payload
with only a wheel uses the legacy venv path; no payload at all installs
the source repository (development).

Frozen as ``PAIOSUninstall.exe`` (same code, no payload) the default
action flips to uninstalling the directory the executable lives in.

Inno-style switches (``/VERYSILENT`` etc.) are accepted and ignored so
the auto-updater can drive either installer flavor with one command
line.
"""

import argparse
import os
import sys
from pathlib import Path

from paios_installer.steps import (
    APP_PAYLOAD_DIR,
    Installer,
    InstallerError,
    InstallOptions,
    Uninstaller,
)


def default_install_dir(standalone: bool = False) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home()
    if standalone:
        # The self-contained application: a programs directory, never
        # the user data home (%LOCALAPPDATA%\PAIOS stays data-only).
        return root / "Programs" / "PAIOS" if base else root / "PAIOS-app"
    return root / "PAIOS" if base else root / "PAIOS"


def bundled_payload_dir() -> Path | None:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is None:
        return None
    payload = Path(bundle_root) / "payload"
    return payload if payload.is_dir() else None


def frozen_uninstaller_dir() -> Path | None:
    """When running as PAIOSUninstall.exe, the install dir is where the
    executable itself lives."""
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    if executable.stem.lower().startswith("paiosuninstall"):
        return executable.parent
    return None


def build_arg_parser(default_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PAIOSSetup", description="PAIOS Windows installer"
    )
    parser.add_argument("--install-dir", type=Path, default=default_dir)
    parser.add_argument(
        "--user-data-dir", type=Path, default=None,
        help="standalone installs: user data home"
        " (default %%LOCALAPPDATA%%\\PAIOS)",
    )
    parser.add_argument(
        "--payload", type=Path, default=None,
        help="payload directory (default: bundled)",
    )
    parser.add_argument("--python", default="python")
    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--no-shortcuts", action="store_true")
    parser.add_argument(
        "--no-startup", action="store_true",
        help="do not register PAIOS.exe at logon",
    )
    parser.add_argument(
        "--runtime-task", action="store_true",
        help="also register the daemon as a logon Task Scheduler task",
    )
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument(
        "--keep-data", action="store_true",
        help="with --uninstall: preserve all PAIOS user data",
    )
    parser.add_argument(
        "--remove-data", action="store_true",
        help="with --uninstall: also delete %%LOCALAPPDATA%%\\PAIOS",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="never prompt (unattended run)",
    )
    return parser


def ask_keep_data(ask=input) -> bool:
    """The uninstall data question. Keeping is the safe default —
    any answer other than an explicit "no" keeps the data."""
    try:
        answer = ask("Keep your PAIOS data? [Y/n] ").strip().lower()
    except (EOFError, OSError):
        return True
    return answer not in ("n", "no")


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # Tolerate Inno-style switches so one silent command line drives
    # both installer flavors (the updater relies on this).
    raw = [token for token in raw if not token.startswith("/")]

    payload_probe = bundled_payload_dir()
    standalone_payload = (
        payload_probe is not None
        and (payload_probe / APP_PAYLOAD_DIR).is_dir()
    )
    uninstall_home = frozen_uninstaller_dir()
    parser = build_arg_parser(
        uninstall_home
        if uninstall_home is not None
        else default_install_dir(standalone_payload)
    )
    arguments = parser.parse_args(raw)

    if arguments.uninstall or uninstall_home is not None:
        if arguments.keep_data:
            remove_user_data = False
        elif arguments.remove_data:
            remove_user_data = True
        elif arguments.yes:
            remove_user_data = False  # unattended: keep data
        else:
            remove_user_data = not ask_keep_data()
        Uninstaller(
            arguments.install_dir,
            keep_data=arguments.keep_data,
            remove_user_data=remove_user_data,
            user_data_dir=arguments.user_data_dir,
        ).run()
        return 0

    payload = arguments.payload or payload_probe
    source = None
    if payload is None:
        # Development fallback: install the repository this file is in.
        source = Path(__file__).resolve().parents[2]
    options = InstallOptions(
        install_dir=arguments.install_dir,
        payload_dir=payload,
        source_dir=source,
        with_gui=not arguments.no_gui,
        create_shortcuts=not arguments.no_shortcuts,
        register_startup=not arguments.no_startup,
        runtime_task=arguments.runtime_task,
        python=arguments.python,
        user_data_dir=arguments.user_data_dir,
    )
    try:
        Installer(options).run()
    except InstallerError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
