# Milestone 13 — Desktop Dashboard (GUI)

## Mission

Build the first graphical desktop interface for PAIOS. The GUI is
presentation only: it never contains business logic, never bypasses the
REST API, and never bypasses the Application layer. The REST API is now
the only backend entry point.

## 1. Architecture

### Framework choice: Qt via PySide6 (justified)

The mission's preferred order is Tauri, Qt (PySide6), Electron. Judged
against the four required criteria:

| Criterion | Tauri | **PySide6 (chosen)** | Electron |
| --- | --- | --- | --- |
| Architecture | Adds a Rust core + a JS web frontend — two new languages around a pure-Python system; the UI itself would be a web app | One language across the whole repo; native widgets speaking HTTP through one small client class | Adds Node + a web frontend; the UI is a browser |
| Maintainability | Rust toolchain + npm ecosystem to keep current | One pip dependency (`PySide6-Essentials`); same test runner, same style, same review process as the backend | npm dependency tree churn |
| Deployment | Requires Rust + Node toolchains to build (neither exists in this environment); per-OS bundling pipeline | `pip install PySide6-Essentials` and `python -m paios_gui` — no build step at all | Ships an entire Chromium per app (~200 MB) |
| Resource usage | Light (system webview) but still a browser runtime | Native widgets, no embedded browser, tens of MB of RAM | Heaviest option: full Chromium + Node per instance |

Tauri's lightness could not outweigh introducing two foreign toolchains
(both absent here) into a repo whose every prior milestone is plain
Python; Electron loses on every criterion but familiarity. PySide6 is
the smallest step that yields a real native desktop app. It is the
project's **first third-party runtime dependency, confined to the GUI
tier** — the backend (`backend/`) remains stdlib-only.

### Package: `frontend/desktop/paios_gui/` — a separate tier

| Module | Responsibility |
| --- | --- |
| `config.py` | `GuiConfig`: base URL, refresh interval (runtime-adjustable), request timeout. |
| `client.py` | The REST client — the GUI's single doorway into PAIOS. Stdlib `urllib`; one method per endpoint; failures become `ApiUnreachable` (server down) or `ApiResponseError` (status + the API's error type/message). |
| `theme.py` | Dark mode: Fusion style, dark palette, one static stylesheet. No animations. |
| `format.py` | String formatters (ISO → clock time, minutes, percent). |
| `widgets.py` | `Section` (titled dashboard card), `NoticeLog` (Notifications feed). |
| `dialogs.py` | One form per action needing input; `values()` is separate from `exec()` so tests drive forms without an event loop. |
| `dashboard_page.py` | The TODAY view: all mission sections rendered from REST payloads; pure payload→lines builders. |
| `pages.py` | Navigation pages: tables over list endpoints + page-local actions; Settings (refresh interval). |
| `main_window.py` | Navigation, poll timer, manual refresh, offline banner, status bar, keyboard shortcuts, `run_action` (one REST call per action + outcome notice). |
| `app.py` / `__main__.py` | `python -m paios_gui [--url U] [--refresh N]`. |

Run it: start the backend with `paios serve`, then `python -m paios_gui`
(from `frontend/desktop/`, or with it on `PYTHONPATH`). Install the GUI
dependency with `pip install -r frontend/desktop/requirements.txt`.

## 2. Dependency graph

```
Desktop GUI (paios_gui — imports: stdlib + PySide6 only)
    │  main_window / pages / dashboard_page / dialogs (widgets)
    │        │
    │  client.py  (urllib; the ONLY module that performs I/O)
    ▼
HTTP  ──────────  the process boundary
    ▼
REST API (paios.api, M12)
    ▼
Application facade
    ▼
Runtime / Scheduler / Decision Engine / Learning / Repositories
```

The GUI imports **nothing from `paios`** — not even exception or enum
types (the M12 API allowed parsing-type imports; the GUI is stricter
because HTTP is a process boundary: enum values appear as string
literals mirroring the REST contract, errors arrive as JSON). It knows
nothing about the Runtime, Scheduler, Decision Engine, Learning, JSON
files, or repositories — all AST-test-enforced, including "no file
access" and "urllib confined to client.py".

### One API addition (transport, not GUI, code)

"Report Disturbance" had no endpoint — M12 explicitly listed disturber
reporting as a future client-milestone addition. M13 adds
**`POST /disturbers`** to `paios.api` following M12's exact conventions
(one facade delegation → `Application.report_disturber`, enum-by-value
parsing, 201 + serialized disturber). The API remains the only backend
entry point; the GUI calls the endpoint like any other.

