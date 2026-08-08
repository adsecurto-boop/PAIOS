"""Tests for backend/paios/api/serialization.py pure functions and helper utilities."""

from datetime import datetime
from uuid import UUID
import pytest

from paios.api.serialization import _identifier, _value, _iso


class CustomID:
    def __init__(self, val):
        self.val = val

    def __str__(self):
        return f"custom-{self.val}"


class FakeEnum:
    def __init__(self, value):
        self.value = value


class NormalObject:
    def __str__(self):
        return "normal-object"


def test_identifier_none():
    assert _identifier(None) is None


def test_identifier_string():
    assert _identifier("test-id-123") == "test-id-123"


def test_identifier_integer():
    assert _identifier(456) == "456"


def test_identifier_uuid():
    uuid_val = UUID("12345678-1234-5678-1234-567812345678")
    assert _identifier(uuid_val) == "12345678-1234-5678-1234-567812345678"


def test_identifier_custom_object():
    custom = CustomID("abc")
    assert _identifier(custom) == "custom-abc"


def test_value_with_enum_attribute():
    fake_enum = FakeEnum("RECOMMENDED")
    assert _value(fake_enum) == "RECOMMENDED"


def test_value_fallback_str():
    normal = NormalObject()
    assert _value(normal) == "normal-object"


def test_iso_none():
    assert _iso(None) is None


def test_iso_datetime():
    dt = datetime(2024, 1, 15, 14, 30, 0)
    assert _iso(dt) == "2024-01-15T14:30:00"
