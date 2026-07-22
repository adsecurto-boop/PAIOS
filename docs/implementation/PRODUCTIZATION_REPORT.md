# Milestone 19 — Productization: Windows Launcher, Installer & System Tray

## Mission

Make PAIOS feel like a native Windows application instead of a Python
repository: one `PAIOS.exe` that owns the whole product, one
`PAIOSSetup.exe` that installs it, a system tray with runtime
controls, and production logging around all of it. Productization
only — no new business functionality.

## 1. Architecture analysis (Phase 1 outcome)

All prior reports and the codebase were reviewed. **No frozen-layer
modification was required** — the milestone proceeded automatically:

- Every deliverable lands in two **new product tiers** —
  `launcher/paios_launcher` (PAIOS.exe) and
  `installer/paios_installer` (PAIOSSetup.exe) — plus
  `scripts/build_installer.py` and packaging configuration.
- The launcher reaches the frozen layers only through **existing
  public command surfaces**: its children are `paios daemon run`,
  `paios serve` and `python -m paios_gui` — the M16 launchers,
  unchanged. Configuration and logging reuse `paios.system.config`
  and `paios.system.logs` (the M16 deployment tier) by import.
- Graceful daemon shutdown uses the **documented M16 file protocol**
  (the `paios-daemon.stop` sentinel the loop's predicate honours
  between ticks) — not a single daemon line changed.
- The installer mirrors the `install.ps1` contract (venv, pip
  install, `paios init`, health checks) and adds the product finish
  (exe, shortcuts, startup, scheduled task).
- Zero diffs across domain, runtime, scheduler, decision engine,
  learning, AI assistant, repositories, application, daemon,
  dashboard, API, GUI, notifications, and `paios.system`.

```
PAIOSSetup.exe (installer/paios_installer, payload: wheel + PAIOS.exe)
    └── installs → <InstallDir>\{venv, config, data, logs, backups, PAIOS.exe}

PAIOS.exe (launcher/paios_launcher, PyInstaller onefile)
    ├── single_instance   named mutex (lock-file fallback)
    ├── supervisor        daemon / api / gui child processes
    │       children run <InstallDir>\venv\Scripts\python.exe
    │       -m paios.cli daemon run | -m paios.cli serve | -m paios_gui
    ├── tray              QSystemTrayIcon + runtime menu
    └── logs              paios-launcher.log + crashes/
```

## 2. PAIOS.exe (`launcher/paios_launcher`)

**Supervisor** (`supervisor.py`, Qt-free): starts daemon → API → GUI
in order; polls them; shuts down in reverse order. Exit semantics:

| Observation | Behaviour |
| --- | --- |
| Exit the supervisor requested | expected; no reaction |
| Unexpected exit, code 0 | *clean exit* (user closed the GUI / stopped the daemon) — left stopped; restarting would fight the user |
| Unexpected exit, non-zero | *crash*: crash report written, restart with backoff (1/2/5/10/30 s), bounded to 5 restarts per 5-minute window, then **failed** (manual restart via tray still works) |

Graceful stop is layered: per-child pre-stop hook (the daemon's hook
writes the M16 stop sentinel), bounded wait, `terminate()`, `kill()`.
The daemon evaluates its predicate only between ticks (60 s default),
so the bounded-wait-then-terminate fallback is the honest strategy —
the store is written through on every mutation, so no committed data
is at risk. Child stdout/stderr append to `logs/paios-<name>.out`.

**Single instance** (`single_instance.py`): a named Windows kernel
mutex (dies with the process — crashes never leave a stale guard);
elsewhere and in tests a PID lock file with liveness probing and
stale-lock takeover. A second `PAIOS.exe` exits with code 2 and a
clear message. `PAIOS_LAUNCHER_MUTEX` lets tests and sandboxes use a
private guard.

**Entry** (`app.py`): frozen-aware environment resolution — children
run with `PAIOS_PYTHON` > `<exe dir>\venv\Scripts\python.exe` > the
current interpreter (development); config resolves flag >
`PAIOS_CONFIG` > `<exe dir>\config\config.yaml` > M16 defaults (logs
nest in the data dir when configless). Modes: tray (default),
`--no-tray` headless (stops on Ctrl+C or the `paios-launcher.stop`
sentinel, which `PAIOS.exe --stop` writes), `--no-gui`. Installed as
the `paios-launcher` console script for development.

## 3. System tray (`tray.py`)

