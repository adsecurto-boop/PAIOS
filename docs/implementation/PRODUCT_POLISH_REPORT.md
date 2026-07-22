# PRODUCT POLISH REPORT — Milestone 20

**Version 2.2.0 · 2026-07-22 · Phases 1–5 complete · 1,114 tests passing (1 documented skip)**

Milestone 20 turns PAIOS from a powerful backend with admin frontends
into a daily operating system: a conversational Planning Workspace as
the landing experience, Quick Capture, a full Event Manager, a live
Timeline, grounded AI explanations, a standalone auto-updater, a
first-run wizard, and a product-wide polish pass — all without touching
a single frozen layer.

---

## 1. Architecture matrix (updated, end of M20)

Legend: ✓ done · ◐ partial by design · ✗ not built (see §7/§8).

| Feature | Domain | Application | REST | Desktop | Mobile | Notes |
|---|---|---|---|---|---|---|
| Create event (planned) | ✓ via Recommendation | ✓ `propose_user_event` (additive) | ✓ POST /events | ✓ | ✓ | Scheduler materializes; API/AI never schedule |
| Create event (now) | ✓ | ✓ (pre-existing `report_spontaneous_action`) | ✓ POST /events mode=now | ✓ | ✓ | |
| Edit event | ✓ (cancel+recreate composition) | ✓ `edit_event` | ✓ PUT /events/{id} | ✓ | ✓ | Returns NEW event id; audit reason on the cancelled original |
| Delete event | ◐ by design | — | — | ◐ Archive-as-removal | ◐ | Domain keeps evidence; UX presents Archive with explanation |
| Archive / Duplicate | ✓ | ✓ | ✓ | ✓ | ✓ | Duplicate copies sidecar metadata |
| Templates | n/a (planning store) | n/a | ✓ /templates CRUD + instantiate | ✓ manager dialog | ✓ | Domain untouched |
| Recurring events | n/a (planning store) | n/a | ✓ /recurrences + /tick expansion | ✓ manager dialog | ◐ read/instantiate | Expansion = intents through the same pipeline |
| Dependencies / Deadline / Duration / Energy / Tags | n/a (sidecar) | n/a | ✓ /events/{id}/metadata | ✓ event form | ✓ event form | MetadataPlanner (R3 seam) applies duration/deadline/dependencies to the plan |
| Priority | ✓ `Recommendation.priority` | ✓ | ✓ | ✓ | ✓ | |
| Planning Workspace | n/a | n/a | ✓ /assistant/plan | ✓ landing page | ✓ first destination | Conversational capture → proposal cards → approve → REST |
| Inbox / Quick Capture | n/a (planning store) | n/a | ✓ /inbox + convert | ✓ | ✓ | AI kind suggestions auto-appear; offline heuristic fallback |
| Timeline | n/a | ✓ `plan()` (additive read) | ✓ GET /plan | ✓ NOW/countdown/progress | ✓ NOW card | Today/Tomorrow/Week/Agenda |
| Drag-and-drop reschedule | ✗ by design | — | — | ◐ visible reason | ◐ visible reason | "Schedule is controlled by the PAIOS Scheduler" shown, never silent |
| Plan My Day / Explain / Review Today | n/a | n/a | ✓ /assistant/plan, /assistant/explain-day | ✓ | ✓ | WHY grounded in Recommendation + plan + sidecar facts; deterministic offline path |
| Search / Log viewer / Backup manager | n/a | ✓ `system/backup` (pre-existing) | ✓ /backups | ✓ | n/a | |
| Keyboard shortcuts | — | — | — | ✓ Ctrl+N/I/P/F + existing | n/a | |
| Auto-updater | isolated `updater/` | — | — | tray toast + consent dialog | n/a | SHA256, backup, rollback, restart; zero paios imports (AST-enforced) |
| First-run wizard | — | — | — | ✓ (once; incl. Planning Style) | n/a | Persisted to %APPDATA%/PAIOS/gui-settings.json |
| Offline cache | — | — | — | n/a | ✓ shared_preferences | Renders cached dashboard/events/plan/inbox under offline banner |
| Mobile M3 polish | — | — | — | — | ✓ | FAB, swipe, adaptive nav (bottom bar < 600dp / rail + drawer) |

**Frozen-layer verdict: zero modifications.** Domain, Runtime,
Scheduler, Decision Engine, Learning, Repositories untouched. The only
Application-layer changes are the four approved additive façade methods
plus two additive composition knobs (`ApplicationConfig.planner`
threaded through the Scheduler's pre-existing R3 constructor
parameter). Guard tests were updated to encode the approved M20
contract explicitly.

## 2. Missing-capability matrix (deliberate non-goals)

