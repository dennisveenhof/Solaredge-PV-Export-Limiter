"""Constants for Solaredge PV Export Limiter."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "solaredge_pv_export_limiter"
DEFAULT_NAME: Final = "Solaredge PV Export Limiter"

# ─── Control loop tuning ──────────────────────────────────────────────────
DEFAULT_UPDATE_INTERVAL_S: Final = 10
MIN_UPDATE_INTERVAL_S: Final = 5
MAX_UPDATE_INTERVAL_S: Final = 60

DEFAULT_SMOOTHING_WINDOW_S: Final = 8
DEFAULT_HYSTERESIS_PCT: Final = 1.5
MIN_HYSTERESIS_PCT: Final = 0.5
MAX_HYSTERESIS_PCT: Final = 5.0

# ─── Inverter ─────────────────────────────────────────────────────────────
DEFAULT_INVERTER_NOMINAL_W: Final = 4000
MIN_INVERTER_NOMINAL_W: Final = 1000
MAX_INVERTER_NOMINAL_W: Final = 10000

INVERTER_MODEL_NOMINAL_MAP: Final[dict[str, int]] = {
    "SE3K": 3000,
    "SE3000": 3000,
    "SE3680": 3680,
    "SE4K": 4000,
    "SE4000": 4000,
    "SE5K": 5000,
    "SE5000": 5000,
    "SE6K": 6000,
    "SE6000": 6000,
    "SE7K": 7000,
    "SE8K": 8000,
    "SE10K": 10000,
}

# ─── Setpoints (W) ────────────────────────────────────────────────────────
DEFAULT_SETPOINT_NORMAL_W: Final = 50
DEFAULT_SETPOINT_VACATION_W: Final = 0
DEFAULT_SETPOINT_NEGATIVE_PRICE_W: Final = 0
DEFAULT_SETPOINT_WIDE_W: Final = 200
DEFAULT_SETPOINT_MANUAL_W: Final = 50

MIN_SETPOINT_W: Final = 0
MAX_SETPOINT_W: Final = 1000

# ─── Event triggers ───────────────────────────────────────────────────────
EVENT_EXPORT_THRESHOLD_W: Final = 200
EVENT_IMPORT_THRESHOLD_W: Final = 500
EVENT_DEBOUNCE_S: Final = 3

# ─── Anomaly detection ────────────────────────────────────────────────────
ANOMALY_EXPORT_THRESHOLD_W: Final = 300
ANOMALY_DURATION_S: Final = 60
ANOMALY_PV_MIN_W: Final = 500  # only consider it anomaly if PV is producing

# ─── Voltage protection ───────────────────────────────────────────────────
DEFAULT_VOLTAGE_WARNING_V: Final = 250.0
DEFAULT_VOLTAGE_RECOVERY_V: Final = 240.0
VOLTAGE_PROTECTION_DURATION_S: Final = 30

# ─── Tariff ───────────────────────────────────────────────────────────────
DEFAULT_TARIFF_NEGATIVE_THRESHOLD_EUR: Final = 0.0
DEFAULT_TARIFF_HIGH_THRESHOLD_EUR: Final = 0.30

# ─── Failsafes ────────────────────────────────────────────────────────────
SENSOR_LOSS_GRACE_PERIOD_S: Final = 120
PV_OFF_THRESHOLD_W: Final = 10
PV_OFF_DURATION_S: Final = 300

# ─── Vacation auto-disable ────────────────────────────────────────────────
# When vacation mode is active and grid import stays above this threshold for
# the duration below, assume someone is actually home and switch to normal.
DEFAULT_VACATION_AUTO_DISABLE_ENABLED: Final = True
DEFAULT_VACATION_AUTO_DISABLE_IMPORT_W: Final = 600
DEFAULT_VACATION_AUTO_DISABLE_DURATION_S: Final = 60


class Mode(StrEnum):
    """Operating modes."""

    NORMAL = "normal"
    VACATION = "vacation"
    NEGATIVE_PRICE = "negative_price"
    WIDE = "wide"
    MANUAL = "manual"
    OFF = "off"


ALL_MODES: Final = [m.value for m in Mode]

MODE_DEFAULT_SETPOINTS_W: Final[dict[str, int]] = {
    Mode.NORMAL: DEFAULT_SETPOINT_NORMAL_W,
    Mode.VACATION: DEFAULT_SETPOINT_VACATION_W,
    Mode.NEGATIVE_PRICE: DEFAULT_SETPOINT_NEGATIVE_PRICE_W,
    Mode.WIDE: DEFAULT_SETPOINT_WIDE_W,
    Mode.MANUAL: DEFAULT_SETPOINT_MANUAL_W,
}


class Status(StrEnum):
    """Coordinator status values."""

    OK = "ok"
    DISABLED = "disabled"
    NO_PV = "no_pv"
    SENSOR_LOSS = "sensor_loss"
    VOLTAGE_HIGH = "voltage_high"
    WRITE_ERROR = "write_error"
    STARTING = "starting"
    BUDGET_FREE = "budget_free"
    BUDGET_EXHAUSTED = "budget_exhausted"


# ─── Config flow / options keys ───────────────────────────────────────────
CONF_INVERTER_AC_POWER: Final = "inverter_ac_power_entity"
CONF_INVERTER_LIMIT: Final = "inverter_limit_entity"
CONF_GRID_IMPORT: Final = "grid_import_entity"
CONF_GRID_EXPORT: Final = "grid_export_entity"
CONF_GRID_VOLTAGE: Final = "grid_voltage_entity"
CONF_GRID_VOLTAGE_L2: Final = "grid_voltage_l2_entity"
CONF_GRID_VOLTAGE_L3: Final = "grid_voltage_l3_entity"
CONF_TARIFF_PRICE: Final = "tariff_price_entity"

CONF_INVERTER_NOMINAL_W: Final = "inverter_nominal_w"
CONF_UPDATE_INTERVAL_S: Final = "update_interval_s"
CONF_SMOOTHING_WINDOW_S: Final = "smoothing_window_s"
CONF_HYSTERESIS_PCT: Final = "hysteresis_pct"

CONF_SETPOINT_NORMAL: Final = "setpoint_normal_w"
CONF_SETPOINT_VACATION: Final = "setpoint_vacation_w"
CONF_SETPOINT_NEGATIVE_PRICE: Final = "setpoint_negative_price_w"
CONF_SETPOINT_WIDE: Final = "setpoint_wide_w"

CONF_VOLTAGE_WARNING_V: Final = "voltage_warning_v"
CONF_VOLTAGE_RECOVERY_V: Final = "voltage_recovery_v"
CONF_VOLTAGE_PROTECTION_ENABLED: Final = "voltage_protection_enabled"

CONF_TARIFF_ENABLED: Final = "tariff_enabled"
CONF_TARIFF_NEGATIVE_THRESHOLD: Final = "tariff_negative_threshold"
CONF_TARIFF_HIGH_THRESHOLD: Final = "tariff_high_threshold"

CONF_NOTIFY_TARGET: Final = "notify_target"
CONF_INITIAL_MODE: Final = "initial_mode"
CONF_ENABLED_AT_START: Final = "enabled_at_start"

CONF_VACATION_AUTO_DISABLE_ENABLED: Final = "vacation_auto_disable_enabled"
CONF_VACATION_AUTO_DISABLE_IMPORT_W: Final = "vacation_auto_disable_import_w"
CONF_VACATION_AUTO_DISABLE_DURATION_S: Final = "vacation_auto_disable_duration_s"

# ─── Export budget ────────────────────────────────────────────────────────
CONF_BUDGET_ENABLED: Final = "budget_enabled"
CONF_BUDGET_KWH: Final = "budget_kwh"
CONF_BUDGET_PERIOD: Final = "budget_period"
CONF_BUDGET_NOTIFY_PCT: Final = "budget_notify_pct"

BUDGET_PERIOD_DAY: Final = "day"
BUDGET_PERIOD_MONTH: Final = "month"
BUDGET_PERIOD_YEAR: Final = "year"
BUDGET_PERIODS: Final = (BUDGET_PERIOD_DAY, BUDGET_PERIOD_MONTH, BUDGET_PERIOD_YEAR)

DEFAULT_BUDGET_ENABLED: Final = False
DEFAULT_BUDGET_KWH: Final = 10.0
DEFAULT_BUDGET_PERIOD: Final = BUDGET_PERIOD_DAY
DEFAULT_BUDGET_NOTIFY_PCT: Final = 80

# ─── Services ─────────────────────────────────────────────────────────────
SERVICE_RECALCULATE: Final = "recalculate"
SERVICE_RESET_TO_100: Final = "reset_to_100"
SERVICE_SET_MODE: Final = "set_mode"

# ─── Lovelace card ────────────────────────────────────────────────────────
LOVELACE_CARD_URL: Final = f"/api/{DOMAIN}/pv-limiter-card.js"

# ─── Curtailment ──────────────────────────────────────────────────────────
CURTAILMENT_DETECT_FRACTION: Final = 0.05
CURTAILMENT_LIMIT_THRESHOLD_PCT: Final = 99.0
