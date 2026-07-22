"""PAIOSUpdater entry point.

    PAIOSUpdater.exe [--check-only] [--yes] [--install-dir DIR]
                     [--repo owner/name] [--current-version X.Y.Z]

Exit codes: 0 up to date or updated; 2 update available (--check-only);
1 failure (3 when the failure was rolled back cleanly).
"""

import argparse
import os
import sys
from pathlib import Path

from paios_updater.engine import UpdateEngine, UpdateError, UpdaterConfig
from paios_updater.releases import DEFAULT_REPO, ReleaseError
from paios_updater.versions import VersionError


def default_install_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    return base / "PAIOS"


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
