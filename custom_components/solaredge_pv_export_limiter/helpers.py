"""Helper utilities for PV Export Limiter."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass
class _Sample:
    timestamp: float
    value: float


class SmoothingBuffer:
    """Time-windowed moving-average buffer.

    Stores ``(timestamp, value)`` pairs per key and returns the mean of all
    samples within the configured window when queried.
    """

    def __init__(self, window_s: float, *, time_fn=time.monotonic) -> None:
        if window_s <= 0:
            raise ValueError("window_s must be positive")
        self._window_s = float(window_s)
        self._time_fn = time_fn
        self._buffers: dict[str, deque[_Sample]] = {}

    def push(self, key: str, value: float) -> float:
        """Append a value to the named buffer and return the current mean."""
        now = self._time_fn()
        buf = self._buffers.setdefault(key, deque())
        buf.append(_Sample(now, float(value)))
        self._evict(buf, now)
        return self._mean(buf)

    def mean(self, key: str) -> float | None:
        """Return the current mean for a key without pushing a new sample."""
        buf = self._buffers.get(key)
        if not buf:
            return None
        self._evict(buf, self._time_fn())
        return self._mean(buf) if buf else None

    def reset(self, key: str | None = None) -> None:
        """Clear a single buffer or all buffers."""
        if key is None:
            self._buffers.clear()
        else:
            self._buffers.pop(key, None)

    def _evict(self, buf: deque[_Sample], now: float) -> None:
        cutoff = now - self._window_s
        while buf and buf[0].timestamp < cutoff:
            buf.popleft()

    @staticmethod
    def _mean(buf: Iterable[_Sample]) -> float:
        samples = list(buf)
        if not samples:
            return 0.0
        return sum(s.value for s in samples) / len(samples)


@dataclass
class TimedFlag:
    """Boolean flag that turns on after a condition has held for a duration."""

    duration_s: float
    _since: float | None = field(default=None, init=False)

    def update(self, condition: bool, now: float) -> bool:
        """Update the flag and return whether it is currently active."""
        if condition:
            if self._since is None:
                self._since = now
            return (now - self._since) >= self.duration_s
        self._since = None
        return False

    def reset(self) -> None:
        self._since = None

    @property
    def held_since(self) -> float | None:
        return self._since


def safe_float(value: object) -> float | None:
    """Convert a state value to float, returning None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (value != value):  # NaN  # noqa: PLR0124
            return None
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.lower() in {"unknown", "unavailable", "none", "nan"}:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def to_watts(value: float | None, unit: str | None) -> float | None:
    """Normalize a power value to W from a HA unit string."""
    if value is None:
        return None
    if unit is None:
        return value
    u = unit.strip().lower()
    if u in {"w", ""}:
        return value
    if u == "kw":
        return value * 1000.0
    if u == "mw":
        return value * 1_000_000.0
    return value
