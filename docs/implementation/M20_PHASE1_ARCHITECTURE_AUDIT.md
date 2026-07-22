# Milestone 20 — Phase 1 Architecture Audit

**Status: STOP condition triggered — awaiting owner approval before any implementation.**

Date: 2026-07-22. Audit performed against `main` @ `f2e54d5` (v2.1.0, Milestone 19 complete).

---

## 1. Scope and method

Full repository audit of: Domain, Application, Runtime, Scheduler, Decision Engine,
Learning Engine, REST API, Desktop GUI, Mobile App, Launcher, Installer, Updater,
AI Assistant, Notification System, Configuration, and implementation reports M1–M19.

Frozen layers (per baseline + stop condition): `domain/`, `runtime/`, `scheduler/`,
`decision_engine/`, `learning/`, `repositories/`, Application core.
Non-frozen: `api/`, `assistant/`, `notifications/`, `system/`, `infrastructure/`
(additive precedent G2), `cli/`, `dashboard/`, `daemon/`, frontends, launcher,
installer, scripts.

## 2. Layer-by-layer findings (condensed)

| Layer | State | Key facts |
|---|---|---|
| Domain | Frozen, complete | `Event` fields: category, description, project_id, start/end_time, `duration`, impact_type, `priority_alignment_score` (0–10), `resource_flow`, outcomes, transitions (`domain/entities/event.py:88-105`). **No** tags, deadline, recurrence, template, dependency fields. No delete (evidence philosophy); Archive is terminal. `ResourceType.ENERGY` exists (`domain/enums.py:126`). `Recommendation` carries `suggested_timing`, `priority`, `related_project_id`, `expected_benefit`, `confidence_score` (`domain/entities/recommendation.py:41-50`). |
| Application | Frozen core; additive-method precedent (M6 admit surfaces, M11 `scheduler_state`) | Facade has full lifecycle commands, `report_spontaneous_action` (`application.py:245`), CRUD-adds for goals/projects/resources/knowledge/reflections. **No** event create/edit/duplicate, no `plan()` query, no assistant integration. |
| Runtime | Frozen | `kernel.admit_recommendation` exists (M6 additive) — sanctioned admission path for externally created Recommendations. |
| Scheduler | Frozen | `_consume_accepted_recommendations` → `_materialize` honors `recommendation.suggested_timing` as `earliest_start` (`scheduler/scheduler.py:302-310`). Read surface: `state`, `plan` → `SchedulingPlan(entries: PlanEntry(event_id, planned_start, duration_minutes))` (`scheduler/plan.py:16-36`). **Planner is an injectable interface** (R3, `scheduler.py:100`, `planner.py`); default slot 60 min (`planner.py:21`). G8: never rejects recommendations. |
| Decision Engine | Frozen | Recommendations carry reason/priority/confidence — the raw material for "why" explanations. |
| Learning Engine | Frozen | Not implicated by M20. |
| REST API | Non-frozen, thin | 30 routes (`api/routes.py:356-410`). Events: GET list/detail + start/pause/resume/complete/cancel/archive only. **Missing:** event create/edit/delete/duplicate, templates, recurrence, dependencies, plan/timeline, inbox, assistant, backups. No auth (loopback-only), stdlib single-threaded server. |
| Desktop GUI | REST-only PySide6 | Lifecycle actions only; no create/edit; no search, log viewer, backup manager, wizard; F5/Ctrl+R/Ctrl+1–9/Ctrl+Q shortcuts exist (`main_window.py:123-135`). |
| Mobile | REST-only Flutter, Material 3 | Lifecycle actions only; no FAB, no swipe, no timeline screen, no offline cache; pull-to-refresh + unread badge exist. |
| Launcher | Non-frozen | Supervises daemon/api/gui as processes; tray with status; single instance; **no update-check logic anywhere**. |
| Installer | Non-frozen | Full install/uninstall step engine; upgrade = manual re-run of PAIOSSetup.exe. |
| Updater | **Does not exist** | No updater code in repo. |
| AI Assistant | Built but **orphaned** | `backend/paios/assistant/`: orchestrator + 14 explain/summarize tasks, Anthropic/OpenAI/Null adapters. Zero call sites outside its tests — not wired to Application, CLI, GUI, or REST. No NL→entities capability. |
| Notifications | Complete backend + frontends | `backend/paios/notifications/` (manager/providers/history); GUI watcher + mobile center. |
| Config | Non-frozen | `SystemConfig` YAML-subset at `<install>/config/config.yaml`; GUI config is CLI-flag-only, not persisted. No first-run concept. |
| Release hygiene | **Broken** | `pyproject.toml` says 1.7.0; latest tag is v2.0.0; commit log says v2.1.0; `CHANGELOG.md` is **empty**; `versions/` is **empty**; GitHub remote exists (`adsecurto-boop/PAIOS`) but no release process. The auto-updater's semantic-version check has no source of truth today. |