| Capability | Status | Why |
|---|---|---|
| Hard event deletion | Not built | The Domain records evidence and has no deletion; Archive is the removal UX, and both frontends say so in the confirm dialog |
| Drag-and-drop rescheduling | Not built | The Scheduler is the sole scheduling authority and rebuilds the plan each cycle; both timelines show "Schedule is controlled by the PAIOS Scheduler" instead of a dead control |
| Editing a Started/Completed event | Rejected with 409 | Edits compose cancel+re-propose; the Domain forbids cancelling terminal states — surfaced as a friendly error |
| User category on materialized events | Tech debt | Frozen `_materialize` sets `category="recommendation"`; the title lives in the description, kinds/tags in the sidecar (§7) |
| Recommendation create via REST | Not needed | `/tick` (engine) and `POST /events` (user intents) cover both sources |

## 3. New REST endpoints

All additive; full reference in `docs/implementation/API.md`.

1. `POST /events` · `PUT /events/{id}` · `POST /events/{id}/duplicate`
2. `GET/PUT /events/{id}/metadata` (tags, deadline, energy, duration, depends_on)
3. `GET /plan`
4. `GET/POST /templates`, `DELETE /templates/{id}`, `POST /templates/{id}/instantiate`
5. `GET/POST /recurrences`, `DELETE /recurrences/{id}` (+ expansion on `POST /tick`, which now returns `recurrences_expanded`)
6. `GET/POST /inbox`, `POST /inbox/{id}/convert|archive`, `DELETE /inbox/{id}`
7. `GET /assistant/status`, `POST /assistant/plan`, `POST /assistant/explain-day` (proposal/explanation only — no side effects)
8. `GET/POST /backups`, `POST /backups/restore`

Transport additions: `do_PUT`/`do_DELETE` on the stdlib server;
`PlanningStoreError`→404/400 and `BackupError`→400 in the error map.

## 4. Screenshots — before vs after

Captured from the real application against a live API server
(`docs/implementation/screenshots/m20/`):

| Before (M19, from commit f2e54d5) | After (M20) |
|---|---|
| `desktop-dashboard-before-m19.png` — Dashboard-first, 11 table-centric nav entries | `desktop-planning.png` — conversational Planning landing page |
| `desktop-events-before-m19.png` — events as a table with lifecycle buttons | `desktop-events.png` — card board under date headers, status chips, full authoring |
| (no equivalent existed) | `desktop-timeline.png` — NOW card, countdown, progress, buckets |
| (no equivalent existed) | `desktop-inbox.png` — Quick Capture with AI suggestions |
| (no equivalent existed) | `desktop-backups.png`, `desktop-logs.png` |
| — | `desktop-dashboard.png` — polished M20 dashboard |

Mobile screenshots require the Flutter SDK (absent on this machine — §7).

## 5. UX improvements (the "daily OS" pass)

- **Landing experience**: Planning Workspace opens first on both apps — type a brain-dump, get classified proposal cards (kind, priority, duration, the WHY, inline clarification questions), edit, approve; only then does anything hit REST, and only the ordinary endpoints.
- **Zero-friction capture**: single Enter captures to Quick Capture; AI kind suggestions appear automatically with one-click "Convert as suggested"; offline the deterministic classifier answers instead of failing.
- **Honest affordances**: no silent missing features — drag-and-drop shows its reason; Archive explains it is the removal; edit explains recreation; backup restore explains the restart.
- **Live time**: NOW cards with countdowns and progress bars on both platforms (display-only ticking; server data stays authoritative).
- **Fewer clicks**: Ctrl+Enter proposes, Ctrl+N new event, Ctrl+I capture, Ctrl+P planning, Ctrl+F search; mobile gets FAB + swipe (archive/delete-with-confirm) + pull-to-refresh everywhere.
- **Consistency & forgiveness**: shared card/chip/hover styles, busy indicators during calls, friendly empty states on every new screen, confirmation dialogs on every destructive action, error snackbars with retry.
- **Update flow that never interrupts**: toast → optional consent dialog (release notes, Update Now / Later) → hand-off to PAIOSUpdater.exe → automatic backup/rollback → restart.
- **First-run wizard** (once): backend URL with live connection test, refresh, work hours, notifications, AI provider status, theme, planning style.

## 5a. Final UX walkthrough (mandated six-question review)

Every screen was walked through as a first-time user (primary action?
one obvious path? fewer clicks possible? communicates what PAIOS is
doing? explains why? daily-OS feel?). Resulting changes, verified in
the final screenshots:

- **Desktop Planning = the Today Home**: opens to "Good Evening." +
  a TODAY'S FOCUS card (running event with progress, else
  "<title> — starts in N minutes" with a live countdown) + a Next
  entry with "Recommended because:" bullets from the grounded
  explain-day reasons, then the single capture box (autofocused,
  placeholder "What do you want to accomplish today?") with **Plan
  it** as the one accented action (`desktop-planning.png`).
- **Desktop Timeline**: vertical NOW → next flow with HH:MM–HH:MM
  ranges, elapsed bars, "Up next in H:MM:SS" ticking live, and the
  footer "Schedule is controlled by the PAIOS Scheduler —
  drag-and-drop rescheduling is not available; edit an event to
  change its intent." (`desktop-timeline.png`).
- **Mobile opens on "Today"** (destination renamed from Planning):
  greeting + Today's Focus + Up Next reasons above the capture
  input; the bottom-bar Capture destination lands with the input
  focused — one tap means typing.
