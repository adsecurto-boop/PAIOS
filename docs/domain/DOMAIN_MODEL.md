# DOMAIN_MODEL.md

This is one of four documents that together describe PAIOS:

```
DOMAIN_MODEL.md          ← What exists (this file)
ENTITY_RELATIONSHIPS.md  ← ERD & ownership
BUSINESS_RULES.md        ← System behavior
GLOSSARY.md              ← Term definitions
```

This file answers **what exists**: the philosophy, the architectural layers, and the purpose of every entity. It intentionally does *not* enumerate entity-to-entity relationships or foreign keys — see `ENTITY_RELATIONSHIPS.md` for that. It also does not restate system behavior rules — see `BUSINESS_RULES.md`. For a one-line definition of any term, see `GLOSSARY.md`.

---

# Architectural Status

Current Version: v0.4 (Conceptual)

Status:
- ✅ Domain entities under active design
- ✅ Philosophy established
- ✅ Architectural layers defined
- ✅ Task entity removed from domain
- ✅ Decision Engine conceptually defined
- ✅ Scheduler conceptually defined (replaces Timeline)
- ✅ Time introduced as a first-class domain concept
- ✅ Context Window introduced (Context made reusable)
- ✅ Event Lifecycle and Event State Machine defined
- ✅ Domain Invariants and Domain Policies defined
- ✅ Behavioral ownership made explicit throughout
- ⏳ Entity relationships under review
- ⏳ Event lifecycle pending (implementation)
- ⏳ Decision Engine implementation pending
- ⏳ Scheduler implementation pending
- ⏳ Timer Engine design pending
- ⏳ Persistence model pending
- ⏳ Behavioral Architecture document pending

Implementation Rule:
The domain model drives the codebase.
The codebase must not drive the domain model.

---

# Core Philosophy

PAIOS is NOT a task manager.

PAIOS is a Personal AI Operating System.

It continuously observes Events, reasons over them, learns patterns, protects the user's priorities, and generates better future plans.

The architecture clearly separates:

- **What actually happened** (History)
- **What PAIOS understands** (Inference)
- **What PAIOS suggests** (Planning)

The user does not optimize tasks.

The user performs Events.

Everything else is inferred from Events.

Events are the immutable source of truth.

The system should optimize decision quality rather than task completion.

**v0.4 evolution:** PAIOS is evolving from a static data model into a living behavioral operating system. The domain now explicitly supports Time, Behavior, State transitions, Dynamic scheduling, and Context evolution — without changing any of the philosophy above. Everything added in v0.4 is additive: it gives the existing entities a heartbeat, not a new skeleton.

---

# Architectural Principles

### 1. Principles are Immutable and Universal

Principles represent timeless rules that guide decision making.

Principles represent Dharma.

They are stable, long-term decision rules and should be treated as immutable.

Examples:
- Protect Health
- Fulfill Responsibilities
- Speak Truth
- Protect Resources
- Learn Continuously
- Avoid Attachment to Results

Principles are NOT owned by the User.

Users follow Principles.

Principles sit above the User, at the foundation of PAIOS itself, and flow down through the reasoning and planning layers:

```
PAIOS
  ↓
Principles
  ↓
Decision Engine
  ↓
Recommendations
  ↓
Scheduler
```

PAIOS enforces Principles across all Recommendations and Scheduler decisions.

Principles themselves should never be modified by the AI.

Principles never evolve. This is what separates a Principle from a Domain Policy — see Principle 22, below.

*(Full ownership rules: see `BUSINESS_RULES.md` → Principle Rules. Full relationships: see `ENTITY_RELATIONSHIPS.md`.)*



### 2. Events are the Center of the System — Task is Removed

Events represent real actions.

Every meaningful action performed by the user becomes an Event.

Everything else should derive from Events.

Examples:
- Study ISTQB
- Smoke Cigarette
- Attend Office
- Read Bhagavad Gita
- Spend Money
- Exercise
- Sleep
- Build PAIOS

Earlier designs implied a flow of `Recommendation → Task → Event`. The Task entity is fully removed from the domain — it implied a prescribed obligation sitting between suggestion and action, which contradicted the principle that Events are the single source of truth and that PAIOS plans and observes rather than prescribes. The corrected architecture flow is:

```
Recommendation → Scheduler → Scheduled Event → Completed Event
```

Events remain the single source of truth. As of v0.4, an Event does not jump straight from suggestion to completion — it moves through a defined lifecycle. See Principle 19, "Event Lifecycle," below.



### 3. Projects Organize Intentional Work

A Project is an intentional body of work.

Projects contain many Events.

Projects consume Resources.

Projects improve Knowledge.

Projects have measurable Progress.

Projects are NOT goals.

Projects provide evidence for future recommendations.



### 4. Goals are Emergent

Goals are NOT fixed objectives.

Goals emerge naturally from long-term project completion and event history.

Example:
```
Repeated ISTQB events
↓
Knowledge growth
↓
Habit formation
↓
Project completion
↓
AI suggests: "Continue towards SDET."
```