## 3. Architecture matrix

Legend: ✓ = exists, ◐ = partial, ✗ = missing, n/a = layer not applicable.
"Missing" column = smallest work needed.

| Feature | Domain | Application | REST | Desktop | Mobile | Missing |
|---|---|---|---|---|---|---|
| Create event (user-authored, future) | ✓ (via Recommendation) | ✗ | ✗ | ✗ | ✗ | Additive facade method + `POST /events` + UI |
| Create event (immediate action) | ✓ | ✓ `report_spontaneous_action` | ✗ | ✗ | ✗ | REST exposure + UI |
| Edit event | ✗ (immutable evidence) | ✗ | ✗ | ✗ | ✗ | Facade composition (cancel+recreate) + `PUT /events/{id}` + UI |
| Delete event | ✗ (by design) | ✗ | ✗ | ✗ | ✗ | Map to Archive in UX; no hard delete |
| Archive event | ✓ | ✓ | ✓ | ✓ | ✓ | UI polish only |
| Duplicate event | ✓ (read+create) | ✗ | ✗ | ✗ | ✗ | Facade composition + `POST /events/{id}/duplicate` + UI |
| Templates | ✗ | ✗ | ✗ | ✗ | ✗ | Infra store + `/templates` REST + UI (Domain untouched) |
| Recurring events | ✗ | ✗ | ✗ | ✗ | ✗ | Infra store + expansion service + `/recurrences` REST + UI |
| Dependencies | ✗ | ✗ | ✗ | ✗ | ✗ | Sidecar metadata + custom Planner (R3 seam) + UI |
| Estimated duration | ✓ `duration` | ◐ (not settable by user) | ✗ | ✗ | ✗ | Via sidecar → custom Planner (default 60 min today) |
| Deadline | ✗ | ✗ | ✗ | ✗ | ✗ | Sidecar metadata + Planner ordering hint + UI |
| Energy | ◐ `resource_flow`, `ResourceType.ENERGY` | ◐ | ✗ | ✗ | ✗ | Sidecar metadata (display/AI only) + UI |
| Priority | ✓ `priority_alignment_score`, `Recommendation.priority` | ◐ | ✗ | ✗ | ✗ | Expose via create path + UI |
| Tags | ✗ | ✗ | ✗ | ✗ | ✗ | Sidecar metadata + UI |
| Planning Workspace (NL → proposal) | n/a | ✗ | ✗ | ✗ | ✗ | Assistant task + `/assistant/plan` + planning page |
| Inbox / Quick Capture | ✗ (deliberately) | ✗ | ✗ | ✗ | ✗ | Infra store + `/inbox` REST + UI (Domain untouched) |
| Timeline data (plan) | n/a | ✗ (`scheduler.plan` unexposed) | ✗ | ✗ | ✗ | Additive `plan()` query (M11 precedent) + `GET /plan` + UI |
| Today/upcoming/overdue/ready buckets | n/a | ◐ | ◐ `/dashboard` only | ◐ | ◐ | Derive in UI from `/events` + `/plan` |
| Drag-and-drop reschedule | ✗ | ✗ | ✗ | ✗ | ✗ | Backend does not support user rescheduling (Scheduler is sole authority; plan is rebuilt each cycle). Documented as unsupported; "pin" hint via sidecar + Planner is optional stretch |
| Countdown / progress / live updates | n/a | n/a | ✓ (poll) | ✗ | ✗ | Pure UI on existing polling |
| "Plan My Day" + WHY explanations | n/a | ✗ | ✗ | ✗ | ✗ | Assistant wiring + `/assistant/*`; reasons come from Recommendation.reason/priority/confidence — never from AI inventing schedule |
| AI providers config | n/a | n/a | n/a | ✗ | n/a | Wizard + `SystemConfig` keys (adapters already exist) |
| Dashboard search | n/a | n/a | ✓ (GETs suffice) | ✗ | n/a | UI only |
| Log viewer | n/a | n/a | n/a (local files) | ✗ | n/a | UI only |
| Backup manager | n/a | ✓ `system/backup.py` (CLI only) | ✗ | ✗ | n/a | `/backups` REST wrapper + UI |
| Keyboard shortcuts | n/a | n/a | n/a | ◐ | n/a | Extend |
| Mobile FAB / swipe / offline cache / adaptive | n/a | n/a | ✓ | n/a | ✗ | UI only |
| Auto updater (PAIOSUpdater.exe) | n/a | n/a | n/a | ✗ | n/a | New isolated component + launcher check + release hygiene fix |
| First-run wizard | n/a | n/a | n/a | ✗ | ✗ | UI + config persistence |
| Product polish (animations, empty states, a11y…) | n/a | n/a | n/a | ✗ | ✗ | UI only |

