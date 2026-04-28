# Installation

## Pre-flight checklist

Before installing Solaredge PV Export Limiter, you need:

- [ ] **Home Assistant 2024.1** or newer
- [ ] **HACS** installed — [official guide](https://hacs.xyz/docs/use/)
- [ ] **SolarEdge Modbus Multi** integration installed via HACS
      ([WillCodeForCats/solaredge-modbus-multi](https://github.com/WillCodeForCats/solaredge-modbus-multi))
- [ ] **Modbus TCP enabled** on your inverter:
      `SetApp → Site Communication → Modbus → TCP Server: enabled`
- [ ] **DSMR / P1 smart meter** integrated (built-in HA `dsmr` integration or USB-cable)
- [ ] At least one writable `number.solaredge_*_active_power_limit` entity visible

Optional (enables more features):

- [ ] An **energy price sensor** (EnergyZero, Nordpool, Tibber, etc.) for tariff-aware mode switching
- [ ] A **voltage sensor** from the SolarEdge Modbus integration for over-voltage protection
- [ ] **HA Companion app** installed for failsafe push notifications

## Step 1 — Install via HACS

1. **HACS → Integrations**
2. Click the three-dot menu → **Custom repositories**
3. Add the repository URL: `https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter`
4. Category: **Integration**
5. Click **Add**, then find **Solaredge PV Export Limiter** in the HACS list
6. Click **Install**
7. **Restart Home Assistant**

> Once submitted to the HACS default list, you can install in one click via the
> [HACS button in the README](../README.md#quick-install).

## Step 2 — Run the wizard

1. **Settings → Devices & Services**
2. **+ Add Integration**
3. Search **Solaredge PV Export Limiter** → click it
4. Walk through the 7 wizard steps. Most fields auto-detect from your existing setup.

The wizard will ask for:

| Step | What |
|---|---|
| 1. Welcome | Confirm you have all pre-requisites |
| 2. Inverter | Pick your `sensor.solaredge_*_ac_power` and `number.solaredge_*_active_power_limit` |
| 3. Grid meter | Pick your P1 import and export sensors |
| 4. Inverter params | Confirm nominal power (auto-suggested from device model) and tuning |
| 5. Optional | Voltage and tariff sensors — both skippable |
| 6. Setpoints | Per-mode max-export targets |
| 7. Finish | Optional notify target |

## Step 3 — Add the dashboard card (optional)

Add a card to any Lovelace view:

```yaml
type: custom:pv-limiter-card
```

The card auto-detects the integration entry. No further config required.

## Step 4 — First-24-hours checklist

- [ ] On a sunny morning, watch `sensor.solaredge_pv_export_limiter_status` — should read **Working**
- [ ] Watch `number.solaredge_*_active_power_limit` — should change as load changes
- [ ] Verify `sensor.electricity_meter_power_production` settles around your **Normal** setpoint
- [ ] Trigger a load (oven, vacuum cleaner) — within ~15 s the limit should rise
- [ ] After PV is off (night) — the limit should reset to 100%
- [ ] Switch the **Mode** select to *Vacation* and back to *Normal* — observe behaviour

If anything looks wrong → see [troubleshooting](troubleshooting.md).
