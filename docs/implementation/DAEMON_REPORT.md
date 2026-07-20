# Daemon Report — Milestone 9

The Runtime Daemon / Timer Engine: PAIOS now operates continuously without
manual `paios tick`. The daemon owns the eternal loop and nothing else —
no business logic, no domain knowledge, no scheduling, no reasoning, no
runtime mutation. It designs the component every canonical document
deferred (DOMAIN_MODEL.md Future Question 13; BEHAVIORAL_ARCHITECTURE.md
"Wait for Next Change: timer-based triggers").

Status: complete, audited, **532 tests passing** (493 prior + 39 daemon).
One approved frozen-layer correction (below); everything else untouched.

## Approved Milestone 6 Correction (discovered by this milestone)

Continuous operation exposed a latent defect in `Application.tick()`: it
evaluated `kernel.latest_snapshot` without refreshing it, so under quiet
operation `snapshot.current_time` went stale. The Decision Engine's
deterministic uuid5 Recommendation IDs are anchored on snapshot time — so
after the first Recommendation's validity lapsed, the engine regenerated
the SAME ID and admission collided (`RuntimeInvariantError: already
admitted`) roughly one simulated hour into a run. This contradicted
Milestone 6's own documented contract ("reasons over the FRESH snapshot")
and DECISION_ENGINE.md §3 ("Ensure all inputs are current").

Owner-approved smallest correction — one statement in
`backend/paios/application/application.py`:

```python
result = components.engine.evaluate(components.kernel.refresh_snapshot())
```

`refresh_snapshot()` is the existing public Kernel API (in-memory only;
`SnapshotUpdated` is deliberately un-bridged, so no feedback loop). The
simulated-day test now proves hourly re-recommendation runs indefinitely.

## 1. Architecture

```
        RuntimeDaemon (the Timer Engine)
              │  owns: loop, cadence, lifecycle, sleep, thread
              ▼
        loop -> clock.now() -> Application.tick() -> sleep -> repeat
              │  knows NOTHING about what a tick does
              ▼
        Application ─► Runtime ─► Scheduler ─► Decision Engine ─► Persistence
```

Dependency achievement — stricter than the mission required: the mission
permitted depending on the Clock abstraction; the daemon avoids even that
import. The clock is reached through the Application's sanctioned
`components` surface and duck-typed (`now`/`advance`/`set_time`). The
daemon imports **paios.application and stdlib only** (grep-verified:
zero runtime/scheduler/decision-engine/repositories/domain imports).

## 2. Folder Structure

```
backend/paios/daemon/
├── __init__.py     exports
├── exceptions.py   DaemonError → DaemonStateError, ClockAdvanceError
├── config.py       DaemonConfig — every number named: tick interval
│                   (default 60s, the RUNTIME_EXECUTION.md "balanced"
│                   option), startup delay, shutdown timeout, sleep
│                   strategy, signal-poll constant
├── sleep.py        SleepStrategy ABC (call-recording) + RealSleep,
│                   NoSleep, SimulatedSleep (advances a ManualClock by
│                   exactly the requested duration)
├── lifecycle.py    DaemonState + local transition table (stdlib-only —
│                   importing domain machinery would break the rules)
└── daemon.py       RuntimeDaemon: the loop, threading, drift-free
                    deadlines, clock helpers
```

## 3. Lifecycle Diagram

```
            start()/run_*()                pause()
  Created ────────────────► Running ────────────────► Paused
     ▲                        │   ▲                     │
     │                        │   └─────── resume() ────┘
     │                stop()/ │ natural end/error       │ stop()
     │                        ▼                         ▼
     └── (restart allowed) Stopped ◄─── Stopping ◄──────┘
```

Restart (`Stopped → Running`) is legal: the daemon is runtime
orchestration, not historical evidence. `resume()` is valid only from
Paused. Foreground runs re-raise a captured tick error after finishing;
background runs store it in `last_error` and stop gracefully.

## 4. Sequence Diagram (one background iteration)

```
Thread            RuntimeDaemon                Application
  │  stop set? ──────► no                          │
  │  paused? ────────► no (else wait on resume     │
  │                     event, SIGNAL_POLL slice)  │
  │  tick_start = clock.now()                      │
  │  ────────────────────────────── tick() ──────► │  TimeProgressed →
  │                                                │  Scheduler → DE over
  │  tick_count += 1; last_tick_at; last_result ◄──│  REFRESHED snapshot →
  │  deadline += interval   (absolute, drift-free) │  present+admit → persist
  │  remaining = deadline - clock.now()            │
  │  sleep(remaining) if > 0, else catch up        │
  └── repeat ──────────────────────────────────────┘
```

