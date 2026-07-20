# Domain Layer Report — Milestone 1

This report documents the implemented PAIOS Domain Layer so that a new
developer can understand it entirely without reading the code.

Status: Milestone 1 complete, architecture-audited (2 violations found and
corrected during audit), 118 unit tests passing.

Technology: Python 3.12, standard library only (`dataclasses`, `enum`,
`typing`, `datetime`, `uuid`, `types`). No frameworks, no I/O, no
persistence, no clock access — every mutation takes an explicit
caller-supplied Current Time.

Governing documents, in precedence order (see
`docs/architecture/CANONICAL_ORDER.md`): DOMAIN_MODEL.md, BUSINESS_RULES.md,
ENTITY_RELATIONSHIPS.md, STATE_MACHINES.md, BEHAVIORAL_ARCHITECTURE.md,
RUNTIME_EXECUTION.md, DECISION_ENGINE.md, ADRs.

## Approved Architectural Resolutions

Five conflict resolutions were approved by the project owner before
implementation and are binding:

1. **Event lifecycle** is exactly the twelve states of DOMAIN_MODEL.md
   Principle 19. "Running" is a runtime concept (Started or Resumed), never
   an Event state. The extended states in BEHAVIORAL_ARCHITECTURE.md §8
   (Pending, Running, Reflected, Learned, Aborted) are rejected.
2. **One Event aggregate.** No ScheduledEvent, PlanningEvent, Task, or Todo
   entity exists. A "Scheduled Event" is an Event in the Scheduled state;
   STATE_MACHINES.md §2 is the Scheduler's behavioral view of the Event.
3. **Running Event invariant at full strength**: exactly one *logical*
   Running Event per User at all times. When no user Event is running, the
   Runtime Kernel (later milestone) owns a System Idle Event. The Idle Event
   belongs to the Runtime layer and is deliberately absent from the Domain
   Layer; the domain preserves the invariant without weakening it.
4. **Recommendation lifecycle**: Generated → Pending → Accepted / Rejected /
   Expired; Accepted → Consumed.
5. **Event Outcome** is an immutable Value Object recorded after execution —
   independent of the lifecycle, never a lifecycle state.

---

## 1. Folder Structure

```
backend/paios/domain/
├── __init__.py               Package doc: domain drives the codebase
├── errors.py                 Domain exception hierarchy
├── enums.py                  All 13 domain enums + RUNNING_STATES
├── value_objects/
│   ├── identifiers.py        15 typed, frozen entity identifiers
│   ├── time.py               Duration (minutes), TimeRange
│   ├── resource_flow.py      ResourceFlow (consumed/produced per Event)
│   └── event_outcome.py      EventOutcome (immutable execution evidence)
├── state_machines/
│   ├── machine.py            Generic StateMachine, TransitionRecord,
│   │                         append-only TransitionHistory
│   └── definitions.py        The 4 formal machines (Event, Context Window,
│                             Recommendation, Event Disturber)
├── entities/
│   ├── base.py               Entity mixin: identity-based equality
│   ├── principle.py          Layer 1 — Foundation
│   ├── context.py            Reusable, unowned definition
│   ├── user.py               Layer 2 — ownership anchor
│   ├── context_window.py     Time-bounded activation of a Context
│   ├── event.py              THE single Event aggregate
│   ├── project.py            + progress.py, resource.py, knowledge.py,
│   ├── recommendation.py       event_disturber.py   (Layer 2)
│   ├── reflection.py         + insight.py, habit.py, goal.py
│   └── ...                     (History / Layer 3 — Emergent)
└── services/
    └── invariants.py         Full invariant catalog + cross-aggregate checks

tests/domain/                 conftest.py + 8 test modules, 118 tests
pyproject.toml                pytest configuration only; zero dependencies
```

Exceptions (`errors.py`): `DomainError` → `DomainValidationError`,
`InvalidTransitionError` (→ `RecommendationExpiredError`),
`ImmutabilityViolationError`, `InvariantViolationError`.

---

## 2. Entities

Equality for mutable entities is by identity (type + ID), via the `Entity`
mixin. Frozen entities are value-like records of History or foundational
definitions.

### Layer 1 — Foundation

| Entity | File | Mutability | Notes |
|---|---|---|---|
| **Principle** | principle.py | Frozen | Represents Dharma. No `user_id` field — foundational and unowned. `reviewed(at)` returns a *new* value (deliberate User action); nothing can edit one in place. Categories: Health, Responsibility, Truth, Resources, Learning, Detachment. |

