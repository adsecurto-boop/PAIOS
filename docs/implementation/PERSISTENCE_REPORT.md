# Persistence Report — Milestone 2

JSON persistence + Repository Layer for PAIOS. Milestone 1 (Domain Layer,
commit `fafc53e`) is the baseline; the only baseline change is the
**approved reconstitution surface** (see section 4 and
DOMAIN_LAYER_REPORT.md — Reconstitution Amendment): additive factories, no
existing method or guard modified. Repositories depend on the Domain; the
Domain never depends on repositories.

Status: complete, audited, 200 tests passing (135 domain — 118 baseline
unchanged + 17 reconstitution — and 65 repository).

**Hydration architecture decision (review outcome):** the initial
implementation rehydrated aggregates by REPLAYING transition history through
public lifecycle commands. Review correctly identified this as coupling
persistence to runtime behavior: history is immutable evidence, and loading
must restore evidence, not re-execute commands (re-adjudicating the past
under present Policies, and colliding with future Runtime Kernel
instrumentation of transition methods). Replay was replaced with
**reconstitution-based hydration** (Option B), documented below.

Technology: Python 3.12 standard library only. Infrastructure surface is
exactly `json` + `pathlib` — no SQLite, no Mongo, no SQLAlchemy, no
network, no clock.

---

## 1. Folder Structure

```
backend/paios/repositories/
├── __init__.py               Package exports (factory, store, errors)
├── errors.py                 Repository exception hierarchy
├── json_store.py             JsonStore: atomic JSON array file I/O
├── interfaces.py             Generic Repository ABC + 15 aggregate interfaces
├── json_repositories.py      Generic JsonRepository + 15 implementations
├── factory.py                RepositoryFactory + data folder initialization
└── serialization/
    ├── __init__.py           Public serialize_*/deserialize_* surface
    ├── primitives.py         Value-object / enum / datetime / transition codecs
    ├── serializers.py        Entity -> JSON dict (one function per aggregate)
    └── deserializers.py      JSON dict -> entity (replay-based rehydration)

tests/repositories/           conftest (rich builders) + 4 test modules
.data/                        Storage location (git-ignored; never committed)
```

## 2. Repository Interfaces

`interfaces.py` defines one generic contract and fifteen typed markers:

```python
class Repository(ABC, Generic[E, I]):
    save(entity)        # insert; DuplicateEntity if the ID exists
    get(entity_id)      # EntityNotFound if missing
    update(entity)      # overwrite; EntityNotFound if missing
    delete(entity_id)   # EntityNotFound if missing
    list()              # all entities, stored order
    exists(entity_id)   # bool
    find_by(**criteria) # attribute-equality filter (persistence query only)
```

Per-aggregate interfaces (all `Repository[Entity, EntityId]` ABCs):
`UserRepository`, `PrincipleRepository`, `ContextRepository`,
`ContextWindowRepository`, `EventRepository`, `ProjectRepository`,
`ProgressRepository`, `ResourceRepository`, `KnowledgeRepository`,
`RecommendationRepository`, `EventDisturberRepository`,
`ReflectionRepository`, `InsightRepository`, `HabitRepository`,
`GoalRepository`.

Repositories only persist. `find_by` is pure attribute equality (e.g.
`find_by(user_id=..., status=EventStatus.COMPLETED)`) — no ranking, no
policy, no reasoning.

## 3. Repository Implementations

`JsonRepository` (generic base) implements the entire contract once; each
concrete class binds four class attributes:

| Repository class | File | ID field |
|---|---|---|
| UserJsonRepository | users.json | user_id |
| PrincipleJsonRepository | principles.json | principle_id |
| ContextJsonRepository | contexts.json | context_id |
| ContextWindowJsonRepository | context_windows.json | window_id |
| EventJsonRepository | events.json | event_id |
| ProjectJsonRepository | projects.json | project_id |
| ProgressJsonRepository | progress.json | progress_id |
| ResourceJsonRepository | resources.json | resource_id |
| KnowledgeJsonRepository | knowledge.json | knowledge_id |
| RecommendationJsonRepository | recommendations.json | recommendation_id |
| EventDisturberJsonRepository | event_disturbers.json | event_disturber_id |
| ReflectionJsonRepository | reflections.json | reflection_id |
| InsightJsonRepository | insights.json | insight_id |
| HabitJsonRepository | habits.json | habit_id |
| GoalJsonRepository | goals.json | goal_id |

One JSON **array** file per aggregate, matching the storage examples in
ENTITY_RELATIONSHIPS.md. `JsonStore` provides the file engine:

- **Atomic writes** — content goes to a `<name>.tmp` sibling then
  `Path.replace()`s into place; a crash mid-write cannot corrupt data.
- **Missing file / empty file** → empty collection (no error).
- **Corrupted JSON / non-array top level** → `SerializationError`.
- **Directory initialization** — created on demand and by
  `RepositoryFactory.initialize()`.

`RepositoryFactory(data_dir=".data")` builds and caches one repository per
aggregate over a single store. `initialize()` creates the folder and seeds
each *missing* file with `[]` (existing data is never touched), making the
documented PAIOS_DATA layout visible on disk.

