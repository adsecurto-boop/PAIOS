# DECISION_ENGINE.md

This document answers: **"How does PAIOS reason before making a recommendation?"**

It describes the reasoning process that transforms current runtime state into intelligent Recommendations, Priority Evaluations, Confidence Scores, and Scheduler inputs.

This document complements:
- `DOMAIN_MODEL.md` — What exists
- `ENTITY_RELATIONSHIPS.md` — How entities connect
- `BUSINESS_RULES.md` — System behavior rules
- `BEHAVIORAL_ARCHITECTURE.md` — How entities behave over time
- `STATE_MACHINES.md` — Formal state transition specifications
- `SYSTEM_EVENTS.md` — Runtime communication events
- `RUNTIME_EXECUTION.md` — How the system runs moment-to-moment

---

## 1. Purpose

The Decision Engine is the reasoning brain of PAIOS. It transforms observations into intelligent guidance.

### Role

The Decision Engine reasons over current runtime state to determine what the user should do next. It analyzes reality, applies constraints, evaluates options, and produces Recommendations.

### What the Decision Engine Does NOT Do

**Owns NO persistent data**
- The Decision Engine is stateless
- It reads from other components but owns nothing
- It maintains no internal state between invocations
- It can be replaced, retrained, or revised without data loss

**Never modifies History**
- Completed Events are immutable
- The Decision Engine never edits past Events
- It never changes Context Window history
- It never alters Resource consumption records

**Never executes Events**
- The Decision Engine does not perform actions
- It does not start, pause, or stop Events
- Execution is the user's domain
- The Decision Engine only suggests

**Never schedules Events**
- The Decision Engine does not allocate time slots
- It does not create Scheduled Events
- Scheduling is the Scheduler's exclusive responsibility
- The Decision Engine only provides inputs for scheduling

**Only reasons**
- The Decision Engine is a pure reasoning process
- It transforms inputs into outputs
- It produces no side effects
- It is deterministic given identical inputs

### Outputs

The Decision Engine produces:
- **Recommendations** — Action suggestions for the user
- **Priority Evaluations** — Relative importance scores for options
- **Confidence Scores** — Certainty that a recommendation is appropriate
- **Scheduler Inputs** — Constraints, preferences, and planning hints

### Why This Separation Exists

The separation between reasoning and execution is fundamental to PAIOS architecture:

**Reasoning must be safe**
- If reasoning fails, the system should still function
- A flawed reasoning process should not corrupt data
- The Decision Engine can be improved without risking History

**Reasoning must be revisable**
- As PAIOS learns, reasoning improves
- New patterns can be recognized
- Old assumptions can be corrected
- Stateless reasoning enables continuous improvement

**Reasoning must be transparent**
- The user should understand why recommendations are made
- Reasoning can be audited and explained
- Separation enables explanation without execution

**Reasoning must respect autonomy**
- The user decides whether to accept Recommendations
- The Decision Engine advises, it does not command
- Separation preserves user agency

---

## 2. Inputs

The Decision Engine consumes a comprehensive snapshot of current runtime state.

### Input List

**Current Time**
- System clock value
- Time of day
- Time until next scheduled Event
- Time remaining in current Context Window

**Contribution:** Time provides the temporal context for all reasoning. Actions that made sense an hour ago may no longer be appropriate. Time urgency, resource availability, and context relevance all depend on Current Time.

**Current Context Window**
- Active Context ID
- Context definition (location, people, environment)
- Context Window start time and duration
- Context Window state (Active/Changing/Expired)

**Contribution:** Context Window explains the situational reality. Different actions are appropriate in different contexts. Context enables the Decision Engine to filter options that don't match the current situation.

**Running Event**
- Event ID if an Event is currently Running
- Event elapsed time
- Event remaining time
- Event Resource consumption so far

**Contribution:** Running Event represents current commitment. The Decision Engine must consider whether to continue, pause, or interrupt the current action. Momentum and completion progress influence recommendations.

**Scheduler State**
- Current Scheduled Events
- Next Scheduled Event timing
- Plan horizon
- Last recalculation time

**Contribution:** Scheduler State shows what is already planned. The Decision Engine reads Scheduler State only to avoid conflicts with existing commitments and to identify gaps where new Recommendations can fit. The Decision Engine never evaluates or judges the Scheduler's plan, and it never determines when the Scheduler should replan.

**Resources**
- Current Resource levels (time, money, energy, health, knowledge, focus)
- Resource regeneration rates
- Resource consumption rates
- Resource threshold status

**Contribution:** Resources constrain what is possible. The Decision Engine cannot recommend actions that require unavailable Resources. Resource levels also signal when replenishment actions are needed.

**Goals**
- Active Goals (emergent, user-accepted)
- Goal progress
- Goal priority
- Goal deadline proximity

**Contribution:** Goals provide directional guidance. They help the Decision Engine prioritize actions that advance long-term direction over short-term convenience.

**Projects**
- Active Projects
- Project Progress
- Project priority
- Project completion percentage

**Contribution:** Projects organize intentional work. The Decision Engine recommends actions that advance Projects while respecting Resource constraints and Principles.

**Principles**
- Immutable Principle definitions
- Principle categories
- Principle priority order

**Contribution:** Principles are non-negotiable constraints. The Decision Engine filters out any option that violates a Principle. Principles are the foundation of all reasoning.

