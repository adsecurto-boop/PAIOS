# GLOSSARY.md

This is one of four documents that together describe PAIOS:

```
DOMAIN_MODEL.md          ← What exists
ENTITY_RELATIONSHIPS.md  ← ERD & ownership
BUSINESS_RULES.md        ← System behavior
GLOSSARY.md              ← Term definitions (this file)
```

One-line-to-one-paragraph definitions for every term used across the other three documents, alphabetized. For full structure and field lists, see `DOMAIN_MODEL.md`. For relationships and ownership, see `ENTITY_RELATIONSHIPS.md`. For governing rules, see `BUSINESS_RULES.md`.

---

**Active (Context Window state)**
The Context Window state indicating this activation of a Context is currently in effect. Normally, only one Context Window per User should be Active at a time; a new Active Context Window automatically closes the previous one.

**Archived (Context Window state)**
The final Context Window state, indicating the window has aged out of active reporting but remains in History.

**Archived (Event state)**
The final Event Lifecycle state. A Completed, Skipped, or Cancelled Event that has aged out of active reporting but remains permanently in History.

**Behavioral Architecture**
A future document, not yet written, that will define **HOW** the entities in this Domain Model behave over time — ticks, triggers, timing, and runtime mechanics. Sits between the Domain Model and Application Services in the implementation order: Domain Model → Behavioral Architecture → Application Services → Infrastructure.

**Cancelled (Event state)**
An Event Lifecycle state indicating a Scheduled, Paused, or Interrupted Event was deliberately abandoned before completion.

**Changing (Context Window state)**
A Context Window state indicating the window is in the process of transitioning — typically triggered by an Event Disturber — before settling into Expired or a new Active window taking over.

**Completed (Event state)**
An Event Lifecycle state indicating the Event finished as intended and has become part of immutable History.

**Completed Event**
An Event that has actually happened, as opposed to a Scheduled Event that is merely planned. Once Completed, an Event is immutable and becomes part of History.

**Context**
A reusable, static definition of a situational category — for example, "Office," "Home," "Temple," "Travel," or "With Team Lead." Context does not carry time; it does not know when it is active. As of v0.4, Context is deliberately not made temporal — see Context Window.

**Context Window**
A time-bounded activation of a Context. Owned by exactly one Event; references exactly one Context. Carries Start Time, End Time, Duration, and a Current State drawn from the Context Lifecycle. The same Context can have many different Context Windows across many days — "same Context, different Context Window."

**Context Lifecycle**
The set of states a Context Window can be in: Created, Active, Changing, Expired, Archived. Context itself has no lifecycle — only its Windows do.

**Created (Context Window state)**
The initial Context Window state, before it becomes Active.

**Current Time**
The reference point every entity in PAIOS reasons relative to. See Time.

**Decision Engine**
The stateless reasoning core of PAIOS. Reads Events, Projects, Resources, Knowledge, Habits, Context, Principles, and the current time; produces Recommendations, priority evaluations, and Scheduler inputs. Owns no data of its own.

**Dharma**
The conceptual foundation behind Principles — the idea of timeless, values-based rules that guide right action, independent of any single decision's short-term outcome.

**Distraction**
One of the three possible Impact classifications for an Event, indicating the Event worked against the user's priorities. See also: Opportunity, Neutral.

**Domain Invariant**
A structural truth that must always hold, regardless of behavior — for example, "exactly one Active Context Window." Invariants describe consistency guarantees, not values, and are distinct from both Principles (which are values) and Policies (which are behavior).

**Domain Policy**
A runtime rule that shapes behavior and is expected to evolve as PAIOS learns — for example, "repeated rejected Recommendations lower confidence." Policies are explicitly not Principles: Policies evolve, Principles never do.

**Emergent Layer**
The architectural layer (Layer 3) containing entities that are never manually created but are instead inferred or suggested from patterns in History: Habits, Insights, and Goals.

**Event**
A single completed action performed by the user. The immutable source of truth for the entire system. As of v0.4, an Event carries a Status drawn from the Event Lifecycle and owns one Context Window.

