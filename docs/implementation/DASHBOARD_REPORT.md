# Milestone 11 — Dashboard (Terminal UI)

## Mission

A read-only, continuously refreshing terminal dashboard rendering the
current state of PAIOS. Not a GUI, not a web app. It never mutates domain
state and never bypasses the Application facade.

## 1. Architecture

### New package: `backend/paios/dashboard/`

| Module | Responsibility |
| --- | --- |
| `config.py` | `DashboardConfig` (refresh interval, frame width, rows per section); `ALLOWED_INTERVALS = (0, 1, 5, 10)`; validation in `__post_init__`. |
| `layout.py` | Frame geometry only: banner, separators, section wrapping, line clipping to width, `compose()`. Knows widths and order — never data. |
| `formatter.py` | Pure value formatting over duck-typed facade outputs: times, `Xh YYm` labels, elapsed/remaining arithmetic, progress bars, display-line builders, canonical state-name string matching for grouping. |
| `renderer.py` | The only module that talks to the facade: 15 read-only queries in, one frame string out. |
| `refresh.py` | `RefreshLoop`: render → single write → sleep, until Ctrl+C / max frames / single-frame mode. Owns flicker avoidance. |
| `dashboard.py` | `Dashboard`: wires renderer + loop over injectable stream and sleep; `render_once()` for tooling/tests; writes `Dashboard closed.` on exit. |

The whole package imports **stdlib and itself only**. Even
`paios.application` is not imported: the Application instance is injected
by the caller (CLI), so the dashboard cannot construct, start, or stop an
application — it can only read from the one it is handed.

### Read-only by construction

The renderer's complete facade surface (verified by audit and by a strict
recording fake that raises on any other attribute access):

`current_time`, `status`, `snapshot`, `scheduler_state`,
`active_recommendations`, `active_event_disturbers`, `list_events`,
`list_goals`, `list_projects`, `get_project_progress`, `list_resources`,
`list_habits`, `list_insights`, `list_reflections`, `list_knowledge`.

All queries; no code path reaches an action, a repository, or an entity
mutator. Nothing is persisted; the only writes are frames to the
dashboard's own output stream.

### Smallest additive facade methods (mission-sanctioned)

Three gaps existed; each became one pure-delegation query:

- `Application.current_time()` → the composed Clock's now (the dashboard
  must not read the OS clock — the Clock is the sole sanctioned time
  source).
- `Application.scheduler_state()` → the Scheduler lifecycle state for the
  SYSTEM section (previously reachable only via the composition-root
  `components` surface, which the dashboard must not use).
- `Application.list_events()` → store-backed read-only Event listing
  (`DomainOperations.list_events`); Event **mutation** remains exclusively
  with the Scheduler.

### Liveness model (deliberate, documented)

Store-backed queries (`list_*`) re-read the JSON store on every frame, so
the dashboard reflects writes made by OTHER processes (CLI commands, an
external daemon) live. Runtime views (execution context, context window,
kernel state, snapshot time) are process-local by architecture — the
kernel's repository access is boot-only (resolution C5) — and are
presented honestly as such.

### Daemon status

The daemon wraps the Application, so it can never be obtained *through*
the facade. `Dashboard`/`DashboardRenderer` accept an optional duck-typed
daemon (`state`, `tick_count`, `last_tick_at`) for embedding processes;
without one, the dashboard reports "Not attached". No daemon module is
imported.

### Presentation mappings (no new domain concepts)

- **CURRENT EVENT** — the store's Started/Resumed event. Start moment
  comes from the Event's lifecycle evidence (the most recent
  Started/Resumed `TransitionRecord`) since the Scheduler records timing
  as transitions; Duration/Remaining derive from the Event's `Duration`
  when present.
- **TODAY** — display grouping by canonical state-name strings:
  Completed (today), Running, Upcoming (Recommended/Scheduled/Ready).
