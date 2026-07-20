# PAIOS Behavioral Architecture

## Document Purpose

The Behavioral Architecture defines how PAIOS entities behave while the system is running.

This document complements the Domain Model. The Domain Model defines WHAT exists. The Behavioral Architecture defines HOW these entities behave over time.

## Scope

This document describes:
- How the system starts and continuously runs
- How time flows through the system
- How contexts evolve
- How events change state
- How recommendations become scheduled events
- How the scheduler adapts
- How learning occurs
- How runtime components interact

This document does NOT describe database schemas or repeat entity definitions already covered in the Domain Model.

---

## 1. Runtime Philosophy

PAIOS is NOT a task manager, a todo application, or a calendar.

PAIOS is a continuously running Personal AI Operating System.

The system operates as an eternal loop:

```
Observe
  ↓
Understand
  ↓
Reason
  ↓
Plan
  ↓
Execute
  ↓
Learn
  ↓
Repeat
```

This loop never stops. PAIOS is always running, always observing, always reasoning, always planning, always learning.

### Change-Driven Runtime

The runtime is driven by change, not by tasks. PAIOS continuously observes changes occurring in reality:

- Time changed
- User started studying
- User left home
- Team lead interrupted
- Weather changed
- Phone battery became low
- Energy decreased
- Money changed
- New context detected

Whenever reality changes, PAIOS updates its runtime state. The Decision Engine reasons again. The Scheduler replans again.

### Events as Immutable Source of Truth

Everything revolves around Events. Events are the immutable source of truth. History is never modified. Only new Events are added.

The system does not optimize task completion. It optimizes decision quality through continuous observation and learning.

---

## 2. Runtime Loop

The PAIOS runtime follows an eternal loop:

```
Initialize Runtime
  ↓
Observe Reality
  ↓
Detect Changes
  ↓
Update Runtime State
  ↓
Decision Engine
  ↓
Generate Recommendations
  ↓
Scheduler
  ↓
Wait for Next Change
  ↓
Repeat Forever
```

### Loop Stages

**Initialize Runtime**
- Load historical Events
- Load current Resources
- Load current Projects
- Load Principles
- Initialize Runtime Kernel
- Start runtime clock

**Observe Reality**
- Monitor Current Time
- Monitor Context changes
- Monitor Resource changes
- Monitor user actions
- Monitor external disturbances

**Detect Changes**
- Compare current reality to previous snapshot
- Identify significant changes
- Filter noise from signal
- Detect Event Disturbers

**Update Runtime State**
- Update Current Time
- Update Active Context Window
- Update Active Event
- Update Current Resources
- Update Scheduled Events
- Update Recommendations

**Decision Engine**
- Reason over current state
- Evaluate priorities
- Generate Recommendations
- Provide Scheduler inputs

**Generate Recommendations**
- Create action suggestions
- Calculate confidence scores
- Ensure Principle compliance
- Present to user

**Scheduler**
- Plan future Events
- Respect Resources
- Respect Principles
- Respect Context
- Recalculate on disturbances

**Wait for Next Change**
- Monitor for reality changes
- Timer-based triggers
- Event-driven triggers
- Hybrid approach

---

## 3. Behavioral Layers

PAIOS runtime is organized into distinct layers, each with specific responsibilities.

### Reality Layer

**Purpose**
Interface with the actual world where the user lives.

**Responsibility**
- Observe time passing
- Detect location changes
- Detect environmental changes
- Detect user actions
- Detect external interruptions

**Inputs**
- System clock
- Location services
- Environmental sensors
- User input
- External notifications

**Outputs**
- Reality events
- Change notifications
- Context triggers

### Runtime Layer

**Purpose**
Maintain the current state of the system.

**Responsibility**
- Maintain Runtime State
- Coordinate all engines
- Publish system events
- Synchronize components
- Prevent inconsistent state

**Inputs**
- Reality events
- Historical data
- User commands

**Outputs**
- Runtime state updates
- System events
- Engine notifications

### Reasoning Layer

**Purpose**
Analyze current state and generate insights.

