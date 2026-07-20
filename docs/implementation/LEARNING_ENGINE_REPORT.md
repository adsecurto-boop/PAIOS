# Learning Engine Report — Milestone 8

The Learning & Knowledge Engine: observes completed History, extracts
patterns, produces reusable knowledge. It never reasons about the future,
never schedules, never transitions entities, never modifies historical
evidence, and never edits Principles or Habits — it proposes candidates;
the Application (future wiring) decides. Deterministic expert analysis:
identical history ⇒ identical output, generated identifiers included.

Status: complete, audited, **493 tests passing** (137 domain + 65
repository + 60 runtime + 54 scheduler + 33 decision engine + 52
application + 47 CLI + 45 learning). **No previous milestone was modified**
— Milestone 8 added only `backend/paios/learning/` and `tests/learning/`.

## 1. Architecture

```
                    LearningEngine.learn(History, as_of=None)
History (immutable) ──► extract ──► patterns ──► trends ──► reflections/
                                                            insights
                       ──► candidate principles ──► candidate habit changes
                       ──► LearningResult (reports + weekly/monthly summaries)

paios.learning ──► paios.domain (entities, enums, IDs — read + construct
       │                         Insight and candidate value objects)
       └─────────► paios.repositories.interfaces (HistoryLoader ONLY —
                   list() reads; never internals, never JSON)
ZERO dependency on runtime, scheduler, decision engine, application,
or infrastructure (grep-verified).
```

Three canon-preserving resolutions, decided openly in Phase 1:

1. **Principles never evolve** — outputs are `CandidatePrinciple` value
   objects, never domain Principle entities; existing Principles suppress
   duplicate candidates; only the User/Application may act.
