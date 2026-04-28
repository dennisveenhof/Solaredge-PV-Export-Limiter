# Operating modes

Solaredge PV Export Limiter has six modes. Switch via the `select.solaredge_pv_export_limiter_mode`
entity, the dashboard card, or the `solaredge_pv_export_limiter.set_mode` service.

## Normal — default everyday mode

**Setpoint default**: 50 W

The limiter keeps grid export below ~50 W on average, with a small tolerance for
P1 jitter. Use this whenever you're at home and just want to minimise feed-in.

**When to use**: 99% of the time.

## Vacation — nobody home

**Setpoint default**: 0 W

Cuts feed-in to ~0 W. Since base load when nobody is home is 100-300 W, the
inverter will run at very low percentages and keep nearly all PV inside the house.

**When to use**: trips, holidays. Combine with `device_tracker` automation:

```yaml
automation:
  - alias: "PV: Vacation when away"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: "not_home"
        for: "01:00:00"
    action:
      - service: solaredge_pv_export_limiter.set_mode
        data: { mode: vacation }
```

## Negative price — exporting actually costs money

**Setpoint default**: 0 W

Triggered automatically when the configured price sensor goes negative (you can
also flip it manually). The inverter is curtailed close to zero so you don't
pay a surcharge for what you're injecting into the grid.

**When to use**: dynamic-tariff contracts (EnergyZero, Frank, ANWB Energie,
Tibber, Vandebron). Enable **Tariff awareness** in options.

## Wide — open the throttle

**Setpoint default**: 200 W

Loosens the limiter for periods when feed-in actually pays well (high tariff
hour, or you've exhausted the day's net-metering budget). Allows up to 200 W
average export.

**When to use**: sunny midday with high spot prices, or before saldering ends.

## Manual — driven by a number entity

Setpoint comes from `number.solaredge_pv_export_limiter_setpoint_manual`. Adjust it via
the dashboard slider or any automation.

**When to use**: experiments, scripted strategies, integrations with external
controllers.

## Off — no regulation

The integration writes 100% to the inverter and stops adjusting. Useful for
debugging or to fully disable the limiter without uninstalling.

**When to use**: when validating sensors or testing other automations.

## Mode-switching examples

**Schedule-based** — Wide between noon and 14:00, Normal otherwise:

```yaml
automation:
  - alias: "PV: Wide at midday"
    trigger:
      - platform: time
        at: "12:00:00"
    action:
      - service: solaredge_pv_export_limiter.set_mode
        data: { mode: wide }
  - alias: "PV: Normal at 14:00"
    trigger:
      - platform: time
        at: "14:00:00"
    action:
      - service: solaredge_pv_export_limiter.set_mode
        data: { mode: normal }
```

**Saldering-end-date** — automatic 0 W from 1 Jan 2027:

```yaml
automation:
  - alias: "PV: Saldering ends"
    trigger:
      - platform: time
        at: "00:00:00"
    condition:
      - condition: template
        value_template: "{{ now() >= as_datetime('2027-01-01 00:00') }}"
    action:
      - service: solaredge_pv_export_limiter.set_mode
        data: { mode: vacation }   # or 'negative_price' for 0 W
```
