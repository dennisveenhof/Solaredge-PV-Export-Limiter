"""Pure functions for PV Export Limiter control logic.

This module has no Home Assistant imports and is fully unit-testable.
"""

from __future__ import annotations

from datetime import datetime

from .const import (
    BUDGET_PERIOD_DAY,
    BUDGET_PERIOD_MONTH,
    BUDGET_PERIOD_YEAR,
    CURTAILMENT_DETECT_FRACTION,
    CURTAILMENT_LIMIT_THRESHOLD_PCT,
    INVERTER_MODEL_NOMINAL_MAP,
)


def compute_load(pv_w: float, import_w: float, export_w: float) -> float:
    """Return the household consumption in W from the power balance.

    Conservation of energy at the grid connection:
        PV + Import = Load + Export
    => Load = PV + Import - Export
    """
    return round(pv_w + import_w - export_w)


def compute_target_w(load_w: float, max_export_w: float) -> float:
    """Return the desired PV output in W to keep export at the setpoint.

    Clamped at zero (we never ask the inverter to consume).
    """
    return max(0.0, load_w + max_export_w)


def compute_target_pct(target_w: float, nominal_w: float) -> float:
    """Convert a target power (W) to inverter limit percentage [0..100].

    Uses round-half-to-even and clamps to the writable range.
    """
    if nominal_w <= 0:
        raise ValueError("nominal_w must be positive")
    pct = (target_w / nominal_w) * 100.0
    return round(max(0.0, min(100.0, pct)), 1)


def should_write(target_pct: float, current_pct: float, hysteresis_pct: float) -> bool:
    """Return True when the difference exceeds the hysteresis threshold."""
    return abs(target_pct - current_pct) > hysteresis_pct


def clamp_pct(value: float) -> float:
    """Clamp a percentage to [0, 100]."""
    return max(0.0, min(100.0, value))


def compute_curtailment(limit_pct: float, nominal_w: float, pv_w: float) -> float:
    """Estimate the W of PV being held back by the limit.

    Returns 0 unless we are reasonably confident the limit is the binding factor:
    - limit must be below the threshold (so we are actively curtailing)
    - actual PV must be hugging the limit value (within CURTAILMENT_DETECT_FRACTION
      of nominal) — otherwise the sun is the bottleneck, not us.
    """
    if limit_pct >= CURTAILMENT_LIMIT_THRESHOLD_PCT:
        return 0.0
    if nominal_w <= 0:
        return 0.0
    max_pv_at_limit = (limit_pct / 100.0) * nominal_w
    if abs(max_pv_at_limit - pv_w) > nominal_w * CURTAILMENT_DETECT_FRACTION:
        return 0.0
    return round(nominal_w - max_pv_at_limit)


def detect_inverter_nominal(model: str | None, fallback_w: int) -> int:
    """Best-effort lookup of nominal AC power from a SolarEdge model string."""
    if not model:
        return fallback_w

    upper = model.upper().replace("-", "").replace("_", "")
    for key, value in INVERTER_MODEL_NOMINAL_MAP.items():
        if key in upper:
            return value
    return fallback_w


def integrate_kwh(power_w: float, elapsed_s: float) -> float:
    """Convert a power sample over an elapsed window into energy (kWh).

    Riemann-sum step: power times time. Negative power and negative durations
    are clamped to zero — we never subtract from the budget counter.
    """
    if power_w <= 0 or elapsed_s <= 0:
        return 0.0
    return (power_w * elapsed_s) / 3_600_000.0


def period_key(now: datetime, period: str) -> str:
    """Return a string key identifying the current period bucket.

    A change in this key between two calls signals a period boundary
    (i.e. the budget counter must reset). Local time is assumed.
    """
    if period == BUDGET_PERIOD_DAY:
        return now.strftime("%Y-%m-%d")
    if period == BUDGET_PERIOD_MONTH:
        return now.strftime("%Y-%m")
    if period == BUDGET_PERIOD_YEAR:
        return now.strftime("%Y")
    return now.strftime("%Y-%m-%d")


def compute_budget_status(used_kwh: float, budget_kwh: float) -> tuple[float, float, bool]:
    """Return (used, remaining, is_exhausted) clamped to non-negative."""
    used = max(0.0, used_kwh)
    remaining = max(0.0, budget_kwh - used)
    exhausted = budget_kwh > 0 and used >= budget_kwh
    return (used, remaining, exhausted)


def budget_remaining_pct(used_kwh: float, budget_kwh: float) -> float:
    """Return the remaining-budget percentage, clamped to [0, 100]."""
    if budget_kwh <= 0:
        return 0.0
    pct = (1.0 - (used_kwh / budget_kwh)) * 100.0
    return round(max(0.0, min(100.0, pct)), 1)


def effective_setpoint_w(
    mode: str,
    setpoint_normal: int,
    setpoint_vacation: int,
    setpoint_negative_price: int,
    setpoint_wide: int,
    setpoint_manual: int,
) -> int | None:
    """Return the active max-export setpoint for the current mode.

    Returns None when the mode is OFF (no regulation should occur).
    """
    if mode == "off":
        return None
    return {
        "normal": setpoint_normal,
        "vacation": setpoint_vacation,
        "negative_price": setpoint_negative_price,
        "wide": setpoint_wide,
        "manual": setpoint_manual,
    }.get(mode, setpoint_normal)