2. **Domain Insights require a source Reflection** — Insight entities are
   generated exclusively from Reflections (deterministic uuid5 IDs,
   timestamps from the Reflection's own `created_at`); reflection-less
   pattern discoveries are learning-layer `Finding`s in the reports.
3. **No clock** — the analysis anchor is caller-supplied `as_of` or the
   newest timestamp in the evidence itself.

One reorganization from the suggested layout: no `lifecycle.py` — the
engine is stateless and pure, so there is no lifecycle to model;
`history.py` (the input view + interface loader) takes its place.

## 2. Folder Structure

```
backend/paios/learning/
├── __init__.py            exports
├── exceptions.py          LearningError → InvalidHistoryError
├── history.py             History (frozen input view) + HistoryProvider
│                          Protocol + HistoryLoader (interface reads only)
├── extractor.py           evidence normalization: status via the evidence
│                          trail (Archived still counts as what it was),
│                          data-derived AnalysisWindow, deterministic
│                          half-splits, category normalization
├── analyzer.py            Findings (repeated failure/success/distraction,
│                          reward misuse, frequent disturbance) + the seven
│                          mandated Trends
├── reflection_engine.py   Insight generation + reflection-quality metrics
├── habit_analyzer.py      CandidateHabitChange: Reinforce/Weaken/Create
├── principle_generator.py CandidatePrinciple from strong evidence
└── learning_engine.py     the pure pipeline + LearningResult, reports,
                           weekly/monthly PeriodSummaries
```

## 3. Required Outputs — where each lives

| Mandated output | Implementation |
|---|---|
| Insight generation | `reflection_engine`: one Insight per Reflection carrying a lesson; `reusable` iff root cause + lesson both present |
| Repeated failure / success detection | Outcome-evidence grouping per category, threshold 3 |
| Repeated distraction detection | Impact-classification grouping, threshold 3 |
| Reward-system misuse | Habit with declared reward whose matching Events skew Distraction |
| Schedule adherence trend | completed/(completed+skipped) ratio, half vs half |
| Study consistency trend | distinct study days, half vs half |
| Smoking / alcohol trends | category-count trends where **lower is better** |
| Finance discipline trend | net Money flow from Event Resource Flows |
| Deep work quality trend | average completed focus-session minutes |
| Reflection quality analysis | coverage trend + `ReflectionQuality` (total/complete/with-lesson) |
| Pattern extraction | `Finding` kinds with full evidence ID lists |
| Principle suggestions | Reduce Smoking/Alcohol (Health), Guard Spending (Resources), Prepare Before Studying (Learning) — suppressed when an existing Principle already names them |
| Habit reinforcement / weakening | impact-majority judgement over matching Events (threshold 3) |
| Habit creation | repeated untracked categories — the documented Domain Policy "Repeated Events infer Habits" made executable |
| Learning summaries / weekly / monthly | `LearningReport`, `TrendReport`, `PeriodSummary` (counts, Opportunity/Distraction minutes, deterministic top category) |

All thresholds, category vocabularies, and tolerances are Domain-Policy
constants — evolvable, documented, never Principles.

## 4. Determinism Guarantees

Sorted iteration everywhere; uuid5 content-hash Insight IDs; timestamps
only from evidence or `as_of`; fixed trend tolerances; whole-result deep
equality is pinned by test (`learn(h) == learn(h)`, including IDs), and
replay consistency is proven over history reloaded twice from real
persisted storage through `HistoryLoader`.

## 5. Tests — 45 new

- `test_extractor_and_patterns.py` (15) — data-derived windows, `as_of`
  override, evidence-trail status buckets (Archived counted), empty
  history, category normalization, invalid input, deterministic half
  split; every Finding kind incl. below-threshold silence.
- `test_trends.py` (11) — all seven trends, both directions where
  meaningful (smoking improving *and* declining), income vs spending,
  insufficiency on missing data.
- `test_insights_and_candidates.py` (13) — Insight-per-lesson, uuid5
  determinism, category from source Event, reusable rules, timestamps
  from Reflections; all three Principle candidates + suppression by an
  existing Principle; Create/Reinforce/Weaken habit proposals + misuse
  rationale + no double-Create for tracked categories.
- `test_engine.py` (11) — full-result determinism, statelessness,
  **zero mutation** (transition counts, statuses, habit strengths
  verified unchanged), empty-history quiet result, `as_of` control,
  weekly/monthly window filtering with Opportunity/Distraction minutes and
  deterministic top category, **replay consistency over persisted
  storage**, 200-event scale.

## 6. Audit

| Check | Result |
|---|---|
| No business-logic leakage / no scheduling / no decision making | the layer only observes and proposes; no transitions, no plans, no rankings of future actions |
| No runtime / entity / history mutation | zero calls to any transition, admission, or evidence-recording API; purity pinned by test |
| No repository knowledge | persistence touched only via `repositories.interfaces` `list()` reads in `HistoryLoader`; no JSON, no files |
| No clock / `datetime.now()` | zero; the codebase total remains the one sanctioned Clock site |
| No randomness / AI / ML | uuid5 content hashes only; fixed constants; grep clean |
| No hidden Task concepts | grep clean |
| Dependency direction | learning → domain + repositories.interfaces only; nothing imports learning |
| Frozen milestones untouched | committed baselines clean; prior 448 tests pass unchanged |

## 7. Intentional Deferrals

| Deferred | Reason |
|---|---|
| Application wiring (persist Insights, apply accepted candidates, CLI `learn`/`reflect` capture commands) | Composition work — the same pattern as the Decision Engine awaiting Milestone 6; the Application decides, per the mission |
| Knowledge-entity updates (revision/retention from Events) | Requires an Application use case mutating Knowledge aggregates — orchestration, not observation |
| Policy evolution (learning adjusting its own thresholds) | Domain Policies evolve in a later milestone; constants are the visible hooks |
| Text understanding of Reflections/lessons | Excluded by the NO-AI mandate; lessons flow through as evidence |
| Goal emergence suggestions | Needs the Goal-acceptance flow at Application level first |

## 8. Suggested Git Commit

```
Milestone 8: Learning Engine - deterministic pattern extraction from History

- Pure LearningEngine.learn(History) -> LearningResult; History view +
  interface-only HistoryLoader
- Findings (failures/successes/distractions/reward misuse/disturbances)
  and the seven mandated trends via deterministic half-window comparison
- Insights generated solely from Reflections (uuid5 IDs, data-derived
  timestamps); CandidatePrinciples and CandidateHabitChanges as proposals
  only - Principles and Habits are never edited
- Learning/Trend reports + weekly/monthly summaries, all clock-free
- 45 new tests incl. whole-result determinism, zero-mutation proof, and
  replay consistency over persisted storage; 493 total passing

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

Milestone 8 deliverables complete. No Dashboard, API, GUI, Mobile,
AI Assistant, or Timer Engine work will begin without explicit approval.