The AI suggests Goals.

The user decides whether to accept them.

Goals therefore represent direction rather than fixed destinations.



### 5. Habits are Inferred

Habits are never manually created.

Repeated Events over time create Habits.

Example:
```
Smoking Event repeated
↓
Smoking Habit
```

Likewise:
```
Repeated Study Events
↓
Study Habit
```



### 6. Recommendations

Recommendations are generated from:
- Principles
- Projects
- Resources
- Knowledge
- Habits
- Historical Events
- Current Context

Recommendations never modify history.

They only suggest future Events.

Recommendations require user acceptance.

Rejected Recommendations remain historical evidence.

Recommendations are also subject to Time: they are not permanently valid. See Principle 16, "Time is the Heartbeat of PAIOS."



### 7. Scheduler Replaces Timeline

Scheduler is responsible for planning future Events. The Scheduler is a rename with a real change in responsibility — it does not passively display a sequence of events, it actively plans and re-plans them.

Scheduler begins planning from the current moment.

Scheduler respects:
- Principles
- Available Resources
- Remaining time
- Recommendations

Scheduler generates future Scheduled Events.

History is never modified.

Only future Events are planned.

Scheduler handles Event Disturbers to recalculate schedules dynamically.

As of v0.4, this behavior is expanded significantly — see Principle 23, "Scheduler Time Tracking."



### 8. Resources are Consumed and Produced

Resources are not simply increased or decreased.

Every Event consumes and produces Resources.

Examples:

**Study:**
- Energy: -10
- Knowledge: +20
- Career: +10

**Smoking:**
- Money: -20
- Health: -5
- Stress: +3
- Focus: +1

**Sleep:**
- Energy: +40
- Health: +15
- Time: -8h

Events modify Resources.



### 9. Knowledge

Knowledge grows through Events.

Knowledge belongs primarily to Projects.

Knowledge contributes toward future Recommendations.



### 10. Context Explains WHY Events Occurred

Every Event occurs within a Context.

Context is different from Reflection.

Context captures the situational factors of a place, group, or setting:
- Location
- People
- Emotion
- Trigger
- Reason
- Environment
- Notes

Example:
```
Office
Location: Office building, 4th floor
People: Team Lead, colleagues
Environment: Open workspace
```

As of v0.4, Context is a **reusable definition** rather than a one-time record — see Principle 17, "Context Window." This allows future reasoning about Event patterns across many occurrences of the same Context, not just one.



### 11. Reflections

Reflections explain WHY Events happened at a deeper level.

They help discover patterns.

They improve Recommendations.

Context captures the immediate situation.

Reflection captures the user's interpretation and learning.



### 12. Progress

Progress is a first-class entity.

Instead of embedding progress directly inside Projects,
Projects should own Progress.

Progress may contain:
- Completion %
- Knowledge gained
- Habit score
- Resource delta
- Velocity
- Estimated completion
- Confidence

Progress, like Resources and Knowledge, changes over time — see Principle 16.



### 13. Event Disturbers

Event Disturbers represent unexpected situations that interrupt the planned Scheduler.

Examples:
- Friend arrived
- Team Lead requested overtime
- Health issue
- Rain
- Power cut
- Unexpected meeting
- Family emergency

The Scheduler uses Event Disturbers to recalculate the remaining day's schedule.

This is one of the defining concepts of PAIOS.

**v0.4 clarification:** An Event Disturber never modifies an Event directly. See Principle 24, "Event Disturber Clarification," for the exact chain of causation.



### 14. Decision Engine

The Decision Engine is a core architectural component.

It reasons over user history.

Inputs:
- Events
- Projects
- Resources
- Knowledge
- Habits
- Context
- Principles
- Current Time

Outputs:
- Recommendations
- Priority evaluation
- Next best action
- Scheduler inputs

The Decision Engine owns no data.

It only reasons.



### 15. Impact Classification

Each Event has one Impact classification.

- Opportunity
- Neutral
- Distraction

Do NOT classify Activities.

Classify Events.

This allows future daily, weekly and monthly reports like:
- Opportunity Hours
- Neutral Hours
- Distraction Hours



### 16. Time is the Heartbeat of PAIOS

Time is no longer just timestamps sitting on individual records. As of v0.4, Time is a core architectural concept in its own right.

Everything inside PAIOS exists relative to **Current Time**.

Time synchronizes:
- Decision Engine
- Scheduler
- Events
- Recommendations
- Resources
- Context
- Progress

Concretely, this means:

- The Scheduler always reasons from **NOW** — it never plans from a stale reference point.
- Recommendations expire over time; a suggestion that made sense an hour ago may no longer be valid.
- Priorities evolve over time, as Resources, Knowledge, and completed Events shift what matters most.
- Resources change over time — this was already true (see Principle 8), but Time is now the explicit axis that drives that change.
- Knowledge changes over time, through revision, application, and decay of retention.
- Context changes over time — not by Context itself changing, but by which Context Window is currently active (see Principle 17).