**Domain Policies**
- Current runtime rules
- Policy confidence thresholds
- Policy evolution status

**Contribution:** Domain Policies shape behavior while remaining evolvable. Unlike Principles, Policies can change as PAIOS learns. The Decision Engine applies Policies as flexible guidance.

**Knowledge**
- Current Knowledge state
- Knowledge confidence levels
- Knowledge retention scores
- Knowledge gaps

**Contribution:** Knowledge informs what the user is capable of and what they need to learn. The Decision Engine recommends actions that build on existing Knowledge and address gaps.

**Habits**
- Detected Habit patterns
- Habit strength scores
- Habit trigger associations
- Habit reward patterns

**Contribution:** Habits represent recurring behaviors. The Decision Engine considers whether to reinforce beneficial Habits, interrupt harmful ones, or leverage existing patterns.

**User Preferences**
- Explicit user preferences
- Preferred activity types
- Preferred timing
- Preferred context

**Contribution:** User preferences personalize Recommendations. They are configuration/settings rather than a domain entity, ensuring the Decision Engine respects individual choices while still applying Principles and constraints.

**Pending Recommendations**
- Previously generated Recommendations
- Recommendation status (Pending/Accepted/Rejected/Expired)
- Recommendation confidence scores

**Contribution:** Pending Recommendations provide continuity. The Decision Engine considers whether to reaffirm, modify, or expire previous suggestions.

**Event Disturbers**
- Active Event Disturbers
- Disturbance severity
- Disturbance impact assessment

**Contribution:** Event Disturbers signal reality changes. The Decision Engine must adjust reasoning to account for interruptions and new constraints.

**Reflection History**
- Past Reflections on Events
- Insights extracted from Reflections
- Lessons learned

**Contribution:** Reflection History provides the learning foundation. The Decision Engine uses past Reflections to avoid repeating mistakes and to reinforce successful patterns.

**Progress**
- Project Progress updates
- Completion velocity
- Estimated completion time
- Confidence in estimates

**Contribution:** Progress shows how intentional work is advancing. The Decision Engine recommends actions that maintain momentum and address stalled Projects.

**Impact Classification**
- Historical Impact classifications (Opportunity/Neutral/Distraction)
- Impact patterns across Events
- Context-Impact correlations
- Time-Impact correlations

**Contribution:** Impact Classification informs pattern recognition about which actions historically produced Opportunity vs Distraction outcomes. This helps the Decision Engine avoid recommending actions that historically resulted in Distractions and prioritize actions that historically produced Opportunities.

**Completed Events (Historical Events)**
- Raw historical Event data
- Event Resource Flow records
- Event Context Window associations
- Event timing and duration data

**Contribution:** Completed Events provide the raw material for pattern recognition, habit detection, and historical success analysis. Unlike Reflection History (which is derived), raw Event data enables the Decision Engine to identify patterns directly from what actually happened.

---

## 3. Reasoning Pipeline

The Decision Engine follows a structured reasoning pipeline from observation to Recommendation.

### Pipeline Overview

```
Observe Reality
  ↓
Validate Runtime State
  ↓
Evaluate Principles
  ↓
Evaluate Resources
  ↓
Evaluate Context
  ↓
Evaluate Current Event
  ↓
Evaluate Goals
  ↓
Evaluate Habits
  ↓
Generate Candidate Actions
  ↓
Filter Invalid Candidates
  ↓
Rank Remaining Candidates
  ↓
Calculate Confidence
  ↓
Generate Recommendation
  ↓
Publish Recommendation
```

### Pipeline Stages

**Observe Reality**
- Load complete Runtime State snapshot from Runtime Kernel
- Ensure all inputs are current
- Detect any missing or stale data
- Establish baseline for reasoning

**WHY:** Reasoning must begin from accurate, complete reality. Garbage in produces garbage out. This stage ensures the Decision Engine works from a valid foundation. The Runtime Kernel provides the unified Runtime State snapshot as the single source of truth.

**Validate Runtime State**
- Perform lightweight reasoning-specific validation
- Verify relevant Domain Invariants hold (e.g., "Exactly one Active Context Window", "Exactly one Running Event")
- Detect conflicting information specific to reasoning needs
- Flag any anomalies that would affect reasoning quality

**WHY:** Invalid state produces invalid reasoning. Before applying logic, the Decision Engine must ensure the input state is coherent and trustworthy. This is lightweight validation focused on reasoning needs—comprehensive system-wide validation is the Runtime Kernel's responsibility per BEHAVIORAL_ARCHITECTURE.md.

**Evaluate Principles**
- Apply Principle constraints
- Filter out Principle-violating options
- Ensure all reasoning respects Dharma
- Establish non-negotiable boundaries

**WHY:** Principles are immutable. No Recommendation may violate a Principle. This stage happens early to eliminate invalid options before expensive computation.

**Evaluate Resources**
- Assess Resource availability
- Calculate Resource requirements for actions
- Identify Resource constraints
- Flag Resource exhaustion

**WHY:** Resources ground reasoning in reality. Recommending impossible actions wastes time and erodes trust. Resource evaluation ensures Recommendations are feasible.

**Evaluate Context**
- Match actions to current Context
- Assess Context compatibility
- Consider Context transitions
- Evaluate Context-specific opportunities

