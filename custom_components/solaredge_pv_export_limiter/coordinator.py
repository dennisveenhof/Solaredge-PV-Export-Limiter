"""Control loop coordinator for PV Export Limiter."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .calc import (
    clamp_pct,
    compute_curtailment,
    compute_load,
    compute_target_pct,
    compute_target_w,
    effective_setpoint_w,
    should_write,
)
from .const import (
    ANOMALY_DURATION_S,
    ANOMALY_EXPORT_THRESHOLD_W,
    ANOMALY_PV_MIN_W,
    CONF_ENABLED_AT_START,
    CONF_GRID_EXPORT,
    CONF_GRID_IMPORT,
    CONF_GRID_VOLTAGE,
    CONF_HYSTERESIS_PCT,
    CONF_INITIAL_MODE,
    CONF_INVERTER_AC_POWER,
    CONF_INVERTER_LIMIT,
    CONF_INVERTER_NOMINAL_W,
    CONF_NOTIFY_TARGET,
    CONF_SETPOINT_NEGATIVE_PRICE,
    CONF_SETPOINT_NORMAL,
    CONF_SETPOINT_VACATION,
    CONF_SETPOINT_WIDE,
    CONF_SMOOTHING_WINDOW_S,
    CONF_TARIFF_ENABLED,
    CONF_TARIFF_HIGH_THRESHOLD,
    CONF_TARIFF_NEGATIVE_THRESHOLD,
    CONF_TARIFF_PRICE,
    CONF_UPDATE_INTERVAL_S,
    CONF_VOLTAGE_PROTECTION_ENABLED,
    CONF_VOLTAGE_RECOVERY_V,
    CONF_VOLTAGE_WARNING_V,
    DEFAULT_HYSTERESIS_PCT,
    DEFAULT_INVERTER_NOMINAL_W,
    DEFAULT_SETPOINT_MANUAL_W,
    DEFAULT_SETPOINT_NEGATIVE_PRICE_W,
    DEFAULT_SETPOINT_NORMAL_W,
    DEFAULT_SETPOINT_VACATION_W,
    DEFAULT_SETPOINT_WIDE_W,
    DEFAULT_SMOOTHING_WINDOW_S,
    DEFAULT_UPDATE_INTERVAL_S,
    DEFAULT_VOLTAGE_RECOVERY_V,
    DEFAULT_VOLTAGE_WARNING_V,
    DOMAIN,
    EVENT_DEBOUNCE_S,
    EVENT_EXPORT_THRESHOLD_W,
    EVENT_IMPORT_THRESHOLD_W,
    SENSOR_LOSS_GRACE_PERIOD_S,
    VOLTAGE_PROTECTION_DURATION_S,
    Mode,
    Status,
)
from .helpers import SmoothingBuffer, TimedFlag, safe_float, to_watts

_LOGGER = logging.getLogger(__name__)

PRICE_NEGATIVE_DEBOUNCE_S = 60


@dataclass
class PVLimiterState:
    """Snapshot of computed values at one update tick — published to entities."""

    load_w: float
    target_w: float
    target_pct: float
    current_pct: float
    pv_w: float
    grid_import_w: float
    grid_export_w: float
    voltage_v: float | None
    tariff_price: float | None
    mode: str
    enabled: bool
    status: str
    curtailment_w: float
    anomaly: bool
    voltage_warning: bool
    last_write_pct: float | None
    last_write_at: float | None


class PVExportLimiterCoordinator(DataUpdateCoordinator[PVLimiterState]):
    """Drives the closed-loop control of the SolarEdge active power limit."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        merged: dict[str, Any] = {**entry.data, **entry.options}
        update_s = int(merged.get(CONF_UPDATE_INTERVAL_S, DEFAULT_UPDATE_INTERVAL_S))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_s),
        )

        self.config_entry = entry
        self._merged = merged

        # Sensor entity ids
        self._inverter_ac_power = merged[CONF_INVERTER_AC_POWER]
        self._inverter_limit = merged[CONF_INVERTER_LIMIT]
        self._grid_import = merged[CONF_GRID_IMPORT]
        self._grid_export = merged[CONF_GRID_EXPORT]
        self._grid_voltage = merged.get(CONF_GRID_VOLTAGE)
        self._tariff_price = merged.get(CONF_TARIFF_PRICE)
        self._notify_target = merged.get(CONF_NOTIFY_TARGET)

        # Inverter
        self._nominal_w = float(
            merged.get(CONF_INVERTER_NOMINAL_W, DEFAULT_INVERTER_NOMINAL_W)
        )

        # Tuning
        smoothing_s = float(
            merged.get(CONF_SMOOTHING_WINDOW_S, DEFAULT_SMOOTHING_WINDOW_S)
        )
        self._smoothing = SmoothingBuffer(window_s=smoothing_s)
        self._hysteresis_pct = float(
            merged.get(CONF_HYSTERESIS_PCT, DEFAULT_HYSTERESIS_PCT)
        )

        # Setpoints
        self._setpoint_normal = int(
            merged.get(CONF_SETPOINT_NORMAL, DEFAULT_SETPOINT_NORMAL_W)
        )
        self._setpoint_vacation = int(
            merged.get(CONF_SETPOINT_VACATION, DEFAULT_SETPOINT_VACATION_W)
        )
        self._setpoint_negative_price = int(
            merged.get(CONF_SETPOINT_NEGATIVE_PRICE, DEFAULT_SETPOINT_NEGATIVE_PRICE_W)
        )
        self._setpoint_wide = int(
            merged.get(CONF_SETPOINT_WIDE, DEFAULT_SETPOINT_WIDE_W)
        )
        self._setpoint_manual = DEFAULT_SETPOINT_MANUAL_W

        # Voltage protection
        self._voltage_protection_enabled = bool(
            merged.get(CONF_VOLTAGE_PROTECTION_ENABLED, False)
        )
        self._voltage_warning_v = float(
            merged.get(CONF_VOLTAGE_WARNING_V, DEFAULT_VOLTAGE_WARNING_V)
        )
        self._voltage_recovery_v = float(
            merged.get(CONF_VOLTAGE_RECOVERY_V, DEFAULT_VOLTAGE_RECOVERY_V)
        )

        # Tariff
        self._tariff_enabled = bool(merged.get(CONF_TARIFF_ENABLED, False))
        self._tariff_negative_threshold = float(
            merged.get(CONF_TARIFF_NEGATIVE_THRESHOLD, 0.0)
        )
        self._tariff_high_threshold = float(
            merged.get(CONF_TARIFF_HIGH_THRESHOLD, 0.30)
        )

        # Mutable runtime state
        self._mode: str = merged.get(CONF_INITIAL_MODE, Mode.NORMAL)
        self._enabled: bool = bool(merged.get(CONF_ENABLED_AT_START, True))
        self._last_write_pct: float | None = None
        self._last_write_at: float | None = None
        self._anomaly_flag = TimedFlag(duration_s=ANOMALY_DURATION_S)
        self._voltage_warning_active = False
        self._voltage_warning_flag = TimedFlag(
            duration_s=VOLTAGE_PROTECTION_DURATION_S
        )
        self._sensor_loss_flag = TimedFlag(duration_s=SENSOR_LOSS_GRACE_PERIOD_S)
        self._negative_price_flag = TimedFlag(duration_s=PRICE_NEGATIVE_DEBOUNCE_S)
        self._user_mode_override = False  # set when user manually picks mode
        self._unsub_listeners: list[CALLBACK_TYPE] = []
        self._last_event_trigger_at = 0.0
        self._notified_anomaly = False

        self.data = self._initial_state()

    # ─── Public API for entities & services ───────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def hysteresis_pct(self) -> float:
        return self._hysteresis_pct

    @property
    def nominal_w(self) -> float:
        return self._nominal_w

    @property
    def setpoint_manual_w(self) -> int:
        return self._setpoint_manual

    async def async_set_mode(self, mode: str) -> None:
        if mode not in Mode.__members__.values() and mode not in [m.value for m in Mode]:
            _LOGGER.warning("Ignoring unknown mode: %s", mode)
            return
        self._mode = mode
        self._user_mode_override = mode != Mode.NORMAL  # remember user choice
        await self.async_request_refresh()

    async def async_set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            await self.async_reset_limit_to_100()
        await self.async_request_refresh()

    async def async_set_hysteresis(self, value: float) -> None:
        self._hysteresis_pct = float(value)
        await self.async_request_refresh()

    async def async_set_nominal(self, value: float) -> None:
        self._nominal_w = float(value)
        await self.async_request_refresh()

    async def async_set_setpoint_manual(self, value: int) -> None:
        self._setpoint_manual = int(value)
        if self._mode == Mode.MANUAL:
            await self.async_request_refresh()

    async def async_reset_limit_to_100(self) -> None:
        await self._write_limit(100.0, force=True)

    async def async_shutdown(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    # ─── Lifecycle ─────────────────────────────────────────────────────

    async def async_config_entry_first_refresh(self) -> None:
        self._setup_event_listeners()
        await super().async_config_entry_first_refresh()

    def _setup_event_listeners(self) -> None:
        """Listen for significant state changes that should trigger a refresh."""

        @callback
        def _changed(event: Event[EventStateChangedData]) -> None:
            now = time.monotonic()
            if now - self._last_event_trigger_at < EVENT_DEBOUNCE_S:
                return
            new_state = event.data.get("new_state")
            if not new_state or new_state.state in ("unknown", "unavailable"):
                return
            value = safe_float(new_state.state)
            if value is None:
                return
            entity_id = event.data["entity_id"]
            threshold = (
                EVENT_EXPORT_THRESHOLD_W
                if entity_id == self._grid_export
                else EVENT_IMPORT_THRESHOLD_W
            )
            if value > threshold:
                self._last_event_trigger_at = now
                self.hass.async_create_task(self.async_request_refresh())

        watched = [self._grid_export, self._grid_import]
        if self._grid_voltage:
            watched.append(self._grid_voltage)
        unsub = async_track_state_change_event(self.hass, watched, _changed)
        self._unsub_listeners.append(unsub)

        @callback
        def _on_started(_event: Event) -> None:
            # Reset to safe state on restart so we don't act on stale data.
            self.hass.async_create_task(self.async_reset_limit_to_100())

        self._unsub_listeners.append(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
        )

    # ─── Update tick ───────────────────────────────────────────────────

    async def _async_update_data(self) -> PVLimiterState:
        try:
            return await self._compute_state()
        except UpdateFailed:
            raise
        except Exception as err:  # pragma: no cover - defensive
            raise UpdateFailed(f"Coordinator failed: {err}") from err

    async def _compute_state(self) -> PVLimiterState:
        now = time.monotonic()

        pv_raw = self._read_power(self._inverter_ac_power)
        imp_raw = self._read_power(self._grid_import)
        exp_raw = self._read_power(self._grid_export)
        voltage_raw = (
            self._read_float(self._grid_voltage) if self._grid_voltage else None
        )
        tariff_price = (
            self._read_float(self._tariff_price) if self._tariff_price else None
        )
        current_pct = self._read_float(self._inverter_limit) or 100.0

        sensor_loss = self._sensor_loss_flag.update(
            condition=(pv_raw is None or imp_raw is None or exp_raw is None),
            now=now,
        )

        if sensor_loss:
            await self._handle_sensor_loss()
            return self._snapshot(
                status=Status.SENSOR_LOSS,
                pv_w=pv_raw or 0,
                imp_w=imp_raw or 0,
                exp_w=exp_raw or 0,
                voltage_v=voltage_raw,
                tariff_price=tariff_price,
                current_pct=current_pct,
                target_pct=100.0,
                target_w=0.0,
                load_w=0.0,
            )

        # Smoothed values
        pv_smooth = self._smoothing.push("pv", pv_raw or 0)
        imp_smooth = self._smoothing.push("imp", imp_raw or 0)
        exp_smooth = self._smoothing.push("exp", exp_raw or 0)

        # Tariff-driven mode override
        if self._tariff_enabled and tariff_price is not None:
            await self._maybe_switch_mode_for_tariff(tariff_price, now)

        # If limiter is OFF or mode is OFF, keep things at 100% and bail.
        if not self._enabled or self._mode == Mode.OFF:
            await self._write_limit(100.0)
            return self._snapshot(
                status=Status.DISABLED,
                pv_w=pv_smooth,
                imp_w=imp_smooth,
                exp_w=exp_smooth,
                voltage_v=voltage_raw,
                tariff_price=tariff_price,
                current_pct=current_pct,
                target_pct=100.0,
                target_w=self._nominal_w,
                load_w=compute_load(pv_smooth, imp_smooth, exp_smooth),
            )

        # Voltage protection — pre-empt control if mains is too high.
        voltage_warning = self._evaluate_voltage_warning(voltage_raw, now)

        # Compute load + target.
        load_w = compute_load(pv_smooth, imp_smooth, exp_smooth)

        # Guard: deeply negative load means the PV sensor is underreporting while
        # the inverter is still producing (e.g. Modbus hiccup returning 0 W).
        # Fall back to import as a conservative load estimate so we still limit.
        if load_w < -100:
            _LOGGER.warning(
                "Computed load %.0f W is negative (PV=%.0f W, import=%.0f W, "
                "export=%.0f W) — PV sensor may be underreporting; using grid "
                "import as load estimate to prevent runaway export",
                load_w, pv_smooth, imp_smooth, exp_smooth,
            )
            load_w = imp_smooth

        setpoint = effective_setpoint_w(
            mode=self._mode,
            setpoint_normal=self._setpoint_normal,
            setpoint_vacation=self._setpoint_vacation,
            setpoint_negative_price=self._setpoint_negative_price,
            setpoint_wide=self._setpoint_wide,
            setpoint_manual=self._setpoint_manual,
        )
        if setpoint is None:
            setpoint = self._setpoint_normal
        target_w = compute_target_w(load_w, setpoint)
        target_pct = compute_target_pct(target_w, self._nominal_w)

        if voltage_warning:
            target_pct = 0.0
            status = Status.VOLTAGE_HIGH
        elif pv_smooth < 50 and current_pct >= 99.0 and exp_smooth < 100:
            # Genuine no-production: PV sensor low AND no significant export.
            # If export is high the sensor is likely glitching — fall through to OK.
            target_pct = 100.0
            status = Status.NO_PV
        else:
            status = Status.OK

        await self._write_limit(target_pct)

        # Anomaly detection (only meaningful when limiter is enabled)
        anomaly = self._evaluate_anomaly(
            export_w=exp_smooth, pv_w=pv_smooth, now=now
        )

        return self._snapshot(
            status=status,
            pv_w=pv_smooth,
            imp_w=imp_smooth,
            exp_w=exp_smooth,
            voltage_v=voltage_raw,
            tariff_price=tariff_price,
            current_pct=current_pct,
            target_pct=target_pct,
            target_w=target_w,
            load_w=load_w,
            anomaly=anomaly,
            voltage_warning=voltage_warning,
        )

    # ─── Internals ─────────────────────────────────────────────────────

    def _read_float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if not state:
            return None
        return safe_float(state.state)

    def _read_power(self, entity_id: str) -> float | None:
        state = self.hass.states.get(entity_id)
        if not state:
            return None
        value = safe_float(state.state)
        unit = state.attributes.get("unit_of_measurement")
        return to_watts(value, unit)

    def _evaluate_anomaly(self, *, export_w: float, pv_w: float, now: float) -> bool:
        condition = (
            export_w > ANOMALY_EXPORT_THRESHOLD_W
            and pv_w > ANOMALY_PV_MIN_W
            and self._enabled
        )
        active = self._anomaly_flag.update(condition, now)
        if active and not self._notified_anomaly and self._notify_target:
            self._notified_anomaly = True
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "notify",
                    self._notify_target,
                    {
                        "title": "Solaredge PV Export Limiter — anomaly",
                        "message": (
                            f"Grid export {export_w:.0f} W exceeds threshold "
                            f"for {ANOMALY_DURATION_S}s while limiter is active."
                        ),
                    },
                    blocking=False,
                )
            )
        if not active:
            self._notified_anomaly = False
        return active

    def _evaluate_voltage_warning(
        self, voltage: float | None, now: float
    ) -> bool:
        if not self._voltage_protection_enabled or voltage is None:
            self._voltage_warning_active = False
            self._voltage_warning_flag.reset()
            return False
        if voltage > self._voltage_warning_v:
            triggered = self._voltage_warning_flag.update(True, now)
            if triggered:
                self._voltage_warning_active = True
        elif voltage < self._voltage_recovery_v:
            self._voltage_warning_flag.reset()
            self._voltage_warning_active = False
        return self._voltage_warning_active

    async def _maybe_switch_mode_for_tariff(
        self, price: float, now: float
    ) -> None:
        if self._user_mode_override and self._mode == Mode.MANUAL:
            return  # respect manual override

        if price < self._tariff_negative_threshold:
            triggered = self._negative_price_flag.update(True, now)
            if triggered and self._mode != Mode.NEGATIVE_PRICE:
                _LOGGER.info("Negative price (%s €) — switching to negative_price mode", price)
                self._mode = Mode.NEGATIVE_PRICE
        else:
            self._negative_price_flag.reset()
            if self._mode == Mode.NEGATIVE_PRICE:
                if price > self._tariff_high_threshold:
                    self._mode = Mode.WIDE
                else:
                    self._mode = Mode.NORMAL

    async def _handle_sensor_loss(self) -> None:
        """Sensor unavailable beyond grace period — reset to 100%."""
        if self._last_write_pct != 100.0:
            await self._write_limit(100.0, force=True)
            if self._notify_target:
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "notify",
                        self._notify_target,
                        {
                            "title": "Solaredge PV Export Limiter — sensor loss",
                            "message": (
                                "One of the configured power sensors has been "
                                "unavailable for too long. Limit reset to 100%."
                            ),
                        },
                        blocking=False,
                    )
                )

    async def _write_limit(self, target_pct: float, *, force: bool = False) -> None:
        target_pct = clamp_pct(target_pct)
        current_pct = self._read_float(self._inverter_limit)

        if not force and current_pct is not None and not should_write(
            target_pct, current_pct, self._hysteresis_pct
        ):
            return

        try:
            await self.hass.services.async_call(
                "number",
                "set_value",
                {
                    "entity_id": self._inverter_limit,
                    "value": round(target_pct, 1),
                },
                blocking=True,
            )
        except Exception as err:
            _LOGGER.warning("Failed to write inverter limit: %s", err)
            return
        self._last_write_pct = round(target_pct, 1)
        self._last_write_at = time.monotonic()

    def _snapshot(
        self,
        *,
        status: str,
        pv_w: float,
        imp_w: float,
        exp_w: float,
        voltage_v: float | None,
        tariff_price: float | None,
        current_pct: float,
        target_pct: float,
        target_w: float,
        load_w: float,
        anomaly: bool = False,
        voltage_warning: bool = False,
    ) -> PVLimiterState:
        return PVLimiterState(
            load_w=load_w,
            target_w=target_w,
            target_pct=target_pct,
            current_pct=current_pct,
            pv_w=pv_w,
            grid_import_w=imp_w,
            grid_export_w=exp_w,
            voltage_v=voltage_v,
            tariff_price=tariff_price,
            mode=self._mode,
            enabled=self._enabled,
            status=status,
            curtailment_w=compute_curtailment(current_pct, self._nominal_w, pv_w),
            anomaly=anomaly,
            voltage_warning=voltage_warning,
            last_write_pct=self._last_write_pct,
            last_write_at=self._last_write_at,
        )

    def _initial_state(self) -> PVLimiterState:
        return PVLimiterState(
            load_w=0,
            target_w=0,
            target_pct=100.0,
            current_pct=100.0,
            pv_w=0,
            grid_import_w=0,
            grid_export_w=0,
            voltage_v=None,
            tariff_price=None,
            mode=self._mode,
            enabled=self._enabled,
            status=Status.STARTING,
            curtailment_w=0,
            anomaly=False,
            voltage_warning=False,
            last_write_pct=None,
            last_write_at=None,
        )