Time is therefore not a field. It is the heartbeat that keeps every other entity honest about what is still relevant *right now*.



### 17. Context Window — Reusable Context, Temporal Activation

Context itself is **not** made temporal. Instead, PAIOS introduces a new entity: **Context Window**.

The reasoning: Context is reusable. "Office," "Home," "Temple," "Travel," and "With Team Lead" are Context *definitions* — they do not change from day to day. What changes every day is not the Context, it is **when** that Context is active.

Therefore, a Context Window references exactly one Context, and carries the time boundaries of a single activation of it:

```
Context:
Office

Context Window (Today):
1:00 PM → 5:45 PM

Context Window (Tomorrow):
8:30 AM → 4:15 PM
```

Same Context. Different Context Window.

Context Window contains:
- Window ID
- Context ID
- Start Time
- End Time
- Duration
- Current State
- Reason Started
- Reason Ended

The Scheduler reasons over Context Windows, not over Context directly — it needs to know *when* a situational category is active, not merely that it exists.

*(For the ownership relationship between Event, Context Window, and Context, see `ENTITY_RELATIONSHIPS.md`.)*



### 18. Context Lifecycle

Context itself is static — it is a definition, not an occurrence.

Context **Window** is what has a lifecycle.

Suggested Context Window states:
- Created
- Active
- Changing
- Expired
- Archived

Only one Context Window should normally be **Active** at a time. When a new Context Window begins, it automatically closes the previous one — the system does not allow two Context Windows to remain Active simultaneously under normal operation. This mirrors the Domain Invariant "Exactly one Active Context Window" in `BUSINESS_RULES.md`.



### 19. Event Lifecycle

An Event no longer moves in a single step from suggestion to completion. It progresses through a defined lifecycle of states:

- **Recommended** — The Event exists only as a suggestion produced by the Decision Engine; it has not yet been accepted or placed on the Scheduler.
- **Scheduled** — The Recommendation has been accepted and the Scheduler has placed the Event into a future Context Window.
- **Ready** — The Scheduled Event's start time has arrived and its preconditions (Resources, Context Window) are satisfied; it is awaiting the user to begin.
- **Started** — The user has begun performing the Event.
- **Paused** — A Started Event has been temporarily halted, by the user's own choice, without external interruption.
- **Resumed** — A Paused or Interrupted Event has continued from where it left off.
- **Completed** — The Event finished as intended and becomes part of immutable History.
- **Skipped** — A Scheduled Event was never started, and its Context Window passed without action.
- **Cancelled** — A Scheduled, Paused, or Interrupted Event was deliberately abandoned before completion.
- **Interrupted** — The current Event was temporarily paused, not by the user's own choice but because an Event Disturber forced a Scheduler recalculation. An Interrupted Event may later Resume, be Cancelled, or be Overtaken.
- **Overtaken** — A higher-priority Event, produced by a new Recommendation and Scheduler recalculation, has replaced the current Event before it could resume. This differs from Cancelled: the Event isn't rejected, it simply lost priority to something more urgent.
- **Archived** — A Completed, Skipped, or Cancelled Event has aged out of active reporting but remains permanently in History.

Interrupted and Overtaken are worth holding apart deliberately: **Interrupted** describes the Event pausing because something external happened; **Overtaken** describes the Event losing its place entirely to something more important. An Interrupted Event still expects to resume; an Overtaken Event does not.



### 20. Event State Machine

Events transition between the lifecycle states above according to a small set of well-defined paths. Representative examples:

```
Scheduled    → Started
Started      → Completed
Started      → Interrupted
Interrupted  → Resumed
Interrupted  → Cancelled
Scheduled    → Skipped
Scheduled    → Overtaken
```

The Scheduler controls these transitions — an Event does not change its own state; the Scheduler changes it in response to the user, the clock, or an Event Disturber.

History remains immutable throughout. A transition does not rewrite what already happened — it only records that a new state was reached, and when. This is the same immutability guarantee that already applies to Events themselves (Principle 2); the State Machine simply gives that guarantee a shape.

*(Full transition rules live in `BUSINESS_RULES.md` → Event Lifecycle Rules.)*



### 21. Behavioral Ownership

Ownership across the domain is now made fully explicit, including for entities introduced in v0.4:

- User owns Projects
- Project owns Progress
- Event owns Context Window
- Context Window references Context
- Recommendations belong to Decision Engine output
- Scheduler owns Scheduled Events
- Habits never own Events
- Insights originate from Reflections
- Goals emerge from Projects

This is not a new ownership model — it is the same model already described throughout this document, stated plainly in one place so it cannot be misread. The complete ownership map, including the entities this document doesn't repeat here, lives in `ENTITY_RELATIONSHIPS.md`.



### 22. Domain Invariants and Domain Policies are Not Principles

Two new categories of rule are introduced in v0.4, and neither of them is a Principle:

- **Domain Invariants** are structural truths that must always hold — for example, "exactly one Active Context Window." They describe what must be true at all times, not what the user values.
- **Domain Policies** are runtime rules that shape behavior and *can* change as PAIOS learns — for example, "repeated rejected Recommendations lower confidence." Policies evolve. Principles never evolve.