The **Decision Engine has no entity** — it is a stateless reasoning
component that owns no data (DOMAIN_MODEL.md). Its absence is intentional.

### Layer 2 — Operational

| Entity | File | Mutability | Key fields / behavior |
|---|---|---|---|
| **User** | user.py | Mutable | `user_id`, `name`, `created_at`, `last_active`; `record_activity(at)`. |
| **Event** | event.py | Controlled | THE aggregate. Fields: `event_id`, `user_id`, `context_window_id` (owns exactly one), optional `project_id`, `category`, `description`, `start_time`, `end_time`, `duration`, `impact_type` (Opportunity/Neutral/Distraction), `priority_alignment_score` (validated 0–10), `resource_flow`, `expected_outcome`, `actual_outcome`, optional `reflection_id`. Lifecycle via `transition_to(state, at, actor="Scheduler", reason)`. `is_running` derives the Running concept. Guards: `event_id` immutable; `_history` non-replaceable; all 13 fact fields freeze permanently on entering Completed/Skipped/Cancelled/Overtaken/Archived; `record_outcome` once, only in Completed/Cancelled/Overtaken; `link_reflection` once, only when Completed/Archived. |
| **Context** | context.py | Frozen | Reusable situational definition (Office, Home…). No `user_id`, no `event_id`, no time boundaries — static by design. Fields: name, location, people, emotion, trigger, reason, environment, notes. |
| **ContextWindow** | context_window.py | Controlled | One activation of one Context, owned by one Event (`event_id` back-reference). Fields: start/end time, duration, reason_started/ended. Methods: `activate`, `mark_changing`, `expire` (writes closing facts, computes duration), `archive`. Guards: facts freeze once Expired/Archived ("past Context Windows are immutable"); `_history` non-replaceable; a failed `expire` mutates nothing. |
| **Project** | project.py | Mutable | Owned by User; `attach_progress` rejects a second Progress. Status: Active/Completed/Paused. |
| **Progress** | progress.py | Mutable | Owned by exactly one Project (required `project_id`). Completion % validated 0–100. `update(at, ...)` stamps `last_updated`. |
| **Resource** | resource.py | Mutable | `consume`/`produce` with positive magnitudes; cannot become invalid (negative where not meaningful) unless `negative_allowed` models the "where meaningful" clause. |
| **Knowledge** | knowledge.py | Mutable | Domain/topic/concept; confidence 0–100; `revise(at)` increments revision count; `mark_applied`; `update_retention`. |
| **Recommendation** | recommendation.py | Controlled | Decision Engine output, owned by User. Required `reason`, `created_at`, `expires_at` (must be later). Methods: `present`, `accept` (raises `RecommendationExpiredError` at/after `expires_at`), `reject`, `expire`, `consume`. Rejection is terminal historical evidence; `_history` non-replaceable. Holds NO Event reference. |
| **EventDisturber** | event_disturber.py | Controlled | Type (Friend/Work/Health/Environment/Family/Other), severity (Low/Medium/High). Structurally holds NO Event foreign key — only `resulting_context_window_id` (set by `apply`) plus an evidential tuple of affected Event IDs. Methods walk the mandatory chain: `record` → `analyze` → `apply` → `resolve` (actor "Scheduler") → `archive`. |

### History and Layer 3 — Emergent

| Entity | File | Mutability | Notes |
|---|---|---|---|
| **Reflection** | reflection.py | Frozen | Requires an Event and its Context Window (required constructor args). Facts, interpretation, root cause, lesson learned, improvement. |
| **Insight** | insight.py | Frozen | Requires a source Reflection. Category, confidence, reusable flag. |
| **Habit** | habit.py | Mutable | Never manually created: `Habit.infer(...)` is the sole intended creation path. Strength 0–100. Holds no Event references (never owns Events). |
| **Goal** | goal.py | Mutable | Suggested by "Decision Engine" (default), `accept(at)` records user acceptance. Emergent direction, not a fixed destination. |

---

## 3. Value Objects

All frozen, self-validating, equality-by-value.

