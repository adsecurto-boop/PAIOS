# RUNTIME_EXECUTION.md

This document explains how PAIOS actually runs during the day.

It describes the runtime loop, component responsibilities, priorities, replanning triggers, ownership, sequences, and guarantees that govern moment-to-moment execution.

This document complements:
- `DOMAIN_MODEL.md` — What exists
- `ENTITY_RELATIONSHIPS.md` — How entities connect
- `BUSINESS_RULES.md` — System behavior rules
- `BEHAVIORAL_ARCHITECTURE.md` — How entities behave over time
- `STATE_MACHINES.md` — Formal state transition specifications

---

## Document Purpose

The Runtime Execution document answers: **"How does PAIOS run from moment to moment?"**

It describes the continuous operational loop that begins at System Time and never stops, observing reality, reasoning over it, and guiding the next Event.

---

## 1. Runtime Loop

PAIOS operates as an eternal runtime loop that begins from System Time and continuously observes the current state of the world.

### Loop Overview

```
Clock Tick
  ↓
Observe Current Context Window
  ↓
Observe Running Event
  ↓
Observe Scheduler
  ↓
Check Event Disturbers
  ↓
Need Replan?
  ↓
YES
  ↓
Scheduler
  ↓
Event State Transition
  ↓
Continue
  ↓
NO
  ↓
Continue Current Event
  ↓
Repeat Forever
```

### Loop Stages

**Clock Tick**
- System Time advances
- Runtime Kernel receives time signal
- All components synchronized to current moment

**Observe Current Context Window**
- Read active Context Window state
- Check if Context Window has changed
- Detect location, people, environment changes
- Identify meaningful reality shifts

**Observe Running Event**
- Check if an Event is currently Running
- Measure elapsed time
- Verify Resource consumption
- Assess completion progress

**Observe Scheduler**
- Review current Scheduled Events
- Check next Scheduled Event timing
- Verify plan alignment with reality
- Assess resource availability

**Check Event Disturbers**
- Scan for unexpected reality changes
- Detect external interruptions
- Assess disturbance severity
- Determine impact on current plan

**Need Replan?**
- Evaluate if reality has deviated from plan
- Check if Resources are exhausted
- Verify if Recommendations expired
- Assess if Priority changed
- Determine if Context shift affects feasibility

**YES → Scheduler**
- Trigger Scheduler recalculation
- Generate revised future plan
- Respect all Principles
- Maintain History immutability

**Event State Transition**
- Apply Scheduler decision
- Execute state transition per STATE_MACHINES.md
- Record transition evidence
- Publish system event

**NO → Continue Current Event**
- Maintain current execution
- Monitor for changes
- Wait for next tick

**Repeat Forever**
- Loop never terminates
- PAIOS is always running
- Always observing, always reasoning

---

## 2. Runtime Responsibilities

Each runtime component owns specific responsibilities. No component owns another component's data.

### Clock

**Owns:** Time

**Responsibility:**
- Produces current System Time
- Provides time synchronization signal
- Enables time-based reasoning across all components

**Why:**
Time is the heartbeat of PAIOS. Clock ensures all components reason from the same current moment.

### Context Window

**Owns:** Current situation

**Responsibility:**
- Maintains active Context Window state
- Tracks location, people, environment
- Records Context transitions
- Provides situational awareness to other components

**Why:**
Context Window represents reality in the moment. It enables the system to understand where the user is and what situation they are in.

### Running Event

**Owns:** Current work

**Responsibility:**
- Tracks currently executing Event
- Monitors Event progress
- Measures Resource consumption
- Signals completion or interruption

**Why:**
Running Event represents what the user is actually doing right now. It is the bridge between planning and execution.

### Scheduler

**Owns:** Future planning

**Responsibility:**
- Plans future Events
- Generates Scheduled Events
- Recalculates on disturbances
- Controls Event state transitions
- Never edits History

**Why:**
Scheduler owns the future. It transforms Recommendations into concrete time-allocated plans while adapting to reality changes.