Principles remain the immutable, Dharma-level foundation described in Principle 1. Invariants and Policies sit underneath them, in the operational layer, and are fully enumerated in `BUSINESS_RULES.md`.



### 23. Scheduler Time Tracking

The Scheduler's responsibility, introduced in Principle 7, is expanded in v0.4. The Scheduler continuously compares:

- Current Clock
- Current Context Window
- Running Event
- Next Scheduled Event
- Available Resources

If enough deviation occurs between what was planned and what is actually true right now, the Scheduler recalculates — the same recalculation behavior already described for Event Disturbers, but now understood as a continuous, time-driven process rather than something that only happens on interruption.

This continuous comparison is expected to eventually be driven by a **Timer Engine** — a future component responsible for triggering the Scheduler's comparisons at the right cadence. The Timer Engine is not yet designed; see Future Questions, below.



### 24. Event Disturber Clarification

An Event Disturber does **not** modify an Event directly. That distinction matters enough to state as its own principle.

Instead, the causal chain is:

```
Event Disturber
  ↓
creates a Context Window transition
  ↓
Scheduler recalculates
  ↓
Scheduler performs an Event State Transition
```

The Event Disturber is a trigger, not an editor. It changes what Context Window is active; the Scheduler is the only component that acts on that change, and even then it acts through the Event State Machine (Principle 20), never by editing the Event itself.

---

# Architectural Layers

### Layer 1 — Foundation

- Principles (immutable rules — Dharma)
- Decision Engine (stateless reasoning component, owns no data)

Neither entity in this layer belongs to the User. Principles are immutable data that the User follows; the Decision Engine is not data at all — it is a reasoning process that reads from every other layer and writes nothing but Recommendations.

### Layer 2 — Operational

- User
- Projects
- Events
- Context
- Context Window
- Scheduler
- Resources
- Knowledge
- Recommendations
- Progress
- Reflections
- Event Disturbers

### Layer 3 — Emergent

- Habits
- Insights
- Goals

*(For how these layers own and reference one another, see `ENTITY_RELATIONSHIPS.md`.)*

---

# System Flow

```
History (What Happened)

Event
  ↓
Context Window  (references Context)
  ↓
Resource Flow
  ↓
Impact Type
  ↓
Reflection
  ↓
Insight


Inference (What PAIOS Understands)

Decision Engine
  ↓
Recommendations
  ↓
Priority Evaluation


Planning (What PAIOS Suggests)

Scheduler
  ↓
Scheduled Event
  ↓
Event Disturber (optional) → Context Window transition → Scheduler recalculation
  ↓
Event State Transition
  ↓
Completed Event
```

This loop never ends. Every completed event improves future recommendations and scheduling. As of v0.4, the entire loop runs relative to Current Time — see Principle 16.

---

# Domain Entities

Each entity below describes **what it is and why it exists**. Field lists indicate structure only. For how entities reference and own one another, see `ENTITY_RELATIONSHIPS.md`. For the rules that govern their behavior, see `BUSINESS_RULES.md`.

## Layer 1 — Foundation

### Principles

**Purpose:**
Represents timeless rules that guide decision making. Represents Dharma.

**Responsibility:**
Provide the ethical and practical foundation for all recommendations and scheduling decisions. Never modified by AI. Universal across all users.

**Why it exists:**
Principles ensure that PAIOS recommendations align with Dharma and core values, preventing optimization that violates fundamental beliefs. Principles are universal rules that users follow, not personal preferences. Unlike Domain Policies (see Architectural Principle 22), Principles never evolve.

**Suggested Fields:**
- Principle ID
- Name
- Description
- Category (Health, Responsibility, Truth, Resources, Learning, Detachment)
- Created At (immutable)
- Last Reviewed



### Decision Engine

**Purpose:**
Reasons over user history to generate intelligent outputs.

**Responsibility:**
Analyzes Events, Projects, Resources, Knowledge, Habits, Context, Principles, and Current Time to produce Recommendations, priority evaluations, and Scheduler inputs. Owns no data.

**Why it exists:**
The Decision Engine is the intelligence layer of PAIOS. It transforms raw data into actionable insights without modifying any data. This separation ensures that analysis never corrupts the source of truth. Because it owns no data, it can be revised, retrained, or replaced without any risk to History.

**Suggested Fields:**
(None — Decision Engine is a reasoning component, not a data entity)



## Layer 2 — Operational

### User

**Purpose:**
Represents the individual using PAIOS.

**Responsibility:**
Owns personal entities in the system. Performs Events, consumes Resources, develops Habits, gains Knowledge, and receives Recommendations. Follows Principles.

**Why it exists:**
The User is the anchor point for all personal data. All entities ultimately belong to and serve the User, but Principles are universal rules that the User follows rather than owns, and Context belongs to no one — it is a shared, reusable definition (see Context, below).

**Suggested Fields:**
- User ID
- Name
- Created At
- Last Active



### Project

