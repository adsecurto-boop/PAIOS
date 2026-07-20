"""Clock abstraction."""

from datetime import datetime, timedelta

import pytest

from paios.runtime.clock import Clock, ManualClock, SystemClock

from tests.runtime.conftest import T0, at


class TestClockAbstraction:
    def test_clock_is_abstract(self):
        with pytest.raises(TypeError):
            Clock()

    def test_system_clock_produces_current_time(self):
        now = SystemClock().now()
        assert isinstance(now, datetime)

    def test_manual_clock_is_deterministic(self):
        clock = ManualClock(T0)
        assert clock.now() == T0
        assert clock.now() == T0

    def test_manual_clock_advance(self):
        clock = ManualClock(T0)
        clock.advance(timedelta(minutes=30))
        assert clock.now() == at(30)

    def test_manual_clock_set_time(self):
        clock = ManualClock(T0)
        clock.set_time(at(120))
        assert clock.now() == at(120)
