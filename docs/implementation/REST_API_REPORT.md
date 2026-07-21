# Milestone 12 — REST API (Application Service Layer)

## Mission

Expose the existing Application facade as a REST API. The API is a
transport layer only: it maps HTTP to facade calls, validates request
syntax, serializes responses, and translates exceptions into HTTP status
codes. It contains no business logic and never bypasses the Application.

## 1. Architecture

### Framework choice: stdlib `http.server` (justified)

The mission asks for the smallest framework that fits the architecture.
The smallest framework is **no framework**:

- PAIOS has **zero runtime dependencies** today (stdlib only, a property
  M11 explicitly preserved for the TUI). Flask/FastAPI would introduce
  the project's first runtime dependency — plus an install step — to do
  what ~200 lines of fully-tested stdlib code do here: match routes,
  parse JSON, write status codes. Neither is even installed in the
  environment.
- The transport's entire responsibility list (map, validate syntax,
  serialize, translate errors) needs no middleware, no DI container, no
  async runtime, no template engine.
- Testability is better than framework-typical: routing lives in a pure
  `ApiRouter.handle(method, path, body) -> (status, payload)` core that
  tests call directly, no sockets or test clients required.

**Single-threaded by design**: `HTTPServer`, not `ThreadingHTTPServer`.
The JSON store and the runtime kernel are not synchronized for concurrent
mutation, so serializing requests at the transport is a correctness
decision, not a simplification (documented for the day a concurrent
server is wanted).

### Package: `backend/paios/api/` (the suggested layout)

| Module | Responsibility |
| --- | --- |
| `config.py` | `ApiConfig` (host, port — 0 = ephemeral for tests, data_dir). |
| `errors.py` | `ApiError` (transport errors) + `translate(exc)`: exception type → HTTP status + JSON error payload. |
| `schemas.py` | Request-syntax validation: JSON object shape, required/optional string/number/bool fields, enum-by-value parsing. Syntax only — semantics stay in the domain. |
| `serialization.py` | Duck-typed entity → JSON-safe dicts (ids as strings, enums as values, datetimes ISO-8601); the `/dashboard` payload builder. |
| `routes.py` | The route table and `ApiRouter`: one facade delegation per endpoint. |
| `server.py` | The wire: `BaseHTTPRequestHandler` (bytes/JSON only) + `ApiServer` (owns socket + Application lifecycle) + `serve()` with graceful Ctrl+C. |
| `__main__.py` | `python -m paios.api [port] [--host H] [--data-dir D]`. |

Entry points: **`paios serve [port]`** (CLI one-shot, reuses `--data-dir`)
and **`python -m paios.api`**. Both print the listening URL, serve until
Ctrl+C, then close the socket and stop the Application (`PAIOS API
stopped.`). A stdlib `HTTPServer.shutdown()` pitfall (it deadlocks unless
`serve_forever` is running) is guarded in `ApiServer.shutdown()`.

## 2. Dependency graph

```
HTTP client
    │
server.py  (bytes ⇄ JSON; no routing decisions)
    │
routes.py  (route table; one facade call per endpoint)
    │            ├─ schemas.py        (request syntax)
    │            ├─ serialization.py  (response shape)
    │            └─ errors.py         (exception → status)
    ▼
Application facade
    ▼
domain operations / runtime / scheduler / decision engine / learning / repositories
```

Imports (AST-test-enforced): stdlib (`http.server`, `json`, …),
`paios.application`, `paios.api.*`, plus the established M8/M10
presentation convention for request **parsing** and error **typing**:
`paios.domain.value_objects.identifiers`, `paios.domain.enums`,
`paios.domain.errors`, `paios.repositories.errors` (exception modules —
no repository implementation, no domain entity, no state machine).
Runtime/Scheduler/Decision-Engine/Learning/Kernel/Dashboard/CLI: never
imported. Runtime exceptions (e.g. `RuntimeInvariantError`) are therefore
untypeable here and intentionally fall to the generic 500 handler.

The Application facade needed **zero additions** — M10's entity
operations and M11's `current_time` / `scheduler_state` / `list_events`
queries already cover every endpoint.

## 3. Endpoint table (32 routes)