**Responsibility**
- Decision Engine reasoning
- Priority evaluation
- Pattern recognition
- Habit detection
- Insight generation

**Inputs**
- Runtime State
- Historical Events
- Principles
- Context

**Outputs**
- Recommendations
- Priority scores
- Pattern insights
- Habit candidates

### Planning Layer

**Purpose**
Convert reasoning into actionable plans.

**Responsibility**
- Schedule future Events
- Respect Resources
- Respect Principles
- Handle disturbances
- Replan continuously

**Inputs**
- Recommendations
- Runtime State
- Resources
- Context
- Event Disturbers

**Outputs**
- Scheduled Events
- Plan updates
- Recalculation triggers

### Execution Layer

**Purpose**
Execute planned Events and track their progress.

**Responsibility**
- Event lifecycle management
- Context Window management
- Resource tracking
- State transitions
- Interruption handling

**Inputs**
- Scheduled Events
- Runtime State
- User actions
- Disturbances

**Outputs**
- Completed Events
- State transitions
- Resource updates
- Context changes

### Learning Layer

**Purpose**
Extract wisdom from completed Events.

**Responsibility**
- Reflection processing
- Insight extraction
- Knowledge updates
- Habit confirmation
- Recommendation improvement

**Inputs**
- Completed Events
- Reflections
- Context history

**Outputs**
- Insights
- Knowledge updates
- Habit updates
- Improved Recommendations

---

## 4. Runtime Kernel

The Runtime Kernel is the central orchestrator of PAIOS.

### Purpose

Coordinate all runtime components and maintain system consistency.

### Responsibility

The Runtime Kernel is responsible for:

- **Maintaining Runtime State**
  - Current Time
  - Current Context Window
  - Active Event
  - Current Resources
  - Scheduled Events
  - Active Recommendations
  - Active Disturbances

- **Publishing System Events**
  - Context changed
  - Event state changed
  - Resource threshold crossed
  - Disturbance detected
  - Time progressed

- **Notifying Engines**
  - Decision Engine triggers
  - Scheduler triggers
  - Event Engine triggers
  - Reflection Engine triggers

- **Synchronizing Components**
  - Ensure consistent state across engines
  - Prevent race conditions
  - Coordinate concurrent operations
  - Manage event ordering

- **Preventing Inconsistent Runtime State**
  - Validate state transitions
  - Enforce invariants
  - Detect conflicts
  - Rollback failed operations

### Interaction Pattern

```
Reality Change
  ↓
Runtime Kernel detects change
  ↓
Runtime Kernel updates Runtime State
  ↓
Runtime Kernel publishes System Event
  ↓
Relevant Engines subscribe and react
  ↓
Engines return results
  ↓
Runtime Kernel updates Runtime State
  ↓
System remains consistent
```

### Kernel Properties

- **Single source of truth** for runtime state
- **Event-driven** architecture
- **Stateless engines** (except Runtime Kernel)
- **Immutable history** (only Runtime State changes)
- **Reactive** to reality changes
- **Proactive** in planning and learning

---

## 5. Runtime State

Runtime State is the current snapshot of the system, separate from stored historical data.

### Purpose

Provide a unified, up-to-date view of the system for all engines to reason over.

### Responsibility

Maintain the current moment of the system's existence.

### Runtime State Contents

**Current Time**
- System clock value
- Time since last update
- Time until next scheduled event

**Current Context Window**
- Active Context ID
- Context Window start time
- Context Window duration
- Context Window state (Active/Changing/Expired)

**Current Active Event**
- Event ID
- Event state (Running/Paused/Interrupted)
- Event start time
- Event elapsed time
- Event remaining time

**Current Scheduled Event**
- Next Event ID
- Scheduled start time
- Scheduled duration
- Priority score

**Current Resources**
- Time remaining today
- Money available
- Energy level
- Health status
- Knowledge state
- Focus level

**Current Recommendations**
- Active recommendations
- Recommendation confidence scores
- Recommendation expiration times
- User acceptance status

**Current Disturbances**
- Active Event Disturbers
- Disturbance impact
- Disturbance resolution status

