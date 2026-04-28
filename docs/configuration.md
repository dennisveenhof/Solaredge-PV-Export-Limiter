# Configuration

## Wizard fields reference

### Step 2 — Inverter

| Field | Type | Required | Notes |
|---|---|---|---|
| Inverter AC power sensor | sensor entity | yes | Usually `sensor.solaredge_*_ac_power` |
| Active power limit (writable) | number entity | yes | Usually `number.solaredge_*_active_power_limit`. Must accept 0-100. |

### Step 3 — Grid meter

| Field | Type | Required | Notes |
|---|---|---|---|
| Grid import sensor | sensor entity | yes | Net consumption from grid in W |
| Grid export sensor | sensor entity | yes | Net production to grid in W. Must differ from import. |

### Step 4 — Inverter parameters

| Field | Default | Range | Notes |
|---|---|---|---|
| Inverter nominal power | auto (4000 for SE4K) | 1000-10000 W | What 100% means in the limit register |
| Update interval | 10 s | 5-60 s | How often the loop recomputes |
| Smoothing window | 8 s | 2-30 s | Rolling-mean buffer for jitter rejection |
| Hysteresis | 1.5 % | 0.5-5.0 % | Minimum delta to trigger a write |

See [tuning.md](tuning.md) for guidance on how to adjust these.

### Step 5 — Optional protections

| Field | Default | Notes |
|---|---|---|
| Grid voltage sensor | empty | If set + protection enabled, > 250 V trips a 0% limit |
| Voltage protection enabled | false | Master toggle for the above |
| Voltage warning threshold | 250.0 V | Above this for 30 s → emergency clamp |
| Voltage recovery threshold | 240.0 V | Below this → return to normal control |
| Tariff price sensor | empty | EnergyZero/Nordpool/Tibber price entity |
| Tariff awareness enabled | false | Master toggle for tariff-driven mode switching |
| Negative price threshold | 0.0 €/kWh | Below this → mode switches to *Negative price* |
| High price threshold | 0.30 €/kWh | Above this → mode switches to *Wide* |

### Step 6 — Mode setpoints

Each mode's maximum allowed feed-in (W). The active mode's value drives the limit.

| Mode | Default | Use case |
|---|---|---|
| Normal | 50 W | Everyday operation, small tolerance for jitter |
| Vacation | 0 W | Nobody home, minimum self-consumption |
| Negative price | 0 W | EPEX is negative, every exported kWh costs you |
| Wide | 200 W | Sunny day, supplier vergoeding hoog → laat lopen |
| Manual | 50 W (slider) | User-driven, edit `number.solaredge_pv_export_limiter_setpoint_manual` |

Plus `Off` (no regulation, limit stays at 100%).

### Step 7 — Finish

Optional notify target for failsafe alerts. Use the part **after** `notify.` —
e.g. for `notify.mobile_app_my_phone`, enter `mobile_app_my_phone`.

## OptionsFlow — change anything later

**Settings → Devices & Services → Solaredge PV Export Limiter → Configure**

Lets you tune all numerical parameters and toggle protections without re-running the wizard.

## Configurable entities

After install you have these settable entities:

| Entity | Purpose |
|---|---|
| `switch.solaredge_pv_export_limiter_limiter_active` | Master on/off |
| `select.solaredge_pv_export_limiter_mode` | Switch operating mode |
| `number.solaredge_pv_export_limiter_setpoint_manual` | Setpoint for *Manual* mode |
| `number.solaredge_pv_export_limiter_hysteresis` | Live-tune hysteresis |
| `number.solaredge_pv_export_limiter_nominal` | Live-tune inverter nominal |

Read-only:

| Entity | Purpose |
|---|---|
| `sensor.solaredge_pv_export_limiter_load` | Computed household consumption (W) |
| `sensor.solaredge_pv_export_limiter_target_w` | Desired PV output (W) |
| `sensor.solaredge_pv_export_limiter_target_pct` | Target inverter limit (%) |
| `sensor.solaredge_pv_export_limiter_current_pct` | Current actual inverter limit (%) |
| `sensor.solaredge_pv_export_limiter_curtailment_w` | Estimated PV being held back (W) |
| `sensor.solaredge_pv_export_limiter_curtailment_kwh` | Cumulative curtailment energy |
| `sensor.solaredge_pv_export_limiter_status` | ok / disabled / no_pv / sensor_loss / voltage_high |
| `binary_sensor.solaredge_pv_export_limiter_anomaly` | Limiter not constraining despite being active |
| `binary_sensor.solaredge_pv_export_limiter_voltage_warning` | Voltage > threshold |

## Services

| Service | Use |
|---|---|
| `solaredge_pv_export_limiter.recalculate` | Force immediate recompute (bypasses interval) |
| `solaredge_pv_export_limiter.reset_to_100` | Set inverter limit to 100% |
| `solaredge_pv_export_limiter.set_mode` | Switch operating mode (use `mode: vacation` etc.) |

Useful in scripts:

```yaml
service: solaredge_pv_export_limiter.set_mode
data:
  mode: vacation
```
