"""Prompt templates: fixed strings, deterministic rendering.

One template per assistant voice (the mission's seven). Rendering is
pure string substitution over named fields — identical inputs render
identical prompts, byte for byte. No clocks, no randomness, no
environment reads.

Every template demands the same strict JSON reply shape so one parser
validates every operation:

    {"answer": "...", "bullets": ["..."], "confidence": 0.0-1.0}
"""

from dataclasses import dataclass
from string import Formatter

#: The reply contract every template embeds and the parser enforces.
RESPONSE_CONTRACT = (
    'Respond with ONLY a JSON object, no other text: {"answer": '
    '"<the full prose answer>", "bullets": ["<key point>", ...], '
    '"confidence": <0.0-1.0>}'
)

_SHARED_RULES = (
    "You are the PAIOS assistant, a language layer over a personal "
    "operating system. You explain and summarize; you never decide. "
    "The Decision Engine is the only authority — never instruct the "
    "user to bypass it, and never claim an action was or will be "
    "taken. Ground every statement in the provided context; if the "
    "context does not contain the answer, say so plainly. "
) + RESPONSE_CONTRACT


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    system: str
    user_template: str

    def render(self, **fields: str) -> str:
        """Substitute fields; unknown or missing fields are errors."""
        required = {
            field_name
            for _, field_name, _, _ in Formatter().parse(self.user_template)
            if field_name
        }
        provided = set(fields)
        if provided != required:
            missing = sorted(required - provided)
            extra = sorted(provided - required)
            raise KeyError(
                f"Template {self.name!r}: missing fields {missing}, "
                f"unexpected fields {extra}"
            )
        return self.user_template.format(**fields)


EXPLAIN = PromptTemplate(
    name="explain",
    system=_SHARED_RULES,
    user_template=(
        "Explain the following to the user in plain language.\n\n"
        "Subject:\n{subject}\n\nContext:\n{context}\n\nQuestion: {question}"
    ),
)

SUMMARIZE = PromptTemplate(
    name="summarize",
    system=_SHARED_RULES,
    user_template=(
        "Summarize the user's situation described below. Be concrete: "
        "name events, goals and numbers from the context; invent "
        "nothing.\n\nScope: {scope}\n\nContext:\n{context}"
    ),
)

REFLECT = PromptTemplate(
    name="reflect",
    system=_SHARED_RULES,
    user_template=(
        "Help the user reflect. Draw only on the reflections and "
        "events below; surface patterns and lessons, and phrase them "
        "as observations, not instructions.\n\nContext:\n{context}"
    ),
)

WEEKLY_REVIEW = PromptTemplate(
    name="weekly_review",
    system=_SHARED_RULES,
    user_template=(
        "Write the user's weekly review from the context below. Cover: "
        "what was completed, what patterns the learning data shows, "
        "and what remained open. State progress factually.\n\n"
        "Context:\n{context}"
    ),
)

RECOMMENDATION_EXPLANATION = PromptTemplate(
    name="recommendation_explanation",
    system=_SHARED_RULES,
    user_template=(
        "The Decision Engine produced this recommendation. Explain "
        "{angle} to the user. Do not accept, reject, or rank it — "
        "explanation only; the user decides in PAIOS.\n\n"
        "Recommendation:\n{subject}\n\nContext:\n{context}"
    ),
)

PROJECT_EXPLANATION = PromptTemplate(
    name="project_explanation",
    system=_SHARED_RULES,
    user_template=(
        "Discuss the user's projects as described below. {instruction}\n\n"
        "Projects:\n{subject}\n\nContext:\n{context}"
    ),
)

LEARNING_EXPLANATION = PromptTemplate(
    name="learning_explanation",
    system=_SHARED_RULES,
    user_template=(
        "Discuss the user's learning data described below. "
        "{instruction}\n\nContext:\n{context}"
    ),
)

#: Milestone 20: the planning-proposal reply contract. Distinct from
#: RESPONSE_CONTRACT because a proposal is structured items, not prose;
#: response_parser.parse_planning_response enforces it.
PLANNING_CONTRACT = (
    'Respond with ONLY a JSON object, no other text: {"answer": "<one '
    'sentence describing the proposal>", "items": [{"text": "<the '
    'original line>", "kind": "goal"|"project"|"event"|"inbox", '
    '"title": "<clean title>", "day_scope": "<day word or null>", '
    '"duplicate_of": "<existing name or null>", "notes": "<short '
    'rationale>"}, ...], "questions": ["<clarification question>", '
    '...], "confidence": <0.0-1.0>}'
)

PLANNING_CLASSIFICATION = PromptTemplate(
    name="planning_classification",
    system=(
        "You are the PAIOS planning assistant. You ONLY classify the "
        "user's captured lines and propose a plan structure — you never "
        "create anything, never schedule anything, and never claim an "
        "action happened. The PAIOS Scheduler is the sole scheduling "
        "authority; your output is a proposal the user must approve. "
        "Classify each line as goal (long-running aspiration), project "
        "(multi-step buildable work), event (single concrete action) or "
        "inbox (unclear — needs triage). Mark duplicates of existing "
        "work. Ask a clarification question when a line is ambiguous. "
    ) + PLANNING_CONTRACT,
    user_template=(
        "Captured lines:\n{captures}\n\nExisting goals:\n{goals}\n\n"
        "Existing projects:\n{projects}\n\nExisting events:\n{events}"
    ),
)

DAY_PLAN_EXPLANATION = PromptTemplate(
    name="day_plan_explanation",
    system=_SHARED_RULES + (
        " You are explaining a schedule the PAIOS Scheduler already "
        "produced. Give one short WHY per plan entry, grounded ONLY in "
        "the supplied facts (priority, deadline, energy, dependencies, "
        "recommendation reasons). Never propose reordering; the "
        "Scheduler and Decision Engine already decided."
    ),
    user_template=(
        "Today's plan (in scheduled order):\n{plan}\n\n"
        "Supporting facts:\n{context}"
    ),
)

#: Registry: template name -> template (fixed, ordered by name).
TEMPLATES: dict[str, PromptTemplate] = {
    template.name: template
    for template in (
        EXPLAIN,
        SUMMARIZE,
        REFLECT,
        WEEKLY_REVIEW,
        RECOMMENDATION_EXPLANATION,
        PROJECT_EXPLANATION,
        LEARNING_EXPLANATION,
        PLANNING_CLASSIFICATION,
        DAY_PLAN_EXPLANATION,
    )
}
