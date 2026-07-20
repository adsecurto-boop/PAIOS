# Application Layer Report — Milestone 6

The composition layer: connects the five completed subsystems into one
runnable application. Dependency composition and orchestration ONLY — no
UI, no API, no AI, and zero business/scheduling/decision/persistence/
kernel logic (every facade method is a delegation).

Status: complete, audited, **401 tests passing** (137 domain + 65
repository + 60 runtime + 54 scheduler + 33 decision engine + 52
application). Prior suites pass unchanged.

## Approved Frozen-Layer Correction (this milestone)

Phase 1 analysis found the canonical loop unexecutable for aggregates
created after boot: BEHAVIORAL_ARCHITECTURE.md §5 mandates Runtime State
contain "Current Recommendations" and "Current Disturbances", and the §2
loop stage "Update Runtime State" includes "Update Recommendations" — but
the frozen Kernel could admit only Events + Windows. Owner-approved
smallest additive correction, mirroring the established admission pattern:

- `RuntimeState.admit_recommendation` / `admit_event_disturber` —
  validated, duplicate-rejecting, append-only.
- `RuntimeKernel.admit_recommendation` / `admit_event_disturber` — require
  Running; broadcast the EXISTING vocabulary (`RecommendationGenerated` /
  `DisturbanceDetected`) with the established `{entity, operation:"save"}`
  persistence payload (both topics already bridged to the Scheduler);
  refresh the snapshot.
- `RuntimeState.active_recommendations` / `active_event_disturbers` —
  filtered surfaces exposing only live lifecycle objects (Generated/
  Pending/Accepted; Detected/Recorded/Analyzed/Applied) so completed
  objects are naturally excluded from scheduling decisions.

No existing guards, state machines, signatures, or behavior changed. The
non-frozen infrastructure `PersistenceSync` gained two additive handlers
for the two topics (save/update by convention; bare signals ignored).

## 1. Architecture

```
                         Application (facade)
                              │ delegates only
        ┌──────────┬──────────┼───────────┬─────────────┐
        ▼          ▼          ▼           ▼             ▼
   Repositories  Runtime   Scheduler  DecisionEngine  Infrastructure
   (factory)     Kernel                               (bridge, sync)
        └───────────┴─────── all depend downward on ──► Domain
Nothing imports paios.application (grep-verified). No cycles. Every layer
below remains independently testable — proven by their unchanged suites.
```

## 2. Folder Structure

```
backend/paios/application/
├── __init__.py       exports
├── exceptions.py     ApplicationError → NotStarted / AlreadyStarted
├── config.py         ApplicationConfig: data_dir + clock selection
│                     (the ONE composition-time decision about time:
│                      None → SystemClock; inject ManualClock for
│                      deterministic runs)
├── bootstrap.py      build_components(config) -> Components: pure
│                     construction, zero side effects — DIP throughout
└── application.py    Application facade + canonical start/stop + the
                      runtime loop pass (tick / bounded run)
tests/application/    conftest + 5 modules, 52 tests
```

## 3. Startup Sequence (deterministic)

```
Application.start()
  ↓ build_components(config)        pure construction of the full graph
  ↓ repositories.initialize()       .data/ folder + seeded aggregate files
  ↓ PersistenceSync.attach()        subscribed BEFORE anything publishes —
  ↓ RecalculationBridge.attach()    and before the bridge, so saves precede
  │                                 scheduler-driven updates
  ↓ Kernel.boot()                   load → restore → validate invariants →
  │                                 Execution Context → snapshot → Ready
  ↓ Kernel.start()                  Running: the kernel accepts work
  ↓ Scheduler.attach()              boot adoption over Runtime State
Application ready
```

One documented deviation from the mission's illustrative order: the
Scheduler attaches AFTER kernel boot because its boot adoption reads
`kernel.runtime_state`, which requires an operational kernel.

## 4. Shutdown Sequence

```
Application.stop()
  ↓ facade closes (further calls raise ApplicationNotStartedError)
  ↓ Kernel.shutdown()   stop accepting work → services removed (with
  │                     ServiceRemoved events) → ephemeral Runtime State
  │                     and snapshot cleared → Stopped → KernelShutdown
  ↓ flush pending persistence — a documented NO-OP: PersistenceSync is
  │                     synchronous write-through; nothing can be pending
Application stopped     (History intact; restart recovers it — tested)
```

## 5. Service Graph (registered at runtime)

```
ServiceRegistry: clock │ event_bus │ snapshot_manager │ invariant_checker
                 (Kernel-registered at boot)          │ scheduler
                                                      (attach-registered)
Bus topology:  Kernel/Scheduler publish ──► EventBus ──► subscribers:
   PersistenceSync (EventStateChanged, ContextChanged, PlanUpdated,
                    RecommendationGenerated, DisturbanceDetected)
   RecalculationBridge (TimeProgressed, ContextChanged,
                    DisturbanceDetected, RecommendationGenerated)
        └──► SchedulerRecalculationRequested ──► Scheduler (sole topic)
```

## 6. Dependency Injection Graph

```
ApplicationConfig ──► build_components:
   clock      = injected Clock | SystemClock (default)
   repositories = RepositoryFactory(data_dir)
   kernel     = RuntimeKernel(repositories, clock)      ◄─ interfaces + clock
   scheduler  = Scheduler(kernel)                        ◄─ kernel API only
   engine     = DecisionEngine()                         ◄─ stateless
   bridge     = RecalculationBridge(kernel)
   sync       = PersistenceSync(kernel, repositories)
All constructor-injected; nothing constructs its own dependencies;
independent builds share nothing (tested).
```

