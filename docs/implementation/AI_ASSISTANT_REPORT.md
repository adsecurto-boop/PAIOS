# Milestone 17 — AI Assistant Layer

## Mission

A reasoning, explanation, summarization, planning and language layer.
Like the GUI: the GUI visualizes, the assistant explains. It makes no
decisions — the Decision Engine remains the only authority.

## 1. Architecture analysis (Phase 1 outcome)

All canonical documents, ADRs, and implementation reports (M1–M16) were
verified. **No frozen-layer modification is required** — the milestone
proceeded automatically. The decisive boundary finding: the mission
requires the assistant to receive `RuntimeSnapshot` / `LearningResult`
instances *and* forbids runtime/learning imports — resolved the way
every PAIOS presentation surface already does it: the assistant
**duck-types** everything it receives (attribute reads only, the
CLI/TUI/API serialization convention) and **imports nothing from
`paios` outside its own package**. Stricter than asked, trivially
auditable.

```
immutable snapshots + collections (received, never fetched)
        │
context_builder  ── deterministic canonical text (sorted, clock-free)
        │
prompts          ── 7 fixed templates, strict JSON response contract
        │
orchestrator     ── AssistantRequest (frozen DTO)
        │
adapters         ── anthropic | openai | null   (translation only)
        │
response_parser  ── validation only -> ParsedResponse (frozen)
        │
AssistantResult  ── frozen DTO; the Application decides what to do
```

Package: `backend/paios/assistant/` exactly per the mission layout
(`prompts.py`, `context_builder.py`, `response_parser.py`, `tools.py`,
`orchestrator.py`, `adapters/{anthropic,openai,null}.py`).

## 2. Inputs and the no-authority rule

The assistant receives only immutable snapshots and plain collections:
RuntimeSnapshot, LearningResult, recommendations, contexts, goals,
projects, resources, habits, insights, principles, knowledge,
reflections (dashboard-shaped data is passed as those collections). It
never receives repositories or live aggregates to act on — and could
not act anyway: it holds exactly one collaborator (the adapter,
asserted by test), owns no clock, no files, no bus, no facade.

Every prompt's system rules state the authority boundary explicitly:
the assistant explains and summarizes, never claims an action was or
will be taken, and never instructs the user to bypass the Decision
Engine. The recommendation templates add "Do not accept, reject, or
rank"; ordering suggestions add "nothing is scheduled".

## 3. Operations (all 14, each returning a frozen `AssistantResult`)

| Operation | Template | Notes |
| --- | --- | --- |
| explain_recommendation | recommendation_explanation | what it means |
| why_recommendation | recommendation_explanation | why it exists (principles/habits/snapshot as context) |
| explain_principle / explain_habit | explain | |
| summarize_today | summarize | snapshot + events/goals/projects/resources |
| summarize_week | weekly_review | events, reflections, LearningResult |
| compare_snapshots | explain | **pure diff first** (see below), then narrative |
| explain_trends | learning_explanation | LearningResult trends/insights |
| explain_deep_work | reflect | |
| suggest_study_order | learning_explanation | knowledge items |
| suggest_project_order | project_explanation | |
| markdown_summary / generate_report | summarize | answer carries Markdown |
| answer_question | explain | free question over provided data |

`compare_snapshots` computes a deterministic `SnapshotComparison` DTO
(times, execution-context change, running-event change, per-collection
count deltas) in pure code — counting is presentation, not decision —
and returns it on the result alongside the narrative.

## 4. Context builder — determinism

Identical snapshot → identical prompt, guaranteed by construction: all
collections sorted by a stable key before rendering; enums render as
values, datetimes as ISO-8601; no clock, randomness, or environment
access (a test freezes `datetime` and asserts identical output);
unknown collection names raise instead of silently dropping context.
Templates render by strict named substitution — missing or unexpected
fields are errors, and kwarg order cannot matter.

## 5. Prompt templates

