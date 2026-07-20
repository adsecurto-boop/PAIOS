# Scheduler Report — Milestone 4

The Scheduler: sole owner of the future and sole controller of Event state
transitions (ADR-002; BUSINESS_RULES.md - Scheduler Rules; DOMAIN_MODEL.md
Principles 7/20/23/24). Event-driven, deterministic, and split from plan
computation behind a Planner interface.

Status: complete, audited, **316 tests passing** (137 domain + 65
repository + 60 runtime + 54 scheduler), including the ADR-003 revision.
The committed Milestone 1/2 baselines were untouched by Milestone 4 itself;
Milestone 3 received only the approved additive amendments listed below,
and ADR-003 subsequently added the Ready-state exits to the Event machine
(documentation, implementation, and tests updated together).

## Approved Rulings (G1–G11) and Refinements

| Ruling | Decision |
|---|---|
| G1 | The Scheduler materializes the Event aggregate (+ its Context Window) when consuming an accepted Recommendation |
| G2 | PersistenceSync: an infrastructure bus subscriber is the only non-boot persistence path |
| G3 | **Rejected** — no `scheduler.json`, ever; the plan is in-memory and rebuilt from evidence |
| G4 | Spontaneous user actions create Events through the implicit legal chain Recommended→Scheduled→Ready→Started |
| G5 | Recurrence out of scope (emerges later via Habits/Decision Engine) |
| G6 | **The Kernel executes Context Window transitions (actor "Runtime"); the Scheduler requests them** |
| G7 | **Rejected** — Scheduler State stays out of RuntimeSnapshot |
| G8 | The Scheduler never rejects Recommendations; infeasible consumption is deferred |
| G9 | Every trigger causes one deterministic recalculation cycle |
| G10 | The Scheduler records externally supplied Outcome evidence at completion |
| G11 | Event-driven, not scan-driven |
| R1 | Single `SchedulerRecalculationRequested` topic + `RecalculationReason` enum; runtime signals translated by the RecalculationBridge |
| R2 | `SchedulingPlan`/`PlanEntry` hold only immutable data and typed IDs — never Event/Recommendation objects |
| R3 | `Planner` interface: the Scheduler orchestrates, the Planner computes — AI planners plug in later without Scheduler changes |

## 1. Folder Structure

```
backend/paios/scheduler/
├── __init__.py         Public exports
├── exceptions.py       SchedulerError → SchedulerLifecycleError,
│                       SchedulingConflictError, UnknownWorkError
├── lifecycle.py        SchedulerState + STATE_MACHINES.md §4 machine
├── plan.py             PlanEntry + SchedulingPlan (frozen, ID-only, R2)
├── planner.py          Planner ABC + PlanCandidate + DeterministicPlanner (R3)
└── scheduler.py        Scheduler + RecalculationReason (R1)

backend/paios/infrastructure/
├── __init__.py
├── recalculation_bridge.py   Runtime signals → the single Scheduler topic
└── persistence_sync.py       Bus announcements → repository write-back (G2)

tests/scheduler/        conftest (fully wired system) + 7 modules, 52 tests
```

### Approved additive amendments to Milestone 3

- `SystemEventType.SCHEDULER_RECALCULATION_REQUESTED` + `SCHEDULER_EVENTS`
  catalog (three-way vocabulary partition; the reserved §12 catalog is
  unchanged).
- `RuntimeState.admit_event(event, window)` — validated admission of
  Scheduler-materialized aggregates into kernel-owned state.
- `RuntimeKernel.admit_event / activate_context_window /
  expire_context_window` — the Kernel executes Context Window transitions
  with the documented actor "Runtime", auto-closing the previous Active
  window per BUSINESS_RULES.md, publishing `ContextChanged` (the reserved
  event gains its intended publisher), and announcing persistence
  operations for PersistenceSync. No existing method or guard changed.

## 2. Dependency Graph

```
paios.scheduler ────► paios.runtime   (kernel API, bus, ExecutionContext types)
        │───────────► paios.domain    (public transition methods, enums, IDs)
        ✗ zero:      repositories / json / files / clock reads / Task / Todo

paios.infrastructure ──► paios.runtime + paios.repositories.interfaces
                     ──► paios.scheduler (the RecalculationReason enum)

Kernel never depends on the Scheduler (grep-verified).
Domain and Repositories never depend on anything above them.
```