**Purpose:**
Organizes intentional work toward a meaningful outcome.

**Responsibility:**
Groups related Events, tracks Progress, consumes Resources, and improves Knowledge. Provides evidence for future Recommendations.

**Why it exists:**
Projects provide structure and intentionality to Events. Without Projects, Events would be disconnected actions without context or direction.

**Suggested Fields:**
- Project ID
- User ID
- Name
- Description
- Status (Active/Completed/Paused)
- Created At
- Progress ID (reference)



### Event

**Purpose:**
Represents a single completed action by the user.

**Responsibility:**
Captures what actually happened. Is the immutable source of truth. Consumes and produces Resources. Has Impact classification. Owns a Context Window describing when and where it occurred. Triggers Reflections. Feeds into Habit detection and Goal emergence. Progresses through the Event Lifecycle (see Architectural Principle 19) under the Scheduler's control (Principle 20).

**Why it exists:**
Events are the raw data of the system. Everything else—insights, recommendations, habits—is derived from Events. Events never change once recorded; corrections and interruptions are captured as new lifecycle states and new corrective Events, never as edits. There is no Task entity sitting between an Event and the Recommendation that led to it.

**Suggested Fields:**
- Event ID
- User ID
- Project ID (optional)
- Context Window ID
- Status (Recommended/Scheduled/Ready/Started/Paused/Resumed/Completed/Skipped/Cancelled/Interrupted/Overtaken/Archived)
- Start Time
- End Time
- Duration
- Category
- Description
- Impact Type (Opportunity/Neutral/Distraction)
- Priority Alignment Score (0-10)
- Resource Flow (object showing consumed/produced resources)
- Expected Outcome
- Actual Outcome
- Reflection ID (optional)



### Context

**Purpose:**
Represents a reusable definition of a situational category — a place, group, or setting the user recurs to. Examples: Office, Home, Temple, Travel, With Team Lead.

**Responsibility:**
Describes the general situational factors of a category: typical Location, People, Emotion, Trigger, Reason, Environment, and Notes. Does not itself carry time — it does not know when it is active. Different from Reflection, which captures interpretation and learning after a specific Event.

**Why it exists:**
Context provides the "why" of a situation in reusable form. It allows PAIOS to reason across many occurrences of the same situational category — for example, noticing a pattern across every Office Context Window — rather than treating each occurrence as an unrelated one-off record. As of v0.4, Context is intentionally *not* made temporal; that responsibility belongs to Context Window (below).

**Suggested Fields:**
- Context ID
- Name
- Location
- People (array)
- Emotion
- Trigger
- Reason
- Environment
- Notes
- Created At



### Context Window

**Purpose:**
Represents a single, time-bounded activation of a Context.

**Responsibility:**
Records when a given Context was active — its start and end time, duration, current lifecycle state, and why it started and ended. Owned by the Event it describes. References exactly one Context.

**Why it exists:**
Context is reusable and does not change; what changes is *when* it is active. Context Window is the entity that carries that change. The same Context ("Office") can have many different Context Windows across many days, each with its own timing, without the underlying Context definition being duplicated or rewritten. This is the mechanism by which Context participates in Time (Architectural Principle 16) without Context itself becoming temporal.

**Suggested Fields:**
- Window ID
- Context ID
- Event ID
- Start Time
- End Time
- Duration
- Current State (Created/Active/Changing/Expired/Archived)
- Reason Started
- Reason Ended



### Scheduler

**Purpose:**
Plans future Events based on current state and Recommendations.

**Responsibility:**
Begins planning from current moment. Respects Principles, Resources, time, and Recommendations. Generates Scheduled Events. Continuously compares Current Clock, Current Context Window, Running Event, Next Scheduled Event, and Available Resources, and recalculates when deviation is significant enough. Handles Event Disturbers by driving Context Window transitions and Event State Transitions (see Architectural Principle 24) rather than editing Events directly. Never modifies history.

**Why it exists:**
Scheduler bridges the gap between recommendation and action. It transforms abstract suggestions into concrete future plans while adapting to real-world interruptions. Unlike the Timeline it replaces, it is an active planner, not a passive display. As of v0.4, it is also the sole controller of Event state transitions, and its continuous time-comparison behavior is expected to eventually be driven by a future Timer Engine (see Future Questions).

**Suggested Fields:**
- Scheduler ID
- User ID
- Current Time
- Scheduled Events (array)
- Active Event Disturbers (array)
- Available Resources
- Active Projects
- Next Scheduled Event
- Current Context Window ID
- Running Event ID
- Last Recalculated At



### Event Disturber

**Purpose:**
Represents unexpected situations that interrupt the planned schedule.

**Responsibility:**
Captures real-world interruptions. Does not modify Events directly. Instead, triggers a Context Window transition, which the Scheduler responds to by recalculating and performing an Event State Transition. One of the defining concepts of PAIOS.

**Why it exists:**
Event Disturbers enable PAIOS to adapt to real life. Without them, the Scheduler would be rigid and unrealistic. They make PAIOS a true operating system that handles the unexpected. Keeping the Event Disturber itself from touching the Event directly (see Architectural Principle 24) preserves the same immutability discipline that protects all of History.