| Method & path | Facade call | Success |
| --- | --- | --- |
| GET /status | `status()` | 200 |
| GET /snapshot | `snapshot()` | 200 (404 if none) |
| POST /tick | `tick()` | 200 |
| GET /recommendations | `active_recommendations()` | 200 |
| POST /recommendations/{id}/accept | `accept_recommendation(id)` | 200 |
| POST /recommendations/{id}/reject | `reject_recommendation(id, reason?)` | 200 |
| GET /events | `list_events()` | 200 |
| GET /events/{id} | `list_events()` lookup | 200 / 404 |
| POST /events/{id}/start | `start_event(id)` | 200 |
| POST /events/{id}/pause | `pause_event(id)` | 200 |
| POST /events/{id}/resume | `resume_event(id)` | 200 |
| POST /events/{id}/complete | `complete_event(id, actual_outcome?)` | 200 |
| POST /events/{id}/cancel | `cancel_event(id, reason?)` | 200 |
| GET /goals | `list_goals()` | 200 |
| POST /goals | `add_goal(owner, name, description?)` | 201 |
| POST /goals/{id}/complete • /pause • /resume | `complete_goal` / `pause_goal` / `resume_goal` | 200 |
| GET /projects | `list_projects()` + `get_project_progress()` | 200 |
| POST /projects | `add_project(owner, name, description?)` | 201 |
| POST /projects/{id}/progress | `update_project_progress(id, completion_percentage)` | 200 |
| GET /resources | `list_resources()` | 200 |
| POST /resources | `add_resource(owner, type, current_value, unit, negative_allowed?)` | 201 |
| POST /resources/{id}/consume • /produce | `consume_resource` / `produce_resource` (amount) | 200 |
| GET /knowledge | `list_knowledge()` | 200 |
| POST /knowledge | `add_knowledge(owner, domain, topic, concept, …)` | 201 |
| GET /reflections | `list_reflections()` | 200 |
| POST /reflections | `add_reflection(event_id, …)` | 201 |
| GET /contexts | `list_contexts()` | 200 |
| GET /dashboard | the TUI's 15 facade queries | 200 |

`owner` resolution mirrors the CLI: explicit `user_id` in the body, else
the first stored User, else `user_001`. POST bodies are JSON objects;
optional-field endpoints accept an empty/absent body.

**GET /dashboard** returns exactly the TUI dashboard's information as
structured JSON — same sections (`current_time`, `current_event` with
elapsed/remaining from lifecycle-evidence timing, `current_context`,
`active_disturbers`, `recommendations`, `goals`, `projects` (+progress),
`today` {completed/running/upcoming}, `health` {resources/habits},
`learning` {latest insight/reflection, last studied, revised today},
`system` {scheduler/decision engine/kernel/snapshot/daemon}) built by the
same grouping rules. `system.daemon` is `null`: the daemon wraps the
Application and is unreachable through the facade (same M11 finding).

## 4. Serialization

- Identifiers → strings; enums → their `.value`; datetimes → ISO-8601;
  tuples → lists. All duck-typed over facade outputs (the CLI/TUI
  formatter convention) — no entity imports.
- Events serialize with their full transition history (state, moment,
  actor) — History is the system's spine and clients get it verbatim.
- Every response body is a JSON object; every endpoint's payload is
  round-trippable through `json.dumps` (asserted in tests).
- Errors: `{"error": {"type": "<ExceptionClassName>", "message": "…"}}`.

## 5. Error handling

| Exception | Status |
| --- | --- |
| `ApiError` (unknown route) | 404 |
| `ApiError` (method mismatch on a real route) | 405 |
| `ApiError` (bad JSON, bad field, bad enum) | 400 |
| `DomainValidationError` (and `DomainError` fallback) | 400 |
| `EntityNotFound` | 404 |
| `DuplicateEntityError`, `ProgressNotAttachedError` | 409 |
| `InvalidTransitionError` (incl. `RecommendationExpiredError`), `ImmutabilityViolationError`, `InvariantViolationError` | 409 |
| `ApplicationNotStartedError` | 503 |
| `RepositoryError`, `ApplicationError` (fallbacks) | 500 |
| `RuntimeInvariantError` / anything unimportable or unexpected | 500 (name preserved in the payload) |