| Value Object | File | Description |
|---|---|---|
| 15 typed identifiers | identifiers.py | `UserId`, `EventId`, `ProjectId`, `ContextId`, `ContextWindowId`, `PrincipleId`, `ResourceId`, `KnowledgeId`, `RecommendationId`, `ProgressId`, `ReflectionId`, `InsightId`, `HabitId`, `GoalId`, `EventDisturberId`. Non-empty strings; `Type.new()` mints a UUID; distinct types never compare equal — an EventId cannot be passed where a UserId belongs. |
| `Duration` | time.py | Non-negative integer **minutes** (per ENTITY_RELATIONSHIPS.md schema). `between(start, end)`, timedelta conversion. |
| `TimeRange` | time.py | `start`/`end` with `end >= start`; `duration`; `contains(moment)`. |
| `ResourceFlow` | resource_flow.py | The consumed/produced breakdown attached to one Event. Keys are `ResourceType`; amounts are **positive magnitudes** (direction = which side of the flow). Mappings exposed read-only. |
| `EventOutcome` | event_outcome.py | `outcome_type` (Completed/Partial/Failed/Abandoned), `recorded_at`, optional note. Immutable evidence, independent of lifecycle (Resolution 5). |

---

## 4. Enums

All in `enums.py`, all `@unique`:

| Enum | Members |
|---|---|
| `EventStatus` | Recommended, Scheduled, Ready, Started, Paused, Resumed, Completed, Skipped, Cancelled, Interrupted, Overtaken, Archived — the canonical twelve |
| `EventOutcomeType` | Completed, Partial, Failed, Abandoned |
| `ImpactType` | Opportunity, Neutral, Distraction |
| `ContextWindowState` | Created, Active, Changing, Expired, Archived |
| `RecommendationStatus` | Generated, Pending, Accepted, Rejected, Expired, Consumed |
| `DisturberType` | Friend, Work, Health, Environment, Family, Other |
| `DisturberSeverity` | Low, Medium, High |
| `DisturberResolutionStatus` | Pending, Resolved |
| `DisturberState` | Detected, Recorded, Analyzed, Applied, Resolved, Archived |
| `ResourceType` | Time, Money, Health, Energy, Knowledge, Focus, Stress, Career, Spiritual |
| `ProjectStatus` | Active, Completed, Paused |
| `GoalStatus` | Active, Completed, Paused |
| `PrincipleCategory` | Health, Responsibility, Truth, Resources, Learning, Detachment |

Constant `RUNNING_STATES = {Started, Resumed}` encodes the GLOSSARY.md
Running Event concept without making it a state.

---

## 5. State Machines

Defined in `state_machines/definitions.py`, transcribed edge-for-edge from
the formal tables of STATE_MACHINES.md. A transition not listed is invalid
and raises `InvalidTransitionError`.

### Event Lifecycle (STATE_MACHINES.md §1)

```
Recommended → Scheduled
Scheduled   → Ready | Skipped | Cancelled | Overtaken
Ready       → Started
Started     → Paused | Interrupted | Completed
Paused      → Resumed | Cancelled
Resumed     → Started | Completed
Interrupted → Resumed | Cancelled | Overtaken
Completed   → Archived
Skipped     → Archived
Cancelled   → Archived
Overtaken   → (terminal)
Archived    → (terminal)
```

Notable consequences, all doc-mandated: `Recommended → Started` impossible
(a Recommendation is not execution); `Scheduled → Completed` impossible (a
plan is not proof of action); Completed history cannot reopen; **Overtaken
does not archive** — BUSINESS_RULES.md permits Archived only from Completed,
Skipped, and Cancelled.

### Context Window Lifecycle (§3)

```
Created → Active → Changing → Expired → Archived
              └──────────────→ Expired
```

Invalid by omission: `Created → Expired`, `Expired → Active`,
`Archived → Active`.

### Recommendation Lifecycle (§6 + Resolution 4)

```
Generated → Pending → Accepted → Consumed
                    → Rejected   (terminal evidence)
                    → Expired    (terminal)
```

Invalid by omission: `Generated → Accepted` (no decision before
presentation), `Pending → Consumed` (Scheduler receives only accepted
Recommendations), reopening Rejected/Expired.

### Event Disturber Lifecycle (§5)

```
Detected → Recorded → Analyzed → Applied → Resolved → Archived
```

Strictly linear: `Detected → Applied` is impossible, forcing the mandatory
causal chain — Disturber → Context Window transition → Scheduler
recalculation → Event State Transition (DOMAIN_MODEL.md Principle 24).

Actors: every transition records the applying authority. Defaults follow the
STATE_MACHINES.md actor columns — "Scheduler" for Event transitions and
Recommendation decisions, "Runtime" for Context Window and Disturber
transitions (except Disturber `resolve`, actor "Scheduler").

---

## 6. Domain Invariants

All fourteen invariants from BUSINESS_RULES.md are **defined** in
`services/invariants.py` as a machine-readable catalog
(`DOMAIN_INVARIANTS`), each with a scope and Milestone-1 enforcement status.
Per the approved rule: entities enforce only their own invariants;
cross-aggregate invariants live in Domain Services; system-wide runtime
invariants belong to the Runtime Kernel (defined now, enforced later).

