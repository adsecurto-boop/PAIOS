"""`python -m paios_launcher` — and the PyInstaller entry for PAIOS.exe."""

from paios_launcher.app import main

if __name__ == "__main__":
    raise SystemExit(main())
