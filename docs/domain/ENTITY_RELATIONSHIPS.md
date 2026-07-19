# ENTITY_RELATIONSHIPS.md

This is one of four documents that together describe PAIOS:

```
DOMAIN_MODEL.md          ← What exists
ENTITY_RELATIONSHIPS.md  ← ERD & ownership (this file)
BUSINESS_RULES.md        ← System behavior
GLOSSARY.md              ← Term definitions
```

This file answers **how entities connect**: ownership, references, the entity-relationship diagram, and the physical data layout. For what each entity *is* and *why it exists*, see `DOMAIN_MODEL.md`. For the rules governing behavior, see `BUSINESS_RULES.md`.

---

# Ownership Overview

Ownership is not uniform across PAIOS. Four different ownership models coexist:

| Model | Applies to | Meaning |
|---|---|---|
| **Foundational, unowned** | Principles | Belongs to PAIOS itself. The User follows Principles but does not own them. |
| **Stateless, no data** | Decision Engine | Owns nothing. Reads everything, writes only Recommendations. |
| **Reusable, unowned by a single Event** | Context | A shared definition (e.g., "Office") referenced by many Context Windows across many Events. Not owned by any one Event or User record. |
| **User-owned** | Projects, Events, Scheduler, Resources, Knowledge, Recommendations, Habits, Insights, Goals | Owned directly by the User. |
| **Entity-owned (nested)** | Context Window (owned by Event, references Context), Progress (owned by Project), Reflection (owned by User, references one Event and its Context Window) | Owned by another operational entity rather than directly by the User. |

Stated explicitly, per the v0.4 Behavioral Ownership principle:

- User owns Projects
- Project owns Progress
- Event owns Context Window
- Context Window references Context
- Recommendations belong to Decision Engine output
- Scheduler owns Scheduled Events
- Habits never own Events
- Insights originate from Reflections
- Goals emerge from Projects

```
PAIOS
 └─ Principles                      (foundational, unowned)
 └─ Decision Engine                 (stateless, owns nothing)

Context                              (reusable, unowned — referenced, not possessed)
 └─ referenced by → many Context Windows

User
 ├─ owns → Projects
 │           └─ owns → Progress
 ├─ owns → Events
 │           └─ owns → Context Window   (1:1, references one Context)
 │           └─ may trigger → Reflection
 ├─ owns → Scheduler
 │           └─ owns → Scheduled Events
 │           └─ handles → Event Disturbers
 ├─ owns → Resources
 ├─ owns → Knowledge
 ├─ owns → Recommendations           (belong to Decision Engine output)
 ├─ owns → Habits            (emergent — inferred, never owns Events)
 ├─ owns → Insights          (emergent — originate from Reflections)
 └─ owns → Goals             (emergent — emerge from Projects, AI-suggested, user-accepted)
```

---

# Entity Relationship Diagram

```
                              ┌───────────────┐
                              │   Principles  │  (foundational, unowned)
                              └───────┬───────┘
                                      │ constrains
                                      ▼
        ┌────────────────────────────────────────────────────┐
        │                    Decision Engine                  │
        │  reads: Events, Projects, Resources, Knowledge,     │
        │  Habits, Context, Principles, Current Time           │
        │  writes: Recommendations only                        │
        └───────────────────────┬────────────────────────────┘
                                 │ generates
                                 ▼
                        ┌────────────────┐        accepted by user
                        │ Recommendation │ ─────────────────────────┐
                        │ (expires over  │                          │
                        │  Time)         │                          │
                        └───────┬────────┘                          │
                                │ consumed by                       ▼
                                ▼                            ┌─────────────┐
                          ┌───────────┐  compares Current    │  Scheduler  │
                          │ Scheduler │◄── Clock/Context/    │  (owned by  │
                          │           │   Running Event/     │    User)    │
                          └─────┬─────┘   Resources          └─────────────┘
                                │ generates
                                ▼
                        ┌────────────────┐
                        │ Scheduled Event │  (Status: Recommended→Scheduled→
                        └───────┬────────┘   Ready→Started→...→Archived)
                                │ Scheduler drives Event State Transitions
                                ▼
        ┌───────────────────────────────────────────────────┐
        │                       Event                         │◄── belongs to (optional) ── Project ── owns ── Progress
        │  owned by: User                                     │
        │  owns: 1 Context Window                              │
        │  has: 1 Impact Type, 1 Resource Flow, 1 Status       │
        │  may trigger: 1 Reflection                           │
        └───────┬──────────────┬───────────────┬─────────────┘
                │              │               │
                ▼              ▼               ▼
        ┌───────────────┐ ┌──────────┐  ┌────────────┐
        │ Context Window │ │ Resources │  │ Reflection │
        │ references →   │ │(modified) │  │(0/1, refs  │
        │   Context       │ └──────────┘  │Event+Window)│
        │ (reusable, 1:N) │               └─────┬──────┘
        └───────┬────────┘                      │ generates
                │                                ▼
                ▼                          ┌───────────┐
          ┌──────────┐                     │  Insight  │
          │ Context   │                     └───────────┘
          │(Office,   │
          │ Home,...) │
          └──────────┘

  Event Disturber ──creates──► Context Window transition ──► Scheduler recalculates ──► Event State Transition
  (never modifies the Event directly)

  Repeated Events over time  ──infer──►  Habit
  Repeated Projects/Events   ──infer──►  Goal  (suggested by Decision Engine, accepted by User)
```

