"""Response parsing: model text -> validated immutable DTO.

Validation only — the parser checks shape and types against the
RESPONSE_CONTRACT and refuses everything else. It never repairs,
reinterprets, or decides.
"""

import json
from dataclasses import dataclass


class ResponseParseError(Exception):
    """The model's reply did not satisfy the response contract."""


@dataclass(frozen=True)
class ParsedResponse:
    answer: str
    bullets: tuple[str, ...]
    confidence: float | None


def parse_response(text: str) -> ParsedResponse:
    """Parse the strict JSON reply; tolerate only a ```json fence."""
    if not isinstance(text, str) or not text.strip():
        raise ResponseParseError("Empty response")
    payload = _decode(_strip_fence(text.strip()))
    if not isinstance(payload, dict):
        raise ResponseParseError(
            f"Expected a JSON object, got {type(payload).__name__}"
        )

    if "answer" not in payload:
        raise ResponseParseError("Missing required field 'answer'")
    answer = payload["answer"]
    if not isinstance(answer, str) or not answer.strip():
        raise ResponseParseError("'answer' must be a non-empty string")

    bullets_raw = payload.get("bullets", [])
    if not isinstance(bullets_raw, list) or any(
        not isinstance(item, str) for item in bullets_raw
    ):
        raise ResponseParseError("'bullets' must be a list of strings")

    confidence_raw = payload.get("confidence")
    confidence: float | None
    if confidence_raw is None:
        confidence = None
    elif isinstance(confidence_raw, bool) or not isinstance(
        confidence_raw, (int, float)
    ):
        raise ResponseParseError("'confidence' must be a number or null")
    else:
        confidence = float(confidence_raw)
        if not 0.0 <= confidence <= 1.0:
            raise ResponseParseError(
                f"'confidence' must be within [0, 1], got {confidence}"
            )

    return ParsedResponse(
        answer=answer, bullets=tuple(bullets_raw), confidence=confidence
    )


#: Milestone 20: item kinds a planning proposal may contain.
_PROPOSAL_KINDS = ("goal", "project", "event", "inbox")


@dataclass(frozen=True)
class ProposalItem:
    """One classified capture line inside a planning proposal."""

    text: str
    kind: str
    title: str
    day_scope: str | None
    duplicate_of: str | None
    notes: str


@dataclass(frozen=True)
class ParsedProposal:
    """A validated planning proposal — structure only, zero side effects."""

    answer: str
    items: tuple[ProposalItem, ...]
    questions: tuple[str, ...]
    confidence: float | None


def parse_planning_response(text: str) -> ParsedProposal:
    """Parse the strict PLANNING_CONTRACT reply (M20). Validation only,
    exactly like parse_response — never repairs, never decides."""
    if not isinstance(text, str) or not text.strip():
        raise ResponseParseError("Empty response")
    payload = _decode(_strip_fence(text.strip()))
    if not isinstance(payload, dict):
        raise ResponseParseError(
            f"Expected a JSON object, got {type(payload).__name__}"
        )
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ResponseParseError("'answer' must be a non-empty string")

    items_raw = payload.get("items")
    if not isinstance(items_raw, list):
        raise ResponseParseError("'items' must be a list")
    items = []
    for index, entry in enumerate(items_raw):
        if not isinstance(entry, dict):
            raise ResponseParseError(f"items[{index}] must be an object")
        kind = entry.get("kind")
        if kind not in _PROPOSAL_KINDS:
            raise ResponseParseError(
                f"items[{index}].kind must be one of {_PROPOSAL_KINDS}"
            )
        item_text = entry.get("text")
        title = entry.get("title") or item_text
        if not isinstance(item_text, str) or not item_text.strip():
            raise ResponseParseError(
                f"items[{index}].text must be a non-empty string"
            )
        if not isinstance(title, str) or not title.strip():
            raise ResponseParseError(
                f"items[{index}].title must be a non-empty string"
            )
        day_scope = entry.get("day_scope")
        duplicate_of = entry.get("duplicate_of")
        notes = entry.get("notes", "")
        if day_scope is not None and not isinstance(day_scope, str):
            raise ResponseParseError(f"items[{index}].day_scope must be text")
        if duplicate_of is not None and not isinstance(duplicate_of, str):
            raise ResponseParseError(
                f"items[{index}].duplicate_of must be text"
            )
        if not isinstance(notes, str):
            raise ResponseParseError(f"items[{index}].notes must be text")
        items.append(
            ProposalItem(
                text=item_text.strip(),
                kind=kind,
                title=title.strip(),
                day_scope=day_scope,
                duplicate_of=duplicate_of,
                notes=notes,
            )
        )

    questions_raw = payload.get("questions", [])
    if not isinstance(questions_raw, list) or any(
        not isinstance(question, str) for question in questions_raw
    ):
        raise ResponseParseError("'questions' must be a list of strings")

    confidence_raw = payload.get("confidence")
    confidence: float | None
    if confidence_raw is None:
        confidence = None
    elif isinstance(confidence_raw, bool) or not isinstance(
        confidence_raw, (int, float)
    ):
        raise ResponseParseError("'confidence' must be a number or null")
    else:
        confidence = float(confidence_raw)
        if not 0.0 <= confidence <= 1.0:
            raise ResponseParseError(
                f"'confidence' must be within [0, 1], got {confidence}"
            )

    return ParsedProposal(
        answer=answer,
        items=tuple(items),
        questions=tuple(questions_raw),
        confidence=confidence,
    )


def _strip_fence(text: str) -> str:
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1 and text.rstrip().endswith("```"):
            return text[first_newline + 1 : text.rstrip().rfind("```")]
    return text


def _decode(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ResponseParseError(f"Malformed JSON: {error}") from error