**WHY:** Context determines situational appropriateness. Actions that are excellent in one Context may be inappropriate in another. Context evaluation ensures Recommendations fit the moment.

**Evaluate Current Event**
- Assess Running Event progress
- Evaluate completion momentum
- Consider interruption costs
- Determine continuation value

**WHY:** The user's current action has momentum. Interrupting without justification is disruptive. This stage ensures the Decision Engine respects current engagement.

**Evaluate Goals**
- Assess Goal alignment
- Evaluate Goal urgency
- Consider Goal dependencies
- Identify Goal-advancing opportunities

**WHY:** Goals provide long-term direction. Without Goal evaluation, the Decision Engine might optimize for short-term convenience at the expense of meaningful progress.

**Evaluate Habits**
- Assess Habit patterns
- Consider Habit triggers
- Evaluate Habit reinforcement
- Identify Habit interruption opportunities

**WHY:** Habits represent automatic behaviors. The Decision Engine can leverage beneficial Habits and interrupt harmful ones by understanding their patterns.

**Generate Candidate Actions**
- Produce possible next actions
- Consider continuation options
- Consider new action options
- Consider rest and recovery options

**WHY:** Before selecting the best action, the Decision Engine must generate a diverse set of possibilities. This stage ensures the final Recommendation is chosen from a comprehensive option space.

**Filter Invalid Candidates**
- Remove Principle-violating candidates
- Remove Resource-infeasible candidates
- Remove Context-incompatible candidates
- Remove already-completed candidates

**WHY:** Filtering invalid candidates early reduces the ranking space and ensures the final Recommendation is valid. Invalid options should never reach ranking.

**Rank Remaining Candidates**
- Evaluate candidates on multiple dimensions
- Apply weighted scoring
- Consider trade-offs
- Identify top candidates

**WHY:** Ranking transforms a set of valid options into an ordered preference list. This enables the Decision Engine to recommend the best option while providing alternatives.

**Calculate Confidence**
- Assess certainty in Recommendation
- Consider data completeness
- Evaluate pattern strength
- Estimate prediction reliability

**WHY:** Confidence communicates uncertainty. A Recommendation with low confidence should be presented differently than one with high confidence. Confidence also enables Domain Policies to use thresholds.

**Generate Recommendation**
- Select top-ranked candidate
- Compose Recommendation message
- Provide explanation
- Attach confidence score

**WHY:** The Recommendation is the Decision Engine's primary output. This stage transforms reasoning results into actionable guidance for the user.

**Publish Recommendation**
- Emit RecommendationGenerated system event to Runtime Kernel
- Runtime Kernel broadcasts Recommendation to subscribed components
- Runtime Kernel triggers Scheduler notification
- Log Recommendation for history
- Enable user presentation

**WHY:** Publishing makes the Recommendation available to the rest of the system. The Runtime Kernel broadcasts the RecommendationGenerated event, the Scheduler considers it, and the user sees it. The Runtime Kernel is the central orchestrator per BEHAVIORAL_ARCHITECTURE.md.

---

## 4. Candidate Generation

Candidate actions are possible next steps the user could take.

### Candidate Types

**Continue Current Event**
- Maintain current Running Event
- Allow completion of ongoing action
- Preserve momentum
- Avoid interruption cost

**Pause Event**
- Temporarily halt current Running Event
- Enable context switch
- Allow resource recovery
- Enable priority reassessment

**Resume Event**
- Continue a previously Paused Event
- Return to interrupted action
- Complete partial work
- Maintain commitment

**Recommend Learning**
- Suggest learning activity
- Address Knowledge gaps
- Build on existing Knowledge
- Advance Project progress

**Recommend Rest**
- Suggest recovery time
- Address Resource depletion
- Prevent burnout
- Enable sustained performance

**Recommend Exercise**
- Suggest physical activity
- Improve Health Resource
- Enhance mental clarity
- Establish beneficial Habit

**Recommend Reflection**
- Suggest review of past Events
- Extract Insights from experience
- Improve future decision quality
- Strengthen learning loop

**Recommend Prayer**
- Suggest spiritual practice
- Align with Spiritual Principles
- Provide mental clarity
- Connect with higher purpose

**Recommend Break**
- Suggest short pause
- Enable mental reset
- Improve focus on return
- Prevent fatigue accumulation

**Recommend Focus Session**
- Suggest deep work period
- Minimize distractions
- Leverage high-focus Context
- Advance high-priority work

### Generation Source

Candidates are generated from current runtime state:

- **From Context:** Context-appropriate actions (e.g., "Office" suggests work actions)
- **From Resources:** Resource-replenishing actions (e.g., low energy suggests rest)
- **From Goals:** Goal-advancing actions (e.g., certification goal suggests study)
- **From Habits:** Habit-consistent actions (e.g., morning Habit suggests exercise)
- **From Projects:** Project-relevant actions (e.g., Project deadline suggests focused work)
- **From Knowledge:** Knowledge-building actions (e.g., Knowledge gap suggests learning)
- **From Current Event:** Continuation or completion actions (e.g., Running Event suggests continue)

### Generation Principles

**Diversity**
- Generate candidates across different action types
- Include both continuation and new actions
- Consider both productive and restorative actions
- Ensure option space is not narrow

