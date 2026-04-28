"""PV Export Limiter integration."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ALL_MODES,
    DOMAIN,
    LOVELACE_CARD_URL,
    SERVICE_RECALCULATE,
    SERVICE_RESET_TO_100,
    SERVICE_SET_MODE,
)
from .coordinator import PVExportLimiterCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the bundled Lovelace card JS file."""
    card_path = Path(__file__).parent / "lovelace" / "pv-limiter-card.js"
    if card_path.is_file():
        try:
            hass.http.register_static_path(
                LOVELACE_CARD_URL, str(card_path), cache_headers=False
            )
        except Exception as err:
            _LOGGER.warning("Could not register Lovelace card static path: %s", err)
    return True


async def _async_register_card_resource(hass: HomeAssistant) -> None:
    """Add the card JS to Lovelace resources (idempotent, persists across restarts)."""
    try:
        lovelace = hass.data.get("lovelace")
        if lovelace:
            resources = lovelace.get("resources")
            if resources is not None:
                await resources.async_load()
                existing = {r.get("url") for r in resources.async_items()}
                if LOVELACE_CARD_URL not in existing:
                    await resources.async_create_item(
                        {"res_type": "module", "url": LOVELACE_CARD_URL}
                    )
                return
        # Fallback: YAML-mode Lovelace or older HA
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, LOVELACE_CARD_URL)
    except Exception as err:
        _LOGGER.warning("Could not register Lovelace card resource: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a PV Export Limiter entry."""
    hass.data.setdefault(DOMAIN, {})

    await _async_register_card_resource(hass)

    coordinator = PVExportLimiterCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: PVExportLimiterCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

        if not hass.data[DOMAIN]:
            for service in (SERVICE_RECALCULATE, SERVICE_RESET_TO_100, SERVICE_SET_MODE):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register the integration's custom services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_RECALCULATE):
        return

    async def _handle_recalculate(call: ServiceCall) -> None:
        for coordinator in hass.data[DOMAIN].values():
            await coordinator.async_request_refresh()

    async def _handle_reset_to_100(call: ServiceCall) -> None:
        for coordinator in hass.data[DOMAIN].values():
            await coordinator.async_reset_limit_to_100()

    async def _handle_set_mode(call: ServiceCall) -> None:
        mode = call.data["mode"]
        for coordinator in hass.data[DOMAIN].values():
            await coordinator.async_set_mode(mode)

    hass.services.async_register(DOMAIN, SERVICE_RECALCULATE, _handle_recalculate)
    hass.services.async_register(DOMAIN, SERVICE_RESET_TO_100, _handle_reset_to_100)
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MODE,
        _handle_set_mode,
        schema=vol.Schema({vol.Required("mode"): vol.In(ALL_MODES)}),
    )
