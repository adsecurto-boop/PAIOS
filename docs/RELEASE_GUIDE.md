# PAIOS Release Guide

The single reference for shipping PAIOS: how developers build a
release, how users install it, how updates and uninstalls work, and
where the Android build fits.

---

## 1. The product in one picture

```
PAIOSSetup.exe                    what the user downloads
   |
   | (wizard install)
   v
C:\Program Files\PAIOS            the application (read-only)
   PAIOS.exe                      launcher: tray + supervisor; also
                                  runs backend/GUI as --child of itself
   _internal\                     bundled Python runtime + PAIOS code
   PAIOSUpdater.exe               standalone auto-updater
   PAIOSUninstall.exe             uninstaller (fallback installer builds)
   version.txt                    installed version (updater fast path)

%LOCALAPPDATA%\PAIOS              user data (NEVER touched by upgrades)
   config\config.yaml             settings (generated on first launch)
   data\                          database (JSON store)
   logs\                          structured logs + crash reports
   backups\                       scheduled + update backups
```

The user needs **no Python, no git, no command prompt**: PAIOS.exe is a
self-contained PyInstaller application; its supervised children
(daemon, REST API, desktop GUI) are `PAIOS.exe --child ...`
re-invocations of the same executable.

## 2. Building a release (developers)

### Required tools

- Windows 10/11, Python 3.12+
- `pip install pyinstaller` (build-time only)
- **Inno Setup 6** (optional but recommended):
  <https://jrsoftware.org/isinfo.php> — produces the wizard-style
  installer; without it a console installer is built instead

### Commands

```bash
scripts\build_exe.cmd        # application only  -> dist\product\PAIOS\
scripts\build_installer.cmd  # full release      -> dist\product\PAIOSSetup.exe
scripts\test_release.cmd     # verify the build  (artifacts, checksums,
                             #  version, sandboxed install/uninstall)
```

Equivalent direct invocations:

```bash
python scripts/build_installer.py                # full build
python scripts/build_installer.py --skip-setup   # app only
python scripts/build_installer.py --no-inno      # force fallback installer
python scripts/test_release.py --full            # release verification
```

### What the build produces (`dist/product/`)

| Artifact | Purpose |
|----------|---------|
| `PAIOSSetup.exe` | **the** release download (Inno wizard, or console fallback) |
| `PAIOS/` | the standalone application tree (onedir) |
| `PAIOSUpdater.exe` | standalone updater, ships inside the install |
| `PAIOSUninstall.exe` | uninstaller for fallback installs |
| `wheels/paios-*.whl` | pip-installable package (developer installs) |
| `SHA256SUMS.txt` | download verification — the updater's trust anchor |
| `RELEASE_NOTES.md` | the CHANGELOG section for this version |

### Release steps

1. Bump `version` in `pyproject.toml` and add the matching
   `## [<version>]` section to `CHANGELOG.md`.
2. `python -m pytest` — the suite must be green.
3. `scripts\build_installer.cmd`, then `scripts\test_release.cmd`.
4. Create a GitHub Release tagged `v<version>` (tag must match
   pyproject) and upload **`PAIOSSetup.exe` + `SHA256SUMS.txt`**
   (both names are contractual — the auto-updater looks for exactly
   these assets) with `RELEASE_NOTES.md` as the body.
5. Installed copies discover the release within 24 h (tray check).

### Build troubleshooting

| Problem | Fix |
|---------|-----|
| `PyInstaller is not installed` | `pip install pyinstaller` |
| Inno installer not produced | Install Inno Setup 6 or set `PAIOS_ISCC` to ISCC.exe; `--no-inno` silences the fallback notice |
| Icon missing warning | `python scripts/make_icon.py` (regenerates `assets/paios.ico`) |
| Antivirus quarantines the exe | Expected for unsigned PyInstaller binaries — sign the executables (see Limitations in the report) or whitelist during development |
| Build log | `dist/product/build-installer.log` |

## 3. Installing PAIOS (users)

