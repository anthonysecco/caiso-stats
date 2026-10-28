# CAISO Stats for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![GitHub release](https://img.shields.io/github/v/release/anthonysecco/caiso-stats)](https://github.com/anthonysecco/caiso-stats/releases)
[![Validate](https://github.com/anthonysecco/caiso-stats/actions/workflows/validate.yml/badge.svg)](https://github.com/anthonysecco/caiso-stats/actions/workflows/validate.yml)
[![Tests](https://github.com/anthonysecco/caiso-stats/actions/workflows/tests.yml/badge.svg)](https://github.com/anthonysecco/caiso-stats/actions/workflows/tests.yml)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-donate-yellow.svg)](https://www.buymeacoffee.com/anthonysecco)

California's grid, live in Home Assistant: grid status and Flex Alerts, demand and net demand, operating reserves, the supply mix, CO2 intensity, and a **Carbon Intensity Index** that compares the grid right now with the last two weeks. Use them on dashboards and in automations, for example to run the EV charger or water heater when the grid is clean and to back off during a Flex Alert.

Data comes from the California ISO's free public [Today's Outlook](https://www.caiso.com/todays-outlook) feeds. No account, API key or cloud service is needed.

> **Unofficial.** This project is not affiliated with or endorsed by the California ISO. It reads the same public files that power CAISO's website and mobile app. They're undocumented and can change without notice. A daily CI job checks the live feeds so breakage shows up quickly.

## Contents
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [Net demand, explained](#net-demand-explained)
- [Carbon Intensity Index](#carbon-intensity-index)
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
| Update interval | 15 min | How often CAISO is polled (5–60 min). Each poll fetches the live stats; the net demand forecast is refetched about once an hour (see [Data and update frequency](#data-and-update-frequency)). |
| Low carbon index threshold | 25 % | **Low Carbon Energy Now** turns on when the [Carbon Intensity Index](#carbon-intensity-index) is at or below this. |
| Carbon Intensity Index window | 14 days | Days of history (7–30) whose cleanest and dirtiest hour set the [Carbon Intensity Index](#carbon-intensity-index)'s 0 and 100. |

## Entities

Entity IDs below assume the default device name **CAISO**. All power values are in MW for the whole CAISO balancing area.

Everything except the Carbon Intensity Index and Low Carbon Energy Now comes straight from CAISO's feeds.

A fresh install enables 6 entities: grid status, net demand, renewables share, CO2 intensity, the Carbon Intensity Index and when the data was last updated. Everything marked *Off by default* is created disabled. To turn one on, open **Settings → Devices & services → CAISO Stats → entities**, select it and choose **Enable**. Disabled entities record no history, which keeps the database small.

> **Upgrading from 0.2.x:** this release drops the load-shifting signals, so the integration sticks to CAISO's own data plus one index.
> - **Removed** (deleted automatically): *Load shift recommendation*, *Grid stress*, *Peak demand period*, *Solar surplus*, *Reserve ratio*, *Solar and wind share*, *Net demand peak time*, *Net demand peak forecast* and *Low demand window start*, along with the options that tuned them.
> - **Renamed:** *CO2 Intensity Index* is now *Carbon Intensity Index*. *Clean energy now* is now *Low Carbon Energy Now* and uses the index instead of a fixed g/kWh threshold. Existing installs keep their entity IDs (`sensor.caiso_co2_intensity_index`, `binary_sensor.caiso_clean_energy_now`).
>
> Update any automations that used the removed entities; the [examples](docs/automations.md) show replacements.

### Grid
| Entity | Unit | Notes |
|---|---|---|
| `sensor.caiso_grid_status` | enum | `normal`, `rmo`, `flex_alert`, `eea_watch`, `transmission_emergency`, `eea_1`, `eea_2`, `eea_3`, `other`. The most severe notice wins. `notices` holds CAISO's raw text. |
| `sensor.caiso_demand` | MW | Current system demand. *Off by default.* |
| `sensor.caiso_net_demand` | MW | System demand minus grid-connected solar and wind output: what gas, hydro, nuclear, geothermal, imports and batteries have to supply. Rooftop solar already lowers demand, so it isn't subtracted again. |
| `sensor.caiso_today_s_peak_demand` | MW | Highest demand so far today (`peak_time` attribute). *Off by default.* |
| `sensor.caiso_forecast_peak_demand_today` | MW | CAISO's forecast peak for today (`peak_time` attribute). *Off by default.* |
| `sensor.caiso_forecast_peak_demand_tomorrow` | MW | Forecast peak for tomorrow. *Off by default.* |
| `sensor.caiso_operating_reserve` | MW | Current operating reserve. *Off by default.* |
| `sensor.caiso_required_reserve` | MW | Reserve CAISO must hold. *Off by default.* |
| `sensor.caiso_available_capacity`, `sensor.caiso_unloaded_capacity_10_min` / `_1_h` / `_4_h` | MW | Capacity headroom. *Off by default.* |

### Supply mix and emissions
| Entity | Unit | Notes |
|---|---|---|
| `sensor.caiso_solar`, `_wind`, `_geothermal`, `_biomass`, `_biogas`, `_small_hydro`, `_large_hydro`, `_nuclear`, `_natural_gas`, `_coal`, `_imports` | MW | Current output by source. *Off by default.* |
| `sensor.caiso_batteries` | MW | **Negative = charging**, positive = discharging. `mode`, `standalone_mw` and `hybrid_mw` attributes. *Off by default.* |
| `sensor.caiso_other_generation`, `sensor.caiso_hybrids` | MW | *Off by default.* |
| `sensor.caiso_renewables` | % | CAISO's own renewables share of demand, the figure on its Today's Outlook page. Counts solar, wind, geothermal, biomass, biogas and small hydro (California's renewables-standard definition); large hydro and nuclear don't count. |
| `sensor.caiso_co2_emissions` | t/h | Metric tons of CO2 per hour from CAISO-area generation and imports. *Off by default.* |
| `sensor.caiso_co2_intensity` | g/kWh | Average CO2 per kWh served right now. |
| `sensor.caiso_carbon_intensity_index` | % | **CAISO Carbon Intensity Index.** How dirty the grid is right now compared with the last 14 days: 0 % = the cleanest hour, 100 % = the dirtiest. Calculated by this integration; see [Carbon Intensity Index](#carbon-intensity-index). |
| `binary_sensor.caiso_low_carbon_energy_now` | on/off | **Low Carbon Energy Now.** On when the Carbon Intensity Index is at or below your threshold (25 by default). *Off by default.* |

### Net demand forecast
| Entity | Unit | Notes |
|---|---|---|
| `sensor.caiso_net_demand_forecast` | MW | CAISO's net demand forecast for the current interval. The `forecast` attribute holds hourly forecast and actuals for charts; it isn't saved to the database. *Off by default.* |

### Diagnostic
| Entity | Notes |
|---|---|
| `sensor.caiso_data_updated` | When CAISO last updated its live snapshot (every 5 minutes on its side). Installs from before 0.2.1 keep the ID `sensor.caiso_data_time`, disabled unless you enabled it. |

## Net demand, explained

**Net demand** is CAISO's system demand minus the output of grid-connected (utility-scale) solar and wind. Rooftop solar isn't subtracted: it already lowers demand before CAISO sees it.

CAISO tracks it because solar and wind run on the weather and can't be turned up on request. Net demand is what's left for everything operators *can* control (gas, hydro, imports and batteries, alongside nuclear and geothermal running steadily) to cover.

- **Low net demand** (sunny middays, windy nights) means surplus clean power, often with batteries charging and prices near zero.
- **High net demand**, usually from about 5 to 9 pm when solar fades but demand stays high, is when the grid is most expensive, most carbon-intensive and most strained. That steep evening climb is the "duck curve", and it's when Flex Alerts and emergencies happen.

> These are grid-wide numbers, not your utility bill. Time-of-use rates and local outages are separate. Combine them with your own TOU or price sensors when cost matters.

## Carbon Intensity Index

`sensor.caiso_carbon_intensity_index` (**CAISO Carbon Intensity Index**) puts the grid's current CO2 intensity on a 0–100 % scale relative to recent history:

> **index = (current intensity − cleanest hour) ÷ (dirtiest hour − cleanest hour) × 100**, clamped to 0–100

- **Current intensity** is the live 5-minute value (`sensor.caiso_co2_intensity`, g/kWh): CAISO's total CO2 divided by demand.
- **Cleanest and dirtiest hour** are hourly averages over the last **14 complete days** (adjustable 7–30 in Options), built from CAISO's daily history files with the same definition. Hourly averages keep a single odd 5-minute reading from setting the scale.
- **0** means as clean as any hour in the window, **100** as dirty. Readings outside the window's range are clamped, so a new record low or high shows as 0 or 100.
- Attributes: `window_min` / `window_max` (g/kWh), `window_min_hour` / `window_max_hour` (when they happened), `window_days`.

Example from October 2026: over Oct 6–19 the cleanest hour was 50 g/kWh (Oct 13, 9 AM, a sunny low-demand morning) and the dirtiest 342 g/kWh (Oct 7, 4 AM). On Oct 20 the index read about 100 overnight, 58 at 8 AM and 40–50 through midday.

**What it is and isn't:**
- It reflects the **average** grid mix, so it's a good "how clean is power right now, compared with lately" gauge for dashboards and automations.
- It is **not** marginal emissions like WattTime's MOER, which estimates which plant answers *your* extra load. And it compares against the **past** 14 days; it doesn't forecast the rest of today.

**Low Carbon Energy Now** (`binary_sensor.caiso_low_carbon_energy_now`, off by default) is on when the index is at or below the *Low carbon index threshold* (25 by default), so it means "the grid is in its cleanest quarter for recent days". Because it's relative, it turns on in winter too, not just on sunny spring middays. Lower the threshold to be pickier. It's unknown until the index is available.

**History:** on first install the integration downloads the last 14 days in the background (28 small files), then adds yesterday's two files once a day after CAISO publishes them, just after midnight Pacific. Only each day's cleanest and dirtiest hour is kept, in Home Assistant's storage, so restarts don't download anything again. The index stays unavailable until 3 days are in; that usually takes about a minute after setup. Days CAISO's server fails to deliver are retried an hour later.

## Examples

Ready-to-paste automations (Flex Alert notifications, running loads when the grid is clean, easing off in the evening) and dashboard cards are in **[docs/automations.md](docs/automations.md)**.

Quick start: notify when CAISO issues a Flex Alert or other grid notice.
```yaml
automation:
  - alias: "Grid: CAISO notice"
    triggers:
      - trigger: state
        entity_id: sensor.caiso_grid_status
        from: normal
    actions:
      - action: notify.notify
        data:
          title: "California grid: {{ state_translated('sensor.caiso_grid_status') }}"
          message: Please hold off on big loads until it clears.
```

Tip: values update every poll (15 min by default) and can bounce around a threshold. Use `for:` on triggers (10–15 min) to avoid flapping.

## Data and update frequency

| Feed | URL | Used for | Fetched |
|---|---|---|---|
| Stats snapshot | `https://wwwmobile.caiso.com/outlook/SP/stats.txt` | Status, demand, reserves, supply mix, CO2 | Every poll |
| Net demand curve | `https://www.caiso.com/outlook/current/netdemand.csv` | Today's net demand forecast (the Net demand forecast sensor) | About once an hour |
| Daily history | `https://www.caiso.com/outlook/history/YYYYMMDD/co2.csv` and `demand.csv` | The Carbon Intensity Index's 14-day range | 28 files once (backfill), then 2 a day |

- CAISO refreshes both files every 5 minutes. This integration polls every **15 minutes** by default, with a 30 s timeout per request. That's frequent enough for home automations and gentle on a free public service. You can lower it to 5 minutes in Options.
- The net demand forecast itself only changes about once an hour: around :28 past each hour (Pacific), CAISO revises the coming hour. So the forecast file is fetched on the first poll after :35, on a new day, at startup, and again on the next poll after any failure. At the default interval that's about 24 forecast requests a day instead of 96. Between fetches, the current forecast value is recomputed from the copy already downloaded; the actuals in the `forecast` chart attribute can lag by up to an hour.
- If the forecast file fails, the live sensors keep working. The last forecast fetched today stays in use until the next fetch succeeds. With no forecast yet today, the Net demand forecast sensor goes unavailable.
- **Coverage:** the CAISO balancing area covers most of California, including PG&E, SCE and SDG&E territory and CCAs like SJCE and PCE. LADWP, SMUD, IID and some other municipal utilities run their own balancing areas.
- CO2 figures are CAISO's own estimates for generation serving CAISO load, including imports.

## Troubleshooting

- **Setup says it can't connect:** check that Home Assistant can reach `wwwmobile.caiso.com` (DNS, firewall, Pi-hole). CAISO occasionally has short maintenance outages; try again in a few minutes.
- **Net demand forecast unavailable:** `www.caiso.com/outlook/current/netdemand.csv` didn't answer or changed format. The rest keeps working.
- **Carbon Intensity Index unavailable:** it needs at least 3 days of history from `www.caiso.com/outlook/history/`. Right after setup that takes about a minute. If it stays unavailable, check that Home Assistant can reach that address; failed days are retried every hour.
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

## 💖 Support

If you found this project useful, consider buying me a coffee. ☕

<a href="https://www.buymeacoffee.com/anthonysecco"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="60" width="217"></a>

## AI Disclosure

This project was built largely with AI coding tools (Claude). I directed the design and reviewed the changes, but most of the code and documentation was written by AI. Please review the code before relying on it, and open an issue if you find a problem.

## License

[MIT](LICENSE). Grid data © California ISO, used under its public website terms.
