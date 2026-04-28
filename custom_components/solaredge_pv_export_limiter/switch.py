"""Master on/off switch for PV Export Limiter."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PVExportLimiterCoordinator
from .entity import PVLimiterBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PVExportLimiterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PVLimiterActiveSwitch(coordinator)])


class PVLimiterActiveSwitch(PVLimiterBaseEntity, SwitchEntity):
    """Toggle the limiter on or off."""

    entity_description = SwitchEntityDescription(
        key="limiter_active",
        icon="mdi:auto-fix",
    )

    def __init__(self, coordinator: PVExportLimiterCoordinator) -> None:
        super().__init__(coordinator, "limiter_active")

    @property
    def is_on(self) -> bool:
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_enabled(False)
