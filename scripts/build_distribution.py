"""Assemble the distributable layout (Milestone 16).

    python scripts/build_distribution.py [--output dist]

Produces:

    dist/paios/
        backend/        the paios package source
        frontend/       desktop GUI + mobile companion source
        config/         config.yaml (generated defaults)
        data/           empty store (created on first run)
        logs/           empty
        backups/        empty
        scripts/        install.ps1 / uninstall.ps1 / this builder
        docs/           implementation reports + canonical docs
        pyproject.toml  the installable package definition
        README.md       installation and usage documentation
"""

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".git", ".pytest_cache", "build", "dist",
    "*.egg-info", ".dart_tool",
)

README = """\
# PAIOS — Personal AI Operating System

This is the distributable layout produced by scripts/build_distribution.py.

## Install (Windows)

    powershell -ExecutionPolicy Bypass -File scripts\\install.ps1

Options:
    -InstallDir <path>   target (default %LOCALAPPDATA%\\PAIOS)
    -WithGui             also install the Qt desktop dashboard
    -AutoStartDaemon     start the background daemon at logon

The installer checks Python 3.12+, creates a private virtual
environment, installs the `paios` launcher, generates config.yaml,
creates the data/logs/backups directories, and runs the health checks.

## Use

    paios shell          interactive shell
    paios dashboard      terminal dashboard
    paios serve          REST API (needed by the GUI and mobile app)
    paios gui            desktop dashboard (Qt)
    paios daemon start   background runtime (tick loop + auto-backups)
    paios health         system diagnostics
    paios backup now     manual backup (see also restore/export/import)

Configuration lives in config/config.yaml. Uninstall with
scripts\\uninstall.ps1 (add -KeepData to preserve your store).

## Layout

    backend/    Python packages (domain ... application, api, cli, system)
    frontend/   desktop (PySide6) and mobile (Flutter) clients
    config/     config.yaml
    data/       the JSON store (your life data — back it up!)
    logs/       structured logs (paios-cli/api/daemon/gui/dashboard)
    backups/    zip archives (automatic per backup policy + manual)
    scripts/    install / uninstall / build_distribution
    docs/       canonical documentation and implementation reports
"""


def build(output: Path) -> Path:
    target = output / "paios"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    shutil.copytree(REPO_ROOT / "backend", target / "backend", ignore=IGNORE)
    shutil.copytree(REPO_ROOT / "frontend", target / "frontend", ignore=IGNORE)
    shutil.copytree(REPO_ROOT / "scripts", target / "scripts", ignore=IGNORE)
    shutil.copytree(REPO_ROOT / "docs", target / "docs", ignore=IGNORE)
    shutil.copy2(REPO_ROOT / "pyproject.toml", target / "pyproject.toml")

    for empty in ("data", "logs", "backups"):
        (target / empty).mkdir()

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from paios.system.config import generate_default_config

    generate_default_config(target / "config" / "config.yaml")
    (target / "README.md").write_text(README, encoding="utf-8")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(REPO_ROOT / "dist"))
    arguments = parser.parse_args(argv)
    target = build(Path(arguments.output))
    print(f"Distribution built: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