**Suggested Fields:**
- Event Disturber ID
- User ID
- Type (Friend/Work/Health/Environment/Family/Other)
- Description
- Severity (Low/Medium/High)
- Occurred At
- Resulting Context Window Transition ID
- Affected Scheduled Events (array)
- Resolution Status



### Resources

**Purpose:**
Tracks quantities that are consumed and produced through Events.

**Responsibility:**
Maintains current state of all consumable and accumulable assets. Provides constraints for Recommendations and Scheduler. Changes over time, in step with Events as they complete (see Architectural Principle 16).

**Why it exists:**
Resources ground recommendations and scheduling in reality. They prevent the system from suggesting actions that are impossible due to lack of time, money, energy, etc.

**Suggested Fields:**
- Resource ID
- User ID
- Type (Time/Money/Health/Energy/Knowledge/Focus/Stress/Career/Spiritual)
- Current Value
- Unit
- Last Updated



### Knowledge

**Purpose:**
Tracks learning and skill acquisition.

**Responsibility:**
Records what the user knows and how well they know it. Contributes to Recommendations by identifying knowledge gaps and opportunities. Like Resources, Knowledge changes over time — through revision, application, and retention decay.

**Why it exists:**
Knowledge helps PAIOS understand the user's capabilities and suggest appropriate next steps. It also tracks the return on investment of time spent learning.

**Suggested Fields:**
- Knowledge ID
- User ID
- Project ID
- Domain
- Topic
- Concept
- Difficulty
- Confidence (0-100)
- Revision Count
- Last Revision
- Source
- Applied (boolean)
- Retention Score



### Recommendation

**Purpose:**
Suggests the next best action based on current state.

**Responsibility:**
Generated by Decision Engine. Analyzes Events, Resources, Projects, Principles, and Context to generate actionable suggestions. Never modifies history. Requires user acceptance. Expires over time if not acted on (see Architectural Principle 16).

**Why it exists:**
Recommendations are the primary output of PAIOS. They translate analysis into guidance, helping users make better decisions.

**Suggested Fields:**
- Recommendation ID
- User ID
- Related Project ID (optional)
- Priority
- Reason
- Expected Benefit
- Suggested Timing
- Confidence Score
- Created At
- Expires At
- Status (Pending/Accepted/Rejected/Expired)



### Progress

**Purpose:**
Tracks advancement toward Project completion.

**Responsibility:**
Measures and reports on how far a Project has come. Provides visibility and motivation. Changes over time as Events complete within the Project.

**Why it exists:**
Progress is a first-class entity because it's complex and important. Embedding it in Projects would hide its complexity. Making it explicit allows for rich tracking and analysis.

**Suggested Fields:**
- Progress ID
- Project ID
- Completion Percentage
- Knowledge Gained
- Habit Score
- Resource Delta
- Velocity
- Estimated Completion
- Confidence
- Last Updated



### Reflection

**Purpose:**
Explains WHY Events happened at a deeper level.

**Responsibility:**
Captures user interpretation of Events. Helps discover patterns. Improves future Recommendations. Different from Context, which captures a reusable situational category rather than a specific interpretation.

**Why it exists:**
Reflections transform raw Events into learning. Without Reflections, PAIOS would have data but no understanding. Context (via Context Window) captures the situation the Event occurred in; Reflection captures what the user made of it afterward.

**Suggested Fields:**
- Reflection ID
- Event ID
- Context Window ID
- Facts
- Interpretation
- Root Cause
- Lesson Learned
- Improvement
- Confidence
- Created At



## Layer 3 — Emergent

### Habit

**Purpose:**
Represents recurring behavior patterns.

**Responsibility:**
Identified automatically from repeated Events. Provides visibility into automatic behaviors. Informs Recommendations.

**Why it exists:**
Habits are never manually created. They emerge from Event history. Making them explicit allows PAIOS to understand and influence automatic behaviors.

**Suggested Fields:**
- Habit ID
- User ID
- Name
- Trigger
- Frequency
- Reward
- Current Trend
- Strength (0-100)
- Desired State
- Detected At
- Last Updated



### Insight

**Purpose:**
Represents knowledge discovered through Reflection.

**Responsibility:**
Extracts patterns and learnings from Reflections. Improves future Recommendations.

**Why it exists:**
Insights are the distilled wisdom from Reflections. They make learnings reusable and actionable.

**Suggested Fields:**
- Insight ID
- Source Reflection ID
- Category
- Confidence
- Reusable (boolean)
- Date Created



### Goal

**Purpose:**
Represents emergent direction from long-term patterns.

**Responsibility:**
Suggested by AI based on Project completion and Event history. Accepted by User. Provides high-level direction for Recommendations.

**Why it exists:**
Goals are not fixed objectives. They emerge from patterns. Making them explicit allows the user to validate and adjust the direction PAIOS is suggesting.

