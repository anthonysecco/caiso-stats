# CAISO Stats for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![GitHub release](https://img.shields.io/github/v/release/anthonysecco/caiso-stats)](https://github.com/anthonysecco/caiso-stats/releases)
[![Validate](https://github.com/anthonysecco/caiso-stats/actions/workflows/validate.yml/badge.svg)](https://github.com/anthonysecco/caiso-stats/actions/workflows/validate.yml)
[![Tests](https://github.com/anthonysecco/caiso-stats/actions/workflows/tests.yml/badge.svg)](https://github.com/anthonysecco/caiso-stats/actions/workflows/tests.yml)

California's grid, live in Home Assistant: grid status and Flex Alerts, demand and net demand, operating reserves, the supply mix, CO2 intensity, and **ready-made load-shifting signals**. Use them to run the EV charger, water heater, pool pump or dishwasher when the grid is clean and has spare capacity, and to back off when it's stressed.

Data comes from the California ISO's free public [Today's Outlook](https://www.caiso.com/todays-outlook) feeds. No account, API key or cloud service is needed.

> **Unofficial.** This project is not affiliated with or endorsed by the California ISO. It reads the same public files that power CAISO's website and mobile app. They're undocumented and can change without notice. A daily CI job checks the live feeds so breakage shows up quickly.

## Contents
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [Load-shifting signals](#load-shifting-signals)
- [Examples](#examples)
- [Data and update frequency](#data-and-update-frequency)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=anthonysecco&repository=caiso-stats&category=integration)

Or add it by hand:
1. In Home Assistant open **HACS**, then the **⋮** menu (top right), then **Custom repositories**.
2. Repository: `https://github.com/anthonysecco/caiso-stats`. Type: **Integration**. Click **Add**.
3. Search HACS for **CAISO Stats**, open it and click **Download**.
4. **Restart Home Assistant.**
5. Add the integration (next section).

Requires Home Assistant **2026.3** or newer.

### Manual
Copy `custom_components/caiso_stats` from the [latest release](https://github.com/anthonysecco/caiso-stats/releases) into your `config/custom_components/` folder, then restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up CAISO Stats.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=caiso_stats)

**Settings → Devices & services → Add integration → CAISO Stats → Submit.** There is nothing to enter. Setup checks that CAISO's feed answers and creates one **CAISO** device.

### Options
**Settings → Devices & services → CAISO Stats → Configure.** Saving reloads the integration.

| Option | Default | What it does |
|---|---|---|
| Update interval | 15 min | How often both feeds are fetched (5–60 min). CAISO refreshes them every 5 min. Each update makes 2 small requests with a 30 s timeout. |
| Clean energy CO2 threshold | 200 g/kWh | **Clean energy now** turns on at or below this grid CO2 intensity. |
| Peak period threshold | 90 % | **Peak demand period** turns on when net demand reaches this share of today's forecast net demand peak. |
| Grid stress reserve threshold | 150 % | **Grid stress** turns on when operating reserve falls below this share of the required reserve, or whenever CAISO reports a non-normal grid status. |
| Solar surplus: battery charging | 1000 MW | **Solar surplus** turns on when grid batteries are charging at least this hard… |
| Solar surplus: solar + wind share | 50 % | …or when solar plus wind supply at least this share of demand. |
| Low demand window length | 3 h | Length of the lowest net demand window searched for in the rest of today's forecast. |

## Entities

Entity IDs below assume the default device name **CAISO**. All power values are in MW for the whole CAISO balancing area.

### Load-shifting signals
| Entity | Type | Meaning |
|---|---|---|
| `sensor.caiso_load_shift_recommendation` | enum: `avoid` / `normal` / `use_now` | One signal for most automations (see [logic](#load-shifting-signals)). Attributes give each input. |
| `binary_sensor.caiso_grid_stress` | problem | Non-normal grid status (Flex Alert, EEA…) or reserves below threshold. |
| `binary_sensor.caiso_peak_demand_period` | on/off | Net demand near today's forecast peak. Usually the late-afternoon and evening ramp. |
| `binary_sensor.caiso_clean_energy_now` | on/off | Grid CO2 intensity at or below your threshold. |
| `binary_sensor.caiso_solar_surplus` | on/off | Batteries soaking up surplus, or solar + wind covering a big share of demand. |

### Grid
| Entity | Unit | Notes |
|---|---|---|
| `sensor.caiso_grid_status` | enum | `normal`, `rmo`, `flex_alert`, `eea_watch`, `transmission_emergency`, `eea_1`, `eea_2`, `eea_3`, `other`. The most severe notice wins. `notices` holds CAISO's raw text. |
| `sensor.caiso_demand` | MW | Current system demand. |
| `sensor.caiso_net_demand` | MW | Demand minus solar and wind: what dispatchable plants, batteries and imports must cover. |
| `sensor.caiso_todays_peak_demand` | MW | Highest demand so far today (`peak_time` attribute). |
| `sensor.caiso_forecast_peak_demand_today` | MW | CAISO's forecast peak for today (`peak_time` attribute). |
| `sensor.caiso_forecast_peak_demand_tomorrow` | MW | Forecast peak for tomorrow. |
| `sensor.caiso_operating_reserve` | MW | Current operating reserve. |
| `sensor.caiso_required_reserve` | MW | Reserve CAISO must hold. |
| `sensor.caiso_reserve_ratio` | % | Operating reserve ÷ required reserve. Below 100 % means CAISO is short. |
| `sensor.caiso_available_capacity`, `sensor.caiso_unloaded_capacity_10_min` / `_1_h` / `_4_h` | MW | Capacity headroom. *Disabled by default.* |

### Supply mix and emissions
| Entity | Unit | Notes |
|---|---|---|
| `sensor.caiso_solar`, `_wind`, `_geothermal`, `_biomass`, `_biogas`, `_small_hydro`, `_large_hydro`, `_nuclear`, `_natural_gas`, `_coal`, `_imports` | MW | Current output by source. |
| `sensor.caiso_batteries` | MW | **Negative = charging**, positive = discharging. `mode`, `standalone_mw` and `hybrid_mw` attributes. |
| `sensor.caiso_other_generation`, `sensor.caiso_hybrids` | MW | *Disabled by default.* |
| `sensor.caiso_renewables` | % | CAISO's renewables share of demand. |
| `sensor.caiso_clean_energy` | % | Renewables + large hydro + nuclear, as a share of demand. |
| `sensor.caiso_solar_and_wind_share` | % | Solar + wind share of demand. *Disabled by default.* |
| `sensor.caiso_co2_emissions` | t/h | Metric tons of CO2 per hour from CAISO-area generation and imports. |
| `sensor.caiso_co2_intensity` | g/kWh | Average CO2 per kWh served right now. |

### Net demand forecast (rest of today)
| Entity | Unit | Notes |
|---|---|---|
| `sensor.caiso_net_demand_forecast` | MW | CAISO's net demand forecast for the current interval. The `forecast` attribute holds hourly forecast and actuals for charts; it isn't saved to the database. |
| `sensor.caiso_net_demand_peak_forecast` | MW | Today's forecast net demand peak. |
| `sensor.caiso_net_demand_peak_time` | timestamp | When that peak is expected. |
| `sensor.caiso_low_demand_window_start` | timestamp | Start of the lowest-average net demand window (default 3 h) in the rest of today. `end`, `average_mw` and `hours` attributes. |

### Diagnostic
| Entity | Notes |
|---|---|
| `sensor.caiso_data_time` | Time of CAISO's snapshot. |

## Load-shifting signals

**Why net demand?** Solar and wind are free to run once built. Whatever demand they don't cover (the *net demand*) is met by gas plants, batteries and imports. Low net demand means surplus clean power, often with batteries charging and prices near zero. High net demand, usually from about 5 to 9 pm when solar fades, is when the grid is most expensive, most carbon-intensive and most strained.

`sensor.caiso_load_shift_recommendation` combines the four binary signals:

| State | When | Suggested use |
|---|---|---|
| `avoid` | **Grid stress** *or* **Peak demand period** | Pause flexible loads; pre-cool or pre-heat beforehand. |
| `use_now` | Not `avoid`, and **Solar surplus** *or* **Clean energy now** | Start EV charging, water heater boost, pool pump, laundry. |
| `normal` | Anything else | No strong signal either way. |

Every signal publishes its inputs and thresholds as attributes, so you can see why it's on.

> These are grid-wide signals, not your utility bill. Time-of-use rates and local outages are separate. Combine them with your own TOU or price sensors when cost matters.

## Examples

Ready-to-paste automations (EV charging, water heater, pre-cooling before the peak, Flex Alert notifications) and dashboard cards are in **[docs/automations.md](docs/automations.md)**.

Quick start: notify when the grid is stressed.
```yaml
automation:
  - alias: "Grid: stress alert"
    triggers:
      - trigger: state
        entity_id: binary_sensor.caiso_grid_stress
        to: "on"
    actions:
      - action: notify.notify
        data:
          title: "California grid stressed"
          message: >
            {{ states('sensor.caiso_grid_status') | replace('_', ' ') | title }},
            reserve ratio {{ states('sensor.caiso_reserve_ratio') }} %.
            Please hold off on big loads until it clears.
```

## Data and update frequency

| Feed | URL | Used for |
|---|---|---|
| Stats snapshot | `https://wwwmobile.caiso.com/outlook/SP/stats.txt` | Status, demand, reserves, supply mix, CO2 |
| Net demand curve | `https://www.caiso.com/outlook/current/netdemand.csv` | Today's net demand forecast, peak and low window |

- CAISO refreshes both every 5 minutes. This integration polls every **15 minutes** by default: 2 requests, in parallel, each with a 30 s timeout. That's frequent enough for load shifting and gentle on a free public service. You can lower it to 5 minutes in Options.
- If the forecast file fails, the live sensors keep working. Only the forecast entities go unavailable, and **Peak demand period** falls back to CAISO's demand-peak forecast.
- **Coverage:** the CAISO balancing area covers most of California, including PG&E, SCE and SDG&E territory and CCAs like SJCE and PCE. LADWP, SMUD, IID and some other municipal utilities run their own balancing areas.
- CO2 figures are CAISO's own estimates for generation serving CAISO load, including imports.

## Troubleshooting

- **Setup says it can't connect:** check that Home Assistant can reach `wwwmobile.caiso.com` (DNS, firewall, Pi-hole). CAISO occasionally has short maintenance outages; try again in a few minutes.
- **Forecast sensors unavailable:** `www.caiso.com/outlook/current/netdemand.csv` didn't answer or changed format. The rest keeps working.
- **Diagnostics:** **Settings → Devices & services → CAISO Stats → ⋮ → Download diagnostics** includes the raw CAISO payloads. Attach it to [issues](https://github.com/anthonysecco/caiso-stats/issues).
- **Debug logging:**
  ```yaml
  logger:
    logs:
      custom_components.caiso_stats: debug
  ```

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff check .
pytest
python scripts/check_live.py   # parse CAISO's live feeds
```

CI runs HACS validation, hassfest, ruff and pytest on every push, plus a daily check against the live feeds.

## License

[MIT](LICENSE). Grid data © California ISO, used under its public website terms.