## 3. UI layout

Dark, minimal, no animations. The dashboard is a scrollable two-column
card grid under a TODAY header, an offline banner above, a footer line
below — every mission section present:

| Section | Data (REST) |
| --- | --- |
| Time | `/dashboard` `current_time` |
| Status | `system` (kernel, scheduler, decision engine, operational, snapshot) |
| Current Event | `current_event` (elapsed/remaining) + Pause / Complete / Cancel buttons |
| Current Context | `current_context` (execution context, reason, since, window) |
| Today's Goals | `goals` (Active first) |
| Today's Projects | `projects` (+ progress %) |
| Recommendations | `recommendations` + per-row Accept / Reject buttons |
| Deep Work | `today` (completed / running / upcoming counts and blocks) |
| Health | `health` (Health/Energy/Stress resources + habits) |
| Resources | `/resources` (all resources, values, units, updated) |
| Study | `learning.last_studied`, `learning.revised_today` |
| Learning | `learning.latest_insight` |
| Recent Reflections | `/reflections` (latest three) |
| Disturbers | `active_disturbers` + "Report disturbance…" button |
| Notifications | GUI notice feed: action outcomes and connection changes (presentation state, color-coded) |
| Footer | server URL · online/OFFLINE · refresh interval · last data time · shortcut hints |

Responsive: the grid stretches both columns equally, cards word-wrap,
tables stretch their last column, everything sits in scroll areas.
Rendering was verified visually (offscreen capture of dashboard, Events,
Settings, and the offline state) — two real defects found and fixed
during that pass: deferred-deleted labels ghost-painting over fresh text
after refresh, and grid rows squashing card text below its size hint.

## 4. Navigation

Left rail (nav list): **Dashboard, Goals, Projects, Events, Resources,
Knowledge, Learning, History, Settings, Refresh** — the mission's ten
entries. Refresh is an action row: it re-polls and bounces back to the
current page. Every page refreshes on entry and on every poll tick.

- **Goals** — table + New goal…
- **Projects** — table + New project…, Update progress…
- **Events** — table + Start, Pause, Resume, Complete…, Cancel…, Reflect…
- **Resources / Knowledge** — read-only tables
- **Learning** — learning summary (from `/dashboard`) + reflections table
- **History** — terminal-state events (Completed/Cancelled/Archived/…) with their full transition chains
- **Settings** — refresh interval spinbox (applies immediately to the poll timer), server URL, shortcut list

Keyboard: **F5 / Ctrl+R** refresh · **Ctrl+1…Ctrl+9** pages · **Ctrl+Q**
quit.

Polling: a `QTimer` at the configured interval (default 5 s, clamped
1–3600, adjustable at runtime) plus the manual refresh entry/shortcuts.
Requests are synchronous with a 2 s timeout — a deliberate choice: the
API is a localhost transport and M12's server is single-threaded by
design, so a worker-thread pipeline would add complexity with no
latency to hide; the timeout bounds the worst case.

## 5. REST usage — every action is exactly one endpoint

| GUI action | REST call |
| --- | --- |
| Accept recommendation | `POST /recommendations/{id}/accept` |
| Reject recommendation | `POST /recommendations/{id}/reject` |
| Start event | `POST /events/{id}/start` |
| Pause event | `POST /events/{id}/pause` |
| Resume event | `POST /events/{id}/resume` |
| Complete event | `POST /events/{id}/complete` |
| Cancel event | `POST /events/{id}/cancel` |
| Create goal | `POST /goals` |
| Create project | `POST /projects` |
| Update progress | `POST /projects/{id}/progress` |
| Create reflection | `POST /reflections` |
| Report disturbance | `POST /disturbers` *(added this milestone)* |

Reads: `GET /dashboard`, `/goals`, `/projects`, `/events`, `/resources`,
`/knowledge`, `/reflections`, `/recommendations`, `/status`. All
actions flow through `MainWindow.run_action`: one call, outcome notice,
then re-poll.

## 6. Error handling

| Failure | Behaviour |
| --- | --- |
| Connection lost / server unavailable | Red **OFFLINE** banner ("retrying every Ns"), one notice per outage, last data stays visible, poll timer keeps retrying; reconnect flips the banner off with a "Connected" notice |
| Validation failure (400/404/409/…) | The API's own error message + type in the status bar and Notifications; view unchanged |
| Server error during a read | Notice; last rendered data kept; polling continues |
| Any of the above | Never an exception out of `refresh_now`/`run_action` — no crashes |