## 4. Stop condition — exact reasoning

The stop condition fires on two independent grounds:

1. **Missing REST endpoints.** Event create/edit/duplicate, templates, recurrence,
   dependencies, metadata, inbox, plan/timeline, assistant, and backups have no
   endpoints. The API layer is not frozen, but the brief requires stopping to
   propose additions rather than inventing them silently.
2. **Application-core additions are unavoidable.** Every event-management path
   requires at least additive methods on the `Application` facade (the only legal
   gateway to kernel/scheduler). Additive facade methods have per-milestone
   approval precedent (M6 admission surfaces, M11 `scheduler_state`), but the
   M20 stop list names "Application core", so approval is required first.

**No frozen-layer *modification* is proposed.** Everything below is additive.

## 5. Smallest additive architecture proposal

### 5.1 Core insight — user intents are Recommendations (zero frozen changes)

The frozen pipeline already contains a complete "external intent → scheduled
event" path:

> construct `Recommendation` (domain factory, uuid5 over intent content) →
> `kernel.admit_recommendation` (M6 additive surface) → user/auto **accept** →
> Scheduler `_consume_accepted_recommendations` → `_materialize` honors
> `suggested_timing`, `priority`, `related_project_id`, `expected_benefit` →
> Event is Scheduled and enters the SchedulingPlan.

A new additive facade method `propose_user_event(...)` composes exactly these
existing calls. The Scheduler remains the only authority that turns intent into
a scheduled Event (G1); it never rejects (G8); the Decision Engine is not
bypassed — user intents simply join its recommendations in the same admission
stream. "Create event now" maps to the existing `report_spontaneous_action`.

Known accepted limitation (frozen `_materialize`): materialized events get
`category="recommendation"` and `description=recommendation.reason` — the user's
title lives in `reason`, category/tags in the sidecar (5.3). Recorded as tech
debt, not worth unfreezing.

### 5.2 New non-frozen module `backend/paios/planning/`

Application-adjacent, imports only the facade + infrastructure stores (same
dependency posture as `api/`). Contains:

- **InboxStore** — JSON-file store of inbox items (id, text, created_at, status).
- **EventMetadataStore** — sidecar keyed by `event_id` (and by intent id before
  materialization): tags, deadline, energy, estimated_duration_minutes,
  depends_on. Domain aggregates never see it; frontends and the AI read it.
- **TemplateStore / RecurrenceStore** — named event templates; recurrence rules
  (RRULE-subset) whose expansion calls `propose_user_event` — expansion is
  triggered from the API layer on `/tick` (non-frozen), never from inside
  Scheduler/Runtime.