1. Download `PAIOSSetup.exe` from the latest GitHub Release.
2. Double-click it and follow the wizard: choose the install folder
   (default `C:\Program Files\PAIOS`), optional desktop shortcut,
   optional start-at-logon.
3. Launch **PAIOS** from the Start Menu.

First launch creates `%LOCALAPPDATA%\PAIOS` (settings, database, logs),
starts the background services, and opens the dark-themed dashboard
with the first-run wizard. No other software is required.

Silent install (IT/scripted): `PAIOSSetup.exe /VERYSILENT /NORESTART
/ALLUSERS` (machine-wide, `C:\Program Files\PAIOS`; requires an
elevated shell). Without `/ALLUSERS` a silent run installs per-user to
`%LOCALAPPDATA%\Programs\PAIOS` — the interactive wizard asks instead.

## 4. How updates work

- The tray icon checks GitHub Releases every 24 h (override:
  `PAIOS_UPDATE_INTERVAL_HOURS`, repo override: `PAIOS_UPDATE_REPO`).
- When a newer version exists the tray offers **Install update**; the
  user approves, PAIOS exits, and `PAIOSUpdater.exe` takes over:

```
detect (installed vs latest release tag)
   -> download PAIOSSetup.exe + SHA256SUMS.txt
   -> verify SHA-256               (mismatch = abort, nothing touched)
   -> stop PAIOS
   -> backup current installation  (%install%\backups\updates\*.zip)
   -> run the installer silently
   -> health check: PAIOS.exe --version must report the new version
   -> restart PAIOS
   -> on ANY post-backup failure: automatic rollback from the backup
```

- `%LOCALAPPDATA%\PAIOS` is never written by the updater — user data
  survives every update and every rollback.
- Manual check: `PAIOSUpdater.exe --check-only` (exit 2 = update
  available), `PAIOSUpdater.exe --yes` to apply.

## 5. How uninstall works

**Settings → Apps → PAIOS → Uninstall** (or the uninstaller in the
install folder). The uninstaller:

1. Stops PAIOS.
2. Removes the application files, shortcuts, startup registration and
   the Apps & Features entry.
3. Asks: **“Keep your PAIOS data?”**
   - **Yes** (default): `%LOCALAPPDATA%\PAIOS` is kept — reinstalling
     later restores the user's world.
   - **No**: all PAIOS data is removed permanently.

Silent uninstalls always keep the data. Scripted control:
`PAIOSUninstall.exe --uninstall --keep-data` or `--remove-data`.

## 6. Release testing matrix

| Scenario | Steps | Expected |
|----------|-------|----------|
| Fresh machine | run `PAIOSSetup.exe`, launch shortcut | install completes; Start Menu entry; first launch initializes `%LOCALAPPDATA%\PAIOS`; dark UI |
| Upgrade | install old version, run new `PAIOSSetup.exe` (or tray update) | app updated in place; `version.txt` bumped; data untouched |
| Uninstall | Apps & Features → Uninstall | app gone; “Keep your PAIOS data?” asked; choice honored |
| Reinstall | uninstall (keep data), install again | clean install; previous data picked up on first launch |

`scripts\test_release.cmd` automates the file-level equivalents of
these scenarios in a sandbox; the full matrix on a clean VM remains a
manual pre-release step.

## 7. Android builds

The Flutter client lives in `frontend/mobile/`; the complete guide —
tooling, setup, APK/App Bundle builds, signing, Play Store steps and
the desktop↔mobile architecture — is
**[docs/ANDROID_BUILD_GUIDE.md](ANDROID_BUILD_GUIDE.md)**.

Short version:

```bash
cd frontend/mobile
flutter create --platforms=android --project-name paios_mobile .
flutter pub get
flutter build apk --release       # sideload APK
flutter build appbundle           # Play Store upload
```

## 8. Developer (non-product) installs

Unchanged by productization:

```bash
pip install -e .[gui]        # editable install
paios gui / paios serve      # CLI surfaces
scripts\install.ps1          # legacy venv-based install
```

The legacy venv install path inside `PAIOSSetup.exe` still exists and
is chosen automatically when the payload carries only the wheel.