**Current World Snapshot**
- Location
- Environment
- People present
- Device state
- Connectivity status

### Why Runtime State Exists Separately

Runtime State is separate from historical data because:

1. **Performance**: Historical data is large; Runtime State is small and fast
2. **Relevance**: Only current state matters for immediate decisions
3. **Immutability**: History never changes; Runtime State changes constantly
4. **Reasoning**: Engines need a unified snapshot, not scattered historical records
5. **Consistency**: Single source of truth prevents conflicts

### Runtime State Lifecycle

```
System Startup
  ↓
Load Historical Data
  ↓
Initialize Runtime State
  ↓
Runtime State evolves continuously
  ↓
System Shutdown
  ↓
Runtime State discarded
  ↓
Historical Data preserved
```

Runtime State is ephemeral. Historical data is permanent.

---

## 6. Time Model

Time is the backbone of PAIOS runtime.

### Purpose

Synchronize all components around a unified time model.

### Responsibility

Ensure that time flows consistently through all layers and components.

### Time Flow

The system continuously runs from 00:00 to 23:59, then repeats.

```
00:00
  ↓
Time advances continuously
  ↓
Every Event occupies time
  ↓
Every Context occupies time
  ↓
Scheduler plans against remaining time
  ↓
23:59
  ↓
00:00 (next day)
```

### Time Synchronization

Time synchronizes:

- **Event lifecycle**: Events have start time, duration, end time
- **Context lifecycle**: Context Windows have start time, end time, duration
- **Scheduler lifecycle**: Scheduler plans from Current Time to end of day
- **Resource lifecycle**: Resources regenerate or deplete over time
- **Recommendation lifecycle**: Recommendations expire over time
- **Priority lifecycle**: Priorities evolve over time

### Time as Backbone

Time is not just metadata. Time is the backbone of runtime because:

1. **Events are time-bound**: Every Event happens at a specific time
2. **Context is time-bound**: Context Windows have temporal boundaries
3. **Resources are time-bound**: Resources change over time
4. **Planning is time-bound**: Scheduler plans against remaining time
5. **Learning is time-bound**: Patterns emerge over time

### Time Tracking

The Runtime Kernel maintains:

- **Current Time**: System clock
- **Time since last update**: For delta calculations
- **Time until next event**: For scheduling
- **Time spent in current state**: For analytics
- **Time remaining in day**: For planning

### Time and Event Disturbers

When an Event Disturber occurs, time is recalculated:

```
Original Plan:
09:00 - Study (2h)
11:00 - Meeting (1h)

Event Disturber at 09:30:
Team Lead requests overtime

Recalculated Plan:
09:30 - Overtime work (3h)
12:30 - Study (1h)
13:30 - Meeting (1h)
```

Time is flexible. History is immutable. Future is replannable.

---

## 7. Context Lifecycle

Context is dynamic. Context changes throughout the day.

### Purpose

Model the changing situational environment of the user.

### Responsibility

Track and manage Context Windows as they activate, change, and expire.

### Context Flow

A typical day flows through multiple Contexts:

```
Morning Context (Home)
  ↓
Commute Context (Travel)
  ↓
Office Context (Work)
  ↓
Meeting Context (Work)
  ↓
Break Context (Office)
  ↓
Home Context (Personal)
  ↓
Sleep Context (Rest)
```

### Context Influence

Context influences:

- **Recommendations**: Different actions suggested in different contexts
- **Priority**: Same action has different priority in different contexts
- **Scheduler**: Plans adapt to context-specific constraints
- **Decision Engine**: Reasoning incorporates context patterns

### Context Change Triggers

Context may change because of:

- **Location**: User moved to different place
- **People**: Different people present
- **Emotion**: User emotional state changed
- **Environment**: Environmental conditions changed
- **Interruptions**: External events occurred
- **Time**: Scheduled context transition
- **User action**: User explicitly changed context

### Context Window vs Context

Context is the definition. Context Window is the instance.