- **MetadataPlanner** — implements the existing `Planner` interface (R3 seam,
  injected via the existing `Scheduler(kernel, planner=...)` constructor
  parameter at composition time): applies per-event estimated durations,
  orders by deadline pressure, and defers dependents until prerequisites
  complete. The Scheduler core is untouched; only its sanctioned plug point
  is used.

### 5.3 Required REST additions (complete list)

| # | Method + path | Delegates to | Serves |
|---|---|---|---|
| 1 | `POST /events` | new additive `app.propose_user_event` (5.1); `mode:"now"` → existing `report_spontaneous_action` | Create |
| 2 | `PUT /events/{id}` | new additive facade composition: cancel(reason="edited") + re-propose | Edit |
| 3 | `POST /events/{id}/duplicate` | read + `propose_user_event` | Duplicate |
| 4 | `GET/PUT /events/{id}/metadata` | EventMetadataStore | Tags, deadline, energy, duration, dependencies, priority display |
| 5 | `GET /plan` | new additive read-only `app.plan()` (mirror of M11 `scheduler_state`) | Timeline |
| 6 | `GET/POST /templates`, `POST /templates/{id}/instantiate`, `DELETE /templates/{id}` | TemplateStore | Templates |
| 7 | `GET/POST /recurrences`, `DELETE /recurrences/{id}` | RecurrenceStore | Recurring events |
| 8 | `GET/POST /inbox`, `POST /inbox/{id}/convert`, `POST /inbox/{id}/archive`, `DELETE /inbox/{id}` | InboxStore (+ existing `/goals`, `/projects`, #1 on convert) | Inbox/Quick Capture |
| 9 | `POST /assistant/plan` (text → structured Planning Proposal; **no side effects**), `POST /assistant/explain-day`, `GET /assistant/status` | AssistantOrchestrator (2 new prompt templates: ClassifyCapture, ExplainDayPlan) | Planning Workspace, Plan My Day |
| 10 | `GET /backups`, `POST /backups`, `POST /backups/restore` | existing `system/backup.BackupManager` | Backup manager UI |

Notes: `DELETE /events/{id}` is deliberately **not** proposed — the Domain has no
deletion by design; UX presents Archive as removal. Drag-and-drop rescheduling is
**documented as unsupported** (Scheduler authority); the timeline is read + lifecycle
actions.

### 5.4 Frontends, updater, wizard (no backend impact beyond the above)

- Desktop: Planning page (landing), Inbox, Event Manager dialogs, Timeline
  (Today/Tomorrow/Week/Agenda from `/plan` + `/events`), dashboard polish, search,
  log viewer, backup manager, expanded shortcuts, first-run wizard persisting to
  `config.yaml` + a `first_run_complete` marker.
- Mobile: same features Material-3-polished (FAB, swipe, offline cache of last
  payloads, adaptive layouts, timeline cards).
- **PAIOSUpdater.exe**: new top-level `updater/` package — imports **nothing** from
  `paios.*` (stdlib only): GitHub Releases API → semver compare → release notes →
  download + SHA256 verify → stop via launcher sentinel → backup → install →
  health check → rollback on failure → restart. Launcher gains a periodic
  check + tray notification + "Update now" (spawns updater, exits).
- **Release hygiene (prerequisite for updater):** bump `pyproject.toml` to
  `2.2.0`, backfill `CHANGELOG.md`, tag releases, publish GitHub Releases with
  `PAIOSSetup.exe` + `.sha256` files; `scripts/build_installer.py` gains checksum
  + release-notes emission.

## 6. Approval requested

1. Additive `Application` facade methods: `propose_user_event`, edit/duplicate
   compositions, read-only `plan()` (5.1, 5.3).
2. New non-frozen `backend/paios/planning/` module + stores + `MetadataPlanner`
   injected through the existing R3 constructor seam (5.2).
3. REST additions #1–#10 (5.3).
4. Explicit non-goals: no hard delete, no drag-and-drop rescheduling, no
   `_materialize` changes (5.3 notes).
5. Version bump to 2.2.0 + release hygiene (5.4).

No code will be written until these are approved.
