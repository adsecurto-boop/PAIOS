# Runtime Kernel Report — Milestone 3

The Runtime Kernel: PAIOS's central orchestrator (BEHAVIORAL_ARCHITECTURE.md
§4). Owns Runtime State, the runtime lifecycle, Runtime Snapshots, the
System Event Bus, the Clock abstraction, Runtime Status, the Service
Registry, invariant enforcement, and the Idle Execution Context — nothing
else. It observes, holds, validates, and broadcasts; it never decides.

Status: complete, audited, **260 tests passing** (135 domain + 65
repository + 60 runtime). Domain and Repositories remain frozen — `git
status` on both layers: clean.

## Approved Resolutions (C1–C7)

1. **C1 — Snapshot contents**: mission list + Principles, Contexts,
   Progress, Event Disturbers, historical Events (carrying Impact), and
   Context Windows as history evidence. Scheduler State deferred to M4;
   Domain Policies and User Preferences are not domain entities — deferred.
2. **C2 — Execution Context invariant (modified by owner)**: no Idle
   Context Window. The runtime invariant is **"exactly one Execution
   Context"** — either `EventExecutionContext` or `IdleExecutionContext`.
   **Only EventExecutionContext owns a Context Window.** The Active-Window
   invariant is enforced as at-most-one per User; an idle runtime
   legitimately has no Active window.
3. **C3 — Kernel lifecycle**: explicit state machine (below); Paused means
   "not accepting work," never "history stops."
4. **C4 — Two event catalogs**: 11 kernel events implemented; the
   BEHAVIORAL_ARCHITECTURE §12 catalog declared as reserved vocabulary
   whose publishers arrive in M4+.
5. **C5 — Repositories**: injected as interfaces (structural
   `RepositoryProvider` Protocol), touched only during boot; the Kernel
   never imports JsonStore, JSON modules, or concrete repositories.
6. **C6 — Clock**: `SystemClock.now` is the single sanctioned OS-clock
   call site in the codebase; everything consumes the `Clock` interface.
7. **C7 — Naming (modified by owner)**: the runtime-only running-execution
   construct is the **ExecutionContext hierarchy** (`IdleExecutionContext`
   / `EventExecutionContext`) — never called an "Event," never a domain
   Event aggregate instance, never persisted, invisible to repositories.

---

## 1. Architecture Report

### Folder structure

```
backend/paios/runtime/
├── __init__.py          Public exports
├── exceptions.py        RuntimeKernelError -> KernelLifecycleError,
│                        BootError, RuntimeInvariantError, ServiceRegistryError
├── clock.py             Clock ABC; SystemClock (sole OS-clock site); ManualClock
├── system_events.py     SystemEvent (frozen) + SystemEventType:
│                        11 KERNEL_EVENTS + 11 RESERVED_EVENTS
├── event_bus.py         Synchronous publish/subscribe, deterministic order
├── lifecycle.py         KernelState + kernel state machine (M1 machinery reused)
├── runtime_state.py     ExecutionContext hierarchy + IdleReason +
│                        RuntimeState (mutable, kernel-owned, ephemeral)
├── runtime_snapshot.py  RuntimeSnapshot (frozen) + SnapshotManager
├── runtime_status.py    RuntimeStatus (frozen report)
├── services.py          ServiceRegistry + InvariantChecker
└── kernel.py            RuntimeKernel + RepositoryProvider Protocol

tests/runtime/           conftest + 6 test modules, 60 tests
```

### Dependency graph

```
COMPOSITION ROOT (tests today; application entry later)
  injects: RepositoryProvider (RepositoryFactory satisfies it), Clock
        │
        ▼
paios.runtime ────────────────► paios.repositories.interfaces  (boot only)
        │                       paios.repositories.errors      (wrapping)
        │                       [NEVER json_store / factory /
        │                        serialization / concrete classes]
        ▼
paios.domain  (entities read; state-machine machinery reused;
               M1 invariant services invoked — one-way, frozen)

paios.repositories ──► paios.domain          (unchanged, frozen)
paios.domain       ──► (nothing above it)     (unchanged, frozen)
```

No cycles. Verified by grep: runtime's only repository imports are
`interfaces` and `errors`; domain and repositories contain zero references
to `paios.runtime`.

### Why Runtime is separate from Scheduler

Per the ownership matrix (RUNTIME_EXECUTION §6): the Kernel owns *now*
(state, time, consistency, communication); the Scheduler owns *next*
(future planning, Event transitions). BUSINESS_RULES makes the Scheduler
the sole controller of Event transitions — accordingly the Kernel performs
**zero** Event transitions and exposes `set_execution_context` as the entry
point the Scheduler will drive in M4. The Scheduler will be a bus
*subscriber* (§12), which requires the bus owner to be a distinct component.

