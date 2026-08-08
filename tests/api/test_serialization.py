from datetime import datetime, timezone, timedelta
from paios.api.serialization import _iso


def test_iso_with_none():
    assert _iso(None) is None


def test_iso_with_naive_datetime():
    dt = datetime(2026, 7, 21, 9, 30, 15)
    assert _iso(dt) == "2026-07-21T09:30:15"


def test_iso_with_timezone_aware_datetime():
    tz = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2026, 7, 21, 9, 30, 15, tzinfo=tz)
    assert _iso(dt) == "2026-07-21T09:30:15+05:30"
