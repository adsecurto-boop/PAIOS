"""Assistant composition and offline fallbacks for the REST layer (M20).
Adapter construction happens here (transport concern), never inside the assistant
package.

Two rules hold everywhere in this module:
1. Nothing here creates, mutates, or schedules — outputs are proposals and
explanations the user acts on through ordinary endpoints. The Scheduler stays the
only scheduling authority.
2. Every operation has a deterministic offline path, so the Planning Workspace
works with no SDK, no key, no network.
"""

import datetime
import json
import os
from pathlib import Path

from paios.assistant.adapters import AdapterError, LlmAdapter
from paios.assistant.adapters.null import NullAdapter
from paios.assistant.orchestrator import AssistantOrchestrator
from paios.assistant.response_parser import ResponseParseError
from paios.planning.classifier import classify_lines

#: Providers the transport can compose. "ollama" is the free, private,
#: local default of the intelligence layer; cloud providers are opt-in.
PROVIDERS = ("none", "null", "ollama", "anthropic", "openai", "gemini")

#: How to turn a real provider on (shown in logs and /assistant/status).
CONFIG_HINT = (
    "choose an intelligence mode in Settings (local Ollama, Google Gemini, OpenAI or"
    " Anthropic), or set PAIOS_AI_PROVIDER=ollama|openai|anthropic|gemini —"
    " cloud providers also need their API key"
)


def resolve_provider(config_provider: str) -> str:
    provider = os.environ.get("PAIOS_AI_PROVIDER", config_provider or "none")
    provider = provider.strip().lower()
    return provider if provider in PROVIDERS else "none"


def calculate_cost(provider_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = provider_name.lower()
    input_rate = 0.0
    output_rate = 0.0

    if "openai" in p or "gpt" in p:
        input_rate = 2.50 / 1_000_000
        output_rate = 10.00 / 1_000_000
    elif "anthropic" in p or "claude" in p:
        if "opus" in p:
            input_rate = 15.00 / 1_000_000
            output_rate = 75.00 / 1_000_000
        else:
            input_rate = 3.00 / 1_000_000
            output_rate = 15.00 / 1_000_000
    elif "gemini" in p:
        if "pro" in p:
            input_rate = 1.25 / 1_000_000
            output_rate = 5.00 / 1_000_000
        else:
            input_rate = 0.075 / 1_000_000
            output_rate = 0.30 / 1_000_000

    return (prompt_tokens * input_rate) + (completion_tokens * output_rate)


def log_request(data_dir: str | Path | None, log_entry: dict) -> None:
    if not data_dir:
        return
    log_file = Path(data_dir) / "ai_request_logs.json"
    cost = calculate_cost(
        log_entry.get("provider", ""),
        log_entry.get("prompt_tokens", 0),
        log_entry.get("completion_tokens", 0),
    )
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "provider": log_entry.get("provider"),
        "latency_ms": log_entry.get("latency_ms"),
        "prompt_tokens": log_entry.get("prompt_tokens"),
        "completion_tokens": log_entry.get("completion_tokens"),
        "success": log_entry.get("success"),
        "error": log_entry.get("error"),
        "cost_usd": cost,
    }
    try:
        if log_file.exists():
            try:
                logs = json.loads(log_file.read_text(encoding="utf-8"))
                if not isinstance(logs, list):
                    logs = []
            except Exception:
                logs = []
        else:
            logs = []
        logs.append(entry)
        if len(logs) > 1000:
            logs = logs[-1000:]
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(json.dumps(logs, indent=2), encoding="utf-8")
    except Exception:
        pass


