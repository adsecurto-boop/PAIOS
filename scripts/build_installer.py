"""Build PAIOS.exe and PAIOSSetup.exe (Milestone 19).

    python scripts/build_installer.py [--output dist/product]
        [--wheel-only] [--skip-setup]

Pipeline (each stage logged to <output>/build-installer.log):

    1. wheel    pip wheel .            -> paios-<version>-*.whl
    2. PAIOS.exe      PyInstaller onefile, windowed: the launcher
                      (supervisor + tray), PySide6 bundled
    3. PAIOSUpdater.exe PyInstaller onefile, console: the standalone
                      auto-updater (stdlib only, no paios imports)
    4. payload        wheel + PAIOS.exe + PAIOSUpdater.exe staged
    5. PAIOSSetup.exe PyInstaller onefile, console: the installer with
                      the payload embedded (unpacked to _MEIPASS)
    6. release        SHA256SUMS.txt + RELEASE_NOTES.md (M20 release
                      hygiene: what a GitHub Release must carry so
                      PAIOSUpdater.exe can verify downloads)

PyInstaller is a build-time tool only (never a runtime dependency):
    pip install pyinstaller
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADD_DATA_SEPARATOR = ";" if os.name == "nt" else ":"


class BuildLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(path, "a", encoding="utf-8")

    def write(self, message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._handle.write(f"{stamp} | {message}\n")
        self._handle.flush()
        print(message)

    def close(self) -> None:
        self._handle.close()


# --- command construction (pure; unit-tested) -------------------------------


def wheel_command(output_dir: Path) -> list[str]:
    return [
        sys.executable, "-m", "pip", "wheel", "--no-deps",
        "--wheel-dir", str(output_dir), str(REPO_ROOT),
    ]


def launcher_command(output_dir: Path, work_dir: Path) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "PAIOS",
        "--distpath", str(output_dir),
        "--workpath", str(work_dir),
        "--specpath", str(work_dir),
        "--paths", str(REPO_ROOT / "backend"),
        "--paths", str(REPO_ROOT / "frontend" / "desktop"),
        "--paths", str(REPO_ROOT / "launcher"),
        str(REPO_ROOT / "launcher" / "paios_launcher" / "__main__.py"),
    ]


def setup_command(
    output_dir: Path, work_dir: Path, payload_dir: Path
) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "PAIOSSetup",
        "--distpath", str(output_dir),
        "--workpath", str(work_dir),
        "--specpath", str(work_dir),
        "--paths", str(REPO_ROOT / "installer"),
        "--add-data", f"{payload_dir}{ADD_DATA_SEPARATOR}payload",
        str(REPO_ROOT / "installer" / "paios_installer" / "__main__.py"),
    ]


def stage_payload(
    payload_dir: Path, wheel_dir: Path, launcher_exe: Path | None
) -> list[Path]:
    """Assemble what PAIOSSetup.exe embeds; returns the staged files."""
    if payload_dir.exists():
        shutil.rmtree(payload_dir)
    payload_dir.mkdir(parents=True)
    staged = []
    wheels = sorted(wheel_dir.glob("paios-*.whl"))
    if not wheels:
        raise FileNotFoundError(f"no paios wheel in {wheel_dir}")
    staged.append(
        Path(shutil.copy2(wheels[-1], payload_dir / wheels[-1].name))
    )
    if launcher_exe is not None and launcher_exe.is_file():
        staged.append(
            Path(shutil.copy2(launcher_exe, payload_dir / "PAIOS.exe"))
        )
    return staged


def updater_command(output_dir: Path, work_dir: Path) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "PAIOSUpdater",
        "--distpath", str(output_dir),
        "--workpath", str(work_dir),
        "--specpath", str(work_dir),
        "--paths", str(REPO_ROOT / "updater"),
        str(REPO_ROOT / "updater" / "paios_updater" / "__main__.py"),
    ]


def project_version() -> str:
    """The single source of truth: [project] version in pyproject.toml."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise ValueError("pyproject.toml has no [project] version")
    return match.group(1)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(output_dir: Path, files: list[Path]) -> Path:
    """SHA256SUMS.txt in `sha256sum` format — the release artifact the
    updater downloads to verify PAIOSSetup.exe before installing."""
    lines = [
        f"{sha256_of(item)}  {item.name}"
        for item in files
        if item.is_file()
    ]
    checksums = output_dir / "SHA256SUMS.txt"
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums


def extract_release_notes(version: str) -> str:
    """The CHANGELOG section for `version`, for the GitHub Release body."""
    changelog = REPO_ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        return f"PAIOS {version}"
    text = changelog.read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(0).strip() if match else f"PAIOS {version}"


def write_release_notes(output_dir: Path, version: str) -> Path:
    notes = output_dir / "RELEASE_NOTES.md"
    notes.write_text(extract_release_notes(version) + "\n", encoding="utf-8")
    return notes


def pyinstaller_available() -> bool:
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


# --- the build --------------------------------------------------------------


def run(command: list[str], log: BuildLog) -> None:
    log.write(f"$ {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        log.write(result.stdout[-2000:] if result.stdout else "")
        log.write(result.stderr[-4000:] if result.stderr else "")
        raise SystemExit(
            f"Build step failed ({result.returncode}): {command[0]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "dist" / "product"
    )
    parser.add_argument(
        "--wheel-only", action="store_true",
        help="build the wheel and stop (no PyInstaller needed)",
    )
    parser.add_argument(
        "--skip-setup", action="store_true",
        help="build PAIOS.exe but not PAIOSSetup.exe",
    )
    arguments = parser.parse_args(argv)

    output: Path = arguments.output
    work = output / "work"
    wheels = output / "wheels"
    payload = output / "payload"
    log = BuildLog(output / "build-installer.log")
    log.write(f"PAIOS product build -> {output}")

    wheels.mkdir(parents=True, exist_ok=True)
    run(wheel_command(wheels), log)
    built_wheel = sorted(wheels.glob("paios-*.whl"))[-1]
    log.write(f"wheel: {built_wheel.name}")
    if arguments.wheel_only:
        log.write("wheel-only build complete.")
        return 0

    if not pyinstaller_available():
        log.write(
            "PyInstaller is not installed - run `pip install pyinstaller`."
        )
        return 1

    run(launcher_command(output, work), log)
    launcher_exe = output / (
        "PAIOS.exe" if os.name == "nt" else "PAIOS"
    )
    log.write(f"launcher: {launcher_exe}")

    run(updater_command(output, work), log)
    updater_exe = output / (
        "PAIOSUpdater.exe" if os.name == "nt" else "PAIOSUpdater"
    )
    log.write(f"updater: {updater_exe}")

    if arguments.skip_setup:
        log.write("setup build skipped.")
        return 0

    staged = stage_payload(payload, wheels, launcher_exe)
    if updater_exe.is_file():
        staged.append(
            Path(shutil.copy2(updater_exe, payload / updater_exe.name))
        )
    run(setup_command(output, work, payload), log)
    setup_exe = output / (
        "PAIOSSetup.exe" if os.name == "nt" else "PAIOSSetup"
    )
    log.write(f"installer: {setup_exe}")

    version = project_version()
    checksums = write_checksums(
        output, [setup_exe, launcher_exe, updater_exe, built_wheel]
    )
    notes = write_release_notes(output, version)
    log.write(f"release artifacts: {checksums.name}, {notes.name} (v{version})")
    log.write("Product build complete.")
    log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