**Event Disturber**
An unexpected situation — a friend arriving, a health issue, a power cut, an emergency — that interrupts the Scheduler's plan. As of v0.4, clarified to never modify an Event directly: it creates a Context Window transition, which the Scheduler responds to by recalculating and performing an Event State Transition.

**Event Lifecycle**
The full sequence of states an Event can occupy: Recommended, Scheduled, Ready, Started, Paused, Resumed, Completed, Skipped, Cancelled, Interrupted, Overtaken, Archived. See `DOMAIN_MODEL.md` → Architectural Principle 19 for the meaning of each.

**Event State Machine**
The set of valid transitions between Event Lifecycle states (e.g., Scheduled → Started, Started → Interrupted). Transitions are controlled exclusively by the Scheduler and are recorded, never used to rewrite History.

**Expired (Context Window state)**
A Context Window state indicating the window's time boundary has passed and it is no longer Active.

**Foundation Layer**
The architectural layer (Layer 1) containing Principles and the Decision Engine — components that sit above the User rather than being owned by them.

**Goal**
An emergent, non-fixed direction suggested by the Decision Engine based on long-term Project completion and Event history. The user may accept or reject a suggested Goal.

**Habit**
A recurring behavior pattern inferred automatically from repeated Events. Habits are never manually created and never own the Events that produced them.

**History**
Everything that has actually happened: Events, their Context Windows, and Reflections on them. Immutable by definition.

**Impact Classification**
A single label — Opportunity, Neutral, or Distraction — applied to each Event (never to an Activity type in the abstract) describing whether that specific occurrence helped, was neutral to, or worked against the user's priorities.

**Inference**
What PAIOS understands, as distinguished from History (what happened) and Planning (what PAIOS suggests). Includes Knowledge, Habits, and Insights.

**Insight**
A piece of reusable, distilled knowledge generated from a Reflection. Insights make individual learnings actionable for future Recommendations.

**Interrupted (Event state)**
An Event Lifecycle state indicating the current Event was temporarily paused because an Event Disturber forced a Scheduler recalculation — not because the user chose to pause it. An Interrupted Event may later Resume, be Cancelled, or be Overtaken.

**Knowledge**
Tracked learning and skill acquisition, gained through Events and belonging primarily to Projects. Changes over time through revision, application, and retention decay.

**Neutral**
One of the three possible Impact classifications for an Event, indicating the Event neither helped nor hurt the user's priorities. See also: Opportunity, Distraction.

**Opportunity**
One of the three possible Impact classifications for an Event, indicating the Event advanced the user's priorities. See also: Neutral, Distraction.

**Operational Layer**
The architectural layer (Layer 2) containing the day-to-day working entities of PAIOS: User, Projects, Events, Context, Context Window, Scheduler, Resources, Knowledge, Recommendations, Progress, Reflections, and Event Disturbers.

**Overtaken (Event state)**
An Event Lifecycle state indicating a higher-priority Event, produced by a new Recommendation and Scheduler recalculation, has replaced the current Event before it could resume. Distinct from Cancelled: an Overtaken Event lost its place to something more urgent rather than being rejected outright.

**PAIOS**
Personal AI Operating System. Not a task manager — a system that continuously observes Events, reasons over them, learns patterns, protects the user's priorities, and generates better future plans. As of v0.4, described as a living behavioral operating system.

**PAIOS_DATA**
The data storage layer that separates raw user data from application logic, enabling schema version control without exposing private data. See `ENTITY_RELATIONSHIPS.md` → PAIOS_DATA Structure.

**Paused (Event state)**
An Event Lifecycle state indicating a Started Event has been temporarily halted by the user's own choice, without external interruption. Distinct from Interrupted, which is externally caused.

**Planning**
What PAIOS suggests, as distinguished from History (what happened) and Inference (what PAIOS understands). Includes Recommendations, the Scheduler, and Scheduled Events.

