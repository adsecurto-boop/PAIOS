"""Request-syntax validation: JSON body shape and field types.

Syntax only — semantic validation stays in the domain. Every failure is
an ApiError(400) with a field-precise message.
"""

from paios.api.errors import ApiError


def body_object(body) -> dict:
    """POST bodies must be a JSON object (or absent -> empty)."""
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise ApiError(400, "Request body must be a JSON object")
    return body


def require_string(body: dict, field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, f"Field {field!r} must be a non-empty string")
    return value


def optional_string(body: dict, field: str) -> str | None:
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(400, f"Field {field!r} must be a string")
    return value


def require_number(body: dict, field: str) -> float:
    value = body.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, f"Field {field!r} must be a number")
    return float(value)


def optional_number(body: dict, field: str) -> float | None:
    if body.get(field) is None:
        return None
    return require_number(body, field)


def optional_bool(body: dict, field: str, default: bool = False) -> bool:
    value = body.get(field, default)
    if not isinstance(value, bool):
        raise ApiError(400, f"Field {field!r} must be a boolean")
    return value


def parse_enum(enum_cls, token: str, field: str):
    """Case-insensitive enum-by-value parsing (the CLI convention)."""
    for member in enum_cls:
        if member.value.lower() == token.lower():
            return member
    valid = ", ".join(member.value for member in enum_cls)
    raise ApiError(
        400, f"Field {field!r} must be one of: {valid} (got {token!r})"
    )
