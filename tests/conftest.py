"""Pytest fixtures for PV Export Limiter tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture
def mock_clock() -> Iterator[list[float]]:
    """Yield a mutable single-element list whose value drives a fake clock.

    Tests can advance time by mutating ``clock[0]``.
    """
    clock = [0.0]
    yield clock


@pytest.fixture
def fake_time_fn(mock_clock):
    """Return a callable that reads the current value from the mock_clock list."""
    return lambda: mock_clock[0]
