"""GUI configuration: the only knobs the presentation layer needs."""

from dataclasses import dataclass

DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_REFRESH_SECONDS = 5
MIN_REFRESH_SECONDS = 1
MAX_REFRESH_SECONDS = 3600


@dataclass
class GuiConfig:
    #: The REST API root — the GUI's only doorway into PAIOS.
    base_url: str = DEFAULT_BASE_URL
    #: Poll interval; user-adjustable at runtime on the Settings page.
    refresh_seconds: int = DEFAULT_REFRESH_SECONDS
    #: Per-request timeout. Short: the API is a localhost transport, and
    #: requests run on the UI thread — a hung server must not hang the
    #: window for more than this.
    request_timeout: float = 2.0

    def clamp_refresh(self, seconds: int) -> int:
        return max(MIN_REFRESH_SECONDS, min(MAX_REFRESH_SECONDS, seconds))