def _construct(
    provider: str,
    model: str | None,
    api_key: str | None = None,
    data_dir: str | None = None,
) -> AssistantOrchestrator | None:
    """The one construction path; raises AdapterError when the chosen
    provider's SDK, key or server is absent, returns None for "none".
    """
    if provider == "none":
        return None

    providers_map = {}
    log_cb = lambda entry: log_request(data_dir, entry)

    # 1. Null
    try:
        providers_map["null"] = NullAdapter()
    except Exception:
        pass

    # Helper function to get stored keys for cloud providers
    from paios.api import ai_settings
    def get_key(prov_name):
        if prov_name == provider and api_key:
            return api_key
        if data_dir:
            resolved = resolve_provider(prov_name)
            return ai_settings.api_key_for(data_dir, resolved)
        return None

    # 2. Ollama
    try:
        from paios.assistant.adapters.ollama import OllamaProvider
        # Only pass model if ollama is the active provider
        ollama_model = model if provider == "ollama" else None
        kwargs = {"model": ollama_model} if ollama_model else {}
        providers_map["ollama"] = OllamaProvider(**kwargs)
    except Exception:
        pass

    # 3. Gemini
    try:
        from paios.assistant.adapters.gemini import GeminiProvider
        gem_key = get_key("gemini")
        gem_model = model if provider == "gemini" else None
        kwargs = {"model": gem_model} if gem_model else {}
        if gem_key is not None:
            kwargs["api_key"] = gem_key
        providers_map["gemini"] = GeminiProvider(**kwargs)
    except Exception as e:
        import logging
        logging.getLogger("paios.api").error(f"Gemini init failed: {e}")

    # 4. Anthropic
    try:
        from paios.assistant.adapters.anthropic import AnthropicAdapter
        ant_key = get_key("anthropic")
        ant_model = model if provider == "anthropic" else None
        kwargs = {"model": ant_model} if ant_model else {}
        if ant_key is not None:
            kwargs["api_key"] = ant_key
        providers_map["anthropic"] = AnthropicAdapter(**kwargs)
    except Exception:
        pass

    # 5. OpenAI
    try:
        from paios.assistant.adapters.openai import OpenAIAdapter
        oai_key = get_key("openai")
        oai_model = model if provider == "openai" else None
        kwargs = {"model": oai_model} if oai_model else {}
        if oai_key is not None:
            kwargs["api_key"] = oai_key
        providers_map["openai"] = OpenAIAdapter(**kwargs)
    except Exception:
        pass

    fallback_chain = []
    if provider == "gemini" and "ollama" in providers_map:
        fallback_chain = ["ollama"]

    if provider not in providers_map:
        if not fallback_chain:
            raise AdapterError(f"AI Provider {provider!r} could not be initialized (missing SDK, server, or API key).")

    from paios.assistant.provider_manager import ProviderManager
    manager = ProviderManager(
        active_provider_name=provider,
        providers=providers_map,
        log_callback=log_cb,
        fallback_chain=fallback_chain,
    )
    return AssistantOrchestrator(manager)


def build_orchestrator(
    provider: str,
    model: str | None = None,
    data_dir: str | None = None,
) -> AssistantOrchestrator | None:
    """None when provider is "none" or its SDK/key is absent — callers
    fall back to the deterministic path.
    """
    model = os.environ.get("PAIOS_AI_MODEL", model or None) or None
    try:
        return _construct(provider, model, data_dir=data_dir)
    except AdapterError:
        return None


def compose_assistant(
    config_provider: str,
    config_model: str | None = None,
    api_key: str | None = None,
    data_dir: str | None = None,
) -> tuple[str, AssistantOrchestrator | None, str]:
    """(provider, orchestrator-or-None, human-readable reason).
    The reason states why the assistant is (un)available in words a user
    can act on — it feeds startup logs and /assistant/status.
    """
    provider = resolve_provider(config_provider)
    model = os.environ.get("PAIOS_AI_MODEL", config_model or None) or None

    if provider == "none":
        return (
            provider,
            None,
            f"no AI provider configured: {CONFIG_HINT}",
        )
    try:
        orchestrator = _construct(provider, model, api_key, data_dir)
    except AdapterError as error:
        return provider, None, str(error)

    if orchestrator and hasattr(orchestrator, "_adapter"):
        manager = orchestrator._adapter
        from paios.assistant.provider_manager import ProviderManager
        if isinstance(manager, ProviderManager) and manager.get_active_provider() is None:
            if "ollama" in manager._providers:
                return provider, orchestrator, f"{provider} is unavailable, falling back to Ollama"
            else:
                return provider, None, f"{provider} is unavailable and no fallback is ready"

    return provider, orchestrator, f"{provider} adapter ready"


#: Exceptions after which the deterministic fallback answers instead.
FALLBACK_ERRORS = (AdapterError, ResponseParseError)