## 7. Tests

`tests/gui/` — 24 tests; plus 2 new API tests; full suite **697 passed**
(671 regression + 26 new). GUI tests run the real stack end to end:
seeded store → Application → `ApiServer` on an ephemeral port (background
thread) → HTTP → `ApiClient` → offscreen-rendered widgets.

- **REST integration** (`test_client.py`) — dashboard/list reads; goal +
  project + progress; full event lifecycle driven purely through REST
  (tick → accept → start → pause → resume → complete → reflect);
  reject; report disturbance; error mapping (400 validation with API
  payload, 404 unknown entity, 500 runtime refusal, unreachable server).
- **GUI smoke** (`test_smoke.py`) — every dashboard section fills from a
  real refresh; navigation order and page switching; shortcut
  installation; create-goal action lands and is listed; event lifecycle
  from the Events page reflects in Current Event; rejected actions
  notify without crashing; disturber round-trip appears in the
  Disturbers card; dialog `values()`; offline banner + no-crash on a
  dead port; reconnect recovery.
- **Forbidden imports** (`test_forbidden_imports.py`) — AST scans: no
  `paios.*` import anywhere in the GUI; only stdlib + PySide6 +
  `paios_gui`; no file/persistence modules and no `open()` calls;
  urllib confined to `client.py`.
- **API** (`tests/api/test_endpoints.py`) — `POST /disturbers` happy
  path (capture chain → Analyzed, visible in `/dashboard`) and bad-enum
  400.

## 8. Audit

| Check | Result |
| --- | --- |
| No Runtime imports | PASS — no `paios.*` import at all (AST-enforced, stricter than required). |
| No Scheduler imports | PASS — same. |
| No Decision Engine imports | PASS — same. |
| REST-only communication | PASS — all I/O is `urllib` in `client.py`; every widget byte comes from REST responses; urllib banned outside `client.py` by test. |
| No business logic | PASS — pure payload→display builders; actions are single delegations; the only client-side grouping is presentation (History's terminal-state filter, Active-first goal ordering — the TUI convention). |
| No persistence | PASS — no file access, no JSON files, no `open()` (AST-enforced); the GUI holds no state beyond what is on screen. |
| Regression | PASS — 697/697; backend untouched except the additive `/disturbers` route. |

## 9. Future improvements

- **Async polling** — a worker thread (or QNetworkAccessManager) if the
  API ever leaves localhost; the synchronous 2 s-timeout design is
  right only while the transport is loopback.
- **Server-side "today" filtering** — Goals/Projects show all entries
  (as the TUI does); `?status=`/`?date=` query parameters would let the
  dashboard ask for exactly today's slice.
- **Live change feed** — polling is the mission's model; server-sent
  events would cut latency and traffic without websockets.
- **Consume/produce resources & goal lifecycle buttons** — endpoints
  exist (M12); the mission's action list did not include them, so the
  GUI does not expose them yet.
- **Packaging** — a PyInstaller spec would produce a double-clickable
  binary once distribution matters.
- **Light theme toggle** — the palette is centralized in `theme.py`;
  a second palette is mechanical.

## 10. Suggested commit message

```
Milestone 13: Desktop dashboard - PySide6 GUI over the REST API

- frontend/desktop/paios_gui: Qt Widgets app (dark, minimal, no
  animations); TODAY dashboard with all mission sections; Goals/
  Projects/Events/Resources/Knowledge/Learning/History/Settings pages
- REST-only: stdlib urllib client is the single I/O module; the GUI
  imports nothing from paios (AST-enforced) and touches no files
- Actions map 1:1 to endpoints (accept/reject, event lifecycle, goal/
  project/progress, reflection, disturbance); POST /disturbers added
  to the API (M12 convention, one facade delegation)
- Configurable polling (Settings + --refresh), manual refresh, offline
  banner with graceful retry, keyboard shortcuts (F5/Ctrl+R, Ctrl+1-9,
  Ctrl+Q)
- Framework: PySide6-Essentials (first third-party dep, GUI tier only;
  backend stays stdlib-only) - justified vs Tauri/Electron
- Tests: 26 new (REST integration, GUI smoke offscreen, forbidden
  imports, /disturbers); full suite 697 green
```

## Stop condition

Milestone 13 ends here. No mobile, AI assistant, notification system,
plugin, voice, or timer work has been started. Awaiting review.
