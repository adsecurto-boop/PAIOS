"""Layout geometry and pure value formatting."""

from datetime import datetime

from paios.dashboard import formatter, layout


class TestLayout:
    def test_banner_is_three_lines_at_width(self):
        lines = layout.banner(57)
        assert len(lines) == 3
        assert lines[0] == "=" * 57
        assert "PAIOS DASHBOARD" in lines[1]
        assert len(lines[1]) == 57

    def test_banner_various_widths(self):
        for width in [0, -5, 5, 10, 15, 30, 80, 120]:
            lines = layout.banner(width)
            assert len(lines) == 3
            expected_width = max(0, width)
            assert lines[0] == "=" * expected_width
            assert lines[2] == "=" * expected_width
            # layout.banner centers layout.TITLE. Python's str.center(width) behaves as:
            # if width <= len(self), returns self as is. Otherwise centers it.
            # So len(lines[1]) should be max(len(layout.TITLE), expected_width)
            expected_len = max(len(layout.TITLE), expected_width)
            assert len(lines[1]) == expected_len
            if expected_width >= len(layout.TITLE):
                assert layout.TITLE in lines[1]
                # Check that it's centered
                left_padding = (expected_width - len(layout.TITLE)) // 2
                assert lines[1].startswith(" " * left_padding)

    def test_clip_never_exceeds_width(self):
        assert layout.clip("x" * 100, 57).endswith("...")
        assert len(layout.clip("x" * 100, 57)) == 57
        assert layout.clip("short", 57) == "short"

    def test_section_wraps_title_and_defaults_empty_to_dash(self):
        lines = layout.section("GOALS", [], 20)
        assert lines == ["-" * 20, "GOALS", "-" * 20, "-"]

    def test_compose_preserves_mission_section_order(self):
        sections = [(title, ["line"]) for title in layout.SECTION_ORDER]
        frame = layout.compose(["header"], sections, 57)
        positions = [frame.index(title) for title in layout.SECTION_ORDER]
        assert positions == sorted(positions)
        assert frame.splitlines()[-1] == "-" * 57

    def test_no_line_wider_than_frame(self):
        sections = [("WIDE", ["y" * 400])]
        frame = layout.compose(["x" * 200], sections, 57)
        assert max(len(line) for line in frame.splitlines()) <= 57


class TestFormatter:
    def test_minutes_label(self):
        assert formatter.minutes_label(5) == "5m"
        assert formatter.minutes_label(60) == "1h 00m"
        assert formatter.minutes_label(135) == "2h 15m"
        assert formatter.minutes_label(-3) == "0m"

    def test_elapsed_and_remaining(self):
        start = datetime(2026, 7, 21, 9, 0)
        now = datetime(2026, 7, 21, 9, 45)
        assert formatter.elapsed_minutes(start, now) == 45
        assert formatter.remaining_minutes(start, 60, now) == 15
        assert formatter.remaining_minutes(start, 30, now) == 0  # never negative
        assert formatter.remaining_minutes(None, 30, now) is None
        assert formatter.remaining_minutes(start, None, now) is None

    def test_progress_bar_bounds(self):
        assert formatter.progress_bar(0) == "[....................] 0%"
        assert formatter.progress_bar(100) == "[####################] 100%"
        assert formatter.progress_bar(150).endswith("100%")
        assert formatter.progress_bar(-5).endswith("0%")
        assert formatter.progress_bar(40).count("#") == 8

    def test_same_day(self):
        reference = datetime(2026, 7, 21, 23, 0)
        assert formatter.same_day(datetime(2026, 7, 21, 0, 1), reference)
        assert not formatter.same_day(datetime(2026, 7, 22, 0, 1), reference)
        assert not formatter.same_day(None, reference)

    def test_value_duck_types_enums_and_strings(self):
        class FakeEnum:
            value = "Started"

        assert formatter.value(FakeEnum()) == "Started"
        assert formatter.value("plain") == "plain"

    def test_clock_time_handles_none(self):
        assert formatter.clock_time(None) == "-"
        assert (
            formatter.clock_time(datetime(2026, 7, 21, 9, 0))
            == "2026-07-21 09:00:00"
        )