## 3. Scheduler State Machine (STATE_MACHINES.md §4, edge-for-edge)

```
Idle → Observing → Evaluating → Planning → Scheduling → Monitoring
                                               ▲            │ deviation
                                               └─ Recalculating ◄┘
Monitoring → Idle   (horizon ends: empty plan, nothing running)
```

Documented invalid bypasses (Observing→Scheduling, Idle→Planning,
Recalculating→Monitoring) are rejected — covered by tests. The historical
machine in STATE_MACHINE_DESIGN.md is superseded and not implemented.

## 4. The Scheduling Cycle (event-driven, deterministic)

```
SchedulerRecalculationRequested(reason) — the ONLY subscription (R1/G11)
  ↓ [DisturbanceDetected only] the mandatory chain (P24), strictly ordered:
  │    request Kernel: expire active Context Window → Started→Interrupted →
  │    ExecutionContext→Idle → resolve the Applied Disturber
  ↓ Expire Pending Recommendations past expires_at
  ↓ Consume Accepted Recommendations (G1): materialize Event+Window,
  │    Recommended→Scheduled, Kernel admission; infeasible → deferred (G8)
  ↓ Advance due Events: Scheduled→Ready at planned start;
  │    Scheduled→Skipped when the slot end passed unstarted
  ↓ Overtake: an Interrupted Event outranked by a due higher-priority
  │    planned Event → Overtaken
  ↓ Rebuild plan: Planner.plan(now, immutable candidates) → new frozen plan
  ↓ Publish PlanUpdated (persistence payload: changed Recommendations,
  │    Disturbers) — PersistenceSync writes everything back (G2)
  ↓ Monitoring — or Idle when the horizon is empty
```

Re-entrancy: signals arriving mid-cycle or mid-user-action coalesce into
exactly one follow-up cycle (the bus is synchronous; the guard makes
cascades deterministic and terminating).

User actions are explicit API calls — the user triggers, the Scheduler is
the recorded actor: `accept_recommendation`, `user_rejected_recommendation`,
`user_started`, `user_paused`, `user_resumed`, `user_completed` (with
externally supplied Outcome, G10), `user_cancelled`, `archive_event`,
`report_spontaneous_action` (G4).

## 5. Deterministic Rules (Domain-Policy-level, documented as evolvable)

- Slots: priority ↓, earliest start ↑, Event ID (stable tiebreak);
  sequential, non-overlapping, never in the past; default slot length 60
  minutes (no domain field carries a planned duration).
- A Recommendation without suggested timing is slotted *now* — its Event
  legally advances to Ready within the accept cascade.