**Principle**
A timeless, immutable rule — representing Dharma — that constrains all Recommendations, Scheduler decisions, and Project actions. Not owned by the User; the User follows Principles rather than possessing them. Never evolves — distinct from a Domain Policy, which does.

**Priority Alignment Score**
A 0–10 field on an Event indicating how well that Event aligned with the user's priorities at the time.

**Progress**
A first-class entity, owned by a Project, tracking completion percentage, knowledge gained, habit score, resource delta, velocity, estimated completion, and confidence. Changes over time.

**Project**
An intentional body of work containing many Events, consuming Resources, improving Knowledge, and owning Progress. Not itself a Goal.

**Ready (Event state)**
An Event Lifecycle state indicating a Scheduled Event's start time has arrived and its preconditions (Resources, Context Window) are satisfied; it awaits the user to begin.

**Recommended (Event state)**
The first Event Lifecycle state: the Event exists only as a suggestion produced by the Decision Engine and has not yet been accepted or placed on the Scheduler.

**Recommendation**
A suggested next action, generated by the Decision Engine and requiring explicit user acceptance before the Scheduler acts on it. Never modifies History; rejected Recommendations remain as historical evidence. As of v0.4, Recommendations expire over time.

**Reflection**
The user's retrospective interpretation of why an Event happened — facts, interpretation, root cause, lesson learned. Distinct from Context, which is a reusable situational definition rather than a specific interpretation. Generates Insights.

**Resource**
A quantity — time, money, health, energy, knowledge, focus, and similar — that Events consume and produce. Grounds Recommendations and the Scheduler in what is actually feasible. Changes relative to Current Time.

**Resource Flow**
The consumed/produced breakdown of Resources attached to a single Event (e.g., Study consumes Energy and produces Knowledge and Career progress). Documented as part of the Event itself.

**Resumed (Event state)**
An Event Lifecycle state indicating a Paused or Interrupted Event has continued from where it left off.

**Running Event**
The single Event, per User, currently in the Started (or Resumed) state. See Domain Invariant: "Exactly one Running Event."

**Scheduled (Event state)**
An Event Lifecycle state indicating the Recommendation has been accepted and the Scheduler has placed the Event into a future Context Window.

**Scheduled Event**
An Event the Scheduler has planned for the future but which has not yet been performed. Becomes a Completed Event once it actually happens.

**Scheduler**
The component that plans future Events, replacing the earlier Timeline concept. Begins from the current moment, respects Principles/Resources/time/Recommendations, generates Scheduled Events, and controls all Event State Transitions. As of v0.4, continuously compares Current Clock, Current Context Window, Running Event, Next Scheduled Event, and Available Resources, recalculating on sufficient deviation. Never edits History.

**Skipped (Event state)**
An Event Lifecycle state indicating a Scheduled Event was never started, and its Context Window passed without action.

**Started (Event state)**
An Event Lifecycle state indicating the user has begun performing the Event.

**Task**
A removed concept. PAIOS does not have a Task entity; the domain intentionally replaced `Recommendation → Task → Event` with `Recommendation → Scheduler → Scheduled Event → Completed Event`. Retained here only so the term is recognized as deliberately absent.

**Time**
As of v0.4, a first-class architectural concept rather than a mere timestamp field. Everything in PAIOS exists relative to Current Time. Time synchronizes the Decision Engine, Scheduler, Events, Recommendations, Resources, Context (via Context Window), and Progress. Described as "the heartbeat of PAIOS."

**Timer Engine**
A not-yet-designed future component responsible for triggering the Scheduler's continuous comparisons at the right cadence (second, minute, event-driven, or hybrid). See `DOMAIN_MODEL.md` → Future Questions.

**Timeline**
A deprecated/renamed concept. See Scheduler — the entity now responsible for planning, which unlike the old Timeline actively recalculates rather than passively displaying a fixed sequence.

**User**
The individual using PAIOS. Owns Projects, Events, Scheduler state, Resources, Knowledge, Recommendations, Habits, Insights, and Goals — but follows rather than owns Principles, and does not own Context, which is a shared, reusable definition.
