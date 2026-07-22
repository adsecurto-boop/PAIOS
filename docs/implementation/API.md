# API

The PAIOS REST surface: a thin, zero-decision transport over the
Application facade (`backend/paios/api/`). JSON in, JSON out; loopback
only (`127.0.0.1:8765` by default); single-threaded by design. Full
implementation notes: `REST_API_REPORT.md` (M12) and the M20 additions
below.

## Endpoints (M12–M19 baseline)

| Method | Path | Purpose |
|---|---|---|
| GET | `/status`, `/snapshot`, `/dashboard` | System state / TUI-parity dashboard |
| POST | `/tick` | One runtime loop pass (M20: response adds `recurrences_expanded`) |
| GET | `/recommendations` · POST `/recommendations/{id}/accept\|reject` | Decision Engine output + user verdicts |
| GET | `/events`, `/events/{id}` | Event listings |
| POST | `/events/{id}/start\|pause\|resume\|complete\|cancel\|archive` | Lifecycle transitions (Scheduler-mediated) |
| GET/POST | `/goals`, `/projects`, `/resources`, `/knowledge`, `/reflections`, `/disturbers`, `/contexts` | Aggregate reads + creations, goal/project/resource actions |

## Milestone 20 additions (approved 2026-07-22)

User-authored events ride the Recommendation → Scheduler pipeline: the
API never schedules; it proposes, the Scheduler materializes.

| Method | Path | Purpose |
|---|---|---|
| POST | `/events` | Create: `{title, mode?: planned\|now, suggested_time?, priority?, project_id?, expected_outcome?, metadata?}` → `{recommendation, event_id, materialized}` (mode `now` → serialized event) |
| PUT | `/events/{id}` | Edit = cancel + re-propose (returns a NEW `event_id`) |
| POST | `/events/{id}/duplicate` | Duplicate (copies sidecar metadata) |
| GET/PUT | `/events/{id}/metadata` | Sidecar: `tags[]`, `deadline`, `energy(low\|medium\|high)`, `estimated_duration_minutes`, `depends_on[]` |
| GET | `/plan` | The Scheduler's SchedulingPlan (timeline data source) |
| GET/POST | `/templates` · DELETE `/templates/{id}` · POST `/templates/{id}/instantiate` | Event templates |
| GET/POST | `/recurrences` · DELETE `/recurrences/{id}` | Recurrence rules (`title`, `time_of_day HH:MM`, `days[mon..sun]`, `first_run?`); due rules expand on `/tick` |
| GET/POST | `/inbox` · POST `/inbox/{id}/convert\|archive` · DELETE `/inbox/{id}` | Quick capture; convert `to: goal\|project\|event` |
| GET | `/assistant/status` | Provider + availability (`fallback: heuristic`) + human-readable `reason` (why the provider is or isn't available). Configure via `PAIOS_AI_PROVIDER=openai\|anthropic` / `PAIOS_AI_MODEL` env vars or `--ai-provider` / `--ai-model` flags, plus the SDK's own API key env var (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) |
| POST | `/assistant/plan` | Text → Planning Proposal `{source, answer, items[], questions[], confidence}` — proposal ONLY, no side effects |
| POST | `/assistant/explain-day` | Per-plan-entry WHY grounded in recorded facts |
| GET/POST | `/backups` · POST `/backups/restore` | Backup archives (restore applies at next start) |

Deliberate non-endpoints: hard event deletion (the Domain keeps
evidence; Archive is the removal UX) and drag-and-drop rescheduling
(the Scheduler is the sole scheduling authority and rebuilds the plan
each cycle).

## Errors

`{"error": {"type", "message"}}` with: 400 validation, 404 unknown
entity/route, 405 wrong method, 409 conflict/invalid transition,
413 oversized body, 503 not started / service not composed, 500
otherwise. M20: `PlanningStoreError` → 404 ("Unknown …") or 400;
`BackupError` → 400.