### Decision Engine

**Owns:** Reasoning

**Responsibility:**
- Reasons over current state
- Generates Recommendations
- Evaluates priorities
- Applies Principles
- Owns no data

**Why:**
Decision Engine provides intelligence. It analyzes data without owning it, ensuring reasoning never corrupts the source of truth.

### Resources

**Owns:** Current capacity

**Responsibility:**
- Tracks available quantities
- Records consumption and production
- Provides constraint information
- Signals threshold crossings

**Why:**
Resources ground the system in reality. They prevent suggesting actions that are impossible due to lack of capacity.

### Recommendations

**Owns:** Future suggestions

**Responsibility:**
- Represents suggested actions
- Carries confidence scores
- Expires over time
- Requires user acceptance

**Why:**
Recommendations are the output of reasoning. They guide the user without forcing execution.

### Event Disturbers

**Owns:** Unexpected reality

**Responsibility:**
- Captures interruptions
- Triggers Context transitions
- Signals Scheduler to recalculate
- Never modifies Events directly

**Why:**
Event Disturbers enable adaptation to real life. They make PAIOS a true operating system that handles the unexpected.

---

## 3. Runtime Tick

PAIOS continuously wakes up on a runtime tick to observe, reason, and act.

### Tick Concept

The runtime tick is the fundamental unit of PAIOS execution. It represents one complete cycle of the runtime loop.

```
Every Tick
  ↓
Observe
  ↓
Reason
  ↓
Act
  ↓
Wait for Next Tick
```

### Tick Frequency

The tick frequency is a conceptual design choice, not an implementation detail. Possible approaches include:

- **Every second**: High responsiveness, higher resource usage
- **Every minute**: Balanced responsiveness and efficiency
- **Event-driven**: React only when changes occur
- **Hybrid**: Regular ticks plus event-driven triggers

The actual frequency is determined by implementation requirements and resource constraints. The architecture supports any of these approaches.

### Tick Activities

Each tick performs:

1. **Observe**: Capture current state of all runtime components
2. **Detect**: Identify changes since previous tick
3. **Reason**: Decision Engine analyzes current state
4. **Decide**: Determine if replanning is required
5. **Act**: Execute state transitions if needed
6. **Publish**: Emit system events for subscribed components
7. **Wait**: Pause until next tick

### Tick Independence

Each tick is independent. The system does not assume state between ticks except through persistent Runtime State. This ensures robustness and prevents cascading errors.

---

## 4. Runtime Priorities

PAIOS follows a strict priority order when making runtime decisions.

### Priority Order

1. **Safety**
2. **Principles**
3. **Running Event**
4. **Event Disturbers**
5. **Scheduler**
6. **Recommendations**

### Priority Explanations

**1. Safety — WHY:**
Safety is non-negotiable. Health emergencies, critical resource exhaustion, or system-threatening conditions override all other considerations. The system must protect the user before optimizing anything else.

**2. Principles — WHY:**
Principles represent Dharma — timeless, immutable values. No Recommendation or Scheduler decision may violate a Principle. Principles are the foundation of all decision-making and cannot be overridden by convenience or efficiency.

**3. Running Event — WHY:**
The user's current action has momentum and commitment. Interrupting a Running Event should only occur for higher-priority reasons (Safety, Principles, or severe Event Disturbers). The system respects the user's current engagement.

**4. Event Disturbers — WHY:**
Event Disturbers represent reality asserting itself. When the real world changes unexpectedly, the system must respond. Disturbers trigger replanning because the current plan may no longer be feasible or relevant.

**5. Scheduler — WHY:**
Scheduler owns future planning. It responds to changes in reality, Resources, and Recommendations to maintain a viable plan. Scheduler replanning is important but does not override what the user is currently doing unless justified by higher priorities.

**6. Recommendations — WHY:**
Recommendations are suggestions, not commands. They guide future decisions but do not force immediate action. Recommendations have the lowest priority because the user's current reality and commitments take precedence.

