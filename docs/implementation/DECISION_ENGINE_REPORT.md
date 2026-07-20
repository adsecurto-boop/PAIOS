# Decision Engine Report — Milestone 5

The reasoning brain of PAIOS (DECISION_ENGINE.md): stateless, pure,
deterministic, explainable, side-effect free. It consumes ONLY a
RuntimeSnapshot and produces ONLY Recommendation entities with full
reasoning trails. Deterministic expert-system reasoning — no LLMs, no
embeddings, no ML, no probability models, no randomness.

Status: complete, audited, **349 tests passing** (137 domain + 65
repository + 60 runtime + 54 scheduler + 33 decision engine). All frozen
milestones (1–4, ADR-001/002/003) untouched — Milestone 5 added only
`backend/paios/decision_engine/` and its tests.

## 1. Architecture

**The engine only reasons.** It never mutates domain entities, never calls
repositories, never schedules, never transitions Event states, never
activates Context Windows, never modifies Runtime State, never reads a
clock. Its entire contract is one pure function:

```
DecisionEngine.evaluate(snapshot: RuntimeSnapshot) -> DecisionResult
```

**Input sufficiency.** The RuntimeSnapshot carries everything §2 of
DECISION_ENGINE.md requires except two items absent by prior owner
rulings, not omission: Scheduler State (G7 — plan-conflict avoidance
remains the Scheduler's defer mechanism) and Domain Policies / User
Preferences (C1 — not domain entities). One apparent gap resolved without
touching the frozen snapshot: `user_id` for produced Recommendations is
derived from each candidate's source aggregates (every rule fires from
aggregates carrying `user_id`; an empty snapshot yields No Action and
needs none). **No snapshot modification was needed.**

**Output.** Recommendation entities in their initial `Generated` state —
presentation (`Generated → Pending`) belongs to the Runtime actor
(STATE_MACHINES.md §6), and consumption belongs to the Scheduler.
Creating a new entity is the engine's documented output, not a mutation.

**Determinism.** Identical snapshots produce identical results including
Recommendation IDs: IDs are uuid5 content hashes over (rule, subject,
snapshot time); `created_at`/`expires_at` derive from the snapshot's
Current Time; all iteration is sorted; ranking has stable tiebreaks;
weights and thresholds are fixed Domain-Policy constants.

## 2. Dependency Graph

```
paios.decision_engine ──► paios.domain          (entities, enums, IDs — read +
        │                                        construct new Recommendations)
        └───────────────► paios.runtime.runtime_snapshot   (the input TYPE only)

        ✗ zero: kernel, event bus, repositories, json, pathlib, clock,
                uuid4/random, Task/Todo
Nothing depends on the engine yet — wiring is composition work (deferred).
```

## 3. Folder Explanation

```
backend/paios/decision_engine/
├── __init__.py               Public exports
├── exceptions.py             DecisionEngineError → InvalidSnapshotError
├── rules.py                  Candidate (frozen, fact-traceable) + Rule ABC +
│                             7 deterministic expert rules + default_rules()
├── evaluator.py              §3 lightweight snapshot validation + §5 filters
│                             in documented order, rejections recorded
├── scoring.py                §6 fixed-weight decomposed Scores + ranking
├── confidence.py             §7 factor-based Confidence + High/Medium/Low
├── explanation.py            Explanation (why / facts / principles /
│                             confidence / expected impact / score parts)
├── recommendation_builder.py Deterministic entity construction (uuid5 IDs,
│                             snapshot-time validity window)
└── engine.py                 DecisionEngine pipeline + DecisionResult
                              (+ ReasonedRecommendation, No-Action signal)
```

## 4. Reasoning Pipeline (DECISION_ENGINE.md §3)

```
RuntimeSnapshot
  ↓ validate            reasoning-specific checks: at most one running user
  │                     Event; an Execution Context exists (the Kernel owns
  │                     comprehensive validation)
  ↓ generate            each rule reads the snapshot, emits Candidates —
  │                     every Candidate carries its facts, its aligned
  │                     Principles (actual Principle names from the
  │                     snapshot), and its planning attributes
  ↓ filter (§5 order)   1. Principle violations (non-negotiable)
  │                     2. Resource infeasibility (Energy requirement vs
  │                        tracked Energy; untracked ⇒ passes but lowers
  │                        confidence instead)
  │                     3. Redundancy (an unexpired Pending Recommendation
  │                        with the same reason)
  │                     — every rejection recorded with its reason
  ↓ rank (§6)           decomposed scores, fixed weights, stable tiebreaks
  ↓ confidence (§7)     factor-based appropriateness certainty
  ↓ build               Recommendation + Explanation per surviving candidate
  ↓
DecisionResult: recommendations (≤ 5), rejected, priority evaluation,
                or a valid No-Action signal with its reason (§8)
```

### The rule catalog (each mapped to the §4 candidate types)

| Rule | Fires when | §4 grounding |
|---|---|---|
| continue-running-event | a user Event is running | Continue Current Event |
| resume-suspended-event | Paused/Interrupted Events exist | Resume Event |
| rest-on-low-energy | Energy < 30 | Recommend Rest / From Resources |
| reflect-on-completed | Completed Events lack Reflections | Recommend Reflection |
| close-knowledge-gap | Knowledge confidence < 50 | Recommend Learning / From Knowledge |
| focus-on-project | least-complete Active Project | Recommend Focus Session / From Projects & Goals |
| reinforce-habit | Habit strength ≥ 40 | From Habits |

