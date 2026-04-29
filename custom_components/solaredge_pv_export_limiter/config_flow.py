"""Config flow for PV Export Limiter."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .calc import detect_inverter_nominal
from .const import (
    ALL_MODES,
    BUDGET_PERIODS,
    CONF_BUDGET_ENABLED,
    CONF_BUDGET_KWH,
    CONF_BUDGET_NOTIFY_PCT,
    CONF_BUDGET_PERIOD,
    CONF_ENABLED_AT_START,
    CONF_GRID_EXPORT,
    CONF_GRID_IMPORT,
    CONF_GRID_VOLTAGE,
    CONF_GRID_VOLTAGE_L2,
    CONF_GRID_VOLTAGE_L3,
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
    CONF_VACATION_AUTO_DISABLE_DURATION_S,
    CONF_VACATION_AUTO_DISABLE_ENABLED,
    CONF_VACATION_AUTO_DISABLE_IMPORT_W,
    CONF_VOLTAGE_PROTECTION_ENABLED,
    CONF_VOLTAGE_RECOVERY_V,
    CONF_VOLTAGE_WARNING_V,
    DEFAULT_BUDGET_ENABLED,
    DEFAULT_BUDGET_KWH,
    DEFAULT_BUDGET_NOTIFY_PCT,
    DEFAULT_BUDGET_PERIOD,
    DEFAULT_HYSTERESIS_PCT,
    DEFAULT_INVERTER_NOMINAL_W,
    DEFAULT_NAME,
    DEFAULT_SETPOINT_NEGATIVE_PRICE_W,
    DEFAULT_SETPOINT_NORMAL_W,
    DEFAULT_SETPOINT_VACATION_W,
    DEFAULT_SETPOINT_WIDE_W,
    DEFAULT_SMOOTHING_WINDOW_S,
    DEFAULT_TARIFF_HIGH_THRESHOLD_EUR,
    DEFAULT_TARIFF_NEGATIVE_THRESHOLD_EUR,
    DEFAULT_UPDATE_INTERVAL_S,
    DEFAULT_VACATION_AUTO_DISABLE_DURATION_S,
    DEFAULT_VACATION_AUTO_DISABLE_ENABLED,
    DEFAULT_VACATION_AUTO_DISABLE_IMPORT_W,
    DEFAULT_VOLTAGE_RECOVERY_V,
    DEFAULT_VOLTAGE_WARNING_V,
    DOMAIN,
    MAX_HYSTERESIS_PCT,
    MAX_INVERTER_NOMINAL_W,
    MAX_SETPOINT_W,
    MAX_UPDATE_INTERVAL_S,
    MIN_HYSTERESIS_PCT,
    MIN_INVERTER_NOMINAL_W,
    MIN_SETPOINT_W,
    MIN_UPDATE_INTERVAL_S,
    Mode,
)

_LOGGER = logging.getLogger(__name__)


def _power_entity_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power"))


def _energy_price_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="sensor"))


def _voltage_entity_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="sensor", device_class="voltage"))


def _number_selector(min_v: float, max_v: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_v,
            max=max_v,
            step=step,
            unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


def _mode_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=ALL_MODES,
            translation_key="mode",
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _suggest_inverter_nominal(hass: HomeAssistant, entity_id: str) -> int:
    """Inspect the inverter device's model attribute to suggest nominal power."""
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if not entry or not entry.device_id:
        return DEFAULT_INVERTER_NOMINAL_W
    device = dr.async_get(hass).async_get(entry.device_id)
    if not device:
        return DEFAULT_INVERTER_NOMINAL_W
    return detect_inverter_nominal(device.model, fallback_w=DEFAULT_INVERTER_NOMINAL_W)


class PVExportLimiterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Walk the user through wizard steps and create a config entry."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Welcome step — single click to start."""
        # Single instance: allow only one entry per HA install (for now)
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return await self.async_step_inverter()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    async def async_step_inverter(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Pick the SolarEdge AC-power sensor and the writable limit number."""
        errors: dict[str, str] = {}

        if user_input is not None:
            ac_power = user_input[CONF_INVERTER_AC_POWER]
            limit_entity = user_input[CONF_INVERTER_LIMIT]

            if not self.hass.states.get(ac_power):
                errors[CONF_INVERTER_AC_POWER] = "entity_not_found"
            if not self.hass.states.get(limit_entity):
                errors[CONF_INVERTER_LIMIT] = "entity_not_found"
            if not limit_entity.startswith("number."):
                errors[CONF_INVERTER_LIMIT] = "must_be_number_entity"

            if not errors:
                self._data.update(user_input)
                return await self.async_step_grid_meter()

        schema = vol.Schema(
            {
                vol.Required(CONF_INVERTER_AC_POWER): _power_entity_selector(),
                vol.Required(CONF_INVERTER_LIMIT): EntitySelector(
                    EntitySelectorConfig(domain="number")
                ),
            }
        )
        return self.async_show_form(step_id="inverter", data_schema=schema, errors=errors)

    async def async_step_grid_meter(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Pick P1 import + export sensors."""
        errors: dict[str, str] = {}

        if user_input is not None:
            for key in (CONF_GRID_IMPORT, CONF_GRID_EXPORT):
                if not self.hass.states.get(user_input[key]):
                    errors[key] = "entity_not_found"
            if user_input[CONF_GRID_IMPORT] == user_input[CONF_GRID_EXPORT]:
                errors["base"] = "import_export_same"

            if not errors:
                self._data.update(user_input)
                return await self.async_step_inverter_params()

        schema = vol.Schema(
            {
                vol.Required(CONF_GRID_IMPORT): _power_entity_selector(),
                vol.Required(CONF_GRID_EXPORT): _power_entity_selector(),
            }
        )
        return self.async_show_form(step_id="grid_meter", data_schema=schema, errors=errors)

    async def async_step_inverter_params(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Inverter nominal power + control loop tuning."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_optional()

        suggested_nominal = _suggest_inverter_nominal(self.hass, self._data[CONF_INVERTER_AC_POWER])

        schema = vol.Schema(
            {
                vol.Required(CONF_INVERTER_NOMINAL_W, default=suggested_nominal): _number_selector(
                    MIN_INVERTER_NOMINAL_W, MAX_INVERTER_NOMINAL_W, 100, "W"
                ),
                vol.Required(
                    CONF_UPDATE_INTERVAL_S, default=DEFAULT_UPDATE_INTERVAL_S
                ): _number_selector(MIN_UPDATE_INTERVAL_S, MAX_UPDATE_INTERVAL_S, 1, "s"),
                vol.Required(
                    CONF_SMOOTHING_WINDOW_S, default=DEFAULT_SMOOTHING_WINDOW_S
                ): _number_selector(2, 30, 1, "s"),
                vol.Required(CONF_HYSTERESIS_PCT, default=DEFAULT_HYSTERESIS_PCT): _number_selector(
                    MIN_HYSTERESIS_PCT, MAX_HYSTERESIS_PCT, 0.1, "%"
                ),
            }
        )
        return self.async_show_form(step_id="inverter_params", data_schema=schema)

    async def async_step_optional(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Optional voltage protection and tariff awareness."""
        if user_input is not None:
            # Strip empty strings to None
            for key in (
                CONF_GRID_VOLTAGE,
                CONF_GRID_VOLTAGE_L2,
                CONF_GRID_VOLTAGE_L3,
                CONF_TARIFF_PRICE,
            ):
                if not user_input.get(key):
                    user_input.pop(key, None)
            self._data.update(user_input)
            return await self.async_step_setpoints()

        schema = vol.Schema(
            {
                vol.Optional(CONF_GRID_VOLTAGE): _voltage_entity_selector(),
                vol.Optional(CONF_GRID_VOLTAGE_L2): _voltage_entity_selector(),
                vol.Optional(CONF_GRID_VOLTAGE_L3): _voltage_entity_selector(),
                vol.Required(CONF_VOLTAGE_PROTECTION_ENABLED, default=False): bool,
                vol.Required(
                    CONF_VOLTAGE_WARNING_V, default=DEFAULT_VOLTAGE_WARNING_V
                ): _number_selector(220, 270, 0.5, "V"),
                vol.Required(
                    CONF_VOLTAGE_RECOVERY_V, default=DEFAULT_VOLTAGE_RECOVERY_V
                ): _number_selector(200, 260, 0.5, "V"),
                vol.Optional(CONF_TARIFF_PRICE): _energy_price_selector(),
                vol.Required(CONF_TARIFF_ENABLED, default=False): bool,
                vol.Required(
                    CONF_TARIFF_NEGATIVE_THRESHOLD,
                    default=DEFAULT_TARIFF_NEGATIVE_THRESHOLD_EUR,
                ): _number_selector(-1.0, 1.0, 0.01, "EUR"),
                vol.Required(
                    CONF_TARIFF_HIGH_THRESHOLD,
                    default=DEFAULT_TARIFF_HIGH_THRESHOLD_EUR,
                ): _number_selector(0.0, 2.0, 0.01, "EUR"),
            }
        )
        return self.async_show_form(step_id="optional", data_schema=schema)

    async def async_step_setpoints(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Per-mode setpoints in W."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_finish()

        sp_schema = lambda default: _number_selector(  # noqa: E731
            MIN_SETPOINT_W, MAX_SETPOINT_W, 5, "W"
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_SETPOINT_NORMAL, default=DEFAULT_SETPOINT_NORMAL_W): sp_schema(
                    DEFAULT_SETPOINT_NORMAL_W
                ),
                vol.Required(
                    CONF_SETPOINT_VACATION, default=DEFAULT_SETPOINT_VACATION_W
                ): sp_schema(DEFAULT_SETPOINT_VACATION_W),
                vol.Required(
                    CONF_SETPOINT_NEGATIVE_PRICE,
                    default=DEFAULT_SETPOINT_NEGATIVE_PRICE_W,
                ): sp_schema(DEFAULT_SETPOINT_NEGATIVE_PRICE_W),
                vol.Required(CONF_SETPOINT_WIDE, default=DEFAULT_SETPOINT_WIDE_W): sp_schema(
                    DEFAULT_SETPOINT_WIDE_W
                ),
                vol.Required(CONF_INITIAL_MODE, default=Mode.NORMAL): _mode_selector(),
                vol.Required(CONF_ENABLED_AT_START, default=True): bool,
            }
        )
        return self.async_show_form(step_id="setpoints", data_schema=schema)

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Optional notify target + final create."""
        if user_input is not None:
            if user_input.get(CONF_NOTIFY_TARGET):
                self._data[CONF_NOTIFY_TARGET] = user_input[CONF_NOTIFY_TARGET]
            return self.async_create_entry(title=DEFAULT_NAME, data=self._data)

        schema = vol.Schema(
            {
                vol.Optional(CONF_NOTIFY_TARGET): TextSelector(
                    TextSelectorConfig(prefix="notify.")
                ),
            }
        )
        return self.async_show_form(step_id="finish", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PVExportLimiterOptionsFlow(config_entry)


class PVExportLimiterOptionsFlow(OptionsFlow):
    """Allow editing every wizard field after install — two steps."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 1 — re-select sensors with clear descriptions."""
        errors: dict[str, str] = {}
        merged = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            for key in (
                CONF_INVERTER_AC_POWER,
                CONF_INVERTER_LIMIT,
                CONF_GRID_IMPORT,
                CONF_GRID_EXPORT,
            ):
                if not self.hass.states.get(user_input.get(key, "")):
                    errors[key] = "entity_not_found"
            if not user_input.get(CONF_INVERTER_LIMIT, "").startswith("number."):
                errors[CONF_INVERTER_LIMIT] = "must_be_number_entity"
            if user_input.get(CONF_GRID_IMPORT) == user_input.get(CONF_GRID_EXPORT):
                errors["base"] = "import_export_same"

            if not errors:
                self._options.update(user_input)
                return await self.async_step_settings()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_INVERTER_AC_POWER,
                    default=merged.get(CONF_INVERTER_AC_POWER, vol.UNDEFINED),
                ): _power_entity_selector(),
                vol.Required(
                    CONF_INVERTER_LIMIT,
                    default=merged.get(CONF_INVERTER_LIMIT, vol.UNDEFINED),
                ): EntitySelector(EntitySelectorConfig(domain="number")),
                vol.Required(
                    CONF_INVERTER_NOMINAL_W,
                    default=merged.get(CONF_INVERTER_NOMINAL_W, DEFAULT_INVERTER_NOMINAL_W),
                ): _number_selector(MIN_INVERTER_NOMINAL_W, MAX_INVERTER_NOMINAL_W, 100, "W"),
                vol.Required(
                    CONF_GRID_IMPORT,
                    default=merged.get(CONF_GRID_IMPORT, vol.UNDEFINED),
                ): _power_entity_selector(),
                vol.Required(
                    CONF_GRID_EXPORT,
                    default=merged.get(CONF_GRID_EXPORT, vol.UNDEFINED),
                ): _power_entity_selector(),
                vol.Optional(
                    CONF_GRID_VOLTAGE,
                    description={"suggested_value": merged.get(CONF_GRID_VOLTAGE)},
                ): _voltage_entity_selector(),
                vol.Optional(
                    CONF_GRID_VOLTAGE_L2,
                    description={"suggested_value": merged.get(CONF_GRID_VOLTAGE_L2)},
                ): _voltage_entity_selector(),
                vol.Optional(
                    CONF_GRID_VOLTAGE_L3,
                    description={"suggested_value": merged.get(CONF_GRID_VOLTAGE_L3)},
                ): _voltage_entity_selector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 2 — setpoints and control loop parameters."""
        merged = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SETPOINT_NORMAL,
                    default=merged.get(CONF_SETPOINT_NORMAL, DEFAULT_SETPOINT_NORMAL_W),
                ): _number_selector(MIN_SETPOINT_W, MAX_SETPOINT_W, 5, "W"),
                vol.Required(
                    CONF_SETPOINT_VACATION,
                    default=merged.get(CONF_SETPOINT_VACATION, DEFAULT_SETPOINT_VACATION_W),
                ): _number_selector(MIN_SETPOINT_W, MAX_SETPOINT_W, 5, "W"),
                vol.Required(
                    CONF_SETPOINT_NEGATIVE_PRICE,
                    default=merged.get(
                        CONF_SETPOINT_NEGATIVE_PRICE, DEFAULT_SETPOINT_NEGATIVE_PRICE_W
                    ),
                ): _number_selector(MIN_SETPOINT_W, MAX_SETPOINT_W, 5, "W"),
                vol.Required(
                    CONF_SETPOINT_WIDE,
                    default=merged.get(CONF_SETPOINT_WIDE, DEFAULT_SETPOINT_WIDE_W),
                ): _number_selector(MIN_SETPOINT_W, MAX_SETPOINT_W, 5, "W"),
                vol.Required(
                    CONF_HYSTERESIS_PCT,
                    default=merged.get(CONF_HYSTERESIS_PCT, DEFAULT_HYSTERESIS_PCT),
                ): _number_selector(MIN_HYSTERESIS_PCT, MAX_HYSTERESIS_PCT, 0.1, "%"),
                vol.Required(
                    CONF_UPDATE_INTERVAL_S,
                    default=merged.get(CONF_UPDATE_INTERVAL_S, DEFAULT_UPDATE_INTERVAL_S),
                ): _number_selector(MIN_UPDATE_INTERVAL_S, MAX_UPDATE_INTERVAL_S, 1, "s"),
                vol.Required(
                    CONF_SMOOTHING_WINDOW_S,
                    default=merged.get(CONF_SMOOTHING_WINDOW_S, DEFAULT_SMOOTHING_WINDOW_S),
                ): _number_selector(2, 30, 1, "s"),
                vol.Required(
                    CONF_VACATION_AUTO_DISABLE_ENABLED,
                    default=merged.get(
                        CONF_VACATION_AUTO_DISABLE_ENABLED,
                        DEFAULT_VACATION_AUTO_DISABLE_ENABLED,
                    ),
                ): bool,
                vol.Required(
                    CONF_VACATION_AUTO_DISABLE_IMPORT_W,
                    default=merged.get(
                        CONF_VACATION_AUTO_DISABLE_IMPORT_W,
                        DEFAULT_VACATION_AUTO_DISABLE_IMPORT_W,
                    ),
                ): _number_selector(100, 5000, 50, "W"),
                vol.Required(
                    CONF_VACATION_AUTO_DISABLE_DURATION_S,
                    default=merged.get(
                        CONF_VACATION_AUTO_DISABLE_DURATION_S,
                        DEFAULT_VACATION_AUTO_DISABLE_DURATION_S,
                    ),
                ): _number_selector(10, 600, 5, "s"),
                vol.Required(
                    CONF_VOLTAGE_PROTECTION_ENABLED,
                    default=merged.get(CONF_VOLTAGE_PROTECTION_ENABLED, False),
                ): bool,
                vol.Required(
                    CONF_VOLTAGE_WARNING_V,
                    default=merged.get(CONF_VOLTAGE_WARNING_V, DEFAULT_VOLTAGE_WARNING_V),
                ): _number_selector(220, 270, 0.5, "V"),
                vol.Required(
                    CONF_TARIFF_ENABLED,
                    default=merged.get(CONF_TARIFF_ENABLED, False),
                ): bool,
                vol.Required(
                    CONF_TARIFF_NEGATIVE_THRESHOLD,
                    default=merged.get(
                        CONF_TARIFF_NEGATIVE_THRESHOLD, DEFAULT_TARIFF_NEGATIVE_THRESHOLD_EUR
                    ),
                ): _number_selector(-1.0, 1.0, 0.01, "EUR"),
                vol.Required(
                    CONF_TARIFF_HIGH_THRESHOLD,
                    default=merged.get(
                        CONF_TARIFF_HIGH_THRESHOLD, DEFAULT_TARIFF_HIGH_THRESHOLD_EUR
                    ),
                ): _number_selector(0.0, 2.0, 0.01, "EUR"),
                vol.Required(
                    CONF_BUDGET_ENABLED,
                    default=merged.get(CONF_BUDGET_ENABLED, DEFAULT_BUDGET_ENABLED),
                ): bool,
                vol.Required(
                    CONF_BUDGET_KWH,
                    default=merged.get(CONF_BUDGET_KWH, DEFAULT_BUDGET_KWH),
                ): _number_selector(0.1, 10000.0, 0.1, "kWh"),
                vol.Required(
                    CONF_BUDGET_PERIOD,
                    default=merged.get(CONF_BUDGET_PERIOD, DEFAULT_BUDGET_PERIOD),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(BUDGET_PERIODS),
                        translation_key="budget_period",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_BUDGET_NOTIFY_PCT,
                    default=merged.get(CONF_BUDGET_NOTIFY_PCT, DEFAULT_BUDGET_NOTIFY_PCT),
                ): _number_selector(0, 100, 5, "%"),
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)
