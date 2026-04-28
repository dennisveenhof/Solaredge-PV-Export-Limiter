# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - TBD

Initial release.

### Added
- DataUpdateCoordinator-based control loop (10 s polling + state-change event triggers)
- 8-step Config Flow wizard for SolarEdge inverter and P1 meter selection
- Options Flow for post-install adjustments (setpoints per mode, hysteresis, intervals)
- Six operating modes: Normal, Vacation, Negative-price, Wide, Manual, Off
- Optional tariff integration (EnergyZero / Nordpool / Tibber / generic price sensor)
- Optional voltage protection (auto-clamp to 0 W on > 250 V grid voltage)
- Failsafes for sensor unavailability, HA restart, and anomaly detection
- Curtailment counter (W instantaneous + kWh integrated, daily/monthly cycles)
- Custom Lovelace card with live energy flow, mode selector, gauge, history
- Custom services: `recalculate`, `reset_to_100`, `set_mode`
- English and Dutch UI translations
- Pure-function `calc.py` module with 100% test coverage
- HACS validation, hassfest, and pytest CI workflows
- MIT license, contribution guide, issue templates

[Unreleased]: https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter/releases/tag/v0.1.0