Thresholds, priorities, weights, the ≤5 cap, and the 60-minute validity
window are Domain-Policy constants — evolvable runtime rules, documented
in code, never Principles.

## 5. Recommendation Pipeline

Candidate + Score + Confidence → `build_recommendation`: deterministic
uuid5 ID; `user_id` from the candidate's source aggregate; `reason` =
the human-readable why; `priority` = the decomposed score total;
`confidence_score` = the confidence value; `created_at` = snapshot Current
Time; `expires_at` = +60 minutes ("Recommendations expire" —
BUSINESS_RULES.md); optional related Project and suggested timing. The
entity is born `Generated`; the Runtime presents, the user decides, the
Scheduler consumes — all later, all outside the engine.

## 6. Explanation System

No black-box recommendations: every `ReasonedRecommendation` pairs the
entity with an `Explanation` — **why** (the reasoning sentence), **which
facts were used** (the observed snapshot facts, verbatim), **which
Principles influenced it** (actual Principle names from the snapshot,
matched by category — e.g. rest cites "Protect Health"), **confidence**
(value + level), **expected impact**, and the full **score decomposition**.
Rejected candidates are reported with their §5 rejection reasons — filtering
is part of the explanation, never a silent disappearance.

## 7. Confidence System (§7 — certainty, not probability)

Deterministic factors, all named in the result: base 0.5; +0.2 strong
fact pattern (≥2 facts); +0.15 Principle alignment; +0.15 historical
support (completed same-category Events); −0.2 when a required Resource is
untracked. Clamped to [0, 1]; levels High ≥ 0.75, Medium ≥ 0.45, else Low.

## 8. Testing — 33 new tests

- `test_rules.py` (8) — each rule fires on its documented facts and
  abstains otherwise; sorted determinism; the fixed default rule order.
- `test_filtering_scoring_confidence.py` (11) — the three filters with
  recorded reasons (violation first, infeasibility, redundancy;
  untracked-Energy passes); named score components and totals; historical
  Impact moving scores both directions; stable ranking tiebreaks;
  confidence factor accumulation, penalty, and level thresholds.
- `test_engine.py` (14) — empty snapshot → valid No-Action; two running
  Events → InvalidSnapshotError; non-snapshot input rejected; full
  snapshot → capped, descending-ranked, Generated-state recommendations
  with correct times/priority/confidence; full explanations incl. real
  Principle names; priority evaluation; **identical inputs → identical
  recommendations (IDs included)** across engines and repeated calls;
  time-dependent ID determinism; **purity** (no snapshot mutation, no
  state between calls); conflicting tied candidates ranked
  deterministically; rejections reported, never silent.

## 9. Audit

| Check | Result |
|---|---|
| No repository access | grep: zero — imports are domain + own modules + the RuntimeSnapshot type |
| No runtime mutation | never touches kernel/bus/state; consumes the frozen snapshot |
| No scheduler logic | no slotting, no transitions, no plan; the Scheduler consumes later |
| No domain mutation | zero calls to any transition/present/accept/consume/record method |
| No `datetime.now()` | zero in the package; codebase total remains the one sanctioned Clock site |
| No hidden persistence | no json/pathlib/open |
| Deterministic | uuid5 IDs, sorted iteration, fixed weights, stable tiebreaks — pinned by tests |
| Pure functions | stateless engine (immutable rule tuple only); purity pinned by tests |
| Explainable | every output carries why/facts/principles/confidence/impact/score parts |
| Frozen milestones untouched | only `decision_engine/` + its tests added |

## 10. Intentional Deferrals

| Deferred | Reason |
|---|---|
| Wiring into the runtime loop (invoke on SnapshotUpdated, publish RecommendationGenerated, persist via PersistenceSync, present Generated → Pending) | Composition-layer work (Milestone 6) — keeps the engine side-effect free as mandated |
| Plan-conflict / time-window filtering | Scheduler State excluded from snapshots by ruling G7; the Scheduler's defer mechanism handles infeasibility |
| Context-compatibility filtering | No domain field models a per-candidate Context requirement; Recommendations carry no Context reference (gap already recorded in SCHEDULER_REPORT.md) |
| Policy evolution (thresholds/weights learning from rejections etc.) | Domain Policies evolve in later milestones; constants are the visible hooks |
| Insight/Reflection-content reasoning beyond counts | Requires text understanding — excluded by the NO-AI mandate; Insights remain snapshot inputs for future deterministic rules |

## 11. Suggested Git Commit

```
Milestone 5: Decision Engine - pure deterministic reasoning over snapshots

- DecisionEngine.evaluate(RuntimeSnapshot) -> DecisionResult: stateless,
  pure, side-effect free, fully explainable
- 7 deterministic expert rules from the documented candidate catalog;
  Domain-Policy constants for thresholds/weights/validity
- Documented filter order with recorded rejections; decomposed scores;
  factor-based confidence; No-Action as a valid outcome
- Recommendations born Generated with uuid5 content-hash IDs and
  snapshot-time validity — identical snapshots yield identical outputs
- Explanation per recommendation: why, facts, Principles, confidence,
  expected impact, score decomposition
- 33 new tests; 349 total passing; frozen milestones untouched

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

Milestone 5 deliverables complete. Milestone 6 will not begin without
explicit approval.