### Priority in Action

When conflicts occur, the system resolves them according to this order:

```
Running Event vs. Recommendation
  ↓
Running Event wins (priority 3 > 6)

Event Disturber vs. Running Event
  ↓
Event Disturber wins if it triggers Safety or Principle violation (priority 4, but may invoke priority 1 or 2)

Scheduler vs. Recommendation
  ↓
Scheduler wins (priority 5 > 6)

Principle vs. Scheduler
  ↓
Principle wins (priority 2 > 5)
```

---

## 5. Runtime Replanning

The Scheduler recalculates when specific conditions indicate the current plan is no longer viable or optimal.

### Replanning Triggers

**Current Context Changed**
- Location changed significantly
- People present changed
- Environment shifted
- Trigger or reason changed
- Context Window transitioned

**Running Event Interrupted**
- Event Disturber occurred
- User paused the Event
- Resource exhaustion prevented continuation
- External factor stopped execution

**Resource Exhausted**
- Critical Resource reached minimum threshold
- Time remaining insufficient for planned Events
- Energy too low for scheduled activity
- Money insufficient for planned expense

**Recommendation Accepted**
- User accepted a new Recommendation
- New action added to consideration set
- Priority landscape changed

**Recommendation Expired**
- Time passed beyond Recommendation validity
- Context changed making Recommendation irrelevant
- Resources changed making Recommendation infeasible

**System Time Drift**
- Significant time passed since last calculation
- Scheduled Event timing became stale
- Plan horizon requires refresh

**Large Delay**
- Unexpected delay occurred
- Original timing assumptions invalid
- Remaining schedule requires adjustment

**Priority Change**
- New higher-priority Event emerged
- Existing Event priority increased
- User explicitly changed priority

### Replanning Process

```
Trigger Detected
  ↓
Scheduler State: Monitoring → Recalculating
  ↓
Load Current Runtime State
  ↓
Apply Principles as constraints
  ↓
Evaluate remaining time
  ↓
Assess available Resources
  ↓
Review current Context
  ↓
Consider active Recommendations
  ↓
Generate revised future plan
  ↓
Validate against Principles
  ↓
Update Scheduled Events
  ↓
Scheduler State: Recalculating → Scheduling
  ↓
Publish PlanUpdated system event
  ↓
Resume Monitoring
```

### Replanning Constraints

Replanning always respects:

- **History immutability**: Only future Events may be modified
- **Principles**: No plan may violate Principles
- **Resources**: Plans must be resource-feasible
- **Context**: Plans must align with current reality
- **Running Event**: Current execution is not interrupted without higher-priority reason

### Replanning Scope

Replanning may affect:

- Future Scheduled Events (timing, sequence, cancellation)
- Resource allocations
- Context Window assignments
- Priority ordering

Replanning never affects:

- Completed Events (immutable History)
- Running Event (unless higher-priority interruption justified)
- Past Context Windows (immutable)
- Historical Resource consumption (immutable)

---

## 6. Runtime Ownership

Runtime ownership is clearly defined to prevent conflicts and ensure data integrity.

### Ownership Matrix

| Component | Owns | Does NOT Own |
|---|---|---|
| **Clock** | Time | Context, Events, Resources |
| **Scheduler** | Future planning | History, Context data, Resources |
| **Decision Engine** | Reasoning process | Any data (stateless) |
| **Context Window** | Current reality | Events, Resources, Planning |
| **Running Event** | Current execution | Future planning, Resources |
| **Resources** | Current capacity | Events, Planning, Context |
| **History** | Completed Events | Runtime state, Future planning |
| **Recommendations** | Future suggestions | Execution, Resources, Context |

### Ownership Principles

**No component owns another component's data**
- Clock does not own Context Window data
- Scheduler does not own Resource data
- Decision Engine owns no data at all
- Context Window does not own Event data
- Running Event does not own Resource data

