"""Unit tests for the pure calc module — full branch coverage targeted."""

from __future__ import annotations

from datetime import datetime

import pytest

from custom_components.solaredge_pv_export_limiter.calc import (
    budget_remaining_pct,
    clamp_pct,
    compute_budget_status,
    compute_curtailment,
    compute_load,
    compute_target_pct,
    compute_target_w,
    detect_inverter_nominal,
    effective_setpoint_w,
    integrate_kwh,
    period_key,
    should_write,
)


class TestComputeLoad:
    def test_pv_only_no_consumption(self):
        # Pure export: 4000 W PV, 0 import, 4000 W export → load 0
        assert compute_load(pv_w=4000, import_w=0, export_w=4000) == 0

    def test_self_consumption_no_grid(self):
        # 2000 W PV exactly matches a 2000 W load — no grid traffic
        assert compute_load(pv_w=2000, import_w=0, export_w=0) == 2000

    def test_partial_export(self):
        # 4000 W PV, household uses 1000, exporting 3000 → load 1000
        assert compute_load(pv_w=4000, import_w=0, export_w=3000) == 1000

    def test_grid_supplemented(self):
        # 1000 W PV, household needs 2500 → import 1500
        assert compute_load(pv_w=1000, import_w=1500, export_w=0) == 2500

    def test_night_time(self):
        # No PV, 200 W base load → all from grid
        assert compute_load(pv_w=0, import_w=200, export_w=0) == 200

    def test_rounds_to_int(self):
        assert compute_load(pv_w=1000.4, import_w=200.3, export_w=50.5) == 1150


class TestComputeTargetW:
    def test_basic_addition(self):
        assert compute_target_w(load_w=300, max_export_w=50) == 350

    def test_zero_load(self):
        assert compute_target_w(load_w=0, max_export_w=50) == 50

    def test_negative_export_setpoint_clamped(self):
        # Negative load (shouldn't happen, but defend) — clamped at 0
        assert compute_target_w(load_w=-100, max_export_w=50) == 0

    def test_high_load(self):
        assert compute_target_w(load_w=4500, max_export_w=50) == 4550


class TestComputeTargetPct:
    def test_full_power(self):
        assert compute_target_pct(target_w=4000, nominal_w=4000) == 100.0

    def test_half_power(self):
        assert compute_target_pct(target_w=2000, nominal_w=4000) == 50.0

    def test_overload_clamped_to_100(self):
        assert compute_target_pct(target_w=5000, nominal_w=4000) == 100.0

    def test_zero(self):
        assert compute_target_pct(target_w=0, nominal_w=4000) == 0.0

    def test_negative_clamped_to_zero(self):
        assert compute_target_pct(target_w=-100, nominal_w=4000) == 0.0

    def test_rounds_to_one_decimal(self):
        # 1235 / 4000 * 100 = 30.875 → 30.9
        assert compute_target_pct(target_w=1235, nominal_w=4000) == 30.9

    def test_invalid_nominal_raises(self):
        with pytest.raises(ValueError, match="positive"):
            compute_target_pct(target_w=100, nominal_w=0)

    def test_negative_nominal_raises(self):
        with pytest.raises(ValueError, match="positive"):
            compute_target_pct(target_w=100, nominal_w=-100)


class TestShouldWrite:
    def test_within_hysteresis_returns_false(self):
        assert should_write(target_pct=51.0, current_pct=50.0, hysteresis_pct=1.5) is False

    def test_above_hysteresis_returns_true(self):
        assert should_write(target_pct=53.0, current_pct=50.0, hysteresis_pct=1.5) is True

    def test_negative_delta_above_hysteresis(self):
        # Delta is absolute
        assert should_write(target_pct=47.0, current_pct=50.0, hysteresis_pct=1.5) is True

    def test_exactly_at_hysteresis_is_false(self):
        # Strictly greater-than → equal threshold = no write
        assert should_write(target_pct=51.5, current_pct=50.0, hysteresis_pct=1.5) is False

    def test_zero_hysteresis_any_delta_writes(self):
        assert should_write(target_pct=50.1, current_pct=50.0, hysteresis_pct=0.0) is True


class TestClampPct:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (-10.0, 0.0),
            (0.0, 0.0),
            (50.0, 50.0),
            (100.0, 100.0),
            (150.0, 100.0),
        ],
    )
    def test_clamping(self, value, expected):
        assert clamp_pct(value) == expected


class TestComputeCurtailment:
    def test_no_curtailment_when_at_full_power(self):
        # limit at 100% → no curtailment regardless of PV
        assert compute_curtailment(limit_pct=100.0, nominal_w=4000, pv_w=2000) == 0.0

    def test_no_curtailment_at_threshold(self):
        # 99% threshold is the cutoff
        assert compute_curtailment(limit_pct=99.0, nominal_w=4000, pv_w=2000) == 0.0

    def test_active_curtailment_pv_at_limit(self):
        # 50% limit, PV exactly at 2000 (the limit) on 4000 W inverter → 2000 W held back
        assert compute_curtailment(limit_pct=50.0, nominal_w=4000, pv_w=2000) == 2000

    def test_no_curtailment_when_pv_well_below_limit(self):
        # Limit at 50% (= 2000 W) but PV only doing 500 W → sun-bound, not curtailment
        assert compute_curtailment(limit_pct=50.0, nominal_w=4000, pv_w=500) == 0.0

    def test_within_detection_band(self):
        # 5% of 4000 = 200 W band — PV at 1850 vs limit 2000 → detected
        assert compute_curtailment(limit_pct=50.0, nominal_w=4000, pv_w=1850) == 2000

    def test_just_outside_detection_band(self):
        # 250 W gap > 200 W band → not curtailment
        assert compute_curtailment(limit_pct=50.0, nominal_w=4000, pv_w=1750) == 0.0

    def test_zero_nominal_returns_zero(self):
        assert compute_curtailment(limit_pct=50.0, nominal_w=0, pv_w=1000) == 0.0

    def test_negative_nominal_returns_zero(self):
        assert compute_curtailment(limit_pct=50.0, nominal_w=-100, pv_w=1000) == 0.0