- **HEALTH** — the health state that exists in the domain today:
  Health/Energy/Stress Resources plus Learning-detected Habits (the
  mission's Smoking/Medication/Exercise examples live here once tracked
  as Habits). No new entities were invented.
- **LEARNING** — latest Insight, latest Reflection (lesson), last-studied
  date and revised-today count from Knowledge. A true *study streak* is
  not computable: the domain stores only `last_revision` per Knowledge
  item, not a revision history (see Future improvements).
- **SYSTEM** — Scheduler state, Decision Engine (stateless — shown
  "ready" while the application is operational), Kernel state, snapshot
  time, daemon status.

## 2. Dependency graph

```
cli ──────────────► dashboard          (constructs Dashboard, passes the
 │                     │                started Application + out stream)
 │                     ▼
 └──────────► application (facade) ── 15 read-only queries only
                       │
                       ▼
        domain operations / runtime / scheduler / ... (unchanged)
```

Dashboard package imports: `dataclasses`, `datetime`, `typing`, `sys`,
`time`, `paios.dashboard.*`. Nothing else — enforced by an AST-based test
(`TestForbiddenImports`) that fails on any import of runtime, scheduler,
decision_engine, learning, repositories, infrastructure, domain, daemon,
or cli from inside the package.

## 3. Layout

57-column frame, mission section order exactly:

```
=========================================================
                     PAIOS DASHBOARD
=========================================================
Current Time:  2026-07-21 09:00:00
Daemon Status: Not attached (start PAIOS with an embed...
---------------------------------------------------------
CURRENT EVENT          Event / Started / Duration / Remaining
CURRENT CONTEXT        Execution Context / Context Window / Disturbers
RECOMMENDATIONS        1. (priority) reason ...
GOALS                  * [Active] name  (accepted marker, active first)
PROJECTS               [Active] name + [####....] completion bar
TODAY                  Completed / Running / Upcoming (counts + lines)
HEALTH                 Health-type Resources + Habits
LEARNING               Latest Insight / Latest Reflection / Study
SYSTEM                 Scheduler / Decision Engine / Kernel / Snapshot / Daemon
---------------------------------------------------------
```

Every line is clipped to the frame width with an ellipsis; empty sections
render `-`; list sections truncate at `max_rows_per_section` (3) with a
`(+N more)` marker.

## 4. Refresh design

- **Intervals**: 0 (render one frame and return — "no refresh"), 1
  (default), 5, 10 seconds. Validated in `DashboardConfig` and again at
  the CLI boundary (`build_dashboard_config` → usage error).
- **No flicker**: each frame is ONE stream write. On a real terminal
  (`isatty()`), the first frame hides the cursor and clears the screen
  once; every frame is written as cursor-home + frame + clear-to-end, so
  the screen is overwritten in place, never blanked between frames. Plain
  VT escape strings — stdlib only, no ANSI/TUI library.
- **Non-terminal streams** (tests, pipes): frames verbatim, zero escape
  codes.
- **Clean exit**: `KeyboardInterrupt` (Ctrl+C) is caught by the loop,
  the cursor is restored, `Dashboard closed.` is written, and control
  returns (to the shell prompt when launched from the shell).
- **Determinism for tests**: injectable `sleep` and `output_stream`, plus
  `max_frames`.

### Commands

- `paios dashboard [seconds]` — one-shot: compose, start, render until
  Ctrl+C, stop.
- `dashboard [seconds]` inside `paios shell` — the Shell hands its own
  started Application and output stream to the Dashboard; on exit the
  prompt returns. (The command is registered in the parser for `help`;
  the processor itself refuses it with a hint, since frames need a
  stream the processor does not own.)

## 5. Audit