The router's `handle()` is exception-tight: nothing propagates to the
socket layer; every failure becomes a JSON error response.

## 6. Tests

`tests/api/` — 37 tests, full suite **671 passed** (634 + 37):

- **Endpoints** — every required route through the pure router over a
  real started application: system, the recommendation accept/reject
  flow, the full event lifecycle (start/pause/resume/complete with
  outcome, cancel), goal creation + lifecycle, project + progress,
  resource consume/produce, knowledge, reflections on completed events,
  contexts, and dashboard TUI-parity (keys, idle honesty, running-event
  reflection).
- **Serialization** — every success payload asserted JSON-serializable;
  ISO times, enum values, id strings checked in place.
- **Error mapping** — 404 route, 405 method, 400 syntax (missing field,
  wrong type, non-object body, bad enum, invalid JSON bytes over HTTP),
  404 unknown entity, 409 duplicate, 400 domain validation, 409
  invariant violation, 409 invalid transition, 503 not-started.
- **Live server** — real `HTTPServer` on an ephemeral port, stdlib
  `urllib` client: GET/POST round-trips, HTTP error statuses, graceful
  shutdown; injected applications are left running on shutdown (the
  caller owns them), owned ones are stopped.
- **Delegation** — the router holds exactly one collaborator (the
  Application); action routes hit exactly one facade method (recording
  fake).
- **Forbidden imports** — AST scan of the package against the forbidden
  prefix list; allowed list is exactly facade + parsing/error types.
- Plus a manual end-to-end smoke: `python -m paios.api` + `curl`
  (status 200, goal 201, unknown 404).

## 7. Audit

| Check | Result |
| --- | --- |
| No business logic | PASS — handlers parse, delegate once, serialize; owner resolution and event lookup are input handling (CLI convention). |
| No Runtime imports | PASS — AST-enforced. |
| No Scheduler imports | PASS — AST-enforced. |
| No Decision Engine imports | PASS — AST-enforced. |
| No Learning imports | PASS — AST-enforced. |
| No Repository implementation imports | PASS — only `repositories.errors` (exception types) is referenced. |
| Application-only delegation | PASS — every route calls facade methods only; recording-fake and single-collaborator tests prove it. |
| Frozen layers | PASS — domain, runtime, scheduler, decision_engine, learning, repositories, infrastructure, daemon, dashboard, **and application** all untouched; changes are the new `api/` package + CLI entry points. |

## 8. Future improvements

- **Authentication & non-loopback binding** — the server binds loopback
  by default and has no auth (mission-excluded); both are prerequisites
  for any remote client.
- **Concurrency** — a threaded/async server needs a synchronized store
  (file locking or a real database) and a thread-safe kernel first.
- **Pagination & filtering** — list endpoints return everything; fine at
  personal scale, worth query parameters (`?status=`, `?limit=`) later.
- **OpenAPI document** — the route table is data; generating an OpenAPI
  spec from it would cost little and give clients a contract.
- **Events over HTTP** — recommendations/disturber reporting
  (`report_disturber`, `report_spontaneous_action`) are facade actions
  not yet exposed; natural additions for a future client milestone.
- **Live change feed** — clients must poll; server-sent events would fit
  the "no websockets" constraint if liveness is wanted later.

## 9. Suggested commit message

```
Milestone 12: REST API - stdlib JSON transport over the facade

- paios.api package (config/errors/schemas/serialization/routes/server/
  __main__): 32 routes mapping HTTP to single facade calls; pure
  ApiRouter core testable without sockets
- Framework: stdlib http.server (zero new dependencies; justified);
  deliberately single-threaded — store/kernel are unsynchronized
- Error translation: domain/application/repository exceptions ->
  400/404/409/503; transport errors -> 400/404/405; everything else 500
- GET /dashboard returns the TUI dashboard's information as JSON
- Entry points: `paios serve [port]` and `python -m paios.api`, both
  with graceful Ctrl+C shutdown
- Tests: 37 new (endpoints, serialization, error mapping, live server,
  delegation, forbidden imports); full suite 671 green
```

## Stop condition

Milestone 12 ends here. No web frontend, React/Vue, Android, desktop
GUI, authentication, AI assistant, or notification work has been
started. Awaiting review.
