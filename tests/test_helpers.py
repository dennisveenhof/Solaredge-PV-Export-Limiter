"""Unit tests for helpers module."""

from __future__ import annotations

import math

import pytest

from custom_components.solaredge_pv_export_limiter.helpers import (
    SmoothingBuffer,
    TimedFlag,
    safe_float,
    to_watts,
)


class TestSmoothingBuffer:
    def test_single_value(self, mock_clock, fake_time_fn):
        buf = SmoothingBuffer(window_s=8, time_fn=fake_time_fn)
        assert buf.push("pv", 100.0) == 100.0

    def test_mean_of_multiple_values(self, mock_clock, fake_time_fn):
        buf = SmoothingBuffer(window_s=8, time_fn=fake_time_fn)
        buf.push("pv", 100.0)
        buf.push("pv", 200.0)
        assert buf.push("pv", 300.0) == 200.0

    def test_window_eviction(self, mock_clock, fake_time_fn):
        buf = SmoothingBuffer(window_s=8, time_fn=fake_time_fn)
        mock_clock[0] = 0.0
        buf.push("pv", 100.0)
        mock_clock[0] = 5.0
        buf.push("pv", 200.0)
        mock_clock[0] = 12.0  # First sample now 12s old → evicted
        result = buf.push("pv", 300.0)
        # Mean of (200, 300) = 250
        assert result == 250.0

    def test_separate_keys_independent(self, fake_time_fn):
        buf = SmoothingBuffer(window_s=8, time_fn=fake_time_fn)
        buf.push("pv", 100.0)
        buf.push("import", 50.0)
        assert buf.mean("pv") == 100.0
        assert buf.mean("import") == 50.0

    def test_mean_returns_none_for_unknown_key(self, fake_time_fn):
        buf = SmoothingBuffer(window_s=8, time_fn=fake_time_fn)
        assert buf.mean("never-pushed") is None

    def test_mean_after_full_eviction(self, mock_clock, fake_time_fn):
        buf = SmoothingBuffer(window_s=8, time_fn=fake_time_fn)
        mock_clock[0] = 0.0
        buf.push("pv", 100.0)
        mock_clock[0] = 100.0  # well past window
        assert buf.mean("pv") is None

    def test_reset_single_key(self, fake_time_fn):
        buf = SmoothingBuffer(window_s=8, time_fn=fake_time_fn)
        buf.push("pv", 100.0)
        buf.push("import", 50.0)
        buf.reset("pv")
        assert buf.mean("pv") is None
        assert buf.mean("import") == 50.0

    def test_reset_all_keys(self, fake_time_fn):
        buf = SmoothingBuffer(window_s=8, time_fn=fake_time_fn)
        buf.push("pv", 100.0)
        buf.push("import", 50.0)
        buf.reset()
        assert buf.mean("pv") is None
        assert buf.mean("import") is None

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError, match="positive"):
            SmoothingBuffer(window_s=0)
        with pytest.raises(ValueError, match="positive"):
            SmoothingBuffer(window_s=-1)


class TestTimedFlag:
    def test_active_after_duration(self):
        flag = TimedFlag(duration_s=10)
        assert flag.update(condition=True, now=0.0) is False
        assert flag.update(condition=True, now=5.0) is False
        assert flag.update(condition=True, now=10.0) is True

    def test_resets_on_condition_false(self):
        flag = TimedFlag(duration_s=10)
        flag.update(condition=True, now=0.0)
        flag.update(condition=True, now=5.0)
        assert flag.update(condition=False, now=8.0) is False
        # Restart timer
        flag.update(condition=True, now=10.0)
        # Only 5s after restart, not yet active
        assert flag.update(condition=True, now=15.0) is False

    def test_held_since_property(self):
        flag = TimedFlag(duration_s=10)
        assert flag.held_since is None
        flag.update(condition=True, now=42.0)
        assert flag.held_since == 42.0
        flag.update(condition=False, now=50.0)
        assert flag.held_since is None

    def test_explicit_reset(self):
        flag = TimedFlag(duration_s=10)
        flag.update(condition=True, now=0.0)
        flag.reset()
        assert flag.held_since is None


class TestSafeFloat:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("", None),
            ("unknown", None),
            ("unavailable", None),
            ("Unknown", None),
            ("UNAVAILABLE", None),
            ("none", None),
            ("nan", None),
            ("not-a-number", None),
            ("123.4", 123.4),
            ("  42  ", 42.0),
            (123, 123.0),
            (45.6, 45.6),
            (True, 1.0),  # bool is int subclass; documented behavior
        ],
    )
    def test_conversions(self, value, expected):
        assert safe_float(value) == expected

    def test_nan_float_returns_none(self):
        assert safe_float(float("nan")) is None

    def test_non_string_non_number_returns_none(self):
        assert safe_float([1, 2, 3]) is None
        assert safe_float({"a": 1}) is None


class TestToWatts:
    @pytest.mark.parametrize(
        ("value", "unit", "expected"),
        [
            (1000.0, "W", 1000.0),
            (1000.0, "w", 1000.0),
            (1000.0, " W ", 1000.0),
            (1.5, "kW", 1500.0),
            (1.5, "kw", 1500.0),
            (0.001, "MW", 1000.0),
            (1000.0, "", 1000.0),
            (1000.0, None, 1000.0),
            (None, "W", None),
            (1000.0, "BTU", 1000.0),  # unrecognized → unchanged
        ],
    )
    def test_conversions(self, value, unit, expected):
        result = to_watts(value, unit)
        if expected is None:
            assert result is None
        else:
            assert math.isclose(result, expected)