**Ownership is exclusive**
- Only one component owns Time (Clock)
- Only one component owns future planning (Scheduler)
- Only one component owns reasoning (Decision Engine)
- Only one component owns current reality (Context Window)

**Ownership is directional**
- Components read data they do not own
- Components write data they own
- Components request changes through proper channels
- Components never directly modify another's owned data

### Ownership in Practice

```
Clock produces time
  ↓
Context Window reads time to track duration
  ↓
Scheduler reads time to plan future Events
  ↓
Running Event reads time to measure progress
  ↓
Resources read time to track regeneration

Scheduler owns future planning
  ↓
Scheduler reads Context Window (does not own)
  ↓
Scheduler reads Resources (does not own)
  ↓
Scheduler reads Recommendations (does not own)
  ↓
Scheduler writes Scheduled Events (owns)
  ↓
Scheduler requests Event state transitions (does not own Events)

Decision Engine owns reasoning
  ↓
Decision Engine reads History (does not own)
  ↓
Decision Engine reads Context Window (does not own)
  ↓
Decision Engine reads Resources (does not own)
  ↓
Decision Engine writes Recommendations (owns output)
  ↓
Decision Engine never writes to any data source
```

---

## 7. Runtime Sequence

The complete runtime sequence shows how components interact during normal operation.

### Sequence Diagram

```
Clock
  ↓ (tick signal)
Context Window
  ↓ (current state)
Running Event
  ↓ (execution state)
Scheduler
  ↓ (current plan)
Event Disturbers
  ↓ (check for disturbances)
Resources
  ↓ (current capacity)
Recommendations
  ↓ (pending suggestions)
Runtime Kernel
  ↓ (collects all state)
Decision Engine
  ↓ (reasons over state)
Recommendations
  ↓ (new suggestions generated)
Scheduler
  ↓ (evaluates plan)
Need Replan?
  ↓
NO
  ↓
Continue Current Event
Running Event
  ↓ (continues execution)
Clock
  ↓ (next tick)

YES
  ↓
Scheduler
  ↓ (recalculates)
Scheduled Events
  ↓ (updated plan)
Event State Transition
  ↓ (applies transition)
Running Event
  ↓ (may change state)
Clock
  ↓ (next tick)

Event Completes
Running Event
  ↓ (signals completion)
Completed Event
  ↓ (immutable History)
Resources
  ↓ (updates based on Event)
Knowledge
  ↓ (updates based on Event)
Progress
  ↓ (updates based on Event)
Reflection
  ↓ (user provides)
Insight
  ↓ (extracted)
Decision Engine
  ↓ (incorporates learning)
Recommendations
  ↓ (improved suggestions)
Scheduler
  ↓ (improved planning)
Clock
  ↓ (next tick)
```

### Normal Operation Sequence

1. **Clock tick** signals new cycle
2. **Context Window** reports current state
3. **Running Event** reports execution progress
4. **Scheduler** reports current plan
5. **Event Disturbers** report any disturbances
6. **Resources** report current capacity
7. **Recommendations** report pending suggestions
8. **Runtime Kernel** collects all state into unified snapshot
9. **Decision Engine** reasons over snapshot
10. **Decision Engine** generates new Recommendations if needed
11. **Scheduler** evaluates current plan against reality
12. **Scheduler** determines if replanning is needed
13. **If NO replanning**: Continue current Event execution
14. **If YES replanning**: Scheduler recalculates future plan
15. **Scheduler** updates Scheduled Events
16. **Scheduler** triggers Event state transitions if needed
17. **Running Event** continues or changes state
18. **Clock** triggers next tick

### Event Completion Sequence

1. **Running Event** signals completion
2. **Event state transitions** to Completed
3. **Completed Event** becomes immutable History
4. **Resources** update based on Event's Resource Flow
5. **Knowledge** updates based on Event's learning outcomes
6. **Progress** updates based on Event's contribution to Project
7. **User** provides Reflection (optional)
8. **Insight** extracted from Reflection
9. **Decision Engine** incorporates new learning
10. **Recommendations** improve based on learning
11. **Scheduler** improves planning based on learning
12. **Clock** triggers next tick