---

# Per-Entity Relationships

### Principles
- Constrains the Decision Engine
- Constrains all Recommendations
- Guides Scheduler decisions
- Constrains Project actions
- NOT owned by User

### Decision Engine
- Reads Events, Projects, Resources, Knowledge, Habits, Context, Principles, Current Time
- Generates Recommendations
- Generates Scheduler inputs
- Owns no data

### User
- Owns Projects
- Performs Events
- Receives Recommendations
- Follows Principles (does not own them)

### Project
- Owned by User
- Contains many Events
- Owns Progress
- Consumes Resources
- Improves Knowledge
- Contributes to emergent Goals
- Constrained by Principles

### Event
- Performed by User
- Belongs to Project (optional)
- Owns exactly one Context Window
- Has one Impact Type
- Has one Resource Flow
- Has one Status, drawn from the Event Lifecycle
- May trigger one Reflection
- Contributes to Habit detection
- Feeds Scheduler
- Constrained by Principles
- State transitions are controlled exclusively by the Scheduler (never by the Event Disturber directly)

### Context
- Referenced by many Context Windows (reusable — a single Context like "Office" is shared across every Context Window that activates it)
- Not owned by any single Event or User record
- Read by the Decision Engine for pattern reasoning across occurrences

### Context Window
- Owned by exactly one Event
- References exactly one Context
- Has a Current State drawn from the Context Lifecycle (Created/Active/Changing/Expired/Archived)
- Read by the Scheduler for time-based reasoning
- A new Context Window automatically closes the previous Active one

### Scheduler
- Owned by User
- Consumes Recommendations
- References Principles
- References Resources
- References Projects
- Owns Scheduled Events
- Continuously compares Current Clock, Current Context Window, Running Event, Next Scheduled Event, and Available Resources
- Handles Event Disturbers by driving Context Window transitions and Event State Transitions
- Controls all Event state transitions

### Event Disturber
- Owned by User
- Creates a Context Window transition (does not touch the Event directly)
- Read by Scheduler, which reacts to the resulting Context Window transition
- Indirectly affects Scheduled Events, only through the Scheduler's response

### Resources
- Owned by User
- Modified by Events (consumed/produced)
- Referenced by Scheduler
- Referenced by Recommendations
- Changes relative to Current Time

### Knowledge
- Owned by User
- Belongs primarily to Projects
- Gained through Events
- Referenced by Recommendations
- Changes relative to Current Time (revision, decay)

### Recommendation
- Generated by Decision Engine (belongs to Decision Engine output)
- References User
- References Projects
- References Principles
- References Resources
- References Context
- Consumed by Scheduler
- Expires relative to Current Time

### Progress
- Owned by Project
- References Events
- References Knowledge
- References Resources
- Changes relative to Current Time

### Reflection
- Created by User
- References one Event
- References that Event's Context Window
- Generates Insights

### Habit
- Emerges from Events
- Owned by User
- Referenced by Recommendations
- Never owns Events

### Insight
- Generated from Reflection (originates from Reflections)
- Owned by User
- Referenced by Decision Engine

### Goal
- Emerges from Projects and events
- Suggested by Decision Engine
- Owned by User
- Guides Recommendations
- Constrained by Principles

---

# Data Separation Architecture

PAIOS separates schema definitions from private user data to enable version control while maintaining user privacy.

## Schema Layer

The schema layer defines the structure and field names for all domain entities. This layer is version-controlled in git and contains:

- Entity definitions (Goal, Project, Event, Context, Context Window, Event Disturber, etc.)
- Field names and data types
- Relationships between entities
- Validation rules
- Business logic constraints

The schema layer is shareable, reviewable, and collaborable without exposing any personal user data.

## Data Layer

