"""PAIOSSetup.exe entry: parse options, run the installer (or the
uninstaller), leave a log either way.

When frozen by PyInstaller the payload (wheel + PAIOS.exe) is unpacked
under ``sys._MEIPASS/payload``; in development ``--payload`` points at
a staged directory, or the repository root is installed from source.
"""

import argparse
import os
import sys
from pathlib import Path

from paios_installer.steps import (
    Installer,
    InstallerError,
    InstallOptions,
    Uninstaller,
)


def default_install_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "PAIOS" if base else Path.home() / "PAIOS"


def bundled_payload_dir() -> Path | None:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is None:
        return None
    payload = Path(bundle_root) / "payload"
    return payload if payload.is_dir() else None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PAIOSSetup", description="PAIOS Windows installer"
    )
    parser.add_argument(
        "--install-dir", type=Path, default=default_install_dir()
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
        help="with --uninstall: preserve data/ and backups/",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_arg_parser().parse_args(
        sys.argv[1:] if argv is None else argv
    )
    if arguments.uninstall:
        Uninstaller(
            arguments.install_dir, keep_data=arguments.keep_data
        ).run()
        return 0

    payload = arguments.payload or bundled_payload_dir()
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
    )
    try:
        Installer(options).run()
    except InstallerError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
