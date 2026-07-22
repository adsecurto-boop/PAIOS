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

#: Providers the transport can compose.
PROVIDERS = ("none", "null", "anthropic", "openai")


def resolve_provider(config_provider: str) -> str:
    provider = os.environ.get("PAIOS_AI_PROVIDER", config_provider or "none")
    provider = provider.strip().lower()
    return provider if provider in PROVIDERS else "none"


def build_orchestrator(
    provider: str, model: str | None = None
) -> AssistantOrchestrator | None:
    """None when provider is "none" or its SDK/key is absent — callers
    fall back to the deterministic path."""
    model = os.environ.get("PAIOS_AI_MODEL", model or None) or None
    try:
        if provider == "null":
            return AssistantOrchestrator(NullAdapter())
        if provider == "anthropic":
            from paios.assistant.adapters.anthropic import AnthropicAdapter

            kwargs = {"model": model} if model else {}
            return AssistantOrchestrator(AnthropicAdapter(**kwargs))
        if provider == "openai":
            from paios.assistant.adapters.openai import OpenAIAdapter

            kwargs = {"model": model} if model else {}
            return AssistantOrchestrator(OpenAIAdapter(**kwargs))
    except AdapterError:
        return None
    return None


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
