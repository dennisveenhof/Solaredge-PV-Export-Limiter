# Tuning guide

The defaults work well for most setups. Tune only when you observe a real problem.

## Update interval

**Default**: 10 s. **Range**: 5-60 s.

| Setting | When |
|---|---|
| 5 s | Aggressive — only with DSMR5 (1 s telegrams) and a stable network. Watch for excessive Modbus writes. |
| 8-10 s | **Recommended sweet spot.** 3-5 fresh P1 samples per cycle, kind to the inverter flash. |
| 15-30 s | DSMR4 (10 s telegrams) or noisy networks. Slightly slower response to load drops. |
| > 30 s | Only for testing. Big load drops will exceed setpoint for long periods. |

> **Don't go below 5 s.** The SolarEdge `active_power_limit` register persists to
> non-volatile storage. Excessive writes shorten its life.

## Smoothing window

**Default**: 8 s. **Range**: 2-30 s.

Should be **slightly less** than the update interval so each cycle has a fresh average.
Rule of thumb: `smoothing = 0.7 * update_interval`.

| Symptom | Action |
|---|---|
| Wild oscillation around setpoint | Increase to 10-12 s |
| Slow to react when load changes | Decrease to 5-6 s |
| Single-sample spikes triggering writes | Increase + raise hysteresis |

## Hysteresis

**Default**: 1.5 %. **Range**: 0.5-5.0 %.

The minimum delta between target and current limit before the integration writes.

| Setting | When |
|---|---|
| 0.5 % | Aggressive tracking, more Modbus writes |
| 1.5 % | **Default.** Balances responsiveness vs flash wear |
| 2.5-3.5 % | Grilly loads (boiler/freezer cycling). Less precise but quieter. |
| > 4 % | Test only. Too sloppy for real-world export limiting. |

A 4000 W inverter at 1.5 % hysteresis = `60 W` minimum step. That's fine.

## Inverter nominal

**Default**: auto-detected from device model (4000 W for SE4K).

Determines what 100% means. If your SE4K can over-rate to 5100 W AC, you have two choices:

- **Set to 4000 W** (recommended) — 100% allows over-rating up to inverter's spec
- **Set to 5100 W** — 100% maps to actual peak; gives the regulator a wider range to use

The first is safer. Only change if you observe the regulator hitting 100% but
the inverter actually delivering less than 4000 W (rare).

## Setpoint per mode

**Normal default**: 50 W.

| Setting | Trade-off |
|---|---|
| 0 W | Strictest. Some over-shoot inevitable due to control delay. |
| 25-50 W | **Recommended.** Tolerates jitter, near-zero average export. |
| 100-200 W | Looser. Use in *Wide* mode for high-tariff windows. |

> Setting **Normal** to 0 W often causes more frequent writes (smaller margin =
> more decisions). Pick 25 W as the most aggressive sane value.

## Voltage protection thresholds

**Warning default**: 250 V. **Recovery default**: 240 V.

Adjust if your area runs higher than typical:

- **Mostly < 240 V** → keep defaults
- **245-250 V regular** → set warning to 252 V, recovery to 245 V (avoid false trips)
- **>= 252 V regular** → fix it with your DSO/grid operator first; this isn't a software problem

The 30 s debounce prevents flap on transient spikes. Don't shorten unless tested.

## Tariff thresholds

| Threshold | Default | Suggestion |
|---|---|---|
| Negative price | 0.0 €/kWh | Lower to -0.05 to ignore very small dips |
| High price | 0.30 €/kWh | Raise to 0.40+ for less frequent *Wide* triggers |

Both apply to whatever your tariff sensor exposes (gross or netto).
Check the entity attributes to confirm the unit.

## Common patterns

### "I want zero export, ever"

```
Update interval: 5 s
Smoothing window: 4 s
Hysteresis: 1.0 %
Setpoint Normal: 0 W
```

Combine with hardware export limit on the SolarEdge SetApp as an extra safety net.

### "I want minimum disturbance, low write rate"

```
Update interval: 15 s
Smoothing window: 12 s
Hysteresis: 3.0 %
Setpoint Normal: 100 W
```

Roughly doubles the average export but cuts Modbus writes by ~70%.

### "I have a flaky network / unreliable P1"

```
Update interval: 20 s
Smoothing window: 15 s
Hysteresis: 2.5 %
```

Prioritises stability over responsiveness. Consider also the failsafe behaviour in
[troubleshooting](troubleshooting.md).