## 4. Serializer Design — Reconstitution-Based Hydration

Serialization reads **only public domain API** (constructor fields and the
`transitions` / `status` / `state` / `outcome` properties). Deserialization
restores evidence through the domain's **reconstitution factories** (the
DDD reconstitution pattern), never through lifecycle commands:

1. **Parse** persisted transitions into frozen `TransitionRecord`s, in
   order — order IS the history.
2. **Reconstitute** via `Event.restore`, `ContextWindow.restore`,
   `Recommendation.restore`, `EventDisturber.restore`. Each factory
   constructs the entity from its facts and attaches a history built by
   `TransitionHistory.from_records`, which performs **structural
   validation**: every record must be a legal edge of the state machine and
   the chain must be continuous (first `from_state` = initial state; each
   `to_state` = the next record's `from_state`).
3. **Evidence-shape rules replace command preconditions**: an Outcome is
   admissible iff the history passed *through* Completed/Cancelled/
   Overtaken (it may since have Archived); a Reflection link iff the
   history reached Completed/Archived; an Applied Disturber requires its
   resulting Context Window reference; Resolved evidence must agree with
   the persisted resolution status.

The validation taxonomy this establishes:

| Kind | Runs | Examples |
|---|---|---|
| Structural evidence validation | At hydration | legal edges, chain continuity, stored-state match, evidence shape |
| Command preconditions & Policies | Only when new commands execute at runtime | accept-time expiry check, outcome state-gating, fact freezing on new writes |

Policies adjudicate the future, never the past: history recorded under
earlier (evolvable) Domain Policies always loads — proven by a test that
restores a Recommendation whose historical acceptance occurred after its
`expires_at`, while a *new* `accept` command on a restored Recommendation
still enforces the present policy.

Consequences, all by design:

- **History stays append-only through persistence** — order, actors,
  reasons, and timestamps restored verbatim; no lifecycle command executes
  during load; loading is inert with respect to future Runtime Kernel
  instrumentation of transition methods.
- **The domain still rejects corrupted evidence.** Illegal sequences,
  broken chains, and mismatched stored states raise `SerializationError`.
- **Guards are armed on reconstituted aggregates:** a restored Completed
  Event rejects fact mutation and history replacement; a restored Expired
  Context Window is fact-frozen from the moment the factory returns; new
  transitions may still be applied afterward (proven by tests).

Primitive conventions (`primitives.py`):

| Value | JSON form |
|---|---|
| Identifier (15 types) | string |
| Enum (13 types) | its human-readable `.value` |
| datetime | ISO 8601 string (`fromisoformat` round-trip) |
| Duration | integer minutes |
| TimeRange | `{"start": iso, "end": iso}` |
| ResourceFlow | `{"consumed": {type: amount}, "produced": {...}}` |
| EventOutcome | `{"outcome_type", "recorded_at", "note"}` |
| TransitionRecord | `{"from_state", "to_state", "occurred_at", "actor", "reason"}` |
| None | JSON null, both directions |

## 5. JSON Schema (example: one Event record in events.json)

```json
{
  "event_id": "evt_001",
  "user_id": "user_001",
  "project_id": "proj_001",
  "context_window_id": "win_evt_001",
  "category": "study",
  "description": "Studied ISTQB Chapter 3 - Test Management",
  "start_time": "2026-07-20T09:00:00",
  "end_time": "2026-07-20T11:00:00",
  "duration": 120,
  "impact_type": "Opportunity",
  "priority_alignment_score": 9,
  "resource_flow": {
    "consumed": {"Time": 120, "Energy": 20},
    "produced": {"Knowledge": 35, "Career": 25}
  },
  "expected_outcome": "Complete Chapter 3 understanding",
  "actual_outcome": "Completed Chapter 3, took notes",
  "reflection_id": "ref_001",
  "outcome": {"outcome_type": "Completed",
              "recorded_at": "2026-07-20T11:01:00", "note": "as planned"},
  "status": "Completed",
  "transitions": [
    {"from_state": "Recommended", "to_state": "Scheduled",
     "occurred_at": "2026-07-20T09:01:00", "actor": "Scheduler",
     "reason": "accepted"},
    {"from_state": "Scheduled", "to_state": "Ready", "...": "..."}
  ]
}
```

Field names are snake_case per the ENTITY_RELATIONSHIPS.md examples.
`status` (and `current_state`/`state` on the other lifecycle aggregates) is
stored for human readability and **verified** against the replayed history
on load — it is never trusted as the source of truth.

## 6. Error Hierarchy

```
RepositoryError                (base — infrastructure, never a domain error)
├── SerializationError         corrupted JSON, invalid enum/datetime,
│                              missing field, or a persisted record the
│                              domain state machine rejects on replay
├── EntityNotFound             get / update / delete on an absent ID
└── DuplicateEntity            save on an existing ID (update overwrites)
```

Deliberately separate from `paios.domain.errors.DomainError`: domain errors
raised during replay are wrapped into `SerializationError` — corrupted data
is an infrastructure problem, not a domain-rule violation at runtime.

## 7. Dependency Graph

```
paios.domain            (frozen baseline — imports NOTHING outside itself)
      ▲
      │ imports (one direction only)
paios.repositories
├── errors                        → (stdlib only)
├── json_store                    → errors, json, pathlib
├── serialization.primitives      → domain VOs/enums/errors, errors, contextlib
├── serialization.serializers     → domain entities, primitives
├── serialization.deserializers   → domain entities/enums/IDs, primitives, errors
├── interfaces                    → domain entities/IDs, abc, typing
├── json_repositories             → interfaces, json_store, serialization, errors
└── factory                       → interfaces, json_repositories, json_store
```

Verified by grep: the domain contains zero references to
`paios.repositories`; the repository layer imports only `paios.domain.*`,
`paios.repositories.*`, and stdlib (`abc`, `typing`, `dataclasses`,
`datetime`, `enum`, `json`, `pathlib`, `contextlib`).

## 8. Tests — 82 new, 200 total passing

- `test_json_store.py` (11) — missing/empty/whitespace files, corrupted
  JSON, non-array top level, directory creation, round-trip, atomic
  overwrite, no temp-file leftovers, unserializable records.
- `test_serialization.py` (31) — parametrized lossless round-trip for all
  15 aggregates built at their richest legal shape; Event fidelity (enums,
  Duration, ResourceFlow, Outcome, reflection link); transition order,
  actors, reasons, and timestamps preserved; rehydrated entities still
  enforce immutability and append-only history; ContextWindow /
  Recommendation / Disturber fidelity; tuple restoration; TimeRange
  round-trip; corruption detection (invalid enum, missing field, illegal
  transition sequence, tampered `from_state`, stored-status mismatch,
  Applied disturber without window reference, invalid datetime).
- `test_repositories.py` (16) — save/get lossless equality, duplicate save,
  missing get/update/delete, overwrite, delete isolation, insertion-order
  list, `find_by` on stored and derived attributes, persistence across
  fresh repository instances, domain guards after reload, 150-event large
  dataset with full histories.
- `test_factory.py` (7) — folder + all 15 files seeded with `[]`,
  one-file-per-aggregate completeness, never clobbers existing data,
  default `.data/` location, instance caching, end-to-end across
  aggregates.
- `tests/domain/test_reconstitution.py` (17) — the reconstitution surface:
  `from_records` chain validation (continuity, illegal edges, order, empty
  history, append-only afterward); `Event.restore` evidence and guards,
  Outcome-with-Archived evidence, evidence-shape rejections;
  fact-frozen restored Context Windows; the Policy-evolution guarantee for
  Recommendations (historical evidence loads, new commands still enforce
  policy); Disturber evidence-shape rules.

## 9. Audit Findings

Checks performed after implementation:

| Check | Result |
|---|---|
| Domain tests (baseline + reconstitution) | **135 passed** (118 baseline unchanged + 17 new) |
| Milestone 2 tests | **65 passed** |
| Baseline change limited to approved reconstitution surface | additive factories only; no existing method or guard modified |
| Domain imports no repositories | grep: zero matches |
| Repositories import domain + stdlib only | verified import-by-import (section 7) |
| Repositories invoke NO lifecycle commands | grep for `transition_to`/`activate`/`accept`/`record_outcome`/etc. in the repository layer: zero matches — hydration is pure reconstitution |
| No Runtime / Scheduler / Decision Engine / Clock code | none; the words appear only in docstrings stating their absence |
| No `datetime.now()` / any clock access | grep: zero matches |
| No hidden business logic / policy evaluation | repositories do CRUD + codec only; structural validation is the domain's reconstitution surface, invoked not implemented |
| No Task / Todo entity | grep: zero matches |
| Only JSON infrastructure | imports limited to `json` + `pathlib` |

History of the design: the first implementation used replay-based
hydration; its own tests surfaced an Outcome-ordering defect
(Completed-then-Archived Events), which review identified as a symptom of
the deeper flaw — hydration re-executing commands. The replay approach was
replaced wholesale by the reconstitution architecture of section 4; the
defect class is now structurally impossible (evidence-shape rules replace
timeline interleaving).

## 10. Intentionally Deferred

| Deferred | Reason |
|---|---|
| `scheduler.json` | The Scheduler has no domain entity; its persisted state arrives with the Scheduler milestone. |
| Runtime Kernel, Runtime State, System Events | Milestone 3+ — this layer stores data, it never orchestrates. |
| Scheduler, Decision Engine, Policies, Timer Engine, Clock | Later milestones per the approved order. |
| Cross-aggregate referential integrity on load (e.g. an Event's `context_window_id` resolving to a stored window) | Cross-aggregate consistency belongs to Domain Services / Runtime Kernel, not to per-aggregate repositories. |
| Concurrency / file locking | Single-user local persistence per the architecture; revisit only if the architecture ever demands it. |
| Schema versioning / migrations | No schema has ever changed yet; a `schema_version` field can be added when Milestone 3+ first requires evolution. |
| Caching / indexing | JSON-scale data; premature until a real bottleneck appears. |

---

Milestone 2 deliverables complete: code, tests, audit, and this report.
Awaiting review — Milestone 3 will not begin until explicitly approved.
