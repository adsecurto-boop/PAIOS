"""Dashboard configuration: the only knobs presentation needs."""

from dataclasses import dataclass

#: Supported refresh intervals in seconds; 0 means "no refresh" — render
#: one frame and return (mission: No refresh / 1 sec / 5 sec / 10 sec).
ALLOWED_INTERVALS: tuple[int, ...] = (0, 1, 5, 10)

DEFAULT_INTERVAL_SECONDS = 1

#: Total frame width in characters (the mission sketch is 57 wide).
FRAME_WIDTH = 57


@dataclass(frozen=True)
class DashboardConfig:
    #: Seconds between redraws; 0 renders a single frame and returns.
    refresh_seconds: int = DEFAULT_INTERVAL_SECONDS
    #: Frame width in characters.
    width: int = FRAME_WIDTH
    #: How many rows each list section may show before truncating.
    max_rows_per_section: int = 3

    def __post_init__(self) -> None:
        if self.refresh_seconds not in ALLOWED_INTERVALS:
            raise ValueError(
                f"refresh_seconds must be one of {ALLOWED_INTERVALS}, "
                f"got {self.refresh_seconds!r}"
            )
