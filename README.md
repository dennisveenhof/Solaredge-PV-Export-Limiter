<p align="center">
  <img src="docs/logo.png" alt="Solaredge PV Export Limiter" width="180" />
</p>

# Solaredge PV Export Limiter

> ⚠️ **SolarEdge only.** This integration is built specifically for **SolarEdge HD-Wave**
> inverters (SE-RW series) communicating over Modbus TCP via the
> [SolarEdge Modbus Multi](https://github.com/WillCodeForCats/solaredge-modbus-multi)
> integration. It will **not** work with Fronius, SMA, Huawei, Growatt, or any other brand.
> Other-brand support is explicitly out of scope.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter/actions/workflows/validate.yml/badge.svg)](https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter/actions/workflows/validate.yml)
[![Tests](https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter/actions/workflows/tests.yml/badge.svg)](https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Dynamic export limiting for SolarEdge inverters in Home Assistant** — keep grid feed-in
> below your chosen setpoint without sacrificing self-consumption. UI-installable, no YAML
> required.

![dashboard](screenshots/dashboard.png)

## Why?

Many SolarEdge owners face one or more of:

- Energy supplier charges fees for surplus feed-in
- Grid voltage trips the inverter on sunny days (> 253 V in NL)
- Net-metering ends in 2027 (NL — saldering) and you want to maximize self-consumption now
- Dynamic tariff contracts with negative price hours

This integration solves all four with a single closed-loop controller: it reads your
household consumption from the P1 meter and your PV output from the SolarEdge Modbus
integration, then writes the optimal `active_power_limit` back to the inverter every
10 seconds.

## Features

- **UI-driven setup wizard** — pick your SolarEdge and P1 sensors from a dropdown, no YAML
- **6 modes**: Normal / Vacation / Negative-price / Wide / Manual / Off
- **Tariff-aware** via EnergyZero, Nordpool, Tibber, or any price sensor
- **Voltage protection** — pre-emptively limits when grid voltage exceeds 250 V
- **Failsafes** — sensor loss, HA restart, anomaly detection all reset to safe state
- **Curtailment counter** — see exactly how much PV energy you're holding back per day/month
- **Custom Lovelace card** — live energy flow, mode selector, history, all in one card
- **Dutch + English** UI translations
- **Built for SolarEdge HD-Wave** (SE-RW series), works with Modbus Multi integration

## Pre-requisites

Before installing, you need:

1. **Home Assistant** 2024.1 or newer
2. **HACS** installed ([install guide](https://hacs.xyz/docs/use/))
3. **SolarEdge Modbus Multi** integration installed via HACS
   ([repo](https://github.com/WillCodeForCats/solaredge-modbus-multi))
4. **Modbus TCP enabled** on your SolarEdge inverter (SetApp → Site Communication → Modbus)
5. A **P1 / DSMR smart meter** integrated into Home Assistant (built-in DSMR integration)

## Quick install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dennisveenhof&repository=Solaredge-PV-Export-Limiter&category=integration)

1. HACS → Integrations → ⋮ → Custom repositories → add this repo URL → Integration
2. Find "Solaredge PV Export Limiter" in HACS → Install → Restart HA
3. Settings → Devices & Services → Add Integration → "Solaredge PV Export Limiter"
4. Follow the wizard

## Modes & Status reference

There are two related concepts:

- **Mode** — the strategy *you* select (how the limiter should behave).
- **Status** — what the integration *automatically reports* about its current state.

### Modes (you choose)

| Mode key | Label | Setpoint | What it does | When to use |
|---|---|---|---|---|
| `normal` | **Default / Standaard** | 50 W | Keeps grid export around 50 W. Small buffer prevents brief grid imports during sudden loads. | Daily use — this is your default |
| `vacation` | **Vacation / Vakantie** | 0 W | Aims for zero export. **Auto-falls back to Default** if grid import stays > 600 W for 60 s (configurable). | Actually away / no one home |
| `negative_price` | **Negative tariff** | 0 W | No export during negative EPEX hours. Switches automatically when a tariff sensor is configured. | Dynamic tariff contract |
| `wide` | **Permissive / Soepel** | 200 W | Allows up to 200 W export. | When you want to export but capped |
| `manual` | **Manual** | user-defined | You set the setpoint via a number entity. | Tuning / experimenting |
| `off` | **Disabled** | n/a | Limiter is off, inverter runs at 100%. | Temporarily disable without removing the integration |

### Status (the integration reports)

| Status | Meaning | What the limiter does |
|---|---|---|
| `ok` | Everything operating normally | Regular control loop active |
| `starting` | Just started, no data yet | Waits for sensor input |
| `disabled` | Limiter off (mode=off or switch off) | Writes 100% to inverter |
| `no_pv` | No PV production (night / overcast) | Writes 100% — nothing to curb |
| `voltage_high` | Grid voltage > threshold (default 250 V) | Forces 0% — protects against inverter trip |
| `sensor_loss` | A sensor became unavailable | Writes 100%, fires alert |
| `write_error` | Modbus write to inverter failed | Retries, alerts |
| `budget_free` | Budget mode on, budget remaining | Writes 100% — export freely |
| `budget_exhausted` | Budget mode on, budget used up | Forces 0% until next period |

### Special features (independent of mode)

| Feature | What | Override priority |
|---|---|---|
| **Voltage protection** | > threshold → 0% export for 30 s | **Wins over everything** (safety) |
| **Export budget** | Max X kWh per day/month/year | Wins over mode setpoint |
| **Vacation auto-disable** | Switches mode when import > threshold | Switches mode only, no override |
| **Negative-price tracking** | Switches mode based on tariff | Switches mode only |

For detailed mode behavior see [docs/modes.md](docs/modes.md).

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Modes explained](docs/modes.md)
- [Tuning guide](docs/tuning.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Architecture](docs/architecture.md) (for contributors)

## Screenshots

| Wizard | Dashboard | Curtailment |
|---|---|---|
| ![wizard](screenshots/wizard.png) | ![dashboard](screenshots/dashboard.png) | ![curtailment](screenshots/curtailment-graph.png) |

## Contributing

Issues and PRs welcome. See [docs/architecture.md](docs/architecture.md) for the developer
guide.

## License

[MIT](LICENSE) — feel free to fork.

## Disclaimer

This integration writes to your inverter via Modbus. Misconfiguration could limit your
PV output below desired levels. The authors take no responsibility for energy lost or
inverter behavior. Test with the **Off** mode first to verify your sensor selection.
