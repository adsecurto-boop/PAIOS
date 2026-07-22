"""Build the PAIOS Windows product: PAIOS.exe and PAIOSSetup.exe.

    python scripts/build_installer.py [--output dist/product]
        [--wheel-only] [--skip-setup] [--no-inno]

Pipeline (each stage logged to <output>/build-installer.log):

    1. wheel          pip wheel .        -> paios-<version>-*.whl
                      (legacy venv installs + dev; the standalone app
                      does not need it at runtime)
    2. PAIOS.exe      PyInstaller ONEDIR, windowed: the launcher
                      (supervisor + tray) with the ENTIRE backend and
                      desktop GUI collected — the standalone product.
                      Children are `PAIOS.exe --child ...`; no Python,
                      venv or pip on the user's machine.
    3. PAIOSUpdater.exe   PyInstaller onefile, console: the standalone
                      auto-updater (stdlib only, no paios imports)
    4. PAIOSUninstall.exe PyInstaller onefile, console: the installer
                      code with no payload; its executable name flips
                      the default action to uninstall
    5. payload        payload/app/<application tree> + version.txt
                      (+ the wheel at the payload root for legacy path)
    6. PAIOSSetup.exe The installer. Preferred: Inno Setup (ISCC) when
                      installed — wizard UI, Program Files, Apps &
                      Features entry, keep-your-data uninstall prompt.
                      Fallback: PyInstaller onefile console installer
                      with the payload embedded. Both accept the same
                      silent switches (/VERYSILENT ...).
    7. release        SHA256SUMS.txt + RELEASE_NOTES.md (what a GitHub
                      Release must carry so PAIOSUpdater.exe can verify
                      downloads)

Build-time tools (never runtime dependencies):
    pip install pyinstaller
    Inno Setup 6 (optional): https://jrsoftware.org/isinfo.php
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
ICON_FILE = REPO_ROOT / "assets" / "paios.ico"
INNO_SCRIPT = REPO_ROOT / "installer" / "PAIOSSetup.iss"
PUBLISHER = "PAIOS Project"


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


def _decorations(work_dir: Path) -> list[str]:
    """Icon + Windows version resource, when they exist."""
    extra: list[str] = []
    if ICON_FILE.is_file():
        extra += ["--icon", str(ICON_FILE)]
    version_resource = work_dir / "version_resource.txt"
    if version_resource.is_file():
        extra += ["--version-file", str(version_resource)]
    return extra


def wheel_command(output_dir: Path) -> list[str]:
    return [
        sys.executable, "-m", "pip", "wheel", "--no-deps",
        "--wheel-dir", str(output_dir), str(REPO_ROOT),
    ]


def launcher_command(output_dir: Path, work_dir: Path) -> list[str]:
    """PAIOS.exe as a ONEDIR application with the full product inside:
    backend, GUI and launcher packages are collected so the frozen
    executable can run every child (`--child`) itself."""
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", "PAIOS",
        "--distpath", str(output_dir),
        "--workpath", str(work_dir),
        "--specpath", str(work_dir),
        "--paths", str(REPO_ROOT / "backend"),
        "--paths", str(REPO_ROOT / "frontend" / "desktop"),
        "--paths", str(REPO_ROOT / "launcher"),
        "--paths", str(REPO_ROOT / "updater"),
        "--collect-submodules", "paios",
        "--collect-submodules", "paios_gui",
        "--collect-submodules", "paios_launcher",
        *_decorations(work_dir),
        str(REPO_ROOT / "launcher" / "paios_launcher" / "__main__.py"),
    ]


def updater_command(output_dir: Path, work_dir: Path) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "PAIOSUpdater",
        "--distpath", str(output_dir),
        "--workpath", str(work_dir),
        "--specpath", str(work_dir),
        "--paths", str(REPO_ROOT / "updater"),
        *_decorations(work_dir),
        str(REPO_ROOT / "updater" / "paios_updater" / "__main__.py"),
    ]


def uninstaller_command(output_dir: Path, work_dir: Path) -> list[str]:
    """PAIOSUninstall.exe: the installer code, no payload; the name
    makes uninstalling the default action (Apps & Features entry)."""
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "PAIOSUninstall",
        "--distpath", str(output_dir),
        "--workpath", str(work_dir),
        "--specpath", str(work_dir),
        "--paths", str(REPO_ROOT / "installer"),
        *_decorations(work_dir),
        str(REPO_ROOT / "installer" / "paios_installer" / "__main__.py"),
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
        *_decorations(work_dir),
        str(REPO_ROOT / "installer" / "paios_installer" / "__main__.py"),
    ]


def stage_payload(
    payload_dir: Path,
    wheel_dir: Path,
    app_dir: Path | None,
    extra_app_files: list[Path] | None = None,
    version: str | None = None,
) -> list[Path]:
    """Assemble what PAIOSSetup.exe embeds; returns the staged files.

    ``app_dir`` is the PyInstaller onedir tree (PAIOS.exe + _internal);
    it becomes ``payload/app/`` — the standalone consumer install.
    ``extra_app_files`` (updater, uninstaller) land beside PAIOS.exe.
    The newest wheel is staged at the payload root for the legacy path.
    """
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
    if app_dir is not None and app_dir.is_dir():
        app_target = payload_dir / "app"
        shutil.copytree(app_dir, app_target)
        for extra in extra_app_files or []:
            if extra.is_file():
                staged.append(
                    Path(shutil.copy2(extra, app_target / extra.name))
                )
        if version:
            (app_target / "version.txt").write_text(
                version + "\n", encoding="utf-8"
            )
        staged.append(app_target / "PAIOS.exe")
    return staged


# --- Inno Setup (the preferred installer) ------------------------------------


def find_iscc() -> str | None:
    """ISCC.exe: $PAIOS_ISCC > PATH > the standard install locations."""
    override = os.environ.get("PAIOS_ISCC")
    if override and Path(override).is_file():
        return override
    on_path = shutil.which("ISCC")
    if on_path:
        return on_path
    bases = [
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:  # per-user Inno Setup installs
        bases.append(str(Path(local) / "Programs"))
    for base in bases:
        candidate = Path(base) / "Inno Setup 6" / "ISCC.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def iscc_command(
    iscc: str, version: str, app_payload_dir: Path, output_dir: Path
) -> list[str]:
    return [
        iscc,
        f"/DAppVersion={version}",
        f"/DPayloadDir={app_payload_dir}",
        f"/DOutputDir={output_dir}",
        f"/DIconFile={ICON_FILE}",
        str(INNO_SCRIPT),
    ]


# --- release metadata --------------------------------------------------------


def project_version() -> str:
    """The single source of truth: [project] version in pyproject.toml."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise ValueError("pyproject.toml has no [project] version")
    return match.group(1)