| Invariant | Scope | Enforced in M1 | How |
|---|---|---|---|
| Exactly one Active Context Window per User | Runtime Kernel | Defined only | `ensure_single_active_context_window` checks on demand; auto-closing the previous window is Kernel behavior |
| Exactly one Running Event per User | Runtime Kernel | Defined only | **Not weakened** (Resolution 3). Domain checks at most one running *user* Event; the Kernel's System Idle Event completes the exactly-one guarantee later |
| Completed Events are immutable | Entity | Yes | Event freezes all fact fields in post-execution states |
| Recommendations never modify Events | Entity | Yes | Structural: Recommendation holds no Event reference |
| Resources cannot become invalid | Entity | Yes | `Resource.consume` rejects invalid results |
| A Reflection requires an Event | Entity | Yes | Structural: required constructor arguments |
| Progress belongs to exactly one Project | Entity | Yes | Required `project_id`; `attach_progress` rejects a second |
| Context Window references exactly one Context | Entity | Yes | Structural: single required `context_id` |
| Scheduler never edits History | Runtime Kernel | Defined only | Domain contributes fact-freezing + non-reopening terminal states |
| Event IDs are immutable once assigned | Entity | Yes | `__setattr__` guard |
| Only one Scheduler per User | Runtime Kernel | Defined only | Scheduler is not a domain entity |
| Every Event owns exactly one Context Window | Domain Service | Yes | Structural per Event + `ensure_unique_context_window_ownership` |
| Disturber never references an Event's mutable fields | Entity | Yes | Structural: only a Context Window reference exists |
| A Principle is never deleted/altered by the Decision Engine | Entity | Yes | Structural: frozen dataclass |

Cross-aggregate check functions (callable now, wired to the Kernel later):
`ensure_single_active_context_window`, `ensure_at_most_one_running_user_event`
/ `find_running_event`, `ensure_unique_context_window_ownership`.

---

## 7. Ownership Relationships

Implemented exactly per ENTITY_RELATIONSHIPS.md:

```
PAIOS
 └─ Principle                    foundational, unowned (no user_id field)
 └─ Decision Engine              stateless, no entity, owns nothing

Context                          reusable, unowned (no user_id/event_id)
 └─ referenced by → many ContextWindows          (context_id, 1:N)

User
 ├─ owns → Project ──owns──► Progress            (progress_id / project_id)
 ├─ owns → Event ───owns──► ContextWindow        (1:1, window has event_id
 │            │                                   back-reference)
 │            └─ may link → Reflection ──generates──► Insight
 ├─ owns → Resource, Knowledge
 ├─ owns → Recommendation        (Decision Engine output; no Event reference)
 ├─ owns → EventDisturber        (references resulting ContextWindow only)
 ├─ owns → Habit                 (emergent; holds no Event references)
 ├─ owns → Insight               (emergent; originates from a Reflection)
 └─ owns → Goal                  (emergent; related_project_ids)
```

References are by typed ID only — entities never hold object references to
other entities, so there are no circular dependencies and no aggregate can
mutate another. The Scheduler and Runtime Kernel own no domain entity;
"ownership" of Scheduled Events is the Scheduler *controlling transitions*
of the one Event aggregate, recorded as the transition actor.

---

## 8. Transition History Design

The append-only machinery in `state_machines/machine.py` implements
"transitions are recorded, never rewritten" (BUSINESS_RULES.md):

- **`StateMachine`** — a named map of allowed transitions over one enum.
  `validate(from, to)` raises `InvalidTransitionError`; a state with no
  outgoing edges is terminal.
- **`TransitionRecord`** — one frozen piece of lifecycle evidence:
  `from_state`, `to_state`, `occurred_at` (caller-supplied), `actor`,
  optional `reason`.
- **`TransitionHistory`** — holds the initial state plus an internal list of
  records. `current_state` is *derived* (last record's target, else the
  initial state); `records` is exposed only as a tuple; `apply` validates
  then appends. There is no removal or rewrite API. A failed `apply` leaves
  the history untouched.

Aggregate-boundary hardening (added during the architecture audit):

- The `_history` attribute of Event, ContextWindow, Recommendation, and
  EventDisturber cannot be reassigned after construction — replacing the
  evidence trail raises `ImmutabilityViolationError`.
- Event facts freeze permanently on entering any post-execution state;
  ContextWindow facts freeze once Expired/Archived. The only post-execution
  writes permitted anywhere are Event's write-once Outcome and write-once
  Reflection link — new evidence *about* History, never edits *of* it.