## 7. The Facade (zero logic — delegation targets shown)

| Method | Delegates to |
|---|---|
| start / stop / started | the canonical sequences above |
| status / snapshot | Kernel |
| active_recommendations / active_event_disturbers | the new filtered Runtime State surfaces |
| evaluate | DecisionEngine (pure — nothing admitted, tested) |
| **tick** | one canonical loop pass: publish TimeProgressed → Scheduler recalculates (via bridge) → DecisionEngine reasons over the fresh snapshot → each new Recommendation is presented (Generated→Pending, the documented Runtime actor) and admitted (broadcast + persisted + Scheduler notified). Deduplication is the Decision Engine's own redundancy filter — a second tick admits nothing (tested) |
| run(n) | bounded tick loop — cadence stays caller-driven because the Timer Engine remains undesigned |
| accept/reject_recommendation, start/pause/resume/complete/cancel/archive_event, report_spontaneous_action | Scheduler user-action API (explicit `at` or the injected Clock) |
| report_disturber | composition of documented steps: create Disturber → Runtime-actor capture chain (Detected→Recorded→Analyzed→Applied when an Active Context Window exists, else it remains Analyzed evidence) → Kernel admission → the Scheduler runs the mandatory chain and resolves it |

## 8. Tests — 52 new

- `test_lifecycle_and_bootstrap.py` (14) — pure construction (no side
  effects), clock injection/defaults, `.data/` default, independent
  builds; startup reaching Running with all five services and seeded
  aggregates; double-start/before-start/after-stop guards; full shutdown;
  **restart recovering persisted reality**; deterministic startup counts.
- `test_admission.py` (10) — the approved correction end-to-end: admission
  into state + storage + snapshot; duplicate rejection; active filtering
  excluding Rejected/Expired and Resolved lifecycles; an admitted
  Recommendation is acceptable and materializes an Event.
- `test_loop.py` (8) — evaluate is pure; tick presents/admits/persists
  with full explanations (real Principle names); a second tick
  deduplicates via the engine's redundancy filter; empty store → valid
  No-Action; bounded run.
- `test_use_cases.py` (11) — the golden path (tick → accept → start →
  complete with Outcome, all persisted); reject; pause/resume; cancel
  (ADR-003 Ready cancel); archive; spontaneous action; disturber with a
  running Event (mandatory chain → Interrupted + Resolved + persisted) and
  without one (Analyzed evidence); resume after disturbance; explicit-`at`
  vs clock defaults.
- `test_determinism_and_guards.py` (9) — identical seeds → identical
  Recommendation IDs across two isolated applications; IDs surviving
  restart; all timestamps from the injected clock; repeatable evaluate;
  facade guard rails; scheduler/domain errors surfacing through the facade
  (unknown work, expired acceptance, completed Events refusing restart).

## 9. Audit

| Check | Result |
|---|---|
| No business/scheduler/decision/repository logic added | facade delegates; bootstrap constructs; the two orchestrations (tick, report_disturber) compose documented steps with documented actors, deciding nothing |
| Dependency direction / no circular imports | `paios.application` is referenced only by itself (grep); all arrows point downward |
| Deterministic startup / shutdown | fixed sequences; pinned by tests incl. cross-instance ID equality |
| No `datetime.now` outside Clock | codebase total remains exactly one — `SystemClock.now` |
| Frozen milestones untouched | committed M1/M2: `git status` clean; M3 changed only by the owner-approved admission correction; scheduler + decision_engine byte-untouched; prior 349 tests pass unchanged |
| Persistence conventions respected | new aggregates persist only through the G2 bus path; sync flush provably unnecessary (synchronous write-through) |

## 10. Deferred Work

| Deferred | Reason |
|---|---|
| Timer Engine (autonomous tick cadence) | Still undesigned (DOMAIN_MODEL.md Future Questions); `tick()/run(n)` keep cadence caller-driven |
| REST API / CLI / UI | Milestone 7+ — explicitly out of scope |
| LLM/AI planner or reasoner integration | Future; the Planner interface (R3) and rule-set injection are the prepared seams |
| Context creation use case | No documented capture flow yet; Contexts are seeded data |
| Learning pipeline wiring (Reflection→Insight, Habit detection, Resource/Knowledge/Progress updates on EventCompleted) | The Learning layer milestone |
| Multi-user composition | Single-user per the current architecture assumptions |

## 11. Suggested Git Commit

```
Milestone 6: Application layer - composition, canonical lifecycle, facade

- ApplicationConfig + pure build_components: full DIP wiring with clock
  selection (Manual/System)
- Canonical startup (sync -> bridge -> boot -> start -> scheduler attach)
  and shutdown (kernel shutdown; flush provably no-op)
- Application facade: zero-logic delegation for recommendations, events,
  spontaneous actions, disturbers; tick()/run(n) runtime loop pass
- Approved Kernel/RuntimeState admission correction: recommendations and
  disturbers enter Runtime State event-driven and append-only, with
  active-only consumption surfaces
- PersistenceSync: additive save handlers for the two admission topics
- 52 new tests; 401 total passing; frozen layers otherwise untouched

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

Milestone 6 deliverables complete. Milestone 7 will not begin without
explicit approval.