```
Context: Office
  - Location: Office building
  - Environment: Work setting
  - Typical activities: Work tasks

Context Window (Today):
  - Context: Office
  - Start: 09:00
  - End: 17:00
  - Duration: 8h

Context Window (Tomorrow):
  - Context: Office
  - Start: 08:30
  - End: 16:15
  - Duration: 7h 45m
```

Same Context. Different Context Window.

### Context Window Lifecycle States

**Created**
- Context Window initialized
- Not yet active
- Waiting for start time

**Active**
- Context Window is current
- User is in this context
- Influencing recommendations and scheduling

**Changing**
- Transition between contexts
- Brief overlap period
- State being updated

**Expired**
- Context Window ended
- No longer active
- Archived for history

**Archived**
- Context Window complete
- Stored in history
- Available for pattern analysis

### Context Change vs Event Disturber

**Context Change is sufficient when:**
- Natural transition (e.g., leaving office, going home)
- Scheduled transition (e.g., end of work day)
- Gradual change (e.g., energy slowly decreasing)

**Event Disturber should be generated when:**
- Unexpected interruption (e.g., emergency, sudden meeting)
- External override (e.g., boss demands overtime)
- Significant disruption (e.g., power outage, illness)
- Context change that forces replanning (e.g., rain cancels outdoor activity)

### Context Runtime Event

A Context change generates a Runtime Event:

```
Context Window changed
  ↓
Runtime Kernel publishes: ContextChanged
  ↓
Decision Engine updates reasoning
  ↓
Scheduler replans if necessary
  ↓
Recommendations updated
```

---

## 8. Event Lifecycle

Events progress through a complete lifecycle from suggestion to learning.

### Purpose

Model the complete journey of an Event through the system.

### Responsibility

Track Event state transitions and ensure proper progression.

### Event Lifecycle States

**Recommended**
- Event suggested by Decision Engine
- Not yet scheduled
- Waiting for user acceptance
- May expire if not accepted

**Scheduled**
- Event accepted by user
- Added to Scheduler
- Has assigned time slot
- Not yet started

**Pending**
- Event scheduled
- Start time approaching
- Resources reserved
- Ready to begin

**Started**
- Event execution began
- User actively performing
- Resources being consumed
- Time being tracked

**Running**
- Event in progress
- Active state
- Monitoring for interruptions
- Tracking resource consumption

**Paused**
- Event temporarily stopped
- Resources partially consumed
- May be resumed
- State preserved

**Resumed**
- Event restarted after pause
- Continues from pause point
- Resources continue consumption
- Time tracking adjusted

**Completed**
- Event finished successfully
- All resources consumed/produced
- Context captured
- Ready for reflection

**Reflected**
- User provided reflection
- Insights extracted
- Learning processed
- Event fully processed

**Learned**
- Event contributed to patterns
- Habits updated
- Knowledge updated
- Future recommendations improved

**Skipped**
- Event scheduled but not performed
- User chose to skip
- Resources released
- Recorded as decision

**Cancelled**
- Event cancelled before start
- Resources released
- Time slot freed
- Reason recorded

**Aborted**
- Event stopped during execution
- Partial resource consumption
- May not be resumable
- Reason recorded

**Overtaken**
- Higher-priority Event replaced current Event
- Current Event paused or cancelled
- Scheduler replanned
- Resources reallocated

**Interrupted**
- Current Event temporarily paused
- External disturbance occurred
- May be resumed later
- State preserved

**Archived**
- Event complete and processed
- Moved to historical storage
- No longer in active runtime
- Available for analysis

### State Transitions

```
Recommended
  ↓ (user accepts)
Scheduled
  ↓ (time arrives)
Pending
  ↓ (user starts)
Started
  ↓ (execution begins)
Running
  ↓ (normal completion)
Completed
  ↓ (user reflects)
Reflected
  ↓ (learning processed)
Learned
  ↓ (archived)
Archived

Running
  ↓ (user pauses)
Paused
  ↓ (user resumes)
Resumed
  ↓ (continues)
Running

Running
  ↓ (disturbance)
Interrupted
  ↓ (disturbance resolved)
Resumed
  ↓ (continues)
Running

Running
  ↓ (higher priority event)
Overtaken
  ↓ (current event stopped)
Cancelled

Scheduled
  ↓ (user skips)
Skipped
  ↓ (archived)
Archived

Scheduled
  ↓ (user cancels)
Cancelled
  ↓ (archived)
Archived

Running
  ↓ (user aborts)
Aborted
  ↓ (archived)
Archived
```