`QSystemTrayIcon` with a programmatically painted status dot (no
asset files): green *ok*, amber *paused*, red *degraded*, grey
*stopped*; the tooltip names each child's state. Menu, exactly as
mandated: **Open Dashboard** (starts the GUI child if not running),
**Pause Runtime** / **Resume Runtime** / **Restart Runtime** (process
lifecycle of the daemon child — pause stops it without restart,
enable/disable follows its state), **View Logs** (opens the log
directory), **Exit** (full graceful shutdown). A 1 s QTimer polls the
supervisor and refreshes the indicator. The tray drives a controller
object, not the supervisor directly — tests exercise the whole menu
against a fake.

## 4. PAIOSSetup.exe (`installer/paios_installer`)

A step engine where every machine-touching operation goes through an
injectable port (process runner, registry) and every step logs to the
install log:

1. **Python check** — 3.12+ located and version-verified.
2. **Directories** — config/, data/, logs/, backups/.
3. **Virtual environment** — `<InstallDir>\venv` (idempotent).
4. **Dependencies** — pip-installs the **bundled wheel**
   (`[gui]` extra by default; `--no-gui` skips it). The backend wheel
   itself is dependency-free, so a GUI-less install is fully offline.
5. **PAIOS.exe** — copied from the payload into the install root.
6. **Configuration** — `paios init` from the install root (the M16
   generator; never overwrites).
7. **Shortcuts** — Desktop and Start Menu `.lnk` via WScript.Shell.
8. **Startup** — HKCU `…\CurrentVersion\Run` → `PAIOS.exe`
   (`--no-startup` skips).
9. **Runtime task (optional)** — `--runtime-task` registers the
   logon Task Scheduler task "PAIOS Daemon" running
   `paios --config <cfg> daemon start` (the Windows-service-style
   option; a true SCM service remains future work).
10. **Health checks** — the M16 diagnostics; problems reported, not
    fatal (parity with `install.ps1`).

`--uninstall [--keep-data]` reverses everything: stop sentinels,
Run-key removal, scheduled-task deletion, shortcut removal, install
directory removal (data/ and backups/ preserved with `--keep-data`).
Without a bundled payload the installer falls back to installing the
source tree — the development path.

## 5. Build (`scripts/build_installer.py`)

    python scripts/build_installer.py        # needs: pip install pyinstaller

wheel (`pip wheel`, now packaging all three roots) → **PAIOS.exe**
(PyInstaller onefile, windowed, PySide6 bundled) → payload staging →
**PAIOSSetup.exe** (onefile, console, payload embedded, unpacked at
run time from `_MEIPASS`). Every stage logs to
`dist/product/build-installer.log`; `--wheel-only` / `--skip-setup`
subset the pipeline. PyInstaller is a build-time tool only — the
runtime dependency posture is unchanged.

## 6. Logging

- **Launcher** — `paios-launcher.log` via the M16 structured format
  (`setup_logging(log_dir, "launcher")`): start/stop, every child
  event (started/exited/crashed/restarted/failed/stopped), instance
  refusals.
- **Installer** — `<InstallDir>\logs\paios-install.log` (uninstall:
  `%TEMP%\paios-uninstall.log`): every step, every failure.
- **Crashes** — `logs\crashes\paios-crash-<child>-<stamp>.log` with
  the command, outcome, restart decision and the last 50 lines of the
  child's output; the launcher's own unhandled exceptions land in
  `paios-crash-launcher-<stamp>.log` via an excepthook.
- **Build** — `dist/product/build-installer.log`.

## 7. Tests

73 new tests; full suite **931 passed, 1 skipped** (the pre-existing
M14 QApplication-guard skip). Coverage per the mission list:

- **Single-instance detection** (`tests/launcher/test_single_instance.py`,
  9) — lock acquire/refuse/release cycle, stale and garbage lock
  takeover, idempotence, and the real named-mutex behaviour on
  Windows.
- **Restart behaviour** (`tests/launcher/test_supervisor.py`, 15) —
  real (tiny) child processes: ordered start, reverse-order shutdown,
  graceful pre-stop hook (proved faster than the kill timeout), clean
  exits not restarted, crash detection + backoff + restart, crash
  report content (exit code + output tail), budget exhaustion →
  failed, window expiry refilling the budget, restart-disabled specs,
  pause/resume/restart controls, observer exception safety.
- **Tray behaviour** (`tests/launcher/test_tray.py`, 10, offscreen
  Qt) — every mandated menu entry present, every action reaching the
  controller, status dot per state, tooltip contents,
  pause/resume enablement following the daemon, monitor timer.