- Starting/resuming one Event pauses the running one first (Paused is "the
  user's own choice" by definition).
- A Resumed Event pausing/completing is first normalized Resumed→Started
  (the documented "execution continues" edge).
- Materialization binds the new Window to the active Context, else the
  first known Context; with no Context known, consumption stays deferred.
- Every trigger recalculates (G9); simultaneous signals coalesce in
  arrival order.

## 6. Audit Report (Phase 4)

| Check | Result |
|---|---|
| Scheduler doing reasoning / learning | None — no ranking, scoring, confidence, or pattern logic; priorities are supplied data, only compared |
| Scheduler editing history | Never — transitions only, through the formal machines; terminal states unreachable backwards; facts untouched except pre-completion evidence via approved setters |
| Scheduler violating Principles | No Principle mutation; enforcement hooks in place (no Principle-constraint data exists yet to violate — Decision Engine milestone) |
| Scheduler violating Runtime ownership | All runtime effects requested from the Kernel: admission, window transitions (G6), ExecutionContext swaps |
| Scheduler bypassing state machines | Every transition validated by the domain machines; transition actors recorded ("Scheduler" for Events/Recommendations, "Runtime" for windows via Kernel) |
| Scheduler mutating immutable entities | None — frozen plan structures (R2), domain guards active |
| Hidden Tasks / Todos | grep: zero |
| Scheduler depending on persistence / JSON | grep: zero `paios.repositories`, `json`, `pathlib` imports in the scheduler package |
| `datetime.now()` | One occurrence in the codebase: the sanctioned `SystemClock.now` |
| Clean Architecture | scheduler→runtime→domain one-way; kernel has no scheduler dependency (grep); infrastructure alone touches repositories |
| Frozen layers | M1/M2 committed baselines untouched; M3 changes limited to the approved additive amendments |
| Full suite | **312 passed** (prior 260 unchanged + 52 scheduler) |

## 7. Test Report — 52 new

- `test_lifecycle.py` (7) — §4 machine paths, invalid bypasses, runtime
  settling (Idle when empty, Monitoring around a running Event), double
  attach rejected.
- `test_plan_and_planner.py` (12) — frozen ID-only entries and plans (R2),
  overlap rejection, ordering, planner determinism, earliest-start and
  never-in-the-past rules, injected stub Planner (R3).
- `test_recommendation_flow.py` (8) — accept→consume→materialize with
  persistence; immediate-Ready cascade; deferral without a Context (G8:
  stays Accepted forever, never Rejected); expiry by time (persisted);
  expired-cannot-accept; user rejection.
- `test_event_flow.py` (10) — future slots becoming Ready on time;
  start/pause/resume/complete with ExecutionContext and window effects and
  Outcome evidence (G10); skip after slot passes; cancel; archive; the
  single-running-Event rule (second start pauses the first).
- `test_disturbance.py` (4) — the mandatory chain in verified order
  (window transition → Event transition → idle context → Disturber
  resolved, all persisted); resume; cancel; Overtaken by a due
  higher-priority Event.
- `test_spontaneous.py` (4) — the implicit legal chain (G4) with
  reason-tagged transitions; persistence; pausing the running Event and
  auto-closing its window; Context requirement.
- `test_boot_and_infrastructure.py` (7) — boot adoption (Monitoring around
  restored running Event), stale-Recommendation sweep at attach, full
  **crash recovery** (shutdown → fresh system over the same store restores
  mid-flight state), single-topic subscription (R1), bridge reason
  forwarding, unknown-reason fallback, idempotent attaches.

## 8. Findings and Deferrals

**Architecture finding — RESOLVED by ADR-003:** the formal Event machine
originally gave `Ready` exactly one exit (`Started`), trapping a Ready
Event whose slot passed. The owner-approved resolution: Ready shares every
non-start exit of Scheduled (`Skipped`, `Cancelled`, `Overtaken`).
DOMAIN_MODEL.md, BUSINESS_RULES.md, GLOSSARY.md, STATE_MACHINES.md, the
Event machine implementation, and the Scheduler's skip rule were updated
together; four regression tests pin the new edges end-to-end. The informal
`Scheduled → Started` example shorthand in DOMAIN_MODEL/BUSINESS_RULES was
aligned to the formal `Scheduled → Ready → Started` path in the same
revision. The architecture is declared internally consistent (see ADR-003,
Architecture Consistency Statement).

Deferred: Decision Engine (Recommendation generation, ranking, confidence,
Principle-filtering data), Timer Engine (ticks arrive as published
`TimeProgressed` events), Resource-requirement feasibility (no domain field
models per-Event resource requirements yet), recurrence (G5), asynchronous
bus delivery, automatic archival cadence (manual `archive_event` only).

## 9. Suggested Git Commit

```
Milestone 4: Scheduler - event-driven planning, sole Event transition control

- Scheduler over the canonical section-4 state machine; single
  SchedulerRecalculationRequested subscription with reason enum (R1)
- Planner interface + DeterministicPlanner; frozen ID-only SchedulingPlan (R2/R3)
- Recommendation consumption materializes Event + Context Window (G1);
  deferral, never rejection (G8); externally supplied Outcome recorded (G10)
- Mandatory disturbance chain enforced end-to-end (P24); Overtaken semantics
- Spontaneous user actions via the implicit legal lifecycle chain (G4)
- Kernel amendments (G6): aggregate admission + Context Window transitions
  executed by the Kernel with actor "Runtime"
- Infrastructure: RecalculationBridge + PersistenceSync bus write-back (G2)
- No scheduler.json (G3); plan rebuilt from evidence; crash recovery proven
- 52 new tests; 312 total passing

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

Milestone 4 deliverables complete. The Decision Engine (Milestone 5) will
not begin without explicit approval.