def heuristic_proposal_payload(
    text: str,
    existing_goals: tuple[str, ...],
    existing_projects: tuple[str, ...],
    existing_events: tuple[str, ...],
) -> dict:
    """The offline Planning Proposal: classifier output in the same JSON
    shape the LLM path produces, marked ``source: "heuristic"``.
    """
    classified = classify_lines(
        text, existing_goals, existing_projects, existing_events
    )
    items = []
    questions = []
    for line in classified:
        if line.kind == "day_header":
            continue
        items.append(
            {
                "text": line.text,
                "kind": line.kind,
                "title": line.text,
                "day_scope": line.day_scope,
                "duplicate_of": line.duplicate_of,
                "notes": (
                    f"similar to: {', '.join(line.similar_to)}"
                    if line.similar_to
                    else ""
                ),
            }
        )
        if line.kind == "inbox":
            questions.append(
                f"'{line.text}' is unclear — is it a goal, a project, or "
                "a single event?"
            )
    return {
        "source": "heuristic",
        "answer": (
            f"Classified {len(items)} captured line(s) deterministically "
            "(no language model configured)."
        ),
        "items": items,
        "questions": questions,
        "confidence": None,
    }


def proposal_payload(proposal) -> dict:
    """AssistantProposal -> the same wire shape as the heuristic path."""
    return {
        "source": "llm",
        "adapter": proposal.adapter,
        "answer": proposal.answer,
        "items": [
            {
                "text": item.text,
                "kind": item.kind,
                "title": item.title,
                "day_scope": item.day_scope,
                "duplicate_of": item.duplicate_of,
                "notes": item.notes,
            }
            for item in proposal.items
        ],
        "questions": list(proposal.questions),
        "confidence": proposal.confidence,
    }


# --- daily-rhythm workflows: deterministic fallbacks -------------------------
# The same wire shape as the LLM path ({source, answer, bullets, ...}),
# built purely from recorded facts. PAIOS's daily rhythm never depends
# on a model being present.


def _event_status(event) -> str:
    status = getattr(event, "status", "")
    return str(getattr(status, "value", status))


def _completed_on(events, day: str) -> list:
    completed = []
    for event in events:
        if _event_status(event) != "Completed":
            continue
        end = getattr(event, "end_time", None)
        if end is not None and end.isoformat()[:10] == day:
            completed.append(event)
    return completed


def heuristic_morning_payload(
    app, planning, check_in: dict, today: str
) -> dict:
    """Morning briefing without a model: the Scheduler's plan entries, top
    priorities, and mechanically detected risks.
    """
    entries = deterministic_day_reasons(app, planning)
    # Priority-tagged entries first (the Scheduler already ordered the
    # rest); the top three become the day's named priorities.
    priorities = [
        entry["title"]
        for entry in entries
        if "priority" in entry["reason"]
    ][:3] or [entry["title"] for entry in entries[:3]]

    risks = []
    energy = str(check_in.get("energy") or "").lower()
    if len(entries) > 8:
        risks.append(
            f"{len(entries)} planned entries — the day may be overloaded"
        )
    if energy == "low":
        high_energy = [
            entry["title"]
            for entry in entries
            if "high energy" in entry["reason"]
        ]
        if high_energy:
            risks.append(
                "low energy reported, but high-energy work is planned: "
                + ", ".join(high_energy)
            )
    deadlines = [
        entry["title"]
        for entry in entries
        if "deadline" in entry["reason"]
    ]
    if deadlines:
        risks.append("deadline-bound today: " + ", ".join(deadlines))

    sleep = check_in.get("sleep_hours")
    if isinstance(sleep, (int, float)) and sleep and sleep < 6:
        risks.append(
            f"only {sleep:g}h sleep reported — consider protecting breaks"
        )

    answer = (
        f"Plan for {today}: {len(entries)} scheduled entr"
        f"{'y' if len(entries) == 1 else 'ies'}."
        + (f" Priorities: {', '.join(priorities)}." if priorities else "")
        + (" No mechanical risks detected." if not risks else "")
    )
    return {
        "source": "heuristic",
        "answer": answer,
        "timeline": entries,
        "priorities": priorities,
        "risks": risks,
        "confidence": None,
    }