**Suggested Fields:**
- Goal ID
- User ID
- Name
- Description
- Suggested By (AI)
- Accepted By User (boolean)
- Accepted At
- Status (Active/Completed/Paused)
- Related Projects
- Confidence Score

---

# PAIOS_DATA Architecture

PAIOS_DATA is the data storage layer that separates user data from the application logic.

## Structure

```
PAIOS
│
├── Core
│   ├── Principles
│   └── Decision Engine
├── AI Engine
├── Event Engine
├── Scheduler Engine
├── Recommendation Engine
│
└── PAIOS_DATA
    ├── Users
    ├── Events
    ├── Context
    ├── Context Windows
    ├── Event Disturbers
    ├── Goals
    ├── Projects
    ├── Resources
    ├── Knowledge
    ├── Habits
    ├── Reflections
    ├── Recommendations
    ├── Scheduler State
    └── Progress
```

## Why PAIOS_DATA Exists

PAIOS_DATA exists to:

1. **Separate data from application logic**: The application can evolve independently of the data structure
2. **Enable AI integration**: Future AI systems can access and analyze data without modifying the application code
3. **Maintain data integrity**: Historical data remains immutable and serves as the single source of truth
4. **Support multiple interfaces**: Different interfaces (CLI, web, mobile) can access the same data source
5. **Facilitate backup and migration**: Data can be backed up, migrated, or exported independently of the application

## Why It Is Kept Separate

PAIOS_DATA is kept separate from the application because:

1. **Immutability**: Historical events and reflections should never be modified by the application logic
2. **AI Safety**: AI systems can read and analyze data without having write access to modify history
3. **Testing**: Application logic can be tested against mock data without affecting real user data
4. **Flexibility**: Data schema can evolve without requiring application changes
5. **Privacy**: User data remains in a controlled location that can be secured independently

## How Future AI Would Use It

A future AI system would use PAIOS_DATA to:

1. **Read historical patterns**: Analyze past events to identify trends and patterns
2. **Generate insights**: Combine events, reflections, context, and goals to discover new insights
3. **Predict outcomes**: Use historical data to predict likely outcomes of different actions
4. **Recommend improvements**: Suggest changes based on what has worked in the past
5. **Answer questions**: Respond to natural language queries about the user's life and progress

**Critical constraint**: The AI would have read-only access to PAIOS_DATA and would never modify historical events or reflections. All AI-generated content would be stored as new Recommendations or Insights, not as modifications to existing data.

*(For the schema/data storage layout and foreign-key structure, see `ENTITY_RELATIONSHIPS.md`.)*

---

# Architectural Notes

## Task Entity Removed

PAIOS has no Task entity. An earlier implied flow of `Recommendation → Task → Event` is removed entirely and replaced with `Recommendation → Scheduler → Scheduled Event → Completed Event`. A Task would have represented a prescribed obligation between suggestion and action; PAIOS instead treats every Recommendation as a suggestion that the Scheduler may turn directly into a Scheduled Event, and the Event itself remains the only record of what actually happened.

## Event Immutability

Events are never modified once recorded. If an error is discovered, a corrective Event is created instead. This preserves the integrity of historical data and enables accurate pattern analysis. As of v0.4, Event *state* changes over the Event Lifecycle, but this is recorded as a sequence of transitions, not as an edit to the Event's historical facts — see "Event Lifecycle & State Machine," below.

## Principle Immutability and Universality

Principles are never modified by the AI. Only the User can update Principles, and even then, it should be a deliberate action. Principles are NOT owned by the User—they are universal rules that users follow. This ensures that the ethical foundation of the system remains stable and shared.

## Emergence vs Prescription

Goals and Habits emerge from data. They are not prescribed. This prevents the system from imposing external structures that don't match the user's actual behavior patterns.

## Recommendation Non-Modifying

Recommendations never modify history. They only suggest future actions. This separation ensures that the AI can analyze without corrupting the source of truth. As of v0.4, Recommendations also expire — see "Time is the Heartbeat of PAIOS."

## Progress as First-Class

Progress is extracted as a separate entity because it's complex and important. Embedding it in Projects would hide its complexity and make it less accessible to analysis.

## Scheduler as Dynamic

Scheduler is not a fixed schedule. It continuously recalculates based on current state and Event Disturbers. This allows PAIOS to adapt to changing circumstances in real-time — a static Timeline could not do this by design, which is why the concept was renamed and re-scoped rather than merely relabeled.

## Context vs Context Window

As of v0.4, Context and Context Window are deliberately separate entities. Context is a static, reusable definition — "Office" does not change from one day to the next. Context Window is the time-bounded record of when that Context was active for a particular Event. This lets PAIOS reason across every occurrence of "Office" as one category, while still knowing precisely when each individual occurrence happened. Context Window replaces what earlier versions of this document treated as a single, per-Event Context record.

## Context vs Reflection

Context captures the general situational category (Location, People, Emotion, Trigger, Reason, Environment). Reflection captures the user's interpretation and learning after the fact (Facts, Interpretation, Root Cause, Lesson Learned). Both are needed for complete understanding. Reflection is authored by the User afterward and references both the Event and its Context Window.

