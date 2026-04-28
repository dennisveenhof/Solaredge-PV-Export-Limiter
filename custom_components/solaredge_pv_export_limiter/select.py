"""Operating mode selector for PV Export Limiter."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ALL_MODES, DOMAIN
from .coordinator import PVExportLimiterCoordinator
from .entity import PVLimiterBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PVExportLimiterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PVLimiterModeSelect(coordinator)])


class PVLimiterModeSelect(PVLimiterBaseEntity, SelectEntity):
    """Switch between Normal/Vacation/Negative-price/Wide/Manual/Off."""

    entity_description = SelectEntityDescription(
        key="mode",
        icon="mdi:tune-variant",
    )

    _attr_options = ALL_MODES

    def __init__(self, coordinator: PVExportLimiterCoordinator) -> None:
        super().__init__(coordinator, "mode")

    @property
    def current_option(self) -> str:
        return self.coordinator.mode

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_mode(option)