The data layer contains the actual user data and is stored locally in a private folder. This layer includes:

- User's personal goals and their details
- Specific projects
- Event logs and activity history
- Context Window data for events
- Personal reflections and insights
- Financial information
- Priority values and rankings

The data layer is never committed to git and remains private to the user's local system. Principles, though universal and rarely changed, are still stored as plain data in this layer — "not owned by the User" describes their architectural role and immutability, not a change in where the bytes physically live. Context is similarly stored as plain data despite being reusable and unowned by any single Event.

## Local Data Storage

User data is stored in a `.data/` folder in the project root:

```
.data/
├── users.json
├── principles.json
├── projects.json
├── events.json
├── context.json
├── context_windows.json
├── scheduler.json
├── event_disturbers.json
├── resources.json
├── knowledge.json
├── recommendations.json
├── progress.json
├── reflections.json
├── habits.json
├── insights.json
└── goals.json
```

## Purpose

- **Privacy**: Sensitive user information never leaves the local system
- **Collaboration**: Team can collaborate on schema and business logic without accessing personal data
- **Flexibility**: Schema can evolve independently of user data
- **AI Context**: Decision Engine loads private data locally to generate personalized recommendations

## AI Integration

The Decision Engine combines both layers:

1. Loads schema definitions from the domain model
2. Loads private user data from the local `.data/` folder
3. Merges schema structure with user data to build context
4. Generates personalized recommendations based on user's actual goals, events, and patterns
5. All processing happens locally — private data never transmitted externally

---

# Data Structure Examples

The examples below show how the ERD's abstract relationships (owns, references, has) become concrete foreign keys in storage.

### Event

**Schema (in git):**
```
Event
- Event ID: string
- User ID: string
- Project ID: string (optional)
- Context Window ID: string
- Status: enum (Recommended/Scheduled/Ready/Started/Paused/Resumed/Completed/Skipped/Cancelled/Interrupted/Overtaken/Archived)
- Start Time: timestamp
- End Time: timestamp
- Duration: number (minutes)
- Category: string
- Description: string
- Impact Type: enum (Opportunity/Neutral/Distraction)
- Priority Alignment Score: number (0-10)
- Resource Flow: object (consumed/produced)
- Expected Outcome: string
- Actual Outcome: string
- Reflection ID: string (optional)
```

**Private Data (local .data/events.json):**
```json
[
  {
    "event_id": "evt_001",
    "user_id": "user_001",
    "project_id": "proj_001",
    "context_window_id": "win_001",
    "status": "completed",
    "start_time": "2024-01-15T09:00:00Z",
    "end_time": "2024-01-15T11:00:00Z",
    "duration": 120,
    "category": "study",
    "description": "Studied ISTQB Chapter 3 - Test Management",
    "impact_type": "opportunity",
    "priority_alignment_score": 9,
    "resource_flow": {
      "consumed": {
        "time": 120,
        "energy": 20
      },
      "produced": {
        "knowledge": 35,
        "career": 25
      }
    },
    "expected_outcome": "Complete Chapter 3 understanding",
    "actual_outcome": "Completed Chapter 3, took notes",
    "reflection_id": null
  }
]
```

### Context

**Schema (in git):**
```
Context
- Context ID: string
- Name: string
- Location: string
- People: array
- Emotion: string
- Trigger: string
- Reason: string
- Environment: string
- Notes: string
- Created At: timestamp
```

