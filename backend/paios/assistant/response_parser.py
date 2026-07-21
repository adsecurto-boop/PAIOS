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
