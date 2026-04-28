"""Number entities for PV Export Limiter (manual setpoint, hysteresis, nominal)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MAX_HYSTERESIS_PCT,
    MAX_INVERTER_NOMINAL_W,
    MAX_SETPOINT_W,
    MIN_HYSTERESIS_PCT,
    MIN_INVERTER_NOMINAL_W,
    MIN_SETPOINT_W,
)
from .coordinator import PVExportLimiterCoordinator
from .entity import PVLimiterBaseEntity


@dataclass(frozen=True, kw_only=True)
class PVLimiterNumberDescription(NumberEntityDescription):
    """Describes a number entity backed by a coordinator setter."""

    value_fn: Callable[[PVExportLimiterCoordinator], float]
    setter_name: str


NUMBERS: tuple[PVLimiterNumberDescription, ...] = (
    PVLimiterNumberDescription(
        key="setpoint_manual",
        translation_key="setpoint_manual",
        icon="mdi:transmission-tower-export",
        native_min_value=MIN_SETPOINT_W,
        native_max_value=MAX_SETPOINT_W,
        native_step=5,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        value_fn=lambda c: c.setpoint_manual_w,
        setter_name="async_set_setpoint_manual",
    ),
    PVLimiterNumberDescription(
        key="hysteresis",
        translation_key="hysteresis",
        icon="mdi:sine-wave",
        native_min_value=MIN_HYSTERESIS_PCT,
        native_max_value=MAX_HYSTERESIS_PCT,
        native_step=0.1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        value_fn=lambda c: c.hysteresis_pct,
        setter_name="async_set_hysteresis",
    ),
    PVLimiterNumberDescription(
        key="nominal",
        translation_key="nominal",
        icon="mdi:solar-power",
        native_min_value=MIN_INVERTER_NOMINAL_W,
        native_max_value=MAX_INVERTER_NOMINAL_W,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        value_fn=lambda c: c.nominal_w,
        setter_name="async_set_nominal",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PVExportLimiterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PVLimiterNumber(coordinator, desc) for desc in NUMBERS)


class PVLimiterNumber(PVLimiterBaseEntity, NumberEntity):
    """Generic number entity backed by a coordinator setter."""

    entity_description: PVLimiterNumberDescription

    def __init__(
        self,
        coordinator: PVExportLimiterCoordinator,
        description: PVLimiterNumberDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        setter = getattr(self.coordinator, self.entity_description.setter_name)
        await setter(value)