- Cheap wins fixed across pages: capture autofocus (both apps),
  countdown/progress logic extracted into shared widgets instead of
  duplicated, Events empty state teaches Ctrl+N, admin-style lists
  demoted behind More/drawer on mobile.
- Screens already passing the review unchanged: Events card board
  (one state-appropriate primary button per card), Backups (restore
  confirm explains the restart), Logs (empty state explains
  --log-dir), Wizard (explains the heuristic AI fallback),
  Recommendations (Accept primary + reason text).

## 6. Production verification (real processes, not fakes)

| Check | Result |
|---|---|
| Full test suite (`python -m pytest tests/`) | **1,114 passed, 1 documented skip** (final run after the UX pass) — domain, runtime, scheduler, DE, learning, application, API (incl. 30+ new M20 endpoint tests), planning, assistant, CLI, daemon, GUI (100), launcher (54), installer (33), updater (23), system, notifications |
| Real HTTP server (`python -m paios.api`, fresh store) | Booted; `POST /events` → Recommendation Consumed → Event materialized → `GET /plan` entry; sidecar metadata honored by the MetadataPlanner on recalculation (60 → 20 min observed live) |
| Full endpoint walk over the wire | duplicate (metadata copied), inbox add/convert, `/assistant/plan` (heuristic source, correct kinds + day scope), `/assistant/explain-day` (grounded reasons: "priority 2; low energy task"), templates, recurrences (next_run advanced), backups created |
| Desktop ↔ API integration | Real `MainWindow` + real `ApiClient` against the live server, offscreen: 16 pages, refresh, plan/inbox/proposal reads — `GUI SMOKE OK` |
| Updater against real GitHub | `--check-only` exits cleanly with "Cannot read releases … 404" — correct behavior while no Release is published yet |
| Updater pipeline correctness | Proven by fakes in tests: checksum mismatch aborts BEFORE stop/backup; installer failure and failed health check both roll back to the previous install |
| Product build (`scripts/build_installer.py`) | PAIOS.exe (~40 MB), PAIOSUpdater.exe (~9 MB), PAIOSSetup.exe with wheel 2.2.0 + both exes in payload, `SHA256SUMS.txt`, `RELEASE_NOTES.md` extracted from the changelog |
| Flutter | Implemented + tests written; **not executed — no Flutter/Dart SDK on this machine** (verified: absent from PATH and standard locations) |

## 7. Remaining technical debt

1. **Flutter tests unexecuted here**: run `flutter test` (and `flutter test --update-goldens test/golden_test.dart` once — layout changed) on a machine with the SDK before shipping mobile.
2. **Materialized event category**: frozen `_materialize` labels user events `category="recommendation"`. Cosmetic; a one-line frozen change if ever approved.
3. **No GitHub Release published yet**: the update loop is live but dormant until `v2.2.0` is tagged and a Release carries `PAIOSSetup.exe` + `SHA256SUMS.txt` (both emitted by the build).
4. **Updater does not self-update** (Windows file locking); it updates PAIOS, not itself — a newer updater arrives via the installer payload.
5. **Context bootstrap**: a brand-new store has no Context, so intents defer (G8) until one exists; the installer's `paios init` covers real installs, but a REST-created context would remove the CLI dependency.
6. **Assistant providers unconfigured by default**: heuristics answer everywhere; set `PAIOS_AI_PROVIDER=anthropic|openai` (+ SDK key env) to enable LLM proposals.
7. **Dashboard payload double-fetch** on desktop (notification watcher + page) — harmless, coalescable later.

## 8. Future roadmap (not started — M21+ candidates, pending approval)

- Publish v2.2.0 GitHub Release; optional CI (pytest + flutter test + build).
- REST context creation + richer onboarding seed data.
- Approved frozen touch-up: user category/duration on `_materialize`.
- Pin-hint rescheduling through a Planner extension (keeps Scheduler authority).
- WebSocket/push channel to replace polling.

## 9. Suggested commit message

```
v2.2.0 - Milestone 20: Product Polish & Daily Planning Experience

Planning Workspace (conversational landing page on desktop + mobile),
Quick Capture inbox with AI suggestions, full Event Manager (create/
edit/duplicate/archive, templates, recurrences, dependencies/deadline/
duration/energy/tags via planning sidecar), live Timeline (NOW,
countdown, progress, Today/Tomorrow/Week/Agenda), grounded AI planning
(propose/explain-day with deterministic offline fallback), standalone
PAIOSUpdater.exe (GitHub Releases, semver, SHA256, backup/rollback)
with launcher update checks and consent dialog, first-run wizard,
Material 3 mobile polish with offline cache, release hygiene (2.2.0
single-sourced, CHANGELOG, SHA256SUMS + release notes in the build).

Frozen layers untouched: user events ride the existing Recommendation
-> Scheduler pipeline via approved additive facade methods and REST;
MetadataPlanner injects through the Scheduler's R3 seam.

1114 tests passing (1 documented skip).
```

---

*Milestone 20 complete. Stopping here per the mission's stop condition —
Milestone 21 will not begin without explicit review and approval.*
