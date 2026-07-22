# PAIOS AI Architecture

The intelligence layer of PAIOS: how AI plugs into the personal
operating system without ever becoming a dependency of it.

## The one rule

**PAIOS must always function without AI.** The Scheduler, Decision
Engine and Learning Engine are deterministic and complete on their own.
AI is a *language layer* over them: it explains, summarizes, proposes —
it never decides, never schedules, never mutates state. Every
AI-touched endpoint has a deterministic fallback that produces the same
wire shape, and a failed or absent provider can never block startup or
a request.

## Topology

```
                     PAIOS CORE
              (Scheduler, Decision Engine,
               Learning Engine, JSON store)
                          |
                  AssistantOrchestrator          backend/paios/assistant/
              (prompt templates -> adapter ->
               strict-JSON response parser)
                          |
        ------------------------------------------------
        |                    |                         |
    Local AI              Cloud AI                Heuristic
    OllamaAdapter         OpenAIAdapter           built-in fallback
    (Qwen2.5, Llama,      AnthropicAdapter        (classifier + plan
     Mistral — free,      (user's own API key,     facts; deterministic;
     private, offline)     DPAPI-encrypted)        always available)
```

Composition happens at the transport edge
(`backend/paios/api/assistant_support.py`), never inside the assistant
package. `compose_assistant()` returns `(provider, orchestrator | None,
reason)`; a `None` orchestrator simply routes every operation to the
deterministic path.

## Providers

| Provider | Module | Needs | Privacy |
|----------|--------|-------|---------|
| `ollama` (default choice) | `assistant/adapters/ollama.py` | Ollama running locally | everything stays on the machine |
| `anthropic` | `assistant/adapters/anthropic.py` | `anthropic` SDK + API key | prompts leave the machine |
| `openai` | `assistant/adapters/openai.py` | `openai` SDK + API key | prompts leave the machine |
| `null` | `assistant/adapters/null.py` | nothing | offline canned replies (tests/demos) |
| `none` | — | nothing | pure heuristic mode |

Adapter contract (`LlmAdapter`): one `complete(request) -> str` and a
`name`. Adapters translate; they add nothing, filter nothing, decide
nothing. A missing SDK, key, or server raises
`AdapterUnavailableError` at construction — composition catches it,
records the human-readable reason, and PAIOS continues in heuristic
mode.

## Configuration

Precedence: **environment > ai-settings.json > built-in default
("none")**.

- `PAIOS_AI_PROVIDER` / `PAIOS_AI_MODEL` — environment overrides.
- `<data_dir>/ai-settings.json` — what Settings and the first-run
  wizard write (`GET/PUT /assistant/config`); changes recompose the
  assistant live, no restart.
- Cloud API keys: stored **only** DPAPI-encrypted (Windows,
  user-bound); on other platforms the file never holds keys — the
  SDKs' own environment variables are used. Keys are never hardcoded
  and never returned by any endpoint.

## API surface

Setup and settings (all under `/assistant`):

| Route | Purpose |
|-------|---------|
| `GET /assistant/status` | provider, availability, reason, fallback |
| `GET /assistant/setup` | hardware profile + model recommendations + Ollama state |
| `GET /assistant/ollama` | server/CLI state and installed models |
| `POST /assistant/ollama/pull` | detached model download (`{"model": "qwen2.5:7b"}`) |
| `POST /assistant/ollama/remove` | remove an installed model |
| `GET/PUT /assistant/config` | read/change provider + model (+ store API key) |
| `POST /assistant/test` | one round trip proving the provider answers |

Workflows (LLM when available, deterministic otherwise — same shape,
`"source"` says which):

| Route | Input | Output |
|-------|-------|--------|
| `POST /assistant/morning-plan` | sleep_hours, mood, energy, notes | suggested timeline, priorities, risks |
| `POST /assistant/evening-review` | notes, productivity | summary, improvements, tomorrow preview |
| `POST /assistant/weekly-review` | — | weekly summary + per-day completion counts |
| `POST /assistant/plan` | captured text | classified planning proposal |
| `POST /assistant/explain-day` | — | per-entry WHY for today's plan |

The workflows are read-only in both paths: outputs are observations
and proposals; acting on them goes through the ordinary endpoints and
the Decision Engine, exactly as before.

## Hardware detection and model recommendation

`backend/paios/system/hardware.py` probes RAM (Win32 / sysconf), CPU
cores, and GPU/VRAM (`nvidia-smi`, optional) — best-effort, never
raising. `recommend_models()` is a pure function over those numbers:

| Effective memory | Offered | Recommended |
|------------------|---------|-------------|
| < 12 GB | Qwen2.5 3B, Llama 3.2 3B | Qwen2.5 3B |
| 12–24 GB | + Qwen2.5 7B, Llama 3.1 8B, Mistral 7B | Qwen2.5 7B |
| ≥ 24 GB | + Qwen2.5 14B (32B at 40 GB+) | Qwen2.5 14B |

The user can always override the recommendation; the catalog lives in
one table (`MODEL_CATALOG`).

## Failure behavior (by design)

- Ollama not installed → `reason` explains, heuristic mode, setup
  screen shows the install hint.
- Model downloading → requests keep working (download is a detached
  process; the single-threaded API is never blocked).
- Provider errors mid-request (`AdapterError`, parse failures) → that
  request silently falls back to the deterministic answer.
- No internet → local Ollama unaffected; cloud providers degrade to
  heuristic per request.

## Boundaries (enforced by tests)

- The assistant package imports stdlib + itself only; each adapter may
  import exactly its declared SDK/transport (AST-enforced,
  `tests/assistant/test_boundaries.py`).
- The API layer touches only the facade + declared collaborators
  (`tests/api/test_errors_and_server.py`).
- Prompts are frozen templates; rendering is deterministic; every
  reply passes one strict JSON parser.