Seven fixed templates (the mission's list): explain, summarize,
reflect, weekly_review, recommendation_explanation,
project_explanation, learning_explanation. All share one system-rule
block embedding the authority boundary and the response contract:

```json
{"answer": "...", "bullets": ["..."], "confidence": 0.0-1.0}
```

## 6. Adapters — translation only

`LlmAdapter` ABC: `name` + `complete(AssistantRequest) -> raw text`.

- **Anthropic** — `claude-opus-4-8` with adaptive thinking (current
  API guidance); lazy SDK import (`AdapterUnavailableError` without
  it); injectable client (tests verify the exact wire translation);
  refusal stop-reason, empty content, and SDK exceptions all become
  `AdapterError`.
- **OpenAI** — chat-completions translation, same lazy/injectable
  pattern.
- **Null** — deterministic, contract-conforming canned JSON derived
  purely from the request; the whole pipeline runs offline with zero
  dependencies (and it is what most tests drive end to end).

The backend's zero-dependency property is preserved: SDKs are optional
and confined to their adapter modules.

## 7. Response parser — validation only

Strict JSON (one tolerance: a ```json fence). Rejects with precise
`ResponseParseError`s: empty text, malformed JSON, non-object payloads,
missing/empty/typed-wrong `answer`, non-string-list `bullets`,
non-numeric or out-of-range `confidence`. Never repairs or reinterprets.

## 8. Tests (61 new; full suite 855 passed, 1 skipped)

- **Prompt determinism** — registry completeness, contract embedding,
  render determinism, missing/unexpected fields.
- **Context determinism** — identical inputs → identical text; input
  order canonicalized; frozen-clock proof; every mission input renders;
  unknown-collection error.
- **Parser validation** — 15 malformed/missing-field cases plus the
  happy paths and immutability.
- **Adapter contracts** — ABC enforcement; Null determinism +
  parseability; Anthropic translation (model, system, adaptive
  thinking, message shape), refusal / empty / SDK-error mapping,
  unavailable-without-SDK; OpenAI translation and error mapping.
- **Orchestrator** — every operation; result immutability; prompt
  determinism across orchestrators; **inputs never mutated** (vars
  snapshot before/after); single-collaborator proof; malformed-reply
  propagation; Null end-to-end.
- **Real snapshots** — a genuine started Application (seeded store):
  `application.snapshot()` before/after a tick through summarize and
  compare (recommendation delta detected), and a real Decision-Engine
  recommendation through why_recommendation — proving the duck-typed
  reading matches the real objects.
- **Boundaries** — AST proof of the whole dependency graph (below).

## 9. Audit (Phase 4) — dependency graph

Enforced by `tests/assistant/test_boundaries.py`, not just by review:

| Rule | Result |
| --- | --- |
| Only Application DTOs / snapshots (received), stdlib, optional SDKs | PASS — the package imports **zero** `paios.*` modules outside `paios.assistant`; snapshots arrive as arguments and are duck-typed. |
| No repository / scheduler / runtime / decision-engine / daemon / learning imports | PASS — impossible by the rule above; AST-asserted per module. |
| SDKs confined | PASS — `anthropic` only in `adapters/anthropic.py`, `openai` only in `adapters/openai.py`, both lazy. |
| No persistence, no files | PASS — no `open()`, no pathlib/pickle/sqlite/socket/urllib/subprocess (AST-asserted). |
| No mutation | PASS — frozen DTOs throughout (asserted), inputs verified unchanged, orchestrator holds only the adapter. |
| Never accepts/rejects/creates/modifies/triggers | PASS — no such code paths exist; prompts additionally forbid claiming actions. |
| Frozen layers untouched | PASS — M17's diff is `backend/paios/assistant/` + `tests/assistant/` only. |

## 10. Future roadmap (not started, per stop conditions)

- Surface the assistant through a composition root (CLI `ask` command
  or REST endpoint) — the Application-decides seam is ready.
- Streaming responses for long reports.
- Prompt caching for the fixed system blocks once traffic exists.
- Vector search / semantic memory / plugins / MCP / autonomous or
  multi-agent behaviour — all explicitly out of scope and untouched.

## 11. Suggested commit message

```
Milestone 17: AI Assistant - explanation layer over immutable snapshots

- paios.assistant: deterministic context builder (sorted, clock-free),
  7 prompt templates with a strict JSON response contract, validating
  response parser, orchestrator returning frozen AssistantResult DTOs
- 14 read-only operations (explain/summarize/compare/trends/orders/
  markdown/report/questions); compare_snapshots computes a pure
  SnapshotComparison diff DTO
- Adapters: Anthropic (claude-opus-4-8, adaptive thinking), OpenAI,
  Null (deterministic offline) - translation only, lazy SDK imports,
  injectable clients
- Boundary: the package imports nothing from paios outside itself;
  snapshots are received and duck-typed; no persistence, no mutation,
  no decisions - Decision Engine remains the only authority
- Tests: 61 new incl. AST dependency-graph proof and real-snapshot
  integration; full suite 855 green + 1 guard skip
```

## Stop condition

Milestone 17 ends here. No vector search, semantic memory, plugins,
MCP, autonomous agents, or multi-agent systems. Awaiting review.