Drift-free scheduling: deadlines are absolute (`previous + interval`),
so tick duration never accumulates error; behind schedule, the daemon
catches up without sleeping and resets the deadline (no spiral).

## 5. API and Configuration

`start() / stop() / pause() / resume() / run_forever() /
run_until(predicate) / run_iterations(n) / tick_once()` plus the
ManualClock testing surface `advance(minutes, seconds)` and
`advance_to(datetime)` (monotonic-only — time never moves backwards, per
RUNTIME_EXECUTION.md). Works with both SystemClock (RealSleep) and
ManualClock (NoSleep for bounded runs; SimulatedSleep for deterministic
time flow). `stop()` signals, then joins the background thread up to
`shutdown_timeout_seconds`.

Known limitation (documented): with RealSleep, an in-progress sleep is
not interruptible, so `stop()` responsiveness is bounded by the remaining
sleep (the thread is daemonized; process exit is never blocked). See
Future Extensions.

## 6. Test Report — 39 new

- `test_config_and_sleep.py` (8) — named defaults, validation, all three
  strategies (SimulatedSleep advancing the clock exactly).
- `test_lifecycle_and_clock.py` (12) — transition table valid/invalid,
  guard rails (pause/resume/stop from Created; tick while Paused),
  natural finish, restart, `advance`/`advance_to`, monotonicity,
  SystemClock advance rejection, auto-starting the Application.
- `test_ticking.py` (10) — single delegation per tick, exact iteration
  counts, `run_until`, startup delay, **cross-system determinism**
  (identical seeds ⇒ identical Recommendation IDs after 3 ticks),
  dedup stability, **no drift** (all sleeps exactly the interval; tick
  moments exactly interval-spaced), behind-schedule catch-up.
- `test_threads_errors_and_scale.py` (9) — background start/stop
  graceful, pause halts ticking / resume continues, stop responsive
  while paused, background restart, double-start rejected, foreground
  error finishing-then-raising, background error captured, restart
  clearing errors, **one simulated day of minute ticks (1440)** staying
  coherent, and performance sanity (500 ticks well under budget).

Suites: domain 137 · repositories 65 · runtime 60 · scheduler 54 ·
decision engine 33 · application 52 · CLI 47 · learning 45 · daemon 39 —
**532 passed**, prior suites unchanged.

## 7. Audit Report

| Check | Result |
|---|---|
| One `datetime.now` in the codebase | Verified: exactly one, `SystemClock.now` (the daemon adds none; `time.sleep` in RealSleep is waiting, not clock-reading) |
| Zero business logic | The loop body is one delegation; the daemon cannot even name a domain concept — it imports none |
| Dependency direction | daemon → application + stdlib only (grep); nothing imports the daemon |
| Deterministic execution | ManualClock + SimulatedSleep pinned by tests: identical seeds ⇒ identical outcomes, exact tick spacing, whole-day replay |
| No circular imports | Leaf package |
| Frozen milestones untouched | Only the owner-approved one-line `Application.tick()` correction; all 493 prior tests pass unchanged |

## 8. Future Extensions

- Interruptible RealSleep (slice against a stop event) for instant
  shutdown under long intervals.
- Event-driven ticking: subscribe wake-ups to bus activity for the
  documented "hybrid" cadence (RUNTIME_EXECUTION.md §3).
- Adaptive intervals (a Domain Policy: quiet periods tick slower).
- CLI integration: `paios daemon start/stop/status` riding the resident
  process the CLI report already anticipates.
- Health reporting: tick latency and missed-deadline metrics on the bus.

## 9. Suggested Git Commit

```
Milestone 9: Runtime Daemon / Timer Engine - continuous operation

- RuntimeDaemon: eternal loop (clock -> Application.tick -> sleep),
  drift-free absolute deadlines, background thread with graceful stop,
  pause/resume, restart, foreground run_forever/run_until/run_iterations
- SleepStrategy (Real/No/Simulated) + DaemonConfig, zero magic numbers
- ManualClock support: advance/advance_to (monotonic-only)
- Imports paios.application + stdlib ONLY (clock duck-typed via facade)
- Approved M6 fix: Application.tick evaluates the REFRESHED snapshot -
  stale snapshot time broke deterministic Recommendation identity under
  continuous operation (proven by the simulated-day test)
- 39 new tests incl. a full simulated day (1440 ticks); 532 total passing

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

Milestone 9 deliverables complete. No GUI, Dashboard, Notifications,
REST API, Mobile, or AI work will begin without explicit approval.
