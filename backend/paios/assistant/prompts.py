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
    )
}
