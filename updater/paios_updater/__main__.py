"""PAIOSUpdater entry point.

    PAIOSUpdater.exe [--check-only] [--yes] [--install-dir DIR]
                     [--repo owner/name] [--current-version X.Y.Z]

Exit codes: 0 up to date or updated; 2 update available (--check-only);
1 failure (3 when the failure was rolled back cleanly).
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from paios_updater.engine import UpdateEngine, UpdateError, UpdaterConfig
from paios_updater.releases import DEFAULT_REPO, ReleaseError
from paios_updater.versions import VersionError


def default_install_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    # Standalone installs live in Programs\PAIOS; the frozen updater
    # runs from there, so its own location is the best default.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    programs = base / "Programs" / "PAIOS"
    if (programs / "PAIOS.exe").is_file():
        return programs
    return base / "PAIOS"


def relaunch_outside_install_dir(
    install_dir: Path, argv: list[str]
) -> bool:
    """A frozen updater running from inside the install dir would lock
    its own file during the install. Copy it to a temp directory and
    re-launch from there; the caller then exits. Returns True when the
    hand-off happened."""
    if not getattr(sys, "frozen", False):
        return False
    executable = Path(sys.executable).resolve()
    try:
        inside = executable.is_relative_to(install_dir.resolve())
    except (OSError, ValueError):
        inside = False
    if not inside:
        return False
    staging = Path(tempfile.mkdtemp(prefix="paios-updater-"))
    relocated = staging / executable.name
    shutil.copy2(executable, relocated)
    creation_flags = 0x00000008 if os.name == "nt" else 0  # DETACHED
    subprocess.Popen(
        [
            str(relocated),
            "--install-dir", str(install_dir),
            "--yes",
            *argv,
        ],
        creationflags=creation_flags,
        close_fds=True,
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="PAIOSUpdater", description=__doc__
    )
    parser.add_argument(
        "--install-dir", type=Path, default=default_install_dir()
    )
    parser.add_argument(
        "--repo", default=os.environ.get("PAIOS_UPDATE_REPO", DEFAULT_REPO)
    )
    parser.add_argument("--current-version", default=None)
    parser.add_argument(
        "--check-only", action="store_true",
        help="report whether an update exists; change nothing",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="apply without the interactive confirmation",
    )
    arguments = parser.parse_args(argv)

    engine = UpdateEngine(
        UpdaterConfig(
            install_dir=arguments.install_dir,
            repo=arguments.repo,
            current_version=arguments.current_version,
        )
    )
    try:
        plan = engine.check()
        if plan is None:
            print("PAIOS is up to date.")
            return 0
        print(
            f"Update available: {plan.current_version} -> "
            f"{plan.target_version}"
        )
        if plan.notes:
            print("\nRelease notes:\n" + plan.notes.strip() + "\n")
        if arguments.check_only:
            return 2
        if not arguments.yes:
            answer = input("Install this update now? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Update declined.")
                return 0
        extra = (
            ["--repo", arguments.repo]
            if arguments.repo != DEFAULT_REPO
            else []
        )
        if relaunch_outside_install_dir(arguments.install_dir, extra):
            print("Updater relocated for file replacement; continuing"
                  " in the background.")
            return 0
        engine.apply(plan)
        print(f"PAIOS {plan.target_version} installed and restarted.")
        return 0
    except UpdateError as error:
        print(f"Update failed: {error}", file=sys.stderr)
        return 3 if error.rolled_back else 1
    except (ReleaseError, VersionError) as error:
        print(f"Update check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
