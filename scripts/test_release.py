"""Release verification: prove the built product is shippable.

    python scripts/test_release.py [--output dist/product] [--full]

Checks (all offline, none mutate the build):

    1. artifacts    PAIOSSetup.exe, PAIOS\\PAIOS.exe, PAIOSUpdater.exe,
                    PAIOSUninstall.exe, the wheel, SHA256SUMS.txt,
                    RELEASE_NOTES.md all exist
    2. checksums    every SHA256SUMS.txt line matches its file
    3. version      PAIOS.exe --version == pyproject.toml version
    4. payload      payload/app carries PAIOS.exe + version.txt
    5. (--full)     scripted install -> installed PAIOS.exe --version
                    -> uninstall (keep data), in a temp sandbox

Exit code 0 = release OK.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_installer import project_version, sha256_of  # noqa: E402


class CheckFailure(Exception):
    pass


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  OK   {label}")
    else:
        raise CheckFailure(f"{label}{f': {detail}' if detail else ''}")


def verify_artifacts(output: Path) -> None:
    print("* Artifacts")
    for relative in (
        "PAIOSSetup.exe",
        "PAIOS/PAIOS.exe",
        "PAIOSUpdater.exe",
        "PAIOSUninstall.exe",
        "SHA256SUMS.txt",
        "RELEASE_NOTES.md",
    ):
        check(relative, (output / relative).is_file())
    check("wheel", bool(list((output / "wheels").glob("paios-*.whl"))))


def verify_checksums(output: Path) -> None:
    print("* Checksums")
    lines = (
        (output / "SHA256SUMS.txt")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    check("SHA256SUMS.txt is not empty", bool(lines))
    for line in lines:
        digest, _, name = line.partition("  ")
        # The application tree is the canonical PAIOS.exe location;
        # a stale onefile PAIOS.exe at the root must not shadow it.
        candidates = [output / "PAIOS" / name, output / name,
                      output / "wheels" / name]
        target = next((c for c in candidates if c.is_file()), None)
        check(f"{name} exists", target is not None)
        check(f"{name} digest", sha256_of(target) == digest.strip())


def launcher_version(exe: Path) -> str:
    completed = subprocess.run(
        [str(exe), "--version"], capture_output=True, text=True, timeout=120
    )
    if completed.returncode != 0:
        raise CheckFailure(
            f"{exe.name} --version failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def verify_version(output: Path) -> None:
    print("* Version")
    expected = project_version()
    reported = launcher_version(output / "PAIOS" / "PAIOS.exe")
    check(
        f"PAIOS.exe --version == {expected}",
        reported == expected,
        f"reported {reported!r}",
    )


def verify_payload(output: Path) -> None:
    print("* Payload")
    app = output / "payload" / "app"
    check("payload/app/PAIOS.exe", (app / "PAIOS.exe").is_file())
    check("payload/app/_internal", (app / "_internal").is_dir())
    check("payload/app/version.txt", (app / "version.txt").is_file())
    check(
        "payload version matches",
        (app / "version.txt").read_text(encoding="utf-8").strip()
        == project_version(),
    )


def scripted_install_cycle(output: Path) -> None:
    """Install -> health -> uninstall in a sandbox, via the installer
    package driven directly (the same code PAIOSSetup.exe freezes)."""
    print("* Install cycle (sandbox)")
    sys.path.insert(0, str(REPO_ROOT / "installer"))
    from paios_installer.registry import NullRegistry
    from paios_installer.steps import InstallOptions, Installer, Uninstaller

    with tempfile.TemporaryDirectory(prefix="paios-release-") as sandbox:
        root = Path(sandbox)
        install_dir = root / "app"
        data_dir = root / "data-home"
        options = InstallOptions(
            install_dir=install_dir,
            payload_dir=output / "payload",
            create_shortcuts=False,
            register_startup=False,
            user_data_dir=data_dir,
        )
        from paios_installer.steps import InstallLog

        Installer(
            options,
            registry=NullRegistry(),
            log=InstallLog(root / "install.log", echo=lambda m: None),
            desktop=root / "Desktop",
            start_menu=root / "StartMenu",
        ).run()
        check("installed PAIOS.exe", (install_dir / "PAIOS.exe").is_file())
        check("installed version.txt",
              (install_dir / "version.txt").is_file())
        reported = launcher_version(install_dir / "PAIOS.exe")
        check(
            "installed --version",
            reported == project_version(),
            f"reported {reported!r}",
        )
        (data_dir / "data" / "keep-me.json").write_text("{}")
        Uninstaller(
            install_dir,
            remove_user_data=False,
            user_data_dir=data_dir,
            registry=NullRegistry(),
            log=InstallLog(root / "uninstall.log", echo=lambda m: None),
            desktop=root / "Desktop",
            start_menu=root / "StartMenu",
        ).run()
        check("app removed", not install_dir.exists())
        check(
            "user data kept",
            (data_dir / "data" / "keep-me.json").is_file(),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "dist" / "product"
    )
    parser.add_argument(
        "--full", action="store_true",
        help="also run the sandboxed install/uninstall cycle",
    )
    arguments = parser.parse_args(argv)
    output: Path = arguments.output
    print(f"PAIOS release check -> {output}")
    try:
        verify_artifacts(output)
        verify_checksums(output)
        verify_version(output)
        verify_payload(output)
        if arguments.full:
            scripted_install_cycle(output)
    except CheckFailure as failure:
        print(f"  FAIL {failure}")
        return 1
    print("Release check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