### Higher Priority Event Replacement

When a higher-priority Event occurs:

```
Current Event: Study (Priority: 5)
  ↓
Higher Priority Event: Emergency Meeting (Priority: 10)
  ↓
Current Event state: Running → Overtaken
  ↓
Higher Priority Event state: Scheduled → Started
  ↓
Scheduler recalculates remaining schedule
  ↓
Current Event may be rescheduled or cancelled
```

The Scheduler controls all state transitions. History remains immutable. Only transitions are recorded.

---

## 9. Scheduler Behavior

The Scheduler is the planning engine of PAIOS.

### Purpose

Convert Recommendations and planning inputs into concrete Scheduled Events.

### Responsibility

Plan future Events while respecting all constraints and adapting to changes.

### Scheduler Principles

**Scheduler never edits history**
- Only operates on future Events
- Historical Events are immutable
- Corrections happen via new Events

**Scheduler only modifies future**
- Plans from Current Time forward
- Never touches past Events
- Always respects completed history

**Scheduler continuously replans**
- Reacts to Context changes
- Reacts to Resource changes
- Reacts to Event Disturbers
- Reacts to new Recommendations

### Scheduler Inputs

The Scheduler consumes:

- **Recommendations**: From Decision Engine
- **Context**: Current Context Window
- **Resources**: Available Resources
- **Time**: Remaining time in day
- **Principles**: Immutable constraints
- **Event Disturbers**: Interruption signals
- **Higher Priority Events**: Urgent requirements

### Scheduler Outputs

The Scheduler produces:

- **Scheduled Events**: Time-allocated future Events
- **Plan updates**: Revised schedule
- **Recalculation triggers**: Signals to replan
- **Resource reservations**: Allocated resources

### Scheduler Reaction Cycle

```
Scheduler has current plan
  ↓
Context changes
  ↓
Scheduler detects change
  ↓
Scheduler recalculates
  ↓
Scheduler generates new plan
  ↓
Scheduler updates Scheduled Events
  ↓
Scheduler notifies Runtime Kernel
```

### Scheduler and Event Disturbers

When an Event Disturber occurs:

```
Event Disturber detected
  ↓
Scheduler pauses current planning
  ↓
Scheduler assesses disturbance impact
  ↓
Scheduler recalculates remaining schedule
  ↓
Scheduler respects new constraints
  ↓
Scheduler generates revised plan
  ↓
Scheduler resumes planning
```

### Scheduler Time Tracking

The Scheduler continuously compares:

- **Current Clock**: Actual system time
- **Current Context Window**: Active context and duration
- **Running Event**: Event in progress and elapsed time
- **Next Scheduled Event**: Upcoming event and time until start
- **Available Resources**: Current resource levels

If deviation exceeds threshold:

```
Deviation detected
  ↓
Scheduler triggers recalculation
  ↓
Scheduler adjusts plan
  ↓
Scheduler updates Scheduled Events
```

### Scheduler Optimization Goals

The Scheduler optimizes for:

- **Minimize Distractions**: Reduce Distraction-classified time
- **Maximize Opportunities**: Increase Opportunity-classified time
- **Respect Principles**: Never violate Principles
- **Resource Efficiency**: Use resources optimally
- **Context Alignment**: Match actions to context
- **Priority Adherence**: Execute high-priority items first

---

## 10. Decision Flow

The Decision Engine is the reasoning core of PAIOS.

### Purpose

Reason over current state to determine the next best actions.

### Responsibility

Analyze runtime state and historical data to generate intelligent Recommendations.

### Decision Engine Properties

**Decision Engine owns no data**
- Stateless reasoning process
- Reads from other entities
- Produces no side effects
- Never writes to History

### Decision Engine Inputs

The Decision Engine consumes:

- **Events (Completed Events)**: Raw historical Event data, supporting pattern recognition, habit detection, and historical success analysis
- **Impact Classification**: Historical Opportunity/Neutral/Distraction patterns, supporting reasoning and candidate generation
- **Projects**: Active Projects and Progress
- **Resources**: Current Resource state
- **Knowledge**: Current Knowledge state
- **Habits**: Detected Habit patterns
- **Context**: Current Context Window
- **Principles**: Immutable constraints
- **Current Time**: Runtime clock

This is a summary; see `DECISION_ENGINE.md` Section 2 for the complete input list.

### Decision Engine Outputs

The Decision Engine produces:

- **Recommendations**: Action suggestions — the system's "Next Best Action" for the current moment
- **Priority evaluation**: Relative importance scores
- **Confidence scores**: Certainty that a Recommendation is appropriate
- **Explanations**: Rationale behind each Recommendation
- **Scheduler inputs**: Planning constraints and preferences

See `DECISION_ENGINE.md` Section 8 for the full specification of these outputs.

### Decision Flow

```
Runtime State snapshot
  ↓
Decision Engine loads inputs
  ↓
Decision Engine reasons over data
  ↓
Decision Engine applies Principles
  ↓
Decision Engine evaluates priorities
  ↓
Decision Engine generates Recommendations
  ↓
Decision Engine calculates confidence scores
  ↓
Decision Engine provides Scheduler inputs
  ↓
Recommendations presented to user
  ↓
User accepts or rejects
  ↓
Accepted Recommendations → Scheduler
```

### Decision Engine Reasoning Process

The Decision Engine:

1. **Analyzes patterns**: Detect recurring behaviors and outcomes
2. **Evaluates context**: Considers current situational factors
3. **Assesses resources**: Determines what is possible
4. **Applies Principles**: Filters out Principle-violating options
5. **Calculates priorities**: Ranks options by importance
6. **Generates options**: Creates actionable Recommendations
7. **Scores confidence**: Estimates likelihood of success
8. **Provides rationale**: Explains why each Recommendation was made

### Decision Engine and Scheduler

The Decision Engine feeds the Scheduler:

```
Decision Engine
  ↓
Priority Evaluation
  ↓
Recommendations
  ↓
Scheduler Input (constraints, preferences)
  ↓
Scheduler
  ↓
Scheduled Events
```

The Decision Engine suggests. The Scheduler plans. They are separate concerns.

---

## 11. Learning Flow

Learning is how PAIOS improves over time.

### Purpose

Extract wisdom from completed Events to improve future Recommendations.

### Responsibility

Process completed Events, generate insights, and update system knowledge.

### Learning Flow

```
Completed Event
  ↓
Context captured
  ↓
Resource Flow recorded
  ↓
User provides Reflection
  ↓
Reflection processed
  ↓
Insight extracted
  ↓
Knowledge updated
  ↓
Habit detection updated
  ↓
Future Recommendations improved
```

### Why Learning Happens After Execution

Learning only occurs from completed history because:

1. **Data completeness**: Only completed Events have full data
2. **Outcome known**: Actual results inform learning
3. **Context captured**: Full context available for analysis
4. **Reflection available**: User interpretation provides meaning
5. **Resource Flow known**: Actual resource consumption recorded

### Reflection Processing

When a user provides a Reflection:

```
Reflection created
  ↓
Reflection Engine processes
  ↓
Extract facts
  ↓
Extract interpretation
  ↓
Extract root cause
  ↓
Extract lesson learned
  ↓
Extract improvement
  ↓
Generate Insight
  ↓
Update Knowledge
```

### Insight Generation

Insights are distilled wisdom from Reflections:

```
Reflection
  ↓
Pattern detection
  ↓
Cross-reference with history
  ↓
Identify recurring themes
  ↓
Extract generalizable learning
  ↓
Create Insight
  ↓
Mark as reusable or specific
  ↓
Feed to Decision Engine
```

### Habit Detection

Habit detection analyzes repeated Events:

```
Repeated Events over time
  ↓
Pattern recognition
  ↓
Identify triggers
  ↓
Identify frequency
  ↓
Identify rewards
  ↓
Calculate habit strength
  ↓
Create or update Habit
  ↓
Feed to Decision Engine
```

### Knowledge Update

Knowledge grows through Events:

```
Completed Event
  ↓
Extract learning outcomes
  ↓
Update domain knowledge
  ↓
Update topic knowledge
  ↓
Update concept confidence
  ↓
Update retention score
  ↓
Feed to Decision Engine
```

### Recommendation Improvement

Learning improves future Recommendations:

```
Insights + Knowledge + Habits
  ↓
Decision Engine incorporates
  ↓
Pattern recognition improves
  ↓
Context understanding improves
  ↓
Priority evaluation improves
  ↓
Recommendation quality improves
  ↓
User outcomes improve
```

Learning is continuous. Every completed Event contributes to system intelligence.

---

## 12. Runtime Communication

PAIOS uses event-driven communication between components.

### Purpose

Enable loose coupling and reactive behavior across engines.

### Responsibility

Coordinate engines through system events rather than direct calls.

### Communication Pattern

```
Component A
  ↓
Publishes System Event
  ↓
Runtime Kernel broadcasts
  ↓
Component B subscribes
  ↓
Component C subscribes
  ↓
Component D subscribes
  ↓
Each component reacts independently
```

### Runtime Communication Participants

**Runtime Kernel**
- Publishes all system events
- Subscribes to nothing (is the publisher)
- Coordinates all communication

**Decision Engine**
- Subscribes to: Runtime State changes, Context changes, Resource changes
- Publishes: Recommendations generated, Priority updates

**Scheduler**
- Subscribes to: Recommendations, Event Disturbers, Context changes, Time changes
- Publishes: Plan updates, Scheduled Events, Recalculation triggers

**Event Engine**
- Subscribes to: Scheduled Events start, User actions, Disturbances
- Publishes: Event state changes, Event completions, Context triggers

**Reflection Engine**
- Subscribes to: Completed Events, User Reflections
- Publishes: Insights generated, Knowledge updates

**Habit Engine**
- Subscribes to: Completed Events, Pattern updates
- Publishes: Habit detected, Habit updated

**Insight Engine**
- Subscribes to: Reflections, Knowledge updates
- Publishes: Insights extracted, Patterns discovered

### System Events

Common system events include:

- **ContextChanged**: Context Window transitioned
- **EventStateChanged**: Event moved to new state
- **ResourceThresholdCrossed**: Resource reached critical level
- **DisturbanceDetected**: Event Disturber occurred
- **TimeProgressed**: Significant time passed
- **RecommendationGenerated**: New Recommendation available
- **PlanUpdated**: Scheduler revised plan
- **EventCompleted**: Event finished execution
- **ReflectionCreated**: User provided Reflection
- **InsightGenerated**: New Insight extracted
- **HabitDetected**: New Habit identified

### Event-Driven Benefits

Event-driven communication provides:

- **Loose coupling**: Components don't directly call each other
- **Reactive behavior**: Components respond to changes
- **Scalability**: Easy to add new subscribers
- **Testability**: Can test components in isolation
- **Flexibility**: Can change implementation without affecting others

### Synchronous vs Asynchronous

Most communication is asynchronous:

```
Publisher publishes event
  ↓
Continues immediately
  ↓
Subscribers process later
  ↓
No blocking
```

Critical operations may be synchronous:

```
Publisher publishes event
  ↓
Waits for critical subscribers
  ↓
Subscribers respond
  ↓
Publisher continues
```

The Runtime Kernel manages which events are synchronous vs asynchronous.

---

## 13. Behavioral Principles

These principles guide the runtime behavior of PAIOS.

### Core Behavioral Principles

**History is immutable**
- Past Events never change
- Corrections happen via new Events
- Historical data is read-only at runtime

**Scheduler only changes future**
- Scheduler never touches past Events
- Planning always starts from Current Time
- Only future Events are modified

**Runtime always reflects reality**
- Runtime State matches actual world state
- Reality overrides planning
- System adapts to changes