class TestDetectInverterNominal:
    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            ("SE3K-RW0TEBEN4", 3000),
            ("SE4K-RW0TEBEN4", 4000),
            ("SE5K-RW0TEBEN4", 5000),
            ("SE6K-RW0TEBEN4", 6000),
            ("SE3680H-RW0TEBNN4", 3680),
            ("SE10K", 10000),
            ("se4k-rw", 4000),  # case insensitive
            ("SE_4000_HD", 4000),
            ("UnknownModel", 4000),  # falls back
            ("", 4000),
        ],
    )
    def test_detection(self, model, expected):
        assert detect_inverter_nominal(model, fallback_w=4000) == expected

    def test_none_model_falls_back(self):
        assert detect_inverter_nominal(None, fallback_w=5000) == 5000


class TestEffectiveSetpointW:
    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            ("normal", 50),
            ("vacation", 0),
            ("negative_price", 0),
            ("wide", 200),
            ("manual", 75),
            ("unknown_mode", 50),  # fallback to normal
        ],
    )
    def test_modes(self, mode, expected):
        assert (
            effective_setpoint_w(
                mode=mode,
                setpoint_normal=50,
                setpoint_vacation=0,
                setpoint_negative_price=0,
                setpoint_wide=200,
                setpoint_manual=75,
            )
            == expected
        )

    def test_off_returns_none(self):
        assert (
            effective_setpoint_w(
                mode="off",
                setpoint_normal=50,
                setpoint_vacation=0,
                setpoint_negative_price=0,
                setpoint_wide=200,
                setpoint_manual=75,
            )
            is None
        )


class TestIntegrateKwh:
    def test_one_kw_one_hour_is_one_kwh(self):
        assert integrate_kwh(power_w=1000.0, elapsed_s=3600.0) == 1.0

    def test_zero_power(self):
        assert integrate_kwh(power_w=0.0, elapsed_s=60.0) == 0.0

    def test_negative_power_clamped(self):
        assert integrate_kwh(power_w=-500.0, elapsed_s=60.0) == 0.0

    def test_negative_elapsed_clamped(self):
        assert integrate_kwh(power_w=500.0, elapsed_s=-1.0) == 0.0

    def test_small_increment(self):
        # 2000 W over 10 s = 5.555... Wh = 0.005555 kWh
        result = integrate_kwh(power_w=2000.0, elapsed_s=10.0)
        assert abs(result - 2000 * 10 / 3_600_000) < 1e-9


class TestPeriodKey:
    def test_day_key(self):
        assert period_key(datetime(2026, 4, 28, 14, 30), "day") == "2026-04-28"

    def test_month_key(self):
        assert period_key(datetime(2026, 4, 28, 14, 30), "month") == "2026-04"

    def test_year_key(self):
        assert period_key(datetime(2026, 4, 28, 14, 30), "year") == "2026"

    def test_unknown_period_falls_back_to_day(self):
        assert period_key(datetime(2026, 4, 28), "weekly") == "2026-04-28"

    def test_day_boundary_change(self):
        a = period_key(datetime(2026, 4, 28, 23, 59), "day")
        b = period_key(datetime(2026, 4, 29, 0, 0), "day")
        assert a != b


class TestComputeBudgetStatus:
    def test_within_budget(self):
        used, remaining, exhausted = compute_budget_status(5.0, 10.0)
        assert used == 5.0
        assert remaining == 5.0
        assert exhausted is False

    def test_exactly_at_budget_is_exhausted(self):
        _used, remaining, exhausted = compute_budget_status(10.0, 10.0)
        assert remaining == 0.0
        assert exhausted is True

    def test_over_budget(self):
        used, remaining, exhausted = compute_budget_status(12.0, 10.0)
        assert used == 12.0
        assert remaining == 0.0
        assert exhausted is True

    def test_negative_used_clamped(self):
        used, remaining, exhausted = compute_budget_status(-1.0, 10.0)
        assert used == 0.0
        assert remaining == 10.0
        assert exhausted is False

    def test_zero_budget_never_exhausted(self):
        # A 0 kWh budget = "no budget set" — not the exhausted state.
        _used, _remaining, exhausted = compute_budget_status(5.0, 0.0)
        assert exhausted is False


class TestBudgetRemainingPct:
    def test_full(self):
        assert budget_remaining_pct(used_kwh=0.0, budget_kwh=10.0) == 100.0

    def test_half(self):
        assert budget_remaining_pct(used_kwh=5.0, budget_kwh=10.0) == 50.0

    def test_empty(self):
        assert budget_remaining_pct(used_kwh=10.0, budget_kwh=10.0) == 0.0

    def test_over_clamped(self):
        assert budget_remaining_pct(used_kwh=12.0, budget_kwh=10.0) == 0.0

    def test_zero_budget_returns_zero(self):
        assert budget_remaining_pct(used_kwh=0.0, budget_kwh=0.0) == 0.0