**Feasibility**
- Generate only candidates that could potentially be valid
- Consider basic Resource constraints during generation
- Respect basic Context compatibility during generation
- Avoid generating obviously impossible options

**Relevance**
- Generate candidates relevant to current situation
- Consider time of day
- Consider current Context
- Consider current Resource state
- Consider current priorities

**Completeness**
- Generate candidates covering all reasonable options
- Don't omit valid action categories
- Include both proactive and reactive options
- Consider both short-term and long-term actions

---

## 5. Candidate Filtering

Candidate filtering removes invalid options before ranking.

### Filter Categories

**Violates Principle**
- Action contradicts a Principle
- Action violates Dharma
- Action conflicts with immutable values
- Action is ethically unacceptable

**Example:** "Work overtime to exhaustion" violates "Protect Health" Principle.

**Insufficient Resources**
- Action requires unavailable Resources
- Action exceeds Resource capacity
- Action would cause Resource exhaustion
- Action is Resource-infeasible

**Example:** "Start 2-hour study session" when Energy Resource is at 10%.

**Wrong Context**
- Action inappropriate for current Context
- Action requires different location
- Action requires different people
- Action requires different environment

**Example:** "Hold meeting" when Context Window is "Home alone."

**Already Completed**
- Action already performed recently
- Action redundant with completed Event
- Action would duplicate effort
- Action already achieved its purpose

**Example:** "Submit report" when Report submission Event completed yesterday.

**Already Running**
- Action currently in progress
- Action already being executed
- Action would cause duplication
- Action already has momentum

**Example:** "Start coding" when Running Event is "Coding session."

**Outside Time Window**
- Action requires unavailable time
- Action exceeds remaining time in Context Window
- Action conflicts with scheduled commitment
- Action timing is infeasible

**Example:** "1-hour exercise" when only 15 minutes remain before next Scheduled Event.

**Conflicts with Higher Priority Event**
- Action would delay higher-priority Scheduled Event
- Action would miss critical deadline
- Action would violate priority order
- Action would cause Overtaken scenario

**Example:** "Casual reading" when high-priority deadline Event is Scheduled in 30 minutes.

### Filtering Order

Filters are applied in a specific order to optimize efficiency:

1. **Principle violations** — Eliminated first (non-negotiable)
2. **Resource infeasibility** — Eliminated second (hard constraint)
3. **Context incompatibility** — Eliminated third (situational constraint)
4. **Already completed/running** — Eliminated fourth (redundancy check)
5. **Time window conflicts** — Eliminated fifth (timing constraint)
6. **Priority conflicts** — Eliminated last (ordering constraint)

This order ensures the most expensive checks (priority conflicts) only run on candidates that have passed all cheaper filters.

### Filtering Outcome

After filtering, the candidate set contains only:
- Principle-compliant actions
- Resource-feasible actions
- Context-appropriate actions
- Non-redundant actions
- Time-feasible actions
- Priority-respecting actions

This filtered set proceeds to ranking.

---

## 6. Ranking

Ranking evaluates remaining valid candidates to identify the best Recommendation.

### Ranking Dimensions

**Principle Alignment**
- How well the action aligns with Principles
- Whether the action advances Principle-aligned outcomes
- Whether the action avoids Principle-violating side effects
- Score: Higher is better

**Goal Contribution**
- How much the action advances active Goals
- Whether the action addresses Goal urgency
- Whether the action resolves Goal dependencies
- Score: Higher is better

**Resource Efficiency**
- How efficiently the action uses Resources
- Whether the action provides good Resource ROI
- Whether the action preserves scarce Resources
- Score: Higher is better

**Context Compatibility**
- How well the action fits current Context
- Whether the action leverages Context advantages
- Whether the action avoids Context disadvantages
- Score: Higher is better

**Urgency**
- How time-sensitive the action is
- Whether delay would cause problems
- Whether the action has a deadline
- Score: Higher is more urgent

**Impact**
- How significant the action's outcome is
- Whether the action produces meaningful change
- Whether the action has lasting benefit
- Score: Higher is better

**Opportunity Gain**
- How much the action increases Opportunity-classified time
- Whether the action moves user from Neutral/Distraction to Opportunity
- Whether the action maximizes value
- Score: Higher is better

**Note:** This is a Recommendation ranking dimension only. The actual optimization of Opportunity vs Distraction time allocation is performed by the Scheduler during planning (per BEHAVIORAL_ARCHITECTURE.md).

**Distraction Reduction**
- How much the action reduces Distraction-classified time
- Whether the action avoids known distractions
- Whether the action protects focus
- Score: Higher is better

**Note:** This is a Recommendation ranking dimension only. The actual optimization of Opportunity vs Distraction time allocation is performed by the Scheduler during planning (per BEHAVIORAL_ARCHITECTURE.md).

**Historical Success**
- How well similar actions succeeded in the past
- Whether the action has a track record of positive outcomes
- Whether the action avoids historical failure patterns
- Score: Higher is better

**Habit Formation**
- How much the action reinforces beneficial Habits
- Whether the action strengthens positive patterns
- Whether the action interrupts negative patterns
- Score: Higher is better

**Knowledge Growth**
- how much the action builds Knowledge
- Whether the action addresses Knowledge gaps
- Whether the action strengthens retention
- Score: Higher is better

