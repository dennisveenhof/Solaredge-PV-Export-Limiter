"""Common base entity for Solaredge PV Export Limiter platforms."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import PVExportLimiterCoordinator


def _read_manifest_version() -> str:
    try:
        manifest = json.loads((Path(__file__).parent / "manifest.json").read_text())
        return str(manifest.get("version", "unknown"))
    except (OSError, ValueError):
        return "unknown"


_SW_VERSION = _read_manifest_version()


class PVLimiterBaseEntity(CoordinatorEntity[PVExportLimiterCoordinator]):
    """Base class — gives every entity the same device + naming."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PVExportLimiterCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Dennis Veenhof",
            model="PV Export Controller",
            sw_version=_SW_VERSION,
            configuration_url="https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter",
            entry_type=None,
        )