---

## 8. Runtime Guarantees

PAIOS provides specific guarantees about runtime behavior.

### Core Guarantees

**History never changes**
- Completed Events are immutable
- Past Context Windows are immutable
- Historical Resource consumption is immutable
- Corrections happen via new Events, never edits

**Exactly one Running Event**
- Only one Event may be in Started or Resumed state at a time
- This is a Domain Invariant enforced by the Scheduler
- Violations trigger immediate correction

**Exactly one Active Context Window**
- Only one Context Window may be Active at a time
- This is a Domain Invariant enforced by Runtime Kernel
- New Active Context Window automatically closes previous one

**Scheduler never edits History**
- Scheduler only operates on future Events
- Historical Events are never modified by Scheduler
- Past state transitions are never rewritten

**Decision Engine owns no data**
- Decision Engine is stateless
- Decision Engine reads from other components
- Decision Engine never writes to any data source
- Decision Engine only produces Recommendations

**Recommendations never force execution**
- Recommendations are suggestions only
- User must accept Recommendations
- Scheduler may choose not to use Recommendations
- Recommendations expire over time

**Principles are never violated**
- No Recommendation may violate Principles
- No Scheduler decision may violate Principles
- No Event may violate Principles
- Principles are immutable constraints

### Consistency Guarantees

**Runtime State consistency**
- Runtime Kernel maintains single source of truth
- All components read from same Runtime State snapshot
- State transitions are atomic
- Failed operations are rolled back

**Event-driven consistency**
- System events are published atomically
- Subscribers react independently
- No component directly calls another
- Loose coupling prevents cascading failures

**Time consistency**
- All components reason from same Current Time
- Time advances monotonically
- Time-based triggers are deterministic
- Clock drift is detected and corrected

### Safety Guarantees

**Resource safety**
- Resources cannot become invalid (e.g., negative where meaningless)
- Resource exhaustion triggers replanning
- Resource constraints are never violated
- Resource thresholds generate alerts

**Priority safety**
- Higher-priority Events override lower-priority Events
- Priority violations are prevented
- Priority changes trigger replanning
- Priority order is never violated

**State safety**
- Invalid state transitions are prevented
- State machines enforce valid paths
- Preconditions are checked before transitions
- Failed transitions are logged and corrected

---

## 9. Runtime Philosophy

PAIOS does not execute tasks.

PAIOS continuously observes reality, reasons over it, protects Principles, and guides the next Event.

### Philosophy Statement

PAIOS is not a task execution engine. It is not a todo list manager. It is not a calendar application.

PAIOS is a Personal AI Operating System that:

- **Observes** reality continuously through Clock, Context Window, and Event Disturbers
- **Reasons** over current state through the Decision Engine
- **Protects** Principles as immutable constraints on all decisions
- **Guides** the user through Recommendations and Scheduler planning
- **Learns** from completed Events through Reflections and Insights

### The Runtime Contract

The runtime contract between PAIOS and the user is:

**PAIOS promises:**
- To always observe reality accurately
- To never violate Principles
- To never modify History
- To provide intelligent Recommendations
- To adapt plans to real-world changes
- To learn from completed Events

**The user retains:**
- The authority to accept or reject Recommendations
- The freedom to start, pause, or stop Events
- The responsibility to provide Reflections
- The ownership of all personal data
- The final decision on every action

### Runtime as Living System

PAIOS runtime is a living system that:

- Breathes through the eternal runtime loop
- Thinks through the Decision Engine
- Plans through the Scheduler
- Acts through Event execution
- Learns through Reflection and Insight
- Adapts through Event Disturbers and replanning

The runtime never sleeps. It never stops observing. It never stops reasoning. It never stops learning.

This is the essence of PAIOS as a Personal AI Operating System.
