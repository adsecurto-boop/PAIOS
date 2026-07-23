"""Semantic version parsing and comparison. Pure functions, stdlib only."""

import re

_VERSION_PATTERN = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<suffix>[0-9A-Za-z.-]+))?$"
)


class VersionError(ValueError):
    """A tag or version string that is not semantic-version shaped."""


def parse(text: str) -> tuple[int, int, int]:
    """'v2.1.0' / '2.1.0' / '2.1.0-rc1' -> (2, 1, 0). Pre-release
    suffixes are accepted but ignored for ordering (releases on the
    update channel are always final)."""
    match = _VERSION_PATTERN.match(str(text).strip())
    if match is None:
        raise VersionError(f"Not a semantic version: {text!r}")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def is_newer(candidate: str, current: str) -> bool:
    """True when `candidate` is strictly newer than `current`."""
    return parse(candidate) > parse(current)
