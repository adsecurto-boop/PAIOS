"""Configuration validation and sleep strategies."""

from datetime import timedelta

import pytest

from paios.daemon.config import (
    DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
    DEFAULT_STARTUP_DELAY_SECONDS,
    DEFAULT_TICK_INTERVAL_SECONDS,
    DaemonConfig,
)
from paios.daemon.exceptions import DaemonError
from paios.daemon.sleep import NoSleep, RealSleep, SimulatedSleep, SleepStrategy
from paios.runtime.clock import ManualClock

from tests.application.conftest import T0


class TestConfig:
    def test_named_defaults(self):
        config = DaemonConfig()
        assert config.tick_interval_seconds == DEFAULT_TICK_INTERVAL_SECONDS
        assert config.startup_delay_seconds == DEFAULT_STARTUP_DELAY_SECONDS
        assert (
            config.shutdown_timeout_seconds == DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
        )
        assert config.sleep_strategy is None

    def test_interval_must_be_positive(self):
        with pytest.raises(DaemonError):
            DaemonConfig(tick_interval_seconds=0)
        with pytest.raises(DaemonError):
            DaemonConfig(tick_interval_seconds=-1)

    def test_delays_cannot_be_negative(self):
        with pytest.raises(DaemonError):
            DaemonConfig(startup_delay_seconds=-1)
        with pytest.raises(DaemonError):
            DaemonConfig(shutdown_timeout_seconds=-0.5)


class TestSleepStrategies:
    def test_strategy_is_abstract(self):
        with pytest.raises(TypeError):
            SleepStrategy()

    def test_no_sleep_records_but_waits_never(self):
        strategy = NoSleep()
        strategy.sleep(60.0)
        assert strategy.calls == [60.0]

    def test_simulated_sleep_advances_the_manual_clock_exactly(self):
        clock = ManualClock(T0)
        strategy = SimulatedSleep(clock)
        strategy.sleep(90.0)
        assert clock.now() == T0 + timedelta(seconds=90)
        assert strategy.calls == [90.0]

    def test_simulated_sleep_ignores_nonpositive(self):
        clock = ManualClock(T0)
        SimulatedSleep(clock).sleep(0)
        assert clock.now() == T0

    def test_real_sleep_accepts_nonpositive_without_waiting(self):
        RealSleep().sleep(0)
        RealSleep().sleep(-1)