**Reality overrides planning**
- Event Disturbers take precedence
- Context changes trigger replanning
- User actions override suggestions

**Higher priority events may interrupt lower priority events**
- Priority determines execution order
- Urgent events can replace scheduled events
- Scheduler handles interruption gracefully

**Context continuously evolves**
- Context changes throughout the day
- Context Windows have lifecycle
- Context influences all decisions

**Time is continuous**
- Runtime clock never stops
- Time flows through all components
- Time synchronizes the system

**Learning only occurs from completed history**
- Only completed Events contribute to learning
- Reflections require completed Events
- Insights need full Event data

### Runtime Invariants

The system maintains these invariants:

- **Exactly one Active Context Window** at any time
- **Exactly one Running Event** at any time (or zero)
- **Completed Events are immutable**
- **Recommendations never modify Events**
- **Resources cannot become invalid**
- **Reflection requires an Event**
- **Progress belongs to one Project**
- **Context Window references one Context**
- **Scheduler never edits History**
- **Event IDs are immutable**
- **Only one Scheduler per User**

### Runtime Policies

Policies are runtime rules that can evolve (unlike Principles):

**Repeated Events infer Habits**
- Pattern detection over time
- Confidence threshold creates Habit candidates
- Habit strength increases with repetition

**Repeated rejected Recommendations lower confidence**
- Track rejection patterns
- Adjust confidence scores
- Improve Recommendation quality

**Repeated harmful Context Windows trigger Recommendations**
- Detect problematic contexts
- Suggest context changes
- Warn user of patterns

**Repeated Event Disturbers increase Scheduler flexibility**
- Learn from disturbances
- Build in buffer time
- Improve robustness

**Recommendations expire**
- Time-based expiration
- Context-based expiration
- Resource-based expiration

**Scheduler recalculates after Context Window changes**
- Context transition triggers replanning
- New context may require new actions
- Old plan may no longer be valid

### Policies vs Principles

**Policies**
- Runtime rules
- Can evolve over time
- Learned from behavior
- Can be adjusted
- Guide execution

**Principles**
- Foundation rules
- Never evolve
- Defined by user
- Immutable
- Guide all decisions

Policies are how the system behaves. Principles are what the system values.

---

## Implementation Guidance

### Implementation Order

When implementing PAIOS, follow this order:

1. **Domain Model**: Define entities and relationships
2. **Behavioral Architecture**: Define runtime behavior (this document)
3. **Application Services**: Implement business logic
4. **Infrastructure**: Implement persistence, APIs, etc.

### Key Implementation Considerations

**Runtime Kernel**
- Must be highly reliable
- Must handle concurrent operations
- Must maintain consistency
- Must be performant

**Event-Driven Communication**
- Use message bus or event system
- Handle event ordering
- Manage event delivery guarantees
- Monitor event processing

**Time Management**
- Use reliable time source
- Handle clock adjustments
- Track time accurately
- Synchronize across components

**State Management**
- Runtime State must be thread-safe
- Historical data must be immutable
- State transitions must be validated
- Rollback on failure

**Learning Pipeline**
- Process Events asynchronously
- Handle Reflection delays
- Update Knowledge incrementally
- Improve Recommendations continuously

### Future Extensions

This Behavioral Architecture will be extended with:

- **Timer Engine**: Detailed time tracking and scheduling
- **State Machines**: Formal state machine definitions
- **System Events**: Comprehensive event catalog
- **Lifecycles**: Detailed lifecycle specifications
- **Runtime**: Detailed runtime behavior

These will be documented in separate files as specified in the file structure.

---

## Conclusion

The Behavioral Architecture defines how PAIOS behaves while running.

The system is:
- **Continuously running**: Never stops observing and learning
- **Change-driven**: Reacts to reality changes
- **Event-centric**: Everything revolves around Events
- **Time-aware**: Time synchronizes all components
- **Context-sensitive**: Context influences all decisions
- **Learning-oriented**: Improves continuously from history

The Domain Model defines WHAT exists. The Behavioral Architecture defines HOW it behaves.

Together, they form the complete foundation for implementing PAIOS as a Personal AI Operating System.
