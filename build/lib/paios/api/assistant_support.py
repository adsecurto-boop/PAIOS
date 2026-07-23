"""Assistant composition and offline fallbacks for the REST layer (M20).

Adapter construction happens here (transport concern), never inside the
assistant package. Two rules hold everywhere in this module:

    1. Nothing here creates, mutates, or schedules — outputs are
       proposals and explanations the user acts on through ordinary
       endpoints. The Scheduler stays the only scheduling authority.
    2. Every operation has a deterministic offline path, so the
       Planning Workspace works with no SDK, no key, no network.
"""

import os

from paios.assistant.adapters import AdapterError, LlmAdapter
from paios.assistant.adapters.null import NullAdapter
from paios.assistant.orchestrator import AssistantOrchestrator
from paios.assistant.response_parser import ResponseParseError
from paios.planning.classifier import classify_lines

#: Providers the transport can compose. "ollama" is the free, private,
#: local default of the intelligence layer; cloud providers are opt-in.
PROVIDERS = ("none", "null", "ollama", "anthropic", "openai")

#: How to turn a real provider on (shown in logs and /assistant/status).
CONFIG_HINT = (
    "choose an intelligence mode in Settings (local Ollama, OpenAI or"
    " Anthropic), or set PAIOS_AI_PROVIDER=ollama|openai|anthropic —"
    " cloud providers also need their API key"
)


def resolve_provider(config_provider: str) -> str:
    provider = os.environ.get("PAIOS_AI_PROVIDER", config_provider or "none")
    provider = provider.strip().lower()
    return provider if provider in PROVIDERS else "none"


def _construct(
    provider: str, model: str | None, api_key: str | None = None
) -> AssistantOrchestrator | None:
    """The one construction path; raises AdapterError when the chosen
    provider's SDK, key or server is absent, returns None for "none"."""
    if provider == "null":
        return AssistantOrchestrator(NullAdapter())
    if provider == "ollama":
        from paios.assistant.adapters.ollama import OllamaAdapter

        kwargs = {"model": model} if model else {}
        return AssistantOrchestrator(OllamaAdapter(**kwargs))
    if provider == "anthropic":
        from paios.assistant.adapters.anthropic import AnthropicAdapter

        kwargs = {"model": model} if model else {}
        if api_key:
            kwargs["api_key"] = api_key
        return AssistantOrchestrator(AnthropicAdapter(**kwargs))
    if provider == "openai":
        from paios.assistant.adapters.openai import OpenAIAdapter

        kwargs = {"model": model} if model else {}
        if api_key:
            kwargs["api_key"] = api_key
        return AssistantOrchestrator(OpenAIAdapter(**kwargs))
    return None


def build_orchestrator(
    provider: str, model: str | None = None
) -> AssistantOrchestrator | None:
    """None when provider is "none" or its SDK/key is absent — callers
    fall back to the deterministic path."""
    model = os.environ.get("PAIOS_AI_MODEL", model or None) or None
    try:
        return _construct(provider, model)
    except AdapterError:
        return None


def compose_assistant(
    config_provider: str,
    config_model: str | None = None,
    api_key: str | None = None,
) -> tuple[str, AssistantOrchestrator | None, str]:
    """(provider, orchestrator-or-None, human-readable reason).

    The reason states why the assistant is (un)available in words a
    user can act on — it feeds startup logs and /assistant/status."""
    provider = resolve_provider(config_provider)
    model = os.environ.get("PAIOS_AI_MODEL", config_model or None) or None
    if provider == "none":
        return (
            provider,
            None,
            f"no AI provider configured: {CONFIG_HINT}",
        )
    try:
        orchestrator = _construct(provider, model, api_key)
    except AdapterError as error:
        return provider, None, str(error)
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
    shape the LLM path produces, marked ``source: "heuristic"``."""
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
    """Morning briefing without a model: the Scheduler's plan entries,
    top priorities, and mechanically detected risks."""
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
        entry["title"] for entry in entries if "deadline" in entry["reason"]
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
    """Evening review without a model: completed vs open, plus the
    user's own notes echoed into a factual summary."""
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
    """Weekly review without a model: per-day completion counts and
    open goal/project tallies — trends as plain arithmetic."""
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
    """One grounded WHY per plan entry, from recorded facts only:
    the intent/recommendation reason, priority, deadline, energy and
    dependencies. Verbalizes what the Scheduler and Decision Engine
    already decided — proposes nothing."""
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