| Check | Result |
| --- | --- |
| No Runtime imports | PASS — AST test + grep: package imports are stdlib + `paios.dashboard.*` only. |
| No Scheduler imports | PASS — same. |
| No Decision Engine imports | PASS — same. |
| No Learning imports | PASS — same. |
| No Repository implementation imports | PASS — same (no repository interfaces either). |
| No business logic | PASS — formatting, display grouping by canonical state names, and presentation arithmetic (elapsed/remaining) only; nothing decides, schedules, or evaluates. |
| No persistence | PASS — no store, file, or JSON access; the only writes are frames to the injected output stream. |
| No domain mutation | PASS — recording-fake test raises on ANY facade member outside the 15 read-only queries; renderer passes. |
| Read-only interface | PASS — no input handling except Ctrl+C; no command execution. |
| Frozen layers | PASS — domain, runtime, scheduler, decision_engine, learning, repositories, infrastructure, daemon all untouched; `application/` gained 3 additive pure-delegation queries; `cli/` gained the entry points. |

## 6. Tests

`tests/dashboard/` — 38 tests, full suite **634 passed** (596 + 38):

- **Layout** — banner geometry, clipping, empty-section dashes, mission
  section order, no line wider than the frame.
- **Formatting** — duration labels, elapsed/remaining (never negative,
  None-safe), progress-bar bounds, same-day logic, enum duck-typing.
- **Renderer** — every section against a real started application: idle
  honesty, running event with lifecycle-evidence timing, numbered
  recommendations, goals/projects with progress bar, TODAY grouping,
  HEALTH resources, LEARNING study line, SYSTEM states, attached-daemon
  display.
- **Refresh** — single-frame mode, interval sleeping, max-frames bound,
  Ctrl+C clean exit, no ANSI on non-terminals, terminal mode clears once
  and homes per frame with cursor restore.
- **Startup/shutdown** — `render_once`, goodbye on exit, one-shot
  `paios dashboard 0` exit 0, bad interval exit 1, shell `dashboard 0`
  returning to a working prompt, unstarted-application error surfaced.
- **Application delegation** — strict read-only recording fake: any
  non-query facade access raises; asserts the query families consulted.
- **No forbidden imports** — AST scan of every module in the package.

## 7. Future improvements

- **Study streak** — needs a revision-history record (dates per revision)
  in the Knowledge aggregate or a Learning-layer log; today only
  `last_revision` exists, so a day-streak cannot be computed honestly.
- **Named health trackers** — Smoking/Medication/Exercise as first-class
  tracked Habits with targets would let HEALTH show per-tracker status
  rather than generic habit strength.
- **Daemon attachment for `paios dashboard`** — a supervised mode that
  runs the daemon and dashboard in one process (daemon ticks, dashboard
  views) would make the one-shot dashboard fully live without a second
  terminal.
- **Terminal width detection** — `shutil.get_terminal_size()` could size
  the frame dynamically; fixed 57 matches the mission sketch for now.
- **REST API** (next milestone candidate) — the renderer's data-gathering
  step is already a clean read-only "view model" over the facade; a REST
  layer can expose the same queries.

## 8. Suggested commit message

```
Milestone 11: Dashboard - read-only terminal UI

- paios.dashboard package (config/layout/formatter/renderer/refresh/
  dashboard): 57-col frame, mission section order, flicker-free
  single-write VT redraw, Ctrl+C clean exit, stdlib only
- Renderer consumes 15 read-only facade queries; application instance
  injected, package imports stdlib + itself only (AST-enforced)
- Additive facade queries: current_time(), scheduler_state(),
  list_events() (read-only; Event mutation stays with the Scheduler)
- CLI: `paios dashboard [seconds]` one-shot + `dashboard` in the shell;
  refresh intervals 0(no refresh)/1(default)/5/10
- Tests: 38 new (layout, formatting, renderer, refresh, lifecycle,
  delegation, forbidden imports); full suite 634 green
```

## Stop condition

Milestone 11 ends here. No REST API, GUI, web frontend, mobile, AI
assistant, or notification work has been started. Awaiting review.
