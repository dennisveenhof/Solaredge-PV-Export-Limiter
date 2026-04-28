"""Binary sensors for anomaly detection and voltage warning."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PVExportLimiterCoordinator, PVLimiterState
from .entity import PVLimiterBaseEntity


@dataclass(frozen=True, kw_only=True)
class PVLimiterBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[PVLimiterState], bool]


BINARY_SENSORS: tuple[PVLimiterBinaryDescription, ...] = (
    PVLimiterBinaryDescription(
        key="anomaly",
        translation_key="anomaly",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle-outline",
        is_on_fn=lambda s: bool(s.anomaly),
    ),
    PVLimiterBinaryDescription(
        key="voltage_warning",
        translation_key="voltage_warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:flash-alert",
        is_on_fn=lambda s: bool(s.voltage_warning),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PVExportLimiterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PVLimiterBinarySensor(coordinator, desc) for desc in BINARY_SENSORS
    )


class PVLimiterBinarySensor(PVLimiterBaseEntity, BinarySensorEntity):
    entity_description: PVLimiterBinaryDescription

    def __init__(
        self,
        coordinator: PVExportLimiterCoordinator,
        description: PVLimiterBinaryDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            return False
        return self.entity_description.is_on_fn(self.coordinator.data)
