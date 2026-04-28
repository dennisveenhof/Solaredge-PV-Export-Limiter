"""Sensor entities for PV Export Limiter (status, computed values, curtailment)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import ALL_MODES, DOMAIN
from .coordinator import PVExportLimiterCoordinator, PVLimiterState
from .entity import PVLimiterBaseEntity


@dataclass(frozen=True, kw_only=True)
class PVLimiterSensorDescription(SensorEntityDescription):
    """Sensor that pulls a single attribute from the coordinator state."""

    value_fn: Callable[[PVLimiterState], float | str | None]


_POWER_SENSOR_DEFAULTS = {
    "device_class": SensorDeviceClass.POWER,
    "state_class": SensorStateClass.MEASUREMENT,
    "native_unit_of_measurement": UnitOfPower.WATT,
    "suggested_display_precision": 0,
}

SENSORS: tuple[PVLimiterSensorDescription, ...] = (
    PVLimiterSensorDescription(
        key="load",
        translation_key="load",
        icon="mdi:home-lightning-bolt",
        value_fn=lambda s: round(s.load_w),
        **_POWER_SENSOR_DEFAULTS,
    ),
    PVLimiterSensorDescription(
        key="target_w",
        translation_key="target_w",
        icon="mdi:solar-panel",
        value_fn=lambda s: round(s.target_w),
        **_POWER_SENSOR_DEFAULTS,
    ),
    PVLimiterSensorDescription(
        key="target_pct",
        translation_key="target_pct",
        icon="mdi:percent-outline",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: round(s.target_pct, 1),
    ),
    PVLimiterSensorDescription(
        key="current_pct",
        translation_key="current_pct",
        icon="mdi:gauge",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: round(s.current_pct, 1),
    ),
    PVLimiterSensorDescription(
        key="curtailment_w",
        translation_key="curtailment_w",
        icon="mdi:waveform",
        value_fn=lambda s: round(s.curtailment_w),
        **_POWER_SENSOR_DEFAULTS,
    ),
    PVLimiterSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:information-outline",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "ok",
            "disabled",
            "no_pv",
            "sensor_loss",
            "voltage_high",
            "write_error",
            "starting",
        ],
        value_fn=lambda s: str(s.status),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PVExportLimiterCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        PVLimiterSensor(coordinator, desc) for desc in SENSORS
    ]
    entities.append(PVLimiterCurtailmentEnergy(coordinator))
    async_add_entities(entities)


class PVLimiterSensor(PVLimiterBaseEntity, SensorEntity):
    """Generic sensor pulling from the coordinator state snapshot."""

    entity_description: PVLimiterSensorDescription

    def __init__(
        self,
        coordinator: PVExportLimiterCoordinator,
        description: PVLimiterSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class PVLimiterCurtailmentEnergy(PVLimiterBaseEntity, SensorEntity):
    """Integrate curtailment power into kWh (Riemann sum, left method)."""

    _attr_translation_key = "curtailment_kwh"
    _attr_icon = "mdi:counter"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: PVExportLimiterCoordinator) -> None:
        super().__init__(coordinator, "curtailment_kwh")
        self._kwh_total = 0.0
        self._last_w: float | None = None
        self._last_at = utcnow()

    @property
    def native_value(self) -> float:
        if self.coordinator.data is None:
            return round(self._kwh_total, 4)
        now = utcnow()
        current_w = max(0.0, float(self.coordinator.data.curtailment_w))
        if self._last_w is not None:
            elapsed_h = (now - self._last_at).total_seconds() / 3600.0
            self._kwh_total += (self._last_w / 1000.0) * elapsed_h
        self._last_w = current_w
        self._last_at = now
        return round(self._kwh_total, 4)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        if self.coordinator.data is None:
            return {}
        return {
            "current_curtailment_w": round(self.coordinator.data.curtailment_w),
            "active_mode": self.coordinator.data.mode,
            "available_modes": ALL_MODES,
        }