- **Launcher lifecycle** (`tests/launcher/test_lifecycle.py`, 17) —
  config resolution precedence, child specs running exactly the M16
  surfaces (with/without `--config`, `--no-gui`), the daemon
  pre-stop sentinel, the headless loop (bounded, sentinel-stopped,
  stale-sentinel cleanup), entry: second instance refused (private
  test mutex), `--stop`, missing config, structured log creation,
  crash-hook report.
- **Installer** (`tests/installer/test_installer_steps.py`, 18) —
  full run step sequence, wheel + `[gui]` spec, layout, PAIOS.exe
  placement, Python version rejection, shortcut PowerShell for both
  locations, Run-key registration, `schtasks` ONLOGON task, config
  generation via `paios init` from the install root (and
  never-overwrite), one real venv creation, uninstall full vs
  `--keep-data`.
- **Installer generation** (`tests/installer/test_build_installer.py`,
  8) — build command construction (onefile/windowed/names/paths/
  add-data) and payload staging (newest wheel, restaging, optional
  launcher, missing-wheel error).

Beyond the suite, the deliverables were verified **as a user would
hit them**, with the actually-built executables:

- `PAIOSSetup.exe --install-dir <scratch> --no-gui --no-shortcuts
  --no-startup` → venv created, wheel installed offline, PAIOS.exe
  placed, config generated, **7/7 health checks OK**.
- The installed `PAIOS.exe --no-tray --no-gui` → picked up the
  install's venv and config, started daemon + API, REST `/status`
  answered `"state": "Running"`; `PAIOS.exe --stop` → sentinel
  shutdown, API down, children stopped, `launcher stopped` logged.
- `PAIOSSetup.exe --uninstall` → everything removed.
- Development smoke: `python -m paios_launcher --no-tray --no-gui`
  from a scratch directory — same lifecycle against the working
  tree.

## 8. Audit

| Check | Result |
| --- | --- |
| Domain Layer untouched | PASS — zero diffs. |
| Runtime / Scheduler / AI untouched | PASS — zero diffs; the launcher supervises processes, never the loop. |
| No new business logic | PASS — process management, file operations, registry/shortcut/task registration, delegation only. |
| Frozen layers reached via public surfaces only | PASS — children are the M16 CLI commands; config/logging imported from `paios.system`; the stop sentinel is the documented M16 file protocol. |
| Prior conventions followed | PASS — injectable ports (M16 runner pattern), structured log format, exception-tight observers, spec-driven tests, `install.ps1` contract mirrored. |
| Full regression | PASS — 931 passed, 1 skipped. |

## 9. Future improvements

- **Code signing** — both executables are unsigned; SmartScreen will
  warn on first run.
- **True Windows service** — the Task Scheduler task approximates it;
  an SCM-integrated service needs a service wrapper (pywin32/NSSM).
- **In-place updates** — PAIOSSetup.exe over an existing install
  upgrades the venv, but the running product is not stopped/restarted
  automatically (the uninstaller's stop sentinels are best-effort).
- **Tray richness** — balloon notifications on crash/restart, an
  "open web dashboard" entry, per-child submenu.
- **Add/Remove Programs entry** — an HKCU Uninstall registry key
  pointing at `PAIOSSetup.exe --uninstall`.
- **Installer UI** — the setup is a console exe; a minimal wizard
  would complete the native feel.

## 10. Suggested commit message

```
Milestone 19: Productization - PAIOS.exe launcher, PAIOSSetup.exe
installer, system tray, crash logging

- launcher/paios_launcher: process supervisor (daemon/api/gui
  children via the M16 CLI surfaces, crash restart with bounded
  backoff, graceful sentinel shutdown, crash reports), named-mutex
  single-instance guard, Qt system tray (status dot, pause/resume/
  restart runtime, view logs, exit), headless mode, structured
  launcher log
- installer/paios_installer: step engine with injectable ports -
  Python check, venv, bundled-wheel install, PAIOS.exe placement,
  config via paios init, Desktop/Start Menu shortcuts, HKCU Run
  startup, optional Task Scheduler runtime task, health checks,
  install/uninstall logs, --uninstall [--keep-data]
- scripts/build_installer.py: wheel -> PAIOS.exe (PyInstaller
  onefile windowed) -> payload -> PAIOSSetup.exe (payload embedded)
- pyproject: launcher package root + paios-launcher script; v1.7.0
- Frozen layers: zero diffs
- Tests: 73 new (single-instance, supervisor/restart, tray,
  lifecycle, installer steps, installer generation); suite 931
  passed + 1 guard skip; built executables verified end to end
  (install -> run -> serve -> stop -> uninstall)
```

## Stop condition

Milestone 19 ends here. Awaiting review — the next milestone is not
begun.