**Private Data (local .data/context.json):**
```json
[
  {
    "context_id": "ctx_001",
    "name": "Office",
    "location": "Downtown office, 4th floor",
    "people": ["Team Lead", "colleagues"],
    "emotion": null,
    "trigger": null,
    "reason": null,
    "environment": "Open workspace",
    "notes": "Primary workday location",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

Note: `context.json` carries no `event_id`. Context is a reusable definition, referenced by many Context Windows — it is not owned by any single Event. Fields like `emotion`, `trigger`, and `reason` are optional here, since those tend to vary per occurrence and often belong more naturally on the Context Window or Reflection for a specific Event.

### Context Window

**Schema (in git):**
```
Context Window
- Window ID: string
- Context ID: string
- Event ID: string
- Start Time: timestamp
- End Time: timestamp
- Duration: number (minutes)
- Current State: enum (Created/Active/Changing/Expired/Archived)
- Reason Started: string
- Reason Ended: string
```

**Private Data (local .data/context_windows.json):**
```json
[
  {
    "window_id": "win_001",
    "context_id": "ctx_001",
    "event_id": "evt_001",
    "start_time": "2024-01-15T09:00:00Z",
    "end_time": "2024-01-15T11:00:00Z",
    "duration": 120,
    "current_state": "expired",
    "reason_started": "Scheduled study session began",
    "reason_ended": "Event completed"
  },
  {
    "window_id": "win_002",
    "context_id": "ctx_001",
    "event_id": "evt_014",
    "start_time": "2024-01-16T08:30:00Z",
    "end_time": "2024-01-16T16:15:00Z",
    "duration": 465,
    "current_state": "active",
    "reason_started": "Arrived at office",
    "reason_ended": null
  }
]
```

Note: `win_001` and `win_002` both reference the same `context_id` ("Office") but have entirely different timing — this is the concrete illustration of "same Context, different Context Window."

### Project

**Schema (in git):**
```
Project
- Project ID: string
- User ID: string
- Name: string
- Description: string
- Status: enum (Active/Completed/Paused)
- Created At: timestamp
- Progress ID: string
```

**Private Data (local .data/projects.json):**
```json
[
  {
    "project_id": "proj_001",
    "user_id": "user_001",
    "project_name": "ISTQB Certification",
    "description": "Complete ISTQB Foundation Level certification",
    "status": "active",
    "created_at": "2024-01-01T00:00:00Z",
    "progress_id": "prog_001"
  }
]
```

### Principles

**Schema (in git):**
```
Principles
- Principle ID: string
- Name: string
- Description: string
- Category: enum (Health/Responsibility/Truth/Resources/Learning/Detachment)
- Created At: timestamp
- Last Reviewed: timestamp
```

**Private Data (local .data/principles.json):**
```json
[
  {
    "principle_id": "prin_001",
    "name": "Protect Health",
    "description": "Prioritize actions that maintain or improve physical and mental health",
    "category": "Health",
    "created_at": "2024-01-01T00:00:00Z",
    "last_reviewed": "2024-01-10T00:00:00Z"
  },
  {
    "principle_id": "prin_002",
    "name": "Speak Truth",
    "description": "Always be honest in communication and actions",
    "category": "Truth",
    "created_at": "2024-01-01T00:00:00Z",
    "last_reviewed": "2024-01-10T00:00:00Z"
  }
]
```

Note that `principles.json` carries no `user_id` — Principles are not scoped to a User the way Projects or Events are. This is the physical confirmation of the "foundational, unowned" ownership model described above.

### Event Disturber

**Schema (in git):**
```
Event Disturber
- Event Disturber ID: string
- User ID: string
- Type: enum (Friend/Work/Health/Environment/Family/Other)
- Description: string
- Severity: enum (Low/Medium/High)
- Occurred At: timestamp
- Resulting Context Window Transition ID: string
- Affected Scheduled Events: array
- Resolution Status: enum (Pending/Resolved)
```

**Private Data (local .data/event_disturbers.json):**
```json
[
  {
    "event_disturber_id": "dist_001",
    "user_id": "user_001",
    "type": "Work",
    "description": "Team Lead requested overtime for production issue",
    "severity": "High",
    "occurred_at": "2024-01-15T14:00:00Z",
    "resulting_context_window_transition_id": "win_002",
    "affected_scheduled_events": ["evt_scheduled_003", "evt_scheduled_004"],
    "resolution_status": "Resolved"
  }
]
```

Note: the Event Disturber references a resulting Context Window (`win_002`), not the affected Event directly — the physical schema mirrors the causal chain `Event Disturber → Context Window transition → Scheduler recalculates → Event State Transition`.

---

# PAIOS_DATA Structure

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

*(For why PAIOS_DATA exists and is kept separate, see `DOMAIN_MODEL.md` → PAIOS_DATA Architecture.)*

---

# Data Flow

```
User Action → Event (Status: Recommended) → PAIOS_DATA (immutable)
                    ↓
              Scheduler accepts → Event (Status: Scheduled) → Context Window created
                    ↓
              Event (Status: Ready → Started)
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
  Event Disturber          No disturbance
        ↓                       ↓
  Context Window            Event (Status: Completed)
  transition                     ↓
        ↓                  Reflection → PAIOS_DATA (immutable)
  Scheduler recalculates          ↓
        ↓                  Insight → PAIOS_DATA (immutable)
  Event State Transition
  (Interrupted/Overtaken/
   Resumed/Cancelled)
        ↓
  Decision Engine Analysis → Recommendation → PAIOS_DATA (new, time-bound)
        ↓
  Scheduler Planning → Scheduled Event → PAIOS_DATA (new)
        ↓
  User Decision → Completed Event → PAIOS_DATA (immutable)
```

This ensures that history is never rewritten — only new data, and new state transitions, are added.
