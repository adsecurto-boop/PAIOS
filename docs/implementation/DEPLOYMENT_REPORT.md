# Milestone 16 — Deployment, Packaging, Installation & Production Runtime

## Mission

Transform PAIOS from a development project into a deployable Windows
product: install it and use it immediately — no PYTHONPATH, no manual
virtual environments, no launch incantations.

## 1. Architecture analysis (Phase 1 outcome)

All M1–M15 reports and the codebase were reviewed. **No frozen-layer
modification was required** — the milestone proceeded automatically:

- Every deliverable lands in a new `paios/system` tier, the CLI
  composition root (the established modifiable surface), scripts, and
  project configuration.
- The M9 daemon already exposes the full loop lifecycle
  (`run_until(predicate)` is the seam the process runner uses for
  graceful stop and backup policy) — its code is untouched.
- Scheduler/runtime logging is an **Event Bus observer**
  (`BusLogObserver`, the M14 pattern); notification logging is a
  **`LogProvider`** implementing the M14 provider abstraction. Frozen
  layers never learned to log — they are observed.
- `paios/api/server.py` gained exactly one sanctioned change (the
  mission's "logging: api" deliverable): the previously silent
  `log_message` now emits to `paios.api`; with no handlers configured
  it stays a no-op, preserving pre-M16 behaviour.
- `config.yaml` is mandated but the backend is deliberately
  stdlib-only; PAIOS generates its own config, so it parses a
  **documented YAML subset** (top-level scalars + one level of nested
  mappings + comments) with a ~60-line stdlib reader that rejects
  anything outside the subset rather than mis-parsing. Zero
  dependencies preserved.

```
launchers (paios.exe / paios.cmd shim)
    └── paios.cli.main  ── config.yaml ──► paios.system
          │                                   ├── config    (subset parser)
          │                                   ├── logs      (setup + BusLogObserver + LogProvider)
          │                                   ├── backup    (BackupManager)
          │                                   ├── health    (run_health_checks)
          │                                   └── daemon_runner (pid/stop files, fg/bg)
          ▼
      Application facade ──► frozen layers (zero diffs)
```

## 2. Installer (`scripts/install.ps1` / `uninstall.ps1`)

`install.ps1 [-InstallDir …] [-WithGui] [-AutoStartDaemon]`:

1. **Dependency check** — Python 3.12+ located and version-verified.
2. Private venv under `<InstallDir>\venv`; `pip install` of the
   package (`[gui]` extra with `-WithGui`).
3. **Directories** — config/, data/, logs/, backups/ created.
4. **First-run initialization** — `paios init` generates the commented
   `config\config.yaml` (never overwrites).
5. **Launcher** — `<InstallDir>\paios.cmd` shim pins `PAIOS_CONFIG` to
   the install's config; the venv is an implementation detail the user
   never sees.
6. Health checks run; `-AutoStartDaemon` registers a logon scheduled
   task ("PAIOS Daemon") and starts the daemon.

`uninstall.ps1 [-KeepData]` stops the daemon, deletes the scheduled
task, removes the install; `-KeepData` preserves data/ and backups/.

## 3. Executables

`pyproject.toml` became a real package: setuptools build backend, two
package roots (`backend` → `paios`, `frontend/desktop` → `paios_gui`),
and console scripts `paios` / `paios-gui`. `paios shell`, `paios
dashboard`, `paios serve`, and the new `paios gui` (which spawns the
Qt app detached, passing the configured URL, refresh, and log dir) are
subcommands of the single launcher. **Verified empirically**: a scratch
venv + `pip install` + running `paios help / init / status / health /
backup / daemon / serve` from an unrelated directory with no
PYTHONPATH anywhere.

## 4. Daemon integration (`paios daemon …`, `paios.system.daemon_runner`)

| Mode | Mechanism |
| --- | --- |
| Foreground | `daemon run` — blocking `RuntimeDaemon.run_until` with Ctrl+C handling |
| Background | `daemon start` — detached process (`DETACHED_PROCESS`), output to `logs/paios-daemon.out` |
| Graceful shutdown | `daemon stop` — a **stop sentinel file** the loop's predicate honours between ticks (portable; no Windows signal games), then waits for exit |
| Restart | `daemon restart` (stop + start) |
| Status | `daemon status` — PID file + a real liveness probe (`OpenProcess`/`GetExitCodeProcess` on Windows, `kill 0` elsewhere; stale PID files detected) |
| Automatic startup | installer's `-AutoStartDaemon` logon task |

The runner also owns the PID file (rewritten with the true pid at loop
start — self-correcting under venv launcher shims) and executes the
backup policy between ticks. Verified live: start → status
`running (pid …)` → stop → clean exit, files removed.

## 5. Configuration (`config/config.yaml`)

Generated defaults cover every mandated knob: data/log/backup
directories (relative paths resolve against the file), server host +
port, GUI refresh interval, dashboard interval, daemon tick interval,
notification settings (quiet hours, cooldown), and the backup policy
(enabled / interval_hours / keep). Search order: `--config` flag >
`PAIOS_CONFIG` env (the shim sets it) > `./config/config.yaml` >
`./config.yaml` > built-in defaults. **Precedence: explicit CLI flags
> config file > defaults** (e.g. `--data-dir`, `--quiet-hours`).
Without any config file, logs nest inside the data directory so
development and test runs stay self-contained.

## 6. Logging (`paios.system.logs`)

One structured line format everywhere:

```
2026-07-22T01:10:40 | INFO | paios.api | "GET /status HTTP/1.1" 200 -
```

Rotating file per surface (1 MB × 3): `paios-cli.log`,
`paios-api.log`, `paios-daemon.log`, `paios-dashboard.log`,
`paios-gui.log`. Coverage per the mission list: **cli** (surface
setup), **api** (request lines via the sanctioned `log_message`),
**daemon** (runner + observers), **gui** (`--log-dir`, stdlib-only —
the M13 "imports nothing from backend" rule still holds, and the log
sink is the one sanctioned file output), **scheduler** (BusLogObserver
routes `PlanUpdated`/`EventStateChanged`/… to `paios.scheduler`, other
broadcasts to `paios.runtime`), **notifications** (LogProvider records
every delivered notification). Observers are exception-tight — logging
can never disturb a kernel broadcast.

## 7. Backup system (`paios.system.backup`, `paios backup …`)

- **Automatic**: the daemon evaluates `maybe_backup()` every tick —
  due when the newest archive (timestamp parsed from its name, so
  injected clocks work) is older than `interval_hours`; pruned to
  `keep`.
- **Manual**: `backup now`, `backup list`.
- **Restore / import**: `backup restore <name>` / `backup import
  <path>` — refused while the daemon is running; archives are
  validated (flat `*.json` members only — zip-path tricks and foreign
  files rejected) before the store is replaced.
- **Export**: `backup export <path>` — an archive at an explicit
  location.

Archives are plain zips of the JSON store (`paios-backup-
YYYYMMDD-HHMMSS.zip`) — file operations only, no domain knowledge.

## 8. Health checks (`paios health`)

Seven diagnostics, each `OK/FAIL + detail`, exit code 0/1:
repositories (every store file parses), **application** (a real boot
against the configured store), scheduler (state), clock (now()),
event bus (subscription count), daemon (liveness probe), api (HTTP
`/status` ping; "not serving" is informational, not a failure).
Diagnostics never crash; a failed boot degrades the dependent checks
with "skipped".

## 9. Packaging (`scripts/build_distribution.py`)

Produces exactly the mandated layout (verified by building one):

```
dist/paios/
    backend/  frontend/  config/config.yaml  data/  logs/  backups/
    scripts/  docs/  pyproject.toml  README.md
```

`README.md` documents install, usage, and the layout; `docs/` carries
the canonical documentation and all implementation reports.

## 10. Tests

41 new tests in `tests/system/`; full suite **794 passed, 1 skipped**
(the pre-existing M14 QApplication-guard skip). New coverage:

- **Config** — subset parsing (scalars, sections, comments, quoted
  strings), subset violations rejected with line numbers, search
  order, env var, relative-path resolution, generated-file round-trip,
  never-overwrite, flag precedence.
- **Backup** — archive contents, same-second collisions, prune-to-keep,
  policy due/not-due/disabled, restore replaces (not merges), export/
  import round-trip, unknown archives, malicious/foreign zips rejected.
- **Logging** — structured line shape, handler replacement, bus
  observer (scheduler vs runtime routing, idempotent attach, detach,
  publisher safety under forced failure), LogProvider.
- **Health** — all seven components OK on a fresh install; corrupted
  store file fails repositories with the file named.
- **Daemon runner** — bounded foreground run (banner, pid cleanup,
  policy backup taken), stop-file ends a live loop from another
  thread, observers built and detached, stale-PID detection, liveness
  probe on a real pid.
- **CLI** — init (create + idempotent adopt), health, the full backup
  cycle, daemon status, gui delegation (command inspected via an
  injected launcher), `--config` driving the data dir, missing config
  error, help listing.

Beyond the suite, the deliverables were verified **as a user would hit
them**: scratch venv → `pip install` → `paios` from a clean directory:
init, health (7×OK), backup now/list, daemon start/status/stop
(background, graceful), and `paios serve` answering HTTP with request
lines landing in the structured log.

## 11. Audit

| Check | Result |
| --- | --- |
| Architectural boundaries preserved | PASS — `paios.system` composes via the facade, the bus vocabulary, and the filesystem; nothing reaches into frozen internals. |
| No business logic outside existing layers | PASS — config/backup/health/runner are file ops, delegation, and diagnostics. |
| Frozen layers untouched | PASS — zero diffs across domain, runtime, scheduler, decision engine, learning, repositories, application, infrastructure, daemon, dashboard, notifications. |
| Sanctioned api change only | PASS — `server.py` `log_message` (mission deliverable); no route or behaviour changes. |
| Prior conventions followed | PASS — observer pattern for frozen-layer visibility, provider abstraction reused, CLI spec/stub convention, exception-tight observers. |
| Full regression | PASS — 794 passed, 1 skipped. |

## 12. Future improvements

- **Code-signed MSI/MSIX** — `install.ps1` is honest but unsigned;
  a real installer package would smooth SmartScreen and updates.
- **PyInstaller single-file launchers** — remove the Python
  prerequisite entirely.
- **Windows service** — the logon scheduled task approximates
  autostart; a proper service (or `sc.exe` wrapper) would survive
  logoff.
- **Log/metrics endpoint** — `GET /health` on the API mirroring
  `paios health` for remote monitoring (REST change → needs approval).
- **Backup encryption + off-machine targets** — the store is personal
  data; zip-at-rest is the minimum.
- **Config hot-reload** — today config is read at process start.

## 13. Suggested commit message

```
Milestone 16: Deployment - installer, launchers, daemon service,
config, logging, backups, health checks, packaging

- paios.system: config.yaml (stdlib YAML-subset), structured logging
  (per-surface rotating files; BusLogObserver + LogProvider observe
  frozen layers), BackupManager (auto policy + restore/export/import,
  validated archives), health checks (7 components), daemon process
  runner (pid/stop files, fg/bg, graceful stop, liveness probe)
- CLI: init / health / gui / daemon <run|start|stop|restart|status> /
  backup <now|list|restore|export|import>; --config option; flag >
  config > default precedence; serve composed with observers
- Packaging: installable pyproject (paios + paios_gui, console
  scripts), scripts/install.ps1 + uninstall.ps1 (venv, shim, dirs,
  first-run init, dependency check, optional daemon autostart),
  build_distribution.py producing the documented layout
- api/server.py: request lines to the structured log (sanctioned)
- Frozen layers: zero diffs; observers only
- Tests: 41 new (config, backup, logging, health, runner, CLI);
  suite 794 green + 1 guard skip; verified end-to-end from a scratch
  venv install with no PYTHONPATH
```

## Stop condition

Milestone 16 ends here. Awaiting review.