def heuristic_evening_payload(app, check_in: dict, today: str) -> dict:
    """Evening review without a model: completed vs open, plus the user's
    own notes echoed into a factual summary.
    """
    events = list(app.list_events())
    completed = _completed_on(events, today)
    open_events = [
        event
        for event in events
        if _event_status(event)
        in ("Scheduled", "Ready", "Started", "Resumed", "Paused")
    ]

    improvements = []
    if open_events and completed:
        improvements.append(
            f"{len(open_events)} item(s) remain open — consider whether"
            " they belong on tomorrow's plan or should be archived"
        )
    if not completed:
        improvements.append(
            "no completions were recorded today — if work happened,"
            " recording outcomes keeps the learning data honest"
        )

    plan = app.plan()
    tomorrow = []
    if plan is not None:
        events_by_id = {str(e.event_id): e for e in events}
        for entry in plan.entries:
            if entry.planned_start.isoformat()[:10] > today:
                event = events_by_id.get(str(entry.event_id))
                if event is not None:
                    tomorrow.append(event.description)

    return {
        "source": "heuristic",
        "answer": (
            f"Today {today}: {len(completed)} completed, "
            f"{len(open_events)} still open."
            + (
                f" Notes: {check_in.get('notes')}"
                if check_in.get("notes")
                else ""
            )
        ),
        "completed": [event.description for event in completed],
        "improvements": improvements,
        "tomorrow": tomorrow[:5],
        "confidence": None,
    }


def heuristic_weekly_payload(app, week_days: list[str]) -> dict:
    """Weekly review without a model: per-day completion counts and open
    goal/project tallies — trends as plain arithmetic.
    """
    events = list(app.list_events())
    per_day = {
        day: len(_completed_on(events, day)) for day in week_days
    }
    total = sum(per_day.values())
    goals = list(app.list_goals())
    projects = list(app.list_projects())

    best_day = max(per_day, key=per_day.get) if per_day else None
    bullets = [f"{day}: {count} completed" for day, count in per_day.items()]

    return {
        "source": "heuristic",
        "answer": (
            f"Week in numbers: {total} completion(s) across "
            f"{len(week_days)} day(s)"
            + (
                f"; most productive day {best_day}."
                if best_day and per_day[best_day]
                else "."
            )
            + f" Open goals: {len(goals)}; projects: {len(projects)}."
        ),
        "per_day": per_day,
        "bullets": bullets,
        "confidence": None,
    }


def deterministic_day_reasons(app, planning) -> list[dict]:
    """One grounded WHY per plan entry, from recorded facts only: the
    intent/recommendation reason, priority, deadline, energy and dependencies.
    Verbalizes what the Scheduler and Decision Engine already decided —
    proposes nothing.
    """
    plan = app.plan()
    if plan is None:
        return []

    events = {str(event.event_id): event for event in app.list_events()}
    recommendations = {
        str(r.recommendation_id): r for r in app.active_recommendations()
    }

    entries = []
    for entry in plan.entries:
        event = events.get(str(entry.event_id))
        sidecar = planning.metadata.resolve(
            str(entry.event_id),
            (
                str(entry.recommendation_id)
                if entry.recommendation_id is not None
                else None
            ),
        ) or {}

        reasons = []
        recommendation = (
            recommendations.get(str(entry.recommendation_id))
            if entry.recommendation_id is not None
            else None
        )
        if recommendation is not None and recommendation.reason:
            reasons.append(recommendation.reason)
        if entry.priority:
            reasons.append(f"priority {entry.priority:g}")
        if sidecar.get("deadline"):
            reasons.append(f"deadline {sidecar['deadline']}")
        if sidecar.get("energy"):
            reasons.append(f"{sidecar['energy']} energy task")
        if sidecar.get("depends_on"):
            reasons.append(
                "ordered after: " + ", ".join(sidecar["depends_on"])
            )

        entries.append(
            {
                "event_id": str(entry.event_id),
                "title": event.description if event is not None else "(event)",
                "planned_start": entry.planned_start.isoformat(),
                "duration_minutes": entry.duration_minutes,
                "reason": (
                    "; ".join(reasons)
                    if reasons
                    else "scheduled in priority order at the next free slot"
                ),
            }
        )
    return entries