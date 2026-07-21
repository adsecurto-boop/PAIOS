"""The refresh loop: flicker-free periodic redraw over injectable streams.

Flicker avoidance: each frame is ONE stream write. On a real terminal the
frame is prefixed with cursor-home and suffixed with clear-to-end (plain
VT escape strings — stdlib only, no ANSI library); the first frame clears
the screen once. On a non-terminal stream (tests, pipes) frames are
written verbatim with a trailing newline and no escape codes.

The loop ends when: the interval is 0 (single frame), max_frames is
reached (deterministic tests), or KeyboardInterrupt arrives (Ctrl+C —
the mission's clean exit).
"""

import time
from typing import Callable, TextIO

CLEAR_SCREEN = "\x1b[2J"
CURSOR_HOME = "\x1b[H"
CLEAR_TO_END = "\x1b[0J"
SHOW_CURSOR = "\x1b[?25h"
HIDE_CURSOR = "\x1b[?25l"


def _is_terminal(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty()) if callable(isatty) else False


class RefreshLoop:
    """Runs render -> write -> sleep until stopped. Owns no data."""

    def __init__(
        self,
        interval_seconds: int,
        output_stream: TextIO,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._interval = interval_seconds
        self._out = output_stream
        self._sleep = sleep if sleep is not None else time.sleep
        self._terminal = _is_terminal(output_stream)
        self.frames_rendered = 0

    def _write_frame(self, frame: str, first: bool) -> None:
        if self._terminal:
            prefix = HIDE_CURSOR + CLEAR_SCREEN if first else ""
            self._out.write(prefix + CURSOR_HOME + frame + "\n" + CLEAR_TO_END)
        else:
            self._out.write(frame + "\n")
        self._out.flush()
        self.frames_rendered += 1

    def _restore_terminal(self) -> None:
        if self._terminal:
            self._out.write(SHOW_CURSOR)
            self._out.flush()

    def run(
        self,
        render: Callable[[], str],
        max_frames: int | None = None,
    ) -> str:
        """Render until interrupted; returns the reason the loop ended
        ('single-frame', 'max-frames', or 'interrupted')."""
        try:
            self._write_frame(render(), first=True)
            if self._interval == 0:
                return "single-frame"
            while max_frames is None or self.frames_rendered < max_frames:
                self._sleep(self._interval)
                self._write_frame(render(), first=False)
            return "max-frames"
        except KeyboardInterrupt:
            return "interrupted"
        finally:
            self._restore_terminal()