---

## 2. Runtime Report

### Runtime Lifecycle Diagram (C3)

```
              boot()                      start()
  Created ──────────► Booting ──────────► Ready ──────► Running
                        │    (sequence ok)               │   ▲
                        │ failure                 pause()│   │resume()
                        ▼                                ▼   │
                      Failed (terminal)                Paused
                                                         │
        Ready / Running / Paused ── shutdown() ──► Stopping ──► Stopped
                                                              (terminal)
```

Boot sequence (inside `Booting`):

```
Load repositories (interfaces, boot-only)
  ↓ restore aggregates          (Option B reconstitution in repositories)
  ↓ structural integrity        (inherent in hydration; failures -> BootError)
  ↓ validate domain invariants  (InvariantChecker, per User)
  ↓ establish Execution Context (EventExecutionContext if a user Event is
  │                              Started/Resumed, else IdleExecutionContext)
  ↓ initialize Runtime State
  ↓ create Runtime Snapshot     (a view OF the state — hence after it;
  ↓                              both inside Boot, before Ready)
Kernel Ready   → KernelBooted, RuntimeReady published
```

Shutdown sequence: stop accepting work (Stopping rejects operations) →
dispose runtime resources (services removed with ServiceRemoved events) →
clear Runtime State and snapshot (ephemeral by design; History untouched)
→ Stopped → KernelShutdown published.

### Execution Context (C2/C7)

```
ExecutionContext (frozen, since: datetime)
├── IdleExecutionContext(reason: Booting|Waiting|Sleeping|Between Events)
│     • runtime-only, never persisted, never historical
│     • owns NO Context Window
└── EventExecutionContext(event_id, context_window_id)
      • the running user Event (Started/Resumed) and the Window it owns
      • the ONLY context that carries a Context Window
```

Runtime invariant: **exactly one Execution Context** — structurally
enforced (`RuntimeState` cannot exist without one; replacement validates
type; `None` is impossible). This keeps "exactly one Running Event" at
full strength without weakening (Resolution 3 + C2).

### Service Registry Diagram

```
        ServiceRegistry (Milestone 3: exactly four)
        ┌──────────────┬──────────────┬───────────────────┬────────────────────┐
        │  "clock"     │ "event_bus"  │ "snapshot_manager"│ "invariant_checker"│
        │  Clock       │ EventBus     │ SnapshotManager   │ InvariantChecker   │
        └──────────────┴──────────────┴───────────────────┴────────────────────┘
   register -> ServiceRegistered        remove -> ServiceRemoved
   Milestone 4+: scheduler / decision_engine / learning_engine plug in here.
```

### Snapshot Flow Diagram

```
   BOOT:  repositories ──list()──► aggregates ──► RuntimeState
                                                     │
                                     SnapshotManager.create(state)
                                                     │
                                        RuntimeSnapshot (frozen)
                                                     │
                                        publish SnapshotCreated
   RUNTIME (no disk access ever again):
     set_execution_context / refresh_snapshot
        └─► RuntimeState updated (in memory)
             └─► SnapshotManager.create(state) ─► publish SnapshotUpdated
   CONSUMERS (M4/M5): Scheduler & Decision Engine receive RuntimeSnapshot —
     the Decision Engine NEVER touches repositories.
```

Snapshot contents (C1): created_at, current_time, execution_context,
running_event, running_context_window, principles, contexts,
context_windows, events (full history incl. Impact), projects, progress,
resources, knowledge, recommendations, event_disturbers, reflections,
insights, habits, goals. Immutability is structural (frozen container,
tuples); referenced entities carry their own domain guards.

### System Events

Kernel events (published in M3): KernelBooted, KernelShutdown,
RuntimeReady, RuntimePaused, RuntimeResumed, SnapshotCreated,
SnapshotUpdated, RunningEventChanged, RunningContextChanged,
ServiceRegistered, ServiceRemoved.

Reserved vocabulary (C4, publishers in M4+): ContextChanged,
EventStateChanged, ResourceThresholdCrossed, DisturbanceDetected,
TimeProgressed, RecommendationGenerated, PlanUpdated, EventCompleted,
ReflectionCreated, InsightGenerated, HabitDetected.

Bus: synchronous, deterministic subscription-order dispatch; asynchronous
delivery is a documented deferral (§12 permits either).

---

## 3. Audit Report

