# Architecture (for contributors)

## Component diagram

```
┌─ Home Assistant Core ─────────────────────────────────────────┐
│                                                               │
│  ┌──────────────────────┐    ┌──────────────────────┐         │
│  │ solaredge_modbus_    │    │ dsmr (P1) /          │         │
│  │ multi (HACS)         │    │ DSMR Reader          │         │
│  │                      │    │                      │         │
│  │ • ac_power           │    │ • power_consumption  │         │
│  │ • active_power_limit │    │ • power_production   │         │
│  │   (RW number)        │    │ • voltage (opt.)     │         │
│  └──────────┬───────────┘    └──────────┬───────────┘         │
│             │                           │                     │
│             │     state events          │                     │
│             ▼                           ▼                     │
│  ┌────────────────────────────────────────────────────┐       │
│  │  custom_components/solaredge_pv_export_limiter/    │       │
│  │                                                    │       │
│  │  config_flow.py  →  ConfigEntry                    │       │
│  │                                                    │       │
│  │  coordinator.py  ─  PVExportLimiterCoordinator     │       │
│  │  ├─ helpers.SmoothingBuffer  (8s rolling mean)     │       │
│  │  ├─ calc.py                  (pure functions)      │       │
│  │  ├─ control loop             (10s + state events)  │       │
│  │  └─ failsafes                (sensor loss, V, etc) │       │
│  │           │                                        │       │
│  │           ▼ (PVLimiterState snapshot)              │       │
│  │  switch / select / number / sensor / binary_sensor │       │
│  │  + lovelace card (auto-served at /api/.../*.js)    │       │
│  └────────────────────────────────────────────────────┘       │
│                              │                                │
│                              │ number.set_value               │
│                              ▼                                │
│           number.solaredge_*_active_power_limit               │
└───────────────────────────────────────────────────────────────┘
                               │
                               │ Modbus TCP
                               ▼
                       SolarEdge inverter
```

## File responsibilities

| File | Purpose | HA imports? |
|---|---|---|
| `__init__.py` | Setup/teardown of config entries; service registration; Lovelace card mount. | yes |
| `manifest.json` | Integration metadata. | n/a |
| `const.py` | All constants — domain, defaults, mode keys, conf keys. Single source of truth. | no |
| `calc.py` | Pure functions: power balance, target %, curtailment estimation, model lookup. | **no** (testable standalone) |
| `helpers.py` | `SmoothingBuffer`, `TimedFlag`, `safe_float`, `to_watts`. Pure. | **no** |
| `config_flow.py` | 7-step wizard + OptionsFlow. | yes |
| `coordinator.py` | `DataUpdateCoordinator`. Reads sensors, computes target, writes limit, manages failsafes. | yes |
| `entity.py` | `PVLimiterBaseEntity` base class — common device info, naming, unique_id. | yes |
| `switch.py` | Master on/off. | yes |
| `select.py` | Mode selector. | yes |
| `number.py` | Manual setpoint, hysteresis, nominal — generic table-driven. | yes |
| `sensor.py` | Status, computed values, curtailment + kWh integrator. | yes |
| `binary_sensor.py` | Anomaly + voltage warning. | yes |
| `services.yaml` | Service descriptions for `recalculate`, `reset_to_100`, `set_mode`. | n/a |
| `strings.json` + `translations/*.json` | UI strings (English source + Dutch). | n/a |
| `lovelace/pv-limiter-card.js` | Self-contained vanilla-JS card. | n/a |

## Control loop sequence

Per tick (every `update_interval_s`, default 10 s):

```
1. Read raw sensor states  ──▶ pv_w, import_w, export_w, voltage_v?, tariff_price?
2. Failsafe: sensor loss?  ──▶ if any None for 2 min, force limit=100%, return
3. Smooth values           ──▶ pv/imp/exp 8s rolling means
4. Tariff handling         ──▶ if enabled & price < threshold: switch mode
5. Disabled / OFF mode?    ──▶ force limit=100%, return
6. Voltage protection      ──▶ if V > 250V for 30s: target_pct=0
7. Compute load            ──▶ pv + import - export
8. Compute target_w        ──▶ load + setpoint(mode)
9. Compute target_pct      ──▶ clamp((target_w / nominal) * 100, 0, 100)
10. Hysteresis check       ──▶ |target - current| > hysteresis?
11. Write inverter limit   ──▶ number.set_value
12. Anomaly detection      ──▶ export > 300W for 60s while enabled?
13. Update state snapshot  ──▶ entities re-render
```

