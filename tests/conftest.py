"""Pytest fixtures for PV Export Limiter tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_clock() -> list[float]:
    """Return a mutable single-element list whose value drives a fake clock.

    Tests can advance time by mutating ``clock[0]``.
    """
    return [0.0]


@pytest.fixture
def fake_time_fn(mock_clock):
    """Return a callable that reads the current value from the mock_clock list."""
    return lambda: mock_clock[0]
