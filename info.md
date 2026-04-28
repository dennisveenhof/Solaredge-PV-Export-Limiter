# Solaredge PV Export Limiter

Dynamic export limiting for SolarEdge inverters in Home Assistant. Reads household
consumption from your P1 meter and PV output from SolarEdge Modbus, then writes the
optimal `active_power_limit` back every 10 seconds.

## Features

- UI wizard for setup — no YAML required
- 6 operating modes (Normal, Vacation, Negative-price, Wide, Manual, Off)
- Tariff-aware via EnergyZero, Nordpool, or any price sensor
- Voltage protection against inverter trips
- Failsafes for sensor loss and HA restart
- Curtailment counter (kWh held back per day/month)
- Custom Lovelace card included
- English + Dutch translations

## Pre-requisites

- SolarEdge Modbus Multi integration (separate HACS install)
- DSMR / P1 smart meter integration
- Modbus TCP enabled on the inverter

See full documentation in the [repository README](https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter).
