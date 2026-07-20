# BUSINESS_RULES.md

This is one of four documents that together describe PAIOS:

```
DOMAIN_MODEL.md          ← What exists
ENTITY_RELATIONSHIPS.md  ← ERD & ownership
BUSINESS_RULES.md        ← System behavior (this file)
GLOSSARY.md              ← Term definitions
```

This file answers **how the system is allowed to behave**. Entities describe structure (`DOMAIN_MODEL.md`) and connections (`ENTITY_RELATIONSHIPS.md`); the rules below describe the constraints that hold regardless of implementation.

As of v0.4, three distinct categories of rule are represented here, and they are not interchangeable:

- **Principles** (defined in `DOMAIN_MODEL.md`) are immutable, Dharma-level values. They never evolve. The "Principle Rules" section below only enforces that Principles are respected — it does not restate the Principles themselves.
- **Domain Invariants** are structural truths that must always hold, regardless of behavior.
- **Domain Policies** are runtime rules that shape behavior and are expected to evolve as PAIOS learns.

---

## Event Rules

- Every Event belongs to one User.
- Every Event belongs to one Project (optional).
- Every Event owns one Context Window, which references one Context.
- Events are immutable.
- Every Event consumes and produces Resources.
- Events may contribute to multiple Goals.
- Events may satisfy multiple Principles.
- Events have one Impact classification (Opportunity/Neutral/Distraction).
- Events never have Tasks — the Task entity does not exist in this domain.
- Every Event has exactly one Status at any given time, drawn from the Event Lifecycle.

## Event Lifecycle Rules

- An Event's lifecycle states are: Recommended, Scheduled, Ready, Started, Paused, Resumed, Completed, Skipped, Cancelled, Interrupted, Overtaken, Archived.
- The Scheduler controls all Event state transitions. An Event never transitions itself.
- Transitions are recorded, never rewritten. History remains immutable — only new transition records are added.
- Interrupted means the current Event was paused by an external cause (an Event Disturber), not by the user's own choice.
- Overtaken means a higher-priority Event replaced the current one before it could resume; the original Event does not automatically return to Started.
- Valid example transitions include: Scheduled → Ready; Ready → Started; Started → Completed; Started → Interrupted; Interrupted → Resumed; Interrupted → Cancelled; Scheduled → Skipped; Ready → Skipped; Ready → Cancelled; Scheduled → Overtaken; Ready → Overtaken.
- Ready shares every non-start exit of Scheduled (Skipped, Cancelled, Overtaken) — a Ready Event is a Scheduled Event whose planned time has arrived, and readiness never removes the user's freedom not to start (ADR-003).
- Completed, Skipped, and Cancelled Events may later transition to Archived, but never back to an earlier active state.

## Context Rules

- Context is a reusable, static definition. It does not itself carry Start Time or End Time.
- A single Context (e.g., "Office") may be referenced by many Context Windows across many Events.
- Context is not owned by any single Event or User record.
- Context enables pattern reasoning across every occurrence of that Context.

## Context Window Rules

- Every Event owns exactly one Context Window.
- Every Context Window references exactly one Context.
- A Context Window's Current State is one of: Created, Active, Changing, Expired, Archived.
- Exactly one Context Window should normally be Active at a time (see Domain Invariants).
- A new Context Window automatically closes the previously Active one.
- Context Window is created with its owning Event, in line with the pre-existing rule that Context is created with Event.

## Habit Rules

- Habits cannot be manually created.
- Habits are inferred from repeated Events.
- Habits emerge from Event history.
- Habits never own Events.
- Habits are identified automatically.

## Scheduler Rules

- Scheduler never edits history.
- Scheduler begins from Current Time.
- Scheduler minimizes Distractions.
- Scheduler maximizes Opportunities.
- Scheduler respects Principles.
- Scheduler handles Event Disturbers by triggering Context Window transitions, then recalculating, then performing Event State Transitions — never by editing the Event directly.
- Scheduler generates Scheduled Events (not Tasks).
- Scheduler continuously compares Current Clock, Current Context Window, Running Event, Next Scheduled Event, and Available Resources.
- Scheduler recalculates when sufficient deviation is detected between the plan and current reality.
- Only one Scheduler exists per User (see Domain Invariants).

## Event Disturber Rules

- Event Disturbers never modify an Event directly.
- An Event Disturber creates a Context Window transition.
- The Scheduler is the only component that reacts to that transition.
- The Scheduler's reaction is expressed as an Event State Transition, following the same rules as any other transition.
- This three-step separation (Disturber → Context Window transition → Scheduler → Event State Transition) is mandatory, not optional.

## Recommendation Rules

- Recommendations never modify history.
- Recommendations require user acceptance.
- Rejected Recommendations remain historical evidence.
- Recommendations are generated by Decision Engine.
- Recommendations are consumed by Scheduler.
- Recommendations expire over time; an expired Recommendation cannot be accepted.

## Principle Rules

- Principles are immutable.
- Principles are NOT owned by User.
- Users follow Principles.
- Recommendations cannot violate Principles.
- Projects cannot recommend actions that violate Principles.
- Scheduler cannot schedule events that violate Principles.
- Principles never evolve — this is what distinguishes a Principle from a Domain Policy.

## Resource Rules

- Resources are consumed and produced by Events.
- Resources are not simply increased or decreased.
- Every Event affects Resources.
- Resources constrain Recommendations.
- Resources constrain Scheduler.
- Resources cannot become invalid (see Domain Invariants).

## Progress Rules

- Progress is a first-class entity.
- Progress is owned by Project.
- Progress is not embedded in Project.
- Progress references Events, Knowledge, and Resources.
- Progress belongs to exactly one Project (see Domain Invariants).

## Decision Engine Rules

- The Decision Engine owns no data.
- The Decision Engine never writes to History.
- The Decision Engine's only outputs are Recommendations, Priority Evaluations, Confidence Scores, Explanations, and Scheduler Inputs.
- The Decision Engine never decides when the Scheduler replans; replanning is owned exclusively by the Scheduler.

---

# Domain Invariants

Domain Invariants are structural truths that must always hold, regardless of what behavior or Policy is in effect. They describe consistency guarantees, not values.

- Exactly one Active Context Window (per User) at any given time.
- Exactly one Running Event (per User) at any given time.
- Completed Events are immutable.
- Recommendations never modify Events.
- Resources cannot become invalid (e.g., negative where a negative value is not meaningful).
- A Reflection requires an Event — it cannot exist independently.
- Progress belongs to exactly one Project.
- A Context Window references exactly one Context.
- The Scheduler never edits History.
- Event IDs are immutable once assigned.
- Only one Scheduler exists per User.
- Every Event owns exactly one Context Window.
- An Event Disturber never has a direct foreign key to an Event's mutable fields — only to a resulting Context Window transition.
- A Principle, once created, is never deleted or altered by the Decision Engine.

---

# Domain Policies

Domain Policies are runtime rules that shape behavior and are expected to evolve as PAIOS learns. **Policies are not Principles.** Principles never evolve; Policies do.

- Repeated Events infer Habits.
- Repeated rejected Recommendations lower confidence.
- A confidence threshold, once crossed, creates Habit candidates.
- Repeated harmful Context Windows trigger Recommendations.
- Repeated Event Disturbers increase Scheduler flexibility (e.g., wider buffers, more conservative scheduling).
- Recommendations expire.
- Scheduler recalculates after Context Window changes.
- Policies may be tuned, replaced, or retired as the Decision Engine improves. Principles may not.
