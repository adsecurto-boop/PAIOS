"""The Dashboard: wires renderer and refresh loop; owns nothing else.

Read-only by construction — the only facade members it ever calls are
queries; there is no code path to an action, a repository, or a domain
mutation.
"""

import sys
from typing import Callable, TextIO

from paios.dashboard.config import DashboardConfig
from paios.dashboard.refresh import RefreshLoop
from paios.dashboard.renderer import DashboardRenderer

GOODBYE = "Dashboard closed."


class Dashboard:
    """A continuously refreshing, read-only view of one Application."""

    def __init__(
        self,
        application,
        config: DashboardConfig | None = None,
        output_stream: TextIO | None = None,
        sleep: Callable[[float], None] | None = None,
        daemon=None,
    ) -> None:
        self._config = config if config is not None else DashboardConfig()
        self._out = (
            output_stream if output_stream is not None else sys.stdout
        )
        self._renderer = DashboardRenderer(
            application, self._config, daemon=daemon
        )
        self._loop = RefreshLoop(
            self._config.refresh_seconds, self._out, sleep=sleep
        )

    @property
    def frames_rendered(self) -> int:
        return self._loop.frames_rendered

    def render_once(self) -> str:
        """One frame as a string — no streams, no loop (testing/tooling)."""
        return self._renderer.render()

    def run(self, max_frames: int | None = None) -> str:
        """Render until Ctrl+C (or max_frames); returns the exit reason."""
        reason = self._loop.run(self._renderer.render, max_frames=max_frames)
        self._out.write(GOODBYE + "\n")
        self._out.flush()
        return reason