Each aggregate starts at its documented initial state (Event: Recommended;
ContextWindow: Created; Recommendation: Generated; Disturber: Detected) with
an empty record list, and exposes `status`/`state`/`current_state` plus a
`transitions` tuple.

---

## 9. Intentionally NOT Implemented (Milestone 2+)

Deliberate absences — none of these is an oversight:

| Deferred | Belongs to | Why deferred |
|---|---|---|
| Repositories, JSON persistence, `.data/` layout | Milestone 2 (Infrastructure) | Domain must stay free of persistence (PERSISTENCE.md / REPOSITORIES.md are placeholders) |
| Runtime Kernel, Runtime State, System Events bus | Milestone 3 | BEHAVIORAL_ARCHITECTURE.md §4–5, §12 |
| **System Idle Event** | Runtime Kernel | Resolution 3: satisfies "exactly one Running Event" when no user Event runs; a Runtime-layer concept by decision |
| Auto-closing the previous Active Context Window | Runtime Kernel | The invariant is defined; the enforcement behavior is runtime orchestration |
| Scheduler (planning, replanning, deviation comparison, disturber handling) | Milestone 4 | ADR-002; the domain only records "Scheduler" as transition actor |
| Decision Engine (reasoning pipeline, candidates, ranking, confidence calculation) | Milestone 5 | DECISION_ENGINE.md; owns no data, so it has no domain footprint |
| Domain Policies (habit inference thresholds, confidence decay, expiry policies) | Reasoning/Runtime layers | Policies evolve; only the *hooks* (e.g. `Habit.infer`, `expires_at`) exist in the domain |
| Timer Engine | Future (undesigned) | DOMAIN_MODEL.md Future Questions |
| APIs, UI, AI integration | Milestone 6+ | API.md is a placeholder |
| Clock access | Runtime | The domain never calls `datetime.now()`; Current Time is always an argument |

---

## 10. Architecture Document → Implementation Mapping

| Document | Where it landed |
|---|---|
| DOMAIN_MODEL.md — entities, layers, Principles 1–24 | Entity set and fields (`entities/`), the three layers in `entities/__init__.py`, one-Event-aggregate design, Context/ContextWindow split, Time-as-argument convention |
| BUSINESS_RULES.md — rules, Invariants, Policies | Entity guards; `services/invariants.py` catalog (all 14); lifecycle rule "transitions recorded, never rewritten" in `TransitionHistory`; expired-cannot-accept in `Recommendation.accept`; Overtaken-does-not-archive in the Event machine |
| ENTITY_RELATIONSHIPS.md — ERD, ownership, schema | Typed ID references, `event_id` back-reference on ContextWindow, Duration in integer minutes, ResourceFlow shape mirroring the storage example, Principle/Context having no owner fields |
| GLOSSARY.md — term definitions | Naming throughout; `RUNNING_STATES` (Running = Started or Resumed); docstrings quote definitions |
| STATE_MACHINES.md — formal transition tables | `state_machines/definitions.py` (all four machines, edge-for-edge), actor defaults per the actor columns, `EventOutcome` VO, invalid transitions covered by tests |
| BEHAVIORAL_ARCHITECTURE.md | Consulted for boundaries; its extended Event states rejected per Resolution 1; Kernel/engine responsibilities catalogued as deferred (§9 above) |
| RUNTIME_EXECUTION.md — guarantees, ownership matrix | "Past Context Windows are immutable" → ContextWindow fact-freeze; component ownership respected by keeping Scheduler/Kernel/Clock out of the domain |
| DECISION_ENGINE.md | Confirms the Decision Engine has no entity and no domain logic; Recommendation fields are its output contract |
| ADR-001 (Task Removal) | No Task/Todo anywhere; flow is Recommendation → (Scheduler) → Event states |
| ADR-002 (Scheduler) | Scheduler is a future component; the domain exposes exactly what it will need: state machines, transition actors, invariant checks |

## Test Suite Summary

118 tests in `tests/domain/`: value objects (IDs, time, ResourceFlow,
Outcome), state-machine machinery (append-only, frozen records, failed
transitions harmless), Event (every valid path, every documented invalid
transition, immutability, outcome-once, reflection-once), ContextWindow
(lifecycle + past-window immutability), Recommendation (lifecycle + expiry by
state and by time), EventDisturber (chain + structural no-Event-reference),
remaining entities, and the invariant catalog/checks. Run with `python -m
pytest` from the repository root; configuration lives in `pyproject.toml`.
