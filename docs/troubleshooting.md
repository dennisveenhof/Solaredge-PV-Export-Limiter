# Troubleshooting

## "The limiter does nothing"

**Symptom**: `number.solaredge_*_active_power_limit` stays at 100% even when there's
clearly export to the grid.

**Checklist**:

1. `switch.solaredge_pv_export_limiter_limiter_active` is **on**?
2. `select.solaredge_pv_export_limiter_mode` is not **off**?
3. `sensor.solaredge_pv_export_limiter_status` reads **Working** — if **Sensor lost**, see below
4. **Modbus TCP enabled** on inverter? `SetApp → Site Communication → Modbus → TCP server`
5. SolarEdge Modbus Multi integration installed with **Read+Write** scope?
6. Try service `solaredge_pv_export_limiter.recalculate` — check logs for write errors

If `sensor.solaredge_pv_export_limiter_target_pct` differs from `current_pct` by > hysteresis
but no write happens → check HA log:
**Settings → System → Logs → filter `solaredge_pv_export_limiter`**.

## "Wild oscillations — limit jumps every cycle"

**Cause**: smoothing too short relative to load grilliness, or hysteresis too tight.

**Fix**: increase **Hysteresis** to 2.5 % and **Smoothing window** to 10-12 s.
See [tuning](tuning.md).

## "Inverter trips on overvoltage"

**Symptom**: SolarEdge mySolarEdge app shows `Reconnect Time` errors during sunny midday.

**Cause**: high grid voltage (> 253 V) — common in PV-dense neighbourhoods.

**Fix**:

1. Enable **Voltage protection** in OptionsFlow
2. Pick the SolarEdge L1 voltage entity (e.g. `sensor.solaredge_*_voltage_l1n`)
3. Lower the warning threshold to 248 V if 250 V is too late

For chronic > 253 V issues: contact your DSO; this is a grid problem.

## "Curtailment counter stuck at 0"

**Symptom**: `sensor.solaredge_pv_export_limiter_curtailment_kwh` never increments despite
visible curtailment.

**Possible causes**:

- The inverter is sun-bound, not limit-bound (clouds keeping PV below the limit anyway)
- Limit is at 99% or higher (not considered curtailment)
- The detection band (5% of nominal) is too tight

The counter only ticks when **both** conditions are true:
- Limit < 99 %
- Actual PV is within 5% of nominal of the limit value

This is on purpose — without that gate, every cloud would falsely add curtailment.

## "Wizard says no SolarEdge inverter found"

**Symptom**: dropdown for inverter sensors is empty.

**Causes**:

- SolarEdge Modbus Multi not installed → install via HACS first
- Modbus TCP not enabled → SetApp → Site Communication → Modbus
- Wrong port → default is 1502 (sometimes 502); set in the SolarEdge Modbus
  integration

## "Sensor unavailable — limit stays at 100%"

**Symptom**: `sensor.solaredge_pv_export_limiter_status` shows **Sensor lost**.

This is the failsafe working correctly. The integration won't make decisions on
stale data. Check:

- DSMR P1 cable connected? (Look at `sensor.electricity_meter_*` for `unavailable`)
- SolarEdge Modbus TCP responding? (Look at `sensor.solaredge_*_ac_power`)
- HA → Developer Tools → States → are the configured entities there?

After 2 min unavailability the limit auto-resets to 100% as a safety measure.

## "It worked yesterday, broke today"

**Most likely cause**: SolarEdge Modbus Multi or DSMR integration was updated
and renamed entities.

**Fix**: OptionsFlow → re-select sensors. The integration uses entity_ids; if those
change, you need to update.

## "I see frequent Modbus writes in the log"

**Symptom**: a write per cycle, every cycle.

**Cause**: hysteresis too tight, or load is genuinely changing fast (electric kettle,
pulsing freezer).

**Fix**: raise hysteresis. SolarEdge inverters can handle thousands of writes per day
fine, but it's polite to keep it under a few hundred.

## "Mode keeps switching back to Normal"

**Cause**: Tariff awareness is enabled and the price moved out of the trigger band.

**Fix**: either disable tariff awareness, or use *Manual* mode (which the tariff
override respects).

## Submitting a bug

1. Reproduce with `solaredge_pv_export_limiter` set to **Debug** logging:
   ```yaml
   logger:
     default: warning
     logs:
       custom_components.solaredge_pv_export_limiter: debug
   ```
2. Capture 5 min of relevant log lines
3. Open an issue with the [bug report template](https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter/issues/new?template=bug_report.yml)
4. Include sensor entity_ids, integration version, HA version, inverter model