| Check | Result |
|---|---|
| No business logic leaked | Kernel decides nothing: no ranking, no planning, no policy evaluation; invariant checks invoke M1 domain services |
| No Scheduler logic | Zero Event transitions performed by runtime code; `set_execution_context` records what the (future) Scheduler decides |
| No Decision Engine logic | No reasoning anywhere; the snapshot is data assembly only |
| No repository access except boot | grep: `self._repositories` used solely inside `_load_and_validate`, called only from `boot()` |
| No domain mutation outside approved interfaces | The Kernel never mutates a domain entity at all in M3 |
| No circular dependencies | runtime → repositories.interfaces/errors → domain; domain & repositories have zero runtime references (grep-verified) |
| No `datetime.now()` — Clock abstraction only | Exactly one occurrence in the codebase: `SystemClock.now` in clock.py, the sanctioned site (C6) |
| Domain frozen / Repositories frozen | `git status` on both layers and their tests: clean |
| No Task / Todo | grep: only the M1 docstring stating their absence |
| Milestone scope | No tick loop (Timer Engine is future work), no Scheduler, no Decision Engine, no API/UI, no persistence writes |

No violations found.

## 4. Test Report — 60 new, 260 total passing

- `test_clock.py` (5) — Clock ABC, SystemClock, ManualClock determinism/advance.
- `test_event_bus.py` (8) — delivery, dispatch order, topic isolation,
  unsubscribe, payload immutability, catalog partition matching §12.
- `test_lifecycle_and_state.py` (11) — kernel machine paths and invalid
  shortcuts; ExecutionContext ownership rules (idle owns no window; event
  context requires both references); exactly-one Execution Context
  (None impossible), replacement semantics, running window derivation.
- `test_services.py` (10) — registry contract; invariant checker: clean
  and empty states pass, two running Events per user rejected, per-user
  separation honored, two Active windows per user rejected, shared window
  ownership rejected.
- `test_kernel_boot.py` (12) — empty-store boot to Ready with Idle
  context; exactly four services; first snapshot; published event order;
  double-boot rejected; aggregates restored into state; running Event
  becomes EventExecutionContext; snapshot resolves running Event/Window;
  status reporting; invariant violation → BootError + Failed + cleanup;
  corrupted store → BootError; Failed kernel cannot reboot.
- `test_kernel_runtime.py` (14) — start/pause/resume with events; full
  shutdown sequence (services removed, state cleared, Stopped);
  post-shutdown rejection; execution-context changes require Running
  (Paused does not accept work); RunningEventChanged /
  RunningContextChanged / SnapshotUpdated publication; idle→idle skips
  window-changed; invalid context rejected; snapshot refresh follows the
  Clock; snapshot immutability and C1 content completeness.

Suites: domain 135 · repositories 65 · runtime 60 — **260 passed**.

## 5. Intentionally Deferred

| Deferred | Arrives with |
|---|---|
| Runtime tick loop / Timer Engine | Future (DOMAIN_MODEL Future Question 13) |
| Scheduler service + scheduler.json + Event transitions at runtime | Milestone 4 |
| Decision Engine service (snapshot consumer) | Milestone 5 |
| Learning Engine, Reflection/Habit/Insight engines | Later milestones |
| Reserved system-event publishers | M4+ |
| Asynchronous bus delivery | When a consumer requires it |
| Scheduler State in snapshots; Domain Policies; User Preferences | M4+ (per C1) |

## 6. Suggested Git Commit

```
Milestone 3: Runtime Kernel - runtime state, lifecycle, snapshots, event bus

- RuntimeKernel: boot (load -> restore -> validate invariants -> snapshot ->
  ready) and shutdown (stop work -> dispose -> clear) over an explicit
  kernel state machine reusing the M1 machinery
- ExecutionContext hierarchy (C2/C7): exactly one Execution Context —
  IdleExecutionContext (runtime-only, no Context Window) or
  EventExecutionContext (owns the running Event's Context Window)
- Immutable RuntimeSnapshot per C1 contents; Decision Engine will consume
  snapshots, never repositories
- Synchronous System Event Bus; 11 kernel events + reserved §12 vocabulary
- Clock abstraction; SystemClock is the codebase's sole OS-clock call site
- ServiceRegistry with the four M3 services; InvariantChecker enforcing
  deferred Domain Invariants per user at boot
- Repository access via injected interfaces, boot-only (DIP)
- Domain and Repositories untouched; 60 new tests; 260 total passing

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

Milestone 3 deliverables complete. Milestone 4 (Scheduler) will not begin
without explicit approval.