In addition: state-change events on `grid_export > 200W` or `grid_import > 500W` trigger
an immediate refresh (debounced to 3 s minimum interval).

## Why DataUpdateCoordinator

We use `DataUpdateCoordinator` even though we have a single source of truth (the
coordinator owns the state). Reason: it gives us:

- Periodic ticking, configurable interval
- Event-driven refresh (`async_request_refresh`)
- Standard listener model for entities
- Built-in error handling and `UpdateFailed` semantics
- HA-style logging integration

The `data` attribute holds a `PVLimiterState` dataclass — entities read attributes
from this snapshot instead of accessing internal coordinator state directly.

## State management

The coordinator holds:

| State | Purpose | Persisted? |
|---|---|---|
| `_mode` | Active operating mode | mirrored to ConfigEntry on write via select entity |
| `_enabled` | Master toggle | mirrored via switch entity |
| `_smoothing` | Rolling buffer | in-memory only |
| `_anomaly_flag` | Sustained-condition timer | in-memory |
| `_voltage_warning_flag` | Same | in-memory |
| `_sensor_loss_flag` | Same | in-memory |
| `_last_write_pct` / `_at` | Last successful write | in-memory |
| `_user_mode_override` | Whether user manually set mode (vs tariff override) | in-memory |

After HA restart, all in-memory state resets. The HA-startup listener forces a
limit reset to 100% to prevent acting on stale data.

## Adding a new mode

1. Add a value to `Mode` enum in `const.py`
2. Add a default to `MODE_DEFAULT_SETPOINTS_W`
3. Update `effective_setpoint_w` in `calc.py` (delegate, no HA imports)
4. Add a translation key in `strings.json` + `translations/*.json`
5. (Optional) wire to `_maybe_switch_mode_for_tariff` if it should auto-trigger

## Adding a new sensor

1. Add `PVLimiterSensorDescription` entry to `SENSORS` in `sensor.py`
2. Update `PVLimiterState` dataclass in `coordinator.py` if new field needed
3. Compute the new field in `_compute_state` and `_snapshot`
4. Add translation keys for `entity.sensor.<key>`

## Tests

| Test file | Subject | HA needed? |
|---|---|---|
| `test_calc.py` | `calc.py` pure functions — full branch coverage | **no** |
| `test_helpers.py` | `helpers.py` — `SmoothingBuffer`, `TimedFlag`, etc. | **no** |
| `test_config_flow.py` | (TODO v0.2) wizard happy/sad paths | yes |
| `test_coordinator.py` | (TODO v0.2) control loop integration | yes |

Run: `pytest`. CI matrix tests Python 3.12 and 3.13.

## Code style

- `ruff` for linting and formatting (config in `pyproject.toml`)
- 100-char line length
- Type hints on all public APIs
- No comments unless explaining *why*; well-named identifiers explain *what*

## Release process

1. Update `CHANGELOG.md` under `[Unreleased]`
2. Move it to a versioned section, set the date
3. Tag: `git tag v0.X.0 -m "Release v0.X.0"` then `git push --tags`
4. CI workflow `release.yml` runs:
   - Sync `manifest.json` version with the tag
   - Build `solaredge_pv_export_limiter.zip`
   - Publish a GitHub Release with auto-generated notes
5. HACS users get the new version on next refresh

## HACS submission flow

For listing in the public HACS default registry:

1. Repo must pass `home-assistant/actions/hassfest@master` and `hacs/action@main`
   (both run by `validate.yml`)
2. Open a PR adding the repo to https://github.com/hacs/default
3. Add brand to https://github.com/home-assistant/brands (logo + icon for the integration)
4. Wait for review

This is optional — until done, users add the repo as a custom HACS repository.
