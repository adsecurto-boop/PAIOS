"""Unit tests for the helper functions in backend/paios/api/serialization.py."""

from datetime import datetime, timezone, timedelta
import pytest

from paios.api.serialization import _iso, _identifier, _value


def test_iso_serialization_none():
    """_iso(None) must return None."""
    assert _iso(None) is None


def test_iso_serialization_naive_datetime():
    """_iso with a naive datetime must return its ISO 8601 string representation."""
    moment = datetime(2026, 7, 21, 9, 15, 30, 123456)
    assert _iso(moment) == "2026-07-21T09:15:30.123456"


def test_iso_serialization_utc_datetime():
    """_iso with a UTC timezone-aware datetime must include 'Z' or '+00:00' format depending on how timezone is constructed."""
    moment = datetime(2026, 7, 21, 9, 15, 30, tzinfo=timezone.utc)
    assert _iso(moment) == "2026-07-21T09:15:30+00:00"


def test_iso_serialization_custom_timezone_datetime():
    """_iso with custom timezone offset must format it correctly."""
    offset = timezone(timedelta(hours=-5))
    moment = datetime(2026, 7, 21, 9, 15, 30, tzinfo=offset)
    assert _iso(moment) == "2026-07-21T09:15:30-05:00"


def test_identifier_serialization_none():
    """_identifier(None) must return None."""
    assert _identifier(None) is None


def test_identifier_serialization_string():
    """_identifier with a string returns the string itself."""
    assert _identifier("user_123") == "user_123"


def test_identifier_serialization_integer():
    """_identifier with an integer returns its string representation."""
    assert _identifier(9876) == "9876"


def test_identifier_serialization_custom_object():
    """_identifier with a custom object returns its str representation."""
    class CustomID:
        def __str__(self):
            return "custom_id_val"

    assert _identifier(CustomID()) == "custom_id_val"


def test_value_serialization_enum_like():
    """_value with an object having a 'value' attribute returns its value."""
    class FakeEnum:
        value = "STARTED"

    assert _value(FakeEnum()) == "STARTED"


def test_value_serialization_standard_string():
    """_value with a string returns the string."""
    assert _value("completed") == "completed"


def test_value_serialization_integer():
    """_value with an integer returns its string representation."""
    assert _value(42) == "42"


def test_value_serialization_custom_str():
    """_value with a custom object without value attribute returns its str representation."""
    class CustomObj:
        def __str__(self):
            return "my_custom_obj"

    assert _value(CustomObj()) == "my_custom_obj"