**Momentum Preservation**
- How much the action maintains current momentum
- Whether the action avoids unnecessary interruption
- Whether the action leverages existing engagement
- Score: Higher is better

### Ranking Process

```
For each remaining candidate:
  ↓
Evaluate on all dimensions
  ↓
Apply dimension weights
  ↓
Calculate weighted sum
  ↓
Produce overall score
  ↓
Sort candidates by score
  ↓
Select top candidate(s)
```

### Dimension Weights

Dimension weights are not fixed. They vary based on:

- **Current Resource state** — Resource exhaustion increases Resource Efficiency weight
- **Current Context** — Context-specific opportunities increase Context Compatibility weight
- **Goal urgency** — Approaching deadlines increase Urgency weight
- **Principle priority** — Some Principles have higher weight in certain situations
- **Time of day** — Morning vs evening may shift emphasis (e.g., learning vs rest)

Weight adaptation ensures ranking responds to current reality rather than applying static formulas.

### Trade-off Handling

Ranking inherently involves trade-offs. Examples:

- **High Impact, Low Resource Efficiency** — Worth it if Resources are sufficient
- **High Urgency, Low Principle Alignment** — Never acceptable (Principles override)
- **High Goal Contribution, Low Context Compatibility** — May be acceptable if Context can change
- **High Habit Formation, Low Historical Success** — Risky but may be worth trying

The Decision Engine explicitly evaluates trade-offs rather than seeking a single optimal dimension. This produces nuanced Recommendations that balance competing concerns.

---

## 7. Confidence

Confidence represents certainty that a Recommendation is appropriate for current runtime state.

### What Confidence Is NOT

**Confidence is NOT probability**
- Confidence does not predict likelihood of user acceptance
- Confidence does not predict likelihood of success
- Confidence does not represent a statistical measure
- Confidence is not a percentage chance

### What Confidence Is

**Confidence IS appropriateness certainty**
- Confidence measures how well the Recommendation fits current state
- Confidence reflects data completeness and pattern strength
- Confidence indicates how strongly the Decision Engine believes this is the right action
- Confidence is a qualitative measure of recommendation quality

### Factors That Increase Confidence

**Strong Pattern Match**
- Current situation closely matches historical successful patterns
- Habit patterns strongly support the action
- Context-Action pairing has high historical success rate

**Complete Data**
- All required inputs are available and current
- No missing or stale data
- Runtime State is consistent and validated
- No anomalies or conflicts detected

**High Principle Alignment**
- Action strongly aligns with multiple Principles
- Action advances Principle-aligned outcomes
- No Principle trade-offs required

**Resource Feasibility**
- Resources are comfortably sufficient
- No Resource constraints near thresholds
- Resource efficiency is high

**Context Fit**
- Action is highly appropriate for current Context
- Context strongly supports the action
- No Context trade-offs required

**Goal Alignment**
- Action strongly advances active Goals
- Action addresses Goal urgency
- Action resolves Goal dependencies

**Historical Success**
- Similar actions have high success rate
- User has positive history with this action type
- No historical failure patterns detected

### Factors That Decrease Confidence

**Weak Pattern Match**
- Current situation is unusual or novel
- No strong Habit patterns support the action
- Context-Action pairing has limited historical data

**Incomplete Data**
- Some inputs are missing or stale
- Runtime State has anomalies or conflicts
- Validation warnings present

**Principle Trade-offs**
- Action requires balancing competing Principles
- Action has minor Principle tension
- Principle alignment is moderate rather than strong

**Resource Constraints**
- Resources are barely sufficient
- Resource constraints near thresholds
- Resource efficiency is marginal

**Context Mismatch**
- Action is only moderately appropriate for Context
- Context provides weak support
- Context trade-offs required

**Goal Ambiguity**
- Action has weak Goal alignment
- Goal priorities are unclear
- Goal dependencies are unresolved

**Mixed History**
- Similar actions have mixed success rates
- User has inconsistent history with this action type
- Some historical failure patterns detected

### Confidence and Domain Policies

Domain Policies may use confidence thresholds for behavioral decisions:

**Habit Emergence**
- Repeated high-confidence Recommendations may trigger Habit candidate generation
- Confidence threshold ensures only strong patterns become Habits
- Prevents weak patterns from being treated as Habits

**Recommendation Persistence**
- High-confidence Recommendations may be reaffirmed across multiple ticks
- Low-confidence Recommendations may expire quickly
- Confidence determines suggestion persistence

**Learning Acceleration**
- High-confidence successful outcomes may accelerate learning
- Low-confidence outcomes may require more evidence
- Confidence weights learning rate

### Confidence Presentation

Confidence is communicated to the user:

**High Confidence**
- Presented as strong Recommendation
- Explanation emphasizes certainty
- User encouraged to accept

**Medium Confidence**
- Presented as moderate Recommendation
- Explanation acknowledges uncertainty
- User invited to consider

**Low Confidence**
- Presented as tentative suggestion
- Explanation highlights uncertainty
- User advised to evaluate carefully

---

## 8. Outputs

The Decision Engine produces specific outputs that guide the system.

### Output List

