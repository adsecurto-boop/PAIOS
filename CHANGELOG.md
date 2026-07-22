# Changelog

All notable changes to PAIOS. Versions follow semantic versioning; the
version in `pyproject.toml` / `paios.__version__` is the source of truth
and is what GitHub Release tags must match (`v<version>`).

## [2.2.0] — 2026-07-22 — Milestone 20 "Product Polish & Daily Planning"

### Added
- Planning module (`backend/paios/planning/`): Inbox, Event Templates,
  Recurrences, Event Metadata sidecar (tags/deadline/energy/duration/
  dependencies), Planning Proposals and intent processing.
- User-authored events: intents ride the existing Recommendation →
  Scheduler materialization pipeline (Scheduler remains the only
  scheduling authority).
- Additive Application façade methods: `propose_user_event`,
  `edit_event`, `duplicate_event`, `plan()`.
- REST: `POST /events`, `PUT /events/{id}`, `POST /events/{id}/duplicate`,
  `/events/{id}/metadata`, `GET /plan`, `/templates`, `/recurrences`,
  `/inbox`, `/assistant/*`, `/backups`.
- AI Assistant wired to REST (proposal + explanation only, never mutation):
  capture classification and day-plan explanation tasks.
- Desktop: Planning landing page, Inbox, full Event Manager, interactive
  Timeline (Today/Tomorrow/Week/Agenda), search, log viewer, backup
  manager, first-run wizard, expanded shortcuts, dashboard polish.
- Mobile: planning/inbox/timeline screens, FAB, swipe actions, offline
  cache, Material 3 polish, adaptive layouts.
- Auto-update: standalone `PAIOSUpdater.exe` (GitHub Releases, semver,
  SHA256 verify, backup/rollback) + periodic update checks in PAIOS.exe.
- Release hygiene: version single-sourced (2.2.0), SHA256 checksum and
  release-notes emission in the installer build.

### Unsupported by design
- Hard event deletion (Domain records evidence; Archive is the removal UX).
- Drag-and-drop rescheduling (the Scheduler is the sole scheduling
  authority and rebuilds the plan each cycle).

## [2.1.0] — 2026-07-22 — Milestone 19 "Productization"

- Product launcher (`PAIOS.exe`): process supervision of daemon + API +
  GUI, system tray with status, single-instance guard, crash reports.
- Windows installer (`PAIOSSetup.exe`): venv layout, wheel install,
  shortcuts, HKCU Run registration, optional logon task, uninstaller.
- PyInstaller build pipeline (`scripts/build_installer.py`).

## [2.0.0] — 2026-07-22 — Milestones 13–18

- Native desktop dashboard (PySide6, REST-only).
- Mobile companion app (Flutter, REST-only).
- AI Assistant package (explain/summarize tasks; Anthropic/OpenAI/Null
  adapters).
- Deployment tooling, backups, system config, notifications.
- Production readiness audit (858 tests passing).

## [1.0.0] — 2026-07-21 — Milestones 10–12

- Terminal dashboard and read-only monitoring interface.
- REST API over the Application façade (`paios serve`).
- CLI shell (`paios shell`).

## [0.9.0] — 2026-07-21 — Milestone 9

- Runtime daemon / timer engine: drift-free continuous execution.

## [0.5.0] — 2026-07-21 — Milestones 4–8 (tag `architecture-consistent-v0.5`)

- Scheduler, Decision Engine, Application layer, Learning Engine, ADR-003
  consistency resolution.

## [0.1.0] — 2026-07-20 — Milestones 1–2

- Frozen Domain layer (12-state Event lifecycle, one Event aggregate).
- Repository layer with aggregate reconstitution (JSON persistence).