## Resource Flow (Consume/Produce)

Resources are not simply increased or decreased. Every Event consumes some resources and produces others. This nuanced view enables better understanding of trade-offs and benefits.

## Event Disturbers as Defining Concept

Event Disturbers are one of the defining concepts of PAIOS. They enable the system to handle real-world interruptions gracefully, making PAIOS a true operating system rather than a rigid planner. As of v0.4, this is formalized: an Event Disturber triggers a Context Window transition, which the Scheduler responds to — the Disturber itself never touches the Event.

## Decision Engine Owns No Data

The Decision Engine is a reasoning component only. It owns no data. It reads from PAIOS_DATA and writes Recommendations to PAIOS_DATA. This separation ensures that analysis never corrupts the source of truth.

## Event Lifecycle & State Machine

Events now carry a Status field that moves through a defined lifecycle (Recommended → Scheduled → Ready → Started → ... → Archived). The Scheduler is the only component that changes an Event's state, and it does so by recording a transition, never by rewriting the Event's history. This keeps the Event Lifecycle consistent with Event Immutability rather than in tension with it.

## Time as a Cross-Cutting Concern

Time is not modeled as a single entity with its own table. It is a cross-cutting concern read by nearly every other component — the Decision Engine, Scheduler, Events, Recommendations, Resources, Context Windows, and Progress all reason relative to Current Time. This is intentional: giving Time its own isolated entity would understate how pervasively it drives the rest of the system.

## Domain Invariants vs Domain Policies vs Principles

These three are easy to conflate and are kept deliberately distinct:

- **Principles** are immutable and represent Dharma. They never evolve.
- **Domain Invariants** are structural truths that must always hold, regardless of behavior (e.g., "exactly one Active Context Window"). They are not values — they are consistency guarantees.
- **Domain Policies** are runtime rules that shape behavior and are expected to evolve as PAIOS learns (e.g., "repeated rejected Recommendations lower confidence").

Full lists of Invariants and Policies live in `BUSINESS_RULES.md`.

---

# Future Questions

The following items are intentionally left open for future exploration:

1. **Event Granularity**: How granular should Events be? Should "Study ISTQB" be one Event or broken into multiple sub-events?
2. **Principle Conflicts**: How should the system handle conflicts between Principles? (e.g., Protect Health vs. Fulfill Responsibilities)
3. **Goal Acceptance**: What happens when a User rejects an AI-suggested Goal? Should the AI adjust its suggestion algorithm?
4. **Habit Detection Thresholds**: How many repeated Events are required before a Habit emerges? Should this be configurable?
5. **Resource Normalization**: How do we normalize different resource types (time, money, energy) for comparison and analysis?
6. **Confidence Scoring**: How should confidence be calculated for Insights, Recommendations, and Goals?
7. **Scheduler Horizon**: How far into the future should Scheduler plan? Hours, days, weeks?
8. **Reflection Triggers**: Should PAIOS automatically prompt for Reflections after certain types of Events?
9. **Progress Velocity**: How should velocity be calculated? Is it linear, exponential, or something else?
10. **Multi-User Support**: Should the architecture support multiple users sharing the same PAIOS instance (e.g., family)?
11. **Event Disturber Handling**: How should the Scheduler prioritize between multiple simultaneous Event Disturbers?
12. **Context Granularity**: How detailed should Context capture be? Should it include environmental sensors, biometric data, etc.?
13. **Timer Engine Cadence**: How frequently should the Scheduler tick — every second, every minute, purely event-driven, or a hybrid of the two?
14. **Context Update Latency**: How long should PAIOS wait before proactively asking the user for a Context update?
15. **Automatic Context Window Closure**: Can inactivity automatically close a Context Window, or should closure always require an explicit reason?
16. **Stale Plan Detection**: Can the Timer Engine automatically detect that a Scheduled plan has gone stale, rather than waiting for the next comparison cycle?

---

# Guiding Principle

PAIOS does not aim to make decisions for the user.

PAIOS aims to help the user recognize the highest-priority decision in the current moment, understand its consequences, and continuously improve through reflection, knowledge, and Dharma-aligned action.

PAIOS is a Personal AI Operating System that continuously observes, reasons, learns, protects, and suggests—never replacing human judgment, but augmenting it with intelligence grounded in the user's own actions and values.

---

# What Comes After This Document

This Domain Model defines **WHAT** exists — the entities, their purpose, and the philosophy that shapes them.

It does not define **HOW** those entities behave moment to moment. That is the responsibility of a future **Behavioral Architecture** document, which will describe execution: ticks, triggers, timing, and the runtime mechanics behind the Event State Machine, the Scheduler's continuous comparisons, and the Timer Engine.

Implementation should always follow this order:

```
Domain Model
  ↓
Behavioral Architecture
  ↓
Application Services
  ↓
Infrastructure
```

The Behavioral Architecture document will become the execution model of PAIOS. This Domain Model remains its foundation.