**Recommendation**
- Suggested action for the user (the system's "Next Best Action")
- Action description
- Suggested timing
- Expected benefit

**Ownership:** Decision Engine owns the Recommendation output. It is the primary product of reasoning and represents the system's "Next Best Action" for the current moment.

**Priority Evaluation**
- Relative importance score
- Comparison to other options
- Ranking position
- Priority justification

**Ownership:** Decision Engine owns the Priority Evaluation. It provides the Scheduler with preference information.

**Confidence**
- Appropriateness certainty score
- Confidence factors
- Confidence level (High/Medium/Low)

**Ownership:** Decision Engine owns the Confidence score. It communicates recommendation quality.

**Explanation**
- Why this Recommendation was made
- Which factors influenced the decision
- What trade-offs were considered
- How Principles were applied

**Ownership:** Decision Engine owns the Explanation. It enables transparency and user understanding.

**Scheduler Input**
- Planning constraints
- Timing preferences
- Resource requirements
- Context dependencies

**Ownership:** Decision Engine owns the Scheduler Input. It provides guidance without controlling scheduling.

**No Action**
- Signal that no Recommendation is appropriate
- Reason for no action (e.g., current state is optimal)
- Suggestion to continue current state

**Ownership:** Decision Engine owns the No Action signal. It is a valid Recommendation outcome/signal when reasoning determines inaction is best, not a separate domain entity.

### Output Characteristics

**Deterministic**
- Given identical Runtime State, outputs are identical
- No randomness in reasoning process
- Reproducible results for debugging

**Principle-Compliant**
- All outputs respect Principles
- No output suggests Principle violation
- Principles are hard constraints on all outputs

**Resource-Aware**
- All outputs consider Resource constraints
- No output suggests Resource-infeasible action
- Resource efficiency is a ranking factor

**Context-Appropriate**
- All outputs fit current Context
- No output suggests Context-incompatible action
- Context compatibility is a ranking factor

**Explainable**
- All outputs include Explanation
- Reasoning can be audited
- User can understand why Recommendation was made

---

## 9. Interaction with Scheduler

The Decision Engine and Scheduler have distinct, complementary responsibilities.

### Responsibility Separation

**Decision Engine does NOT schedule**
- Decision Engine does not allocate time slots
- Decision Engine does not create Scheduled Events
- Decision Engine does not manage Event timing
- Decision Engine does not handle Event conflicts

**Scheduler does NOT perform Decision Engine reasoning**
- Scheduler does not assess Goal alignment
- Scheduler does not rank Recommendation candidates
- Scheduler does not generate Recommendations
- Scheduler enforces Principles as non-negotiable planning constraints; this is constraint enforcement, not Decision Engine reasoning

**Decision Engine suggests**
- Decision Engine produces Recommendations
- Decision Engine provides priority guidance
- Decision Engine offers constraints and preferences
- Decision Engine explains reasoning

**Scheduler plans**
- Scheduler consumes Recommendations
- Scheduler allocates time and Context
- Scheduler manages Event conflicts
- Scheduler handles Event Disturbers

### Interaction Flow

```
Decision Engine
  ↓ (produces Recommendation)
Scheduler
  ↓ (evaluates Recommendation)
Scheduler
  ↓ (checks feasibility against Resources)
Scheduler
  ↓ (checks availability in Context Window)
Scheduler
  ↓ (checks conflicts with existing Scheduled Events)
Scheduler
  ↓ (accepts or defers Recommendation)
Scheduler
  ↓ (creates Scheduled Event if accepted)
Scheduler
  ↓ (updates plan)
```

### Scheduler Consumption of Decision Engine Outputs

**Recommendation**
- Scheduler considers Recommendation for scheduling
- Scheduler may accept, defer, or reject based on feasibility
- Scheduler does not modify the Recommendation itself

**Priority Evaluation**
- Scheduler uses priority to order Scheduled Events
- Higher-priority Recommendations get preferred time slots
- Scheduler respects priority order unless Resource/Context constraints prevent

**Confidence**
- Scheduler may use confidence to weight Recommendation importance
- High-confidence Recommendations may be scheduled more aggressively
- Low-confidence Recommendations may be scheduled tentatively

**Scheduler Input**
- Scheduler uses constraints to guide planning
- Scheduler respects timing preferences when possible
- Scheduler considers Resource requirements in allocation

**No Action**
- Scheduler interprets No Action as signal to maintain current plan
- Scheduler continues with existing Scheduled Events
- Scheduler does not generate new Scheduled Events

### Why Separation Matters

**Reasoning requires different expertise than planning**
- Decision Engine expertise: pattern recognition, Principle application, priority evaluation
- Scheduler expertise: time allocation, conflict resolution, Context management

**Reasoning is stateless, planning is stateful**
- Decision Engine: pure function, no persistent state
- Scheduler: maintains current plan, replans on changes

**Reasoning is advisory, planning is operational**
- Decision Engine: suggests what to do
- Scheduler: decides when and how to do it

**Reasoning can be improved independently**
- Decision Engine can be retrained or replaced without affecting Scheduler
- Scheduler can be optimized without affecting Decision Engine

---

## 10. Interaction with Runtime

The Decision Engine participates in the eternal runtime loop.

### Runtime Sequence

```
Runtime Tick
  ↓
Runtime Kernel
  ↓ (collects Runtime State)
Decision Engine
  ↓ (receives Runtime State snapshot)
Decision Engine
  ↓ (executes reasoning pipeline)
Decision Engine
  ↓ (produces Recommendation)
Runtime Kernel
  ↓ (broadcasts Recommendation)
Scheduler
  ↓ (consumes Recommendation)
Scheduler
  ↓ (creates or updates Scheduled Event)
Scheduler
  ↓ (triggers Event State Transition if needed)
Runtime Kernel
  ↓ (publishes system events)
Decision Engine
  ↓ (may be triggered again on next tick)
```

### Step-by-Step Explanation

**Runtime Tick**
- Clock advances
- Runtime Kernel initiates new cycle
- All components prepare for observation

**Runtime Kernel**
- Collects current state from all components
- Assembles unified Runtime State snapshot
- Validates snapshot consistency (system-wide validation)
- Provides snapshot to Decision Engine
- The Runtime Kernel is the central orchestrator per BEHAVIORAL_ARCHITECTURE.md Section 4

**Decision Engine**
- Receives Runtime State snapshot
- Executes reasoning pipeline
- Produces Recommendation, Priority, Confidence, Explanation
- Returns outputs to Runtime Kernel

**Recommendation**
- Runtime Kernel receives Decision Engine outputs
- Runtime Kernel publishes RecommendationGenerated system event
- Subscribed components (Scheduler, user interface) receive the event
- Logs Recommendation for history
- Presents Recommendation to user

**Scheduler**
- Receives Recommendation from Runtime Kernel
- Evaluates Recommendation against current plan
- Checks feasibility (Resources, Context, time)
- Accepts, defers, or rejects Recommendation
- Creates or updates Scheduled Event if accepted
- Triggers Event State Transition if needed

**Event State Transition**
- Scheduler applies state transition per STATE_MACHINES.md
- Runtime Kernel publishes EventStateChanged system event
- Other components react to state change
- Running Event may start, pause, resume, or complete

**Runtime Kernel**
- Publishes all system events (e.g., ContextChanged, ResourceThresholdCrossed, EventStateChanged)
- Notifies subscribed components
- Decision Engine subscribes to events like ContextChanged and ResourceThresholdCrossed to trigger reasoning
- Maintains Runtime State consistency
- Waits for next tick

**Decision Engine**
- May be triggered again on next tick
- Receives updated Runtime State
- Repeats reasoning cycle
- Produces new Recommendations as needed

### Continuous Operation

The Decision Engine runs continuously as part of the eternal runtime loop:

- Every tick: Observe new state
- Every tick: Reason over current state
- Every tick: Produce updated Recommendations
- Every tick: Adapt to reality changes

The Decision Engine never sleeps. It never stops reasoning. It is always ready to guide the next decision.

---

## 11. Learning

Completed Events improve future Decision Engine reasoning.

### Learning Flow

```
Completed Event
  ↓
Reflection (user provides)
  ↓
Insight (extracted)
  ↓
Knowledge (updated)
  ↓
Decision Engine
  ↓ (incorporates learning)
Better Recommendations
```

### Learning Components

**Reflection**
- User's interpretation of why Event occurred
- Captures facts, interpretation, root cause, lesson learned
- Provides meaning to raw Event data
- User-owned, user-controlled

**Insight**
- Distilled wisdom from Reflection
- Reusable learning applicable to future situations
- Extracted by Reflection Engine
- Feeds Decision Engine pattern recognition

**Knowledge**
- Tracked learning and skill acquisition
- Updated through Events
- Changes over time (revision, application, retention decay)
- Provides capability assessment to Decision Engine

### Decision Engine Learning Integration

**Pattern Recognition**
- Decision Engine identifies recurring patterns across Events
- Patterns strengthen with repetition
- Patterns inform candidate generation
- Patterns influence ranking weights

**Context-Action Learning**
- Decision Engine learns which actions work in which Contexts
- Context-Action success rates improve over time
- Context compatibility scoring becomes more accurate
- Context-specific Recommendations improve

**Resource Learning**
- Decision Engine learns actual Resource consumption patterns
- Resource estimates become more accurate
- Resource efficiency scoring improves
- Resource feasibility assessment improves

**Habit Learning**
- Decision Engine identifies Habit patterns from repeated Events
- Habit strength influences candidate generation
- Habit reinforcement/interruption Recommendations improve
- Habit-based scheduling becomes more effective

**Failure Learning**
- Decision Engine learns from failed or abandoned Events
- Failure patterns are avoided in future Recommendations
- Risk assessment becomes more accurate
- Confidence scoring becomes more reliable

### Stateless Engine, Evolving Knowledge

The Decision Engine itself remains stateless:

- **Decision Engine code**: Does not change between invocations
- **Decision Engine logic**: Remains consistent
- **Decision Engine process**: Pure function of inputs

But the Knowledge it reads evolves:

- **Knowledge data**: Updated through Events
- **Insight data**: Updated through Reflections
- **Habit data**: Updated through pattern detection
- **Pattern data**: Updated through historical analysis

This separation enables:

- **Safe improvement**: Knowledge can evolve without risking reasoning integrity
- **Reproducible reasoning**: Same inputs always produce same outputs
- **Continuous learning**: System improves without code changes
- **Auditability**: Reasoning can be debugged independently of data

### Learning Feedback Loop

```
Better Recommendations
  ↓
User accepts and executes
  ↓
Completed Event
  ↓
Reflection and Insight
  ↓
Knowledge update
  ↓
Pattern strengthening
  ↓
Even better Recommendations
```

This feedback loop continuously improves Decision Engine quality without modifying the reasoning engine itself.

---

## 12. Guarantees

The Decision Engine provides specific architectural guarantees.

### Core Guarantees

**Decision Engine never edits History**
- Completed Events are never modified
- Past Context Windows are never changed
- Reflections are never altered
- All History remains immutable

**Decision Engine owns no persistent data**
- Decision Engine maintains no internal state
- Decision Engine owns no database records
- Decision Engine owns no configuration
- Decision Engine is completely stateless

**Decision Engine cannot violate Principles**
- All Recommendations respect Principles
- All reasoning applies Principle constraints
- Principle violations are filtered before ranking
- Principles are hard constraints, not soft preferences

**Decision Engine never executes Events**
- Decision Engine does not start Events
- Decision Engine does not pause Events
- Decision Engine does not stop Events
- Execution is the user's domain

**Decision Engine schedules nothing**
- Decision Engine does not allocate time slots
- Decision Engine does not create Scheduled Events
- Decision Engine does not manage Event timing
- Scheduling is the Scheduler's exclusive responsibility

**Decision Engine never owns Scheduler**
- Decision Engine does not control Scheduler
- Decision Engine does not modify Scheduler state
- Decision Engine only provides inputs to Scheduler
- Scheduler maintains autonomy

**Decision Engine always produces deterministic outputs for identical runtime state**
- Same inputs always produce same outputs
- No randomness in reasoning process
- No hidden state influencing results
- Reproducible for debugging and auditing

### Consistency Guarantees

**Input consistency**
- Decision Engine reads from unified Runtime State snapshot
- All inputs represent same moment in time
- No partial or stale inputs
- All inputs validated before reasoning

**Reasoning consistency**
- Reasoning pipeline is fixed and ordered
- All stages execute in sequence
- No skipped stages
- All candidates pass through same process

**Output consistency**
- Output format is consistent
- All Recommendations include Explanation
- All outputs include Confidence
- All outputs are Principle-compliant

### Safety Guarantees

**Principle safety**
- Principles are applied before any other reasoning
- Principle violations are impossible in outputs
- Principles cannot be overridden by other factors
- Principle alignment is a hard filter, not a soft score

**Resource safety**
- Resource constraints are checked before ranking
- Resource-infeasible actions are filtered out
- Resource exhaustion triggers specific Recommendations
- Resources are never recommended below safety thresholds

**Context safety**
- Context incompatibility is filtered early
- Context-specific constraints are respected
- Context transitions trigger re-evaluation
- Context-appropriate actions are prioritized

**Priority safety**
- Priority order is respected in ranking
- Higher-priority items are not overridden by convenience
- Priority changes trigger re-evaluation
- Priority conflicts are resolved deterministically

---

## 13. Runtime Philosophy

The Decision Engine is the reasoning brain of PAIOS.

It does not command.

It advises.

It continuously transforms reality into better future decisions while respecting Principles, Context, Resources, and User autonomy.

### Philosophy Statement

PAIOS is not a command-and-control system. It is not an authority that dictates what the user must do.

PAIOS is a reasoning engine that observes reality, applies wisdom, and suggests better paths.

The Decision Engine embodies this philosophy:

- **It observes** — Reading Runtime State without judgment
- **It reasons** — Applying Principles and patterns without bias
- **It suggests** — Offering Recommendations without force
- **It explains** — Providing transparency without manipulation
- **It learns** — Improving through experience without losing integrity

### The Advisory Contract

The Decision Engine's contract with the user is:

**The Decision Engine promises:**
- To always reason from accurate reality
- To never violate Principles
- To never suggest Resource-infeasible actions
- To provide clear explanations
- To improve through learning
- To respect user autonomy

**The user retains:**
- The authority to accept or reject Recommendations
- The freedom to follow or ignore guidance
- The responsibility to provide Reflections
- The ownership of all personal data
- The final decision on every action

### Reasoning as Service

The Decision Engine provides reasoning as a service to the user:

- **Service, not control** — Reasoning is offered, not imposed
- **Guidance, not commands** — Recommendations point the way, they don't force the path
- **Wisdom, not rules** — Principles inform reasoning, they don't rigidly constrain it
- **Support, not substitution** — The Decision Engine augments human intelligence, it doesn't replace it

### Continuous Reasoning

The Decision Engine never stops reasoning:

- Every tick, it observes new reality
- Every tick, it applies current wisdom
- Every tick, it offers updated guidance
- Every tick, it learns from new experience

This continuous reasoning is what makes PAIOS a living operating system rather than a static tool. The Decision Engine breathes, thinks, and advises in an eternal loop of observation, reasoning, and learning.

### The Essence of Decision Engine

The Decision Engine is the bridge between what is and what could be better:

- **What is**: Current Runtime State — the reality of the moment
- **What could be better**: Future possibilities — paths not yet taken
- **The bridge**: Reasoning — the transformation of observation into guidance

The Decision Engine does not create the future. It illuminates possible futures and suggests the path that aligns with Principles, respects Resources, fits Context, and advances Goals.

The user walks the path. The Decision Engine lights the way.

This is the essence of PAIOS as a reasoning, advisory, learning Personal AI Operating System.