def version_resource_text(version: str) -> str:
    """A PyInstaller VSVersionInfo file: what Windows Explorer shows in
    the executable's Details tab (version, publisher, product)."""
    parts = [int(p) for p in re.findall(r"\d+", version)[:4]]
    while len(parts) < 4:
        parts.append(0)
    tuple_text = ", ".join(str(p) for p in parts)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({tuple_text}),
    prodvers=({tuple_text}),
    mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', '{PUBLISHER}'),
        StringStruct('FileDescription',
                     'PAIOS - Personal AI Operating System'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('ProductName', 'PAIOS'),
        StringStruct('ProductVersion', '{version}'),
        StringStruct('LegalCopyright', '(c) {PUBLISHER}'),
      ]),
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""


def write_version_resource(work_dir: Path, version: str) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "version_resource.txt"
    target.write_text(version_resource_text(version), encoding="utf-8")
    return target


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
    parser.add_argument(
        "--no-inno", action="store_true",
        help="always use the fallback installer even when ISCC exists",
    )
    arguments = parser.parse_args(argv)

    output: Path = arguments.output
    work = output / "work"
    wheels = output / "wheels"
    payload = output / "payload"
    log = BuildLog(output / "build-installer.log")
    version = project_version()
    log.write(f"PAIOS product build v{version} -> {output}")

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

    write_version_resource(work, version)
    if not ICON_FILE.is_file():
        log.write("icon missing; run `python scripts/make_icon.py` first")

    run(launcher_command(output, work), log)
    app_dir = output / "PAIOS"  # onedir tree: PAIOS.exe + _internal
    launcher_exe = app_dir / ("PAIOS.exe" if os.name == "nt" else "PAIOS")
    log.write(f"application: {app_dir}")

    run(updater_command(output, work), log)
    updater_exe = output / (
        "PAIOSUpdater.exe" if os.name == "nt" else "PAIOSUpdater"
    )
    log.write(f"updater: {updater_exe}")

    run(uninstaller_command(output, work), log)
    uninstaller_exe = output / (
        "PAIOSUninstall.exe" if os.name == "nt" else "PAIOSUninstall"
    )
    log.write(f"uninstaller: {uninstaller_exe}")

    if arguments.skip_setup:
        log.write("setup build skipped.")
        return 0

    stage_payload(
        payload,
        wheels,
        app_dir,
        extra_app_files=[updater_exe, uninstaller_exe],
        version=version,
    )
    log.write(f"payload staged: {payload}")

    setup_exe = output / (
        "PAIOSSetup.exe" if os.name == "nt" else "PAIOSSetup"
    )
    iscc = None if arguments.no_inno else find_iscc()
    if iscc is not None:
        run(iscc_command(iscc, version, payload / "app", output), log)
        log.write(f"installer (Inno Setup): {setup_exe}")
    else:
        run(setup_command(output, work, payload), log)
        log.write(
            f"installer (fallback): {setup_exe} - install Inno Setup 6"
            " for the wizard-style PAIOSSetup.exe"
        )

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
