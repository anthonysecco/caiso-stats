# CAISO Stats for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![GitHub release](https://img.shields.io/github/v/release/anthonysecco/caiso-stats)](https://github.com/anthonysecco/caiso-stats/releases)
[![Validate](https://github.com/anthonysecco/caiso-stats/actions/workflows/validate.yml/badge.svg)](https://github.com/anthonysecco/caiso-stats/actions/workflows/validate.yml)
[![Tests](https://github.com/anthonysecco/caiso-stats/actions/workflows/tests.yml/badge.svg)](https://github.com/anthonysecco/caiso-stats/actions/workflows/tests.yml)

California's grid, live in Home Assistant: grid status and Flex Alerts, demand and net demand, operating reserves, the supply mix, CO2 intensity, and **ready-made load-shifting signals**. Use them to run the EV charger, water heater, pool pump or dishwasher when the grid is clean and has spare capacity, and to back off when it's stressed.

Data comes from the California ISO's free public [Today's Outlook](https://www.caiso.com/todays-outlook) feeds. No account, API key or cloud service is needed.

> **Unofficial.** This project is not affiliated with or endorsed by the California ISO. It reads the same public files that power CAISO's website and mobile app. They're undocumented and can change without notice. A daily CI job checks the live feeds so breakage shows up quickly.

> **AI Coded.** This project is has been largely built and coded by AI.

<img width="483" height="888" alt="image" src="https://github.com/user-attachments/assets/909be513-37ca-4e05-8160-d2a1bdbe481b" /><img width="485" height="915" alt="image" src="https://github.com/user-attachments/assets/84ef5d56-251b-4568-8424-1df0ee62ac46" />

## Contents
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [Load-shifting signals](#load-shifting-signals)
- [Choosing the right signal](#choosing-the-right-signal)
- [CO2 intensity index](#co2-intensity-index)
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
| Clean energy CO2 threshold | 200 g/kWh | **Clean energy now** turns on at or below this grid CO2 intensity. |
| Peak period threshold | 90 % | **Peak demand period** turns on when net demand reaches this share of today's forecast net demand peak. |
| Grid stress reserve threshold | 150 % | **Grid stress** turns on when operating reserve falls below this share of the required reserve, or whenever CAISO reports a non-normal grid status. |
| Solar surplus: battery charging | 1000 MW | **Solar surplus** turns on when grid batteries are charging at least this hard… |
| Solar surplus: solar + wind share | 50 % | …or when solar plus wind supply at least this share of demand. |
| Low demand window length | 3 h | Length of the lowest net demand window searched for in the rest of today's forecast. |
| CO2 intensity index window | 14 days | Days of history (7–30) whose cleanest and dirtiest hour set the [CO2 intensity index](#co2-intensity-index)'s 0 and 100. |

## Entities

Entity IDs below assume the default device name **CAISO**. All power values are in MW for the whole CAISO balancing area.

A fresh install enables 13 entities: the load-shifting signals plus the context that explains them (grid status, net demand, renewables share, CO2 intensity and its 0–100 index, the net demand peak time, the low demand window and when the data was last updated). Everything marked *Off by default* is created disabled. To turn one on, open **Settings → Devices & services → CAISO Stats → entities**, select it and choose **Enable**. Disabled entities record no history, which keeps the database small.

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
| `sensor.caiso_demand` | MW | Current system demand. *Off by default.* |
| `sensor.caiso_net_demand` | MW | Demand minus solar and wind: what dispatchable plants, batteries and imports must cover. |
| `sensor.caiso_today_s_peak_demand` | MW | Highest demand so far today (`peak_time` attribute). *Off by default.* |
| `sensor.caiso_forecast_peak_demand_today` | MW | CAISO's forecast peak for today (`peak_time` attribute). *Off by default.* |
| `sensor.caiso_forecast_peak_demand_tomorrow` | MW | Forecast peak for tomorrow. *Off by default.* |
| `sensor.caiso_operating_reserve` | MW | Current operating reserve. *Off by default.* |
| `sensor.caiso_required_reserve` | MW | Reserve CAISO must hold. *Off by default.* |
| `sensor.caiso_reserve_ratio` | % | Operating reserve ÷ required reserve. Below 100 % means CAISO is short. *Off by default.* |
| `sensor.caiso_available_capacity`, `sensor.caiso_unloaded_capacity_10_min` / `_1_h` / `_4_h` | MW | Capacity headroom. *Off by default.* |

### Supply mix and emissions
| Entity | Unit | Notes |
|---|---|---|
| `sensor.caiso_solar`, `_wind`, `_geothermal`, `_biomass`, `_biogas`, `_small_hydro`, `_large_hydro`, `_nuclear`, `_natural_gas`, `_coal`, `_imports` | MW | Current output by source. *Off by default.* |
| `sensor.caiso_batteries` | MW | **Negative = charging**, positive = discharging. `mode`, `standalone_mw` and `hybrid_mw` attributes. *Off by default.* |
| `sensor.caiso_other_generation`, `sensor.caiso_hybrids` | MW | *Off by default.* |
| `sensor.caiso_renewables` | % | CAISO's own renewables share of demand, the figure on its Today's Outlook page. Counts solar, wind, geothermal, biomass, biogas and small hydro (California's renewables-standard definition); large hydro and nuclear don't count. |
| `sensor.caiso_solar_and_wind_share` | % | Solar + wind share of demand. *Off by default.* |
| `sensor.caiso_co2_emissions` | t/h | Metric tons of CO2 per hour from CAISO-area generation and imports. *Off by default.* |
| `sensor.caiso_co2_intensity` | g/kWh | Average CO2 per kWh served right now. |
| `sensor.caiso_co2_intensity_index` | 0–100 | How dirty the grid is right now compared with the last 14 days: 0 = the cleanest hour, 100 = the dirtiest. See [CO2 intensity index](#co2-intensity-index). |

### Net demand forecast (rest of today)
| Entity | Unit | Notes |
|---|---|---|
| `sensor.caiso_net_demand_forecast` | MW | CAISO's net demand forecast for the current interval. The `forecast` attribute holds hourly forecast and actuals for charts; it isn't saved to the database. *Off by default.* |
| `sensor.caiso_net_demand_peak_forecast` | MW | Today's forecast net demand peak. *Off by default.* |
| `sensor.caiso_net_demand_peak_time` | timestamp | When that peak is expected. |
| `sensor.caiso_low_demand_window_start` | timestamp | Start of the lowest-average net demand window (default 3 h) in the rest of today. `end`, `average_mw` and `hours` attributes. See [the low demand window, explained](#the-low-demand-window-explained). |

### Diagnostic
| Entity | Notes |
|---|---|
| `sensor.caiso_data_updated` | When CAISO last updated its live snapshot (every 5 minutes on its side). Installs from before 0.2.1 keep the ID `sensor.caiso_data_time`, disabled unless you enabled it. |

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

## Choosing the right signal

### What you get out of the box
| Entity | Answers |
|---|---|
| **Load shift recommendation** | *Should flexible loads run right now?* `use_now`, `normal` or `avoid`. Start here. |
| **Solar surplus** | *Is the grid wasting clean power right now?* Batteries charging hard, or solar + wind covering half of demand. |
| **Clean energy now** | *Is power below my CO2 threshold right now?* (default 200 g/kWh) |
| **Peak demand period** | *Are we in today's evening crunch?* |
| **Grid stress** | *Is CAISO short or issuing an alert?* |
| **Low demand window start** | *When should a job I can schedule later today start?* (see below) |
| **Net demand peak time** | *When is today's crunch?* Finish or pre-cool before this. |
| **CO2 intensity index** | *How dirty is power now compared with the last 14 days?* 0–100. |
| **CO2 intensity** | The grid's average CO2 per kWh right now (g/kWh). |
| **Renewables** | CAISO's renewables share of demand right now. |
| **Net demand** | Demand that solar and wind aren't covering; the number most signals are built on. |
| **Grid status** | CAISO's official notice (Normal, Flex Alert, EEA…). |
| **Data updated** | When CAISO last refreshed its numbers, so you can tell the signals are current. |

### Match the signal to the load
| Kind of load | Examples | Use | How |
|---|---|---|---|
| **Runs whenever it's told** | EV charging, pool pump, water heater boost | **Load shift recommendation** | Turn on at `use_now`, off at `avoid`, leave alone at `normal`. Add a deadline fallback (e.g. finish charging by 6 AM). |
| **One run you can schedule** | Dishwasher, laundry, a 3-hour EV top-up | **Low demand window start** | Use it as a time trigger, or check that `end` is before **Net demand peak time**. |
| **Get ahead of the peak** | Pre-cooling, pre-heating, charging a home battery | **Net demand peak time** | Start 1–3 hours before it; coast through **Peak demand period**. |
| **Must-run, nudge only** | Manual chores, cooking | **Load shift recommendation** or **CO2 intensity index** | Notify when `use_now` or index < 25; dashboards. |
| **Protect the grid** | Big loads during emergencies | **Grid stress** | Pause or alert when on; it also forces `avoid`. |

### The low demand window, explained
**Low demand window start** answers: *"I have a job that takes about 3 hours and can run any time later today. When should it start?"*

CAISO forecasts net demand for every hour of today. The integration looks at the hours left until midnight, slides a 3-hour box (adjustable in Options) across them, and reports when the lowest-average stretch begins. `end` and `average_mw` are attributes.

Example (Oct 19, 6 PM): the remaining forecast was 27,770 MW at 6 PM, 27,570 at 7, 26,578 at 8, 25,736 at 9, 24,286 at 10 and 22,816 at 11. The lowest 3-hour stretch is 9 PM–midnight, so the sensor read **9:00 PM**. Earlier on a sunny day it usually points at late morning or midday.

Keep in mind:
- It's a **time**, not a "good right now" signal. For right now, use **Load shift recommendation**.
- It only looks at **the rest of today**; late in the evening the remaining stretch is short, and it resets at midnight.
- The window is chosen by average, so it **can run into the evening peak**: in mid-afternoon it may pick e.g. 3:40–6:40 PM, starting in the solar hours but ending after **Net demand peak time**. For loads that must not run during the peak, check `end` against **Net demand peak time**, or shorten the window length in Options.

### Tips
- **Avoid flapping.** The recommendation and binary signals are re-evaluated every poll (15 min) and can switch back and forth around their thresholds. Use `for:` on triggers (10–15 min) and separate on/off conditions, as in the [examples](docs/automations.md).
- **Clean energy now vs. CO2 intensity index.** *Clean energy now* uses a fixed threshold (200 g/kWh by default). That's easy in spring and summer middays but rarer in winter. Raise it in Options for winter, or use the **CO2 intensity index**, which adapts automatically because it compares with the last 14 days.
- **Combine with your rate plan.** These signals are about the grid, not your bill. For example, require both `use_now` and your utility's off-peak period for the EV.
- **Look at the reasons.** Every signal's attributes list its inputs and thresholds, so a quick look in **Developer tools → States** shows why it's on.

## CO2 intensity index

`sensor.caiso_co2_intensity_index` puts the grid's current CO2 intensity on a 0–100 scale relative to recent history:

> **index = (current intensity − cleanest hour) ÷ (dirtiest hour − cleanest hour) × 100**, clamped to 0–100

- **Current intensity** is the live 5-minute value (`sensor.caiso_co2_intensity`, g/kWh): CAISO's total CO2 divided by demand.
- **Cleanest and dirtiest hour** are hourly averages over the last **14 complete days** (adjustable 7–30 in Options), built from CAISO's daily history files with the same definition. Hourly averages keep a single odd 5-minute reading from setting the scale.
- **0** means as clean as any hour in the window, **100** as dirty. Readings outside the window's range are clamped, so a new record low or high shows as 0 or 100.
- Attributes: `window_min` / `window_max` (g/kWh), `window_min_hour` / `window_max_hour` (when they happened), `window_days`.

Example from October 2026: over Oct 6–19 the cleanest hour was 50 g/kWh (Oct 13, 9 AM, a sunny low-demand morning) and the dirtiest 342 g/kWh (Oct 7, 4 AM). On Oct 20 the index read about 100 overnight, 58 at 8 AM and 40–50 through midday.

**What it is and isn't:**
- It reflects the **average** grid mix, so it's a good "how clean is power right now, compared with lately" gauge for dashboards and automations.
- It is **not** marginal emissions like WattTime's MOER, which estimates which plant answers *your* extra load. And it compares against the **past** 14 days, not the next 24 hours. For the best time later today, use **Low demand window start**.

**History:** on first install the integration downloads the last 14 days in the background (28 small files), then adds yesterday's two files once a day after CAISO publishes them, just after midnight Pacific. Only each day's cleanest and dirtiest hour is kept, in Home Assistant's storage, so restarts don't download anything again. The index stays unavailable until 3 days are in; that usually takes about a minute after setup. Days CAISO's server fails to deliver are retried an hour later.

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
            reserve ratio {{ state_attr('binary_sensor.caiso_grid_stress', 'reserve_ratio') | float(0) | round | int }} %.
            Please hold off on big loads until it clears.
```

## Data and update frequency

| Feed | URL | Used for | Fetched |
|---|---|---|---|
| Stats snapshot | `https://wwwmobile.caiso.com/outlook/SP/stats.txt` | Status, demand, reserves, supply mix, CO2 | Every poll |
| Net demand curve | `https://www.caiso.com/outlook/current/netdemand.csv` | Today's net demand forecast, peak and low window | About once an hour |
| Daily history | `https://www.caiso.com/outlook/history/YYYYMMDD/co2.csv` and `demand.csv` | The CO2 intensity index's 14-day range | 28 files once (backfill), then 2 a day |

- CAISO refreshes both files every 5 minutes. This integration polls every **15 minutes** by default, with a 30 s timeout per request. That's frequent enough for load shifting and gentle on a free public service. You can lower it to 5 minutes in Options.
- The net demand forecast itself only changes about once an hour: around :28 past each hour (Pacific), CAISO revises the coming hour. So the forecast file is fetched on the first poll after :35, on a new day, at startup, and again on the next poll after any failure. At the default interval that's about 24 forecast requests a day instead of 96. Between fetches, the low demand window and the current forecast value are recomputed from the copy already downloaded; the actuals in the `forecast` chart attribute can lag by up to an hour.
- If the forecast file fails, the live sensors keep working. The last forecast fetched today stays in use until the next fetch succeeds. With no forecast yet today, the forecast entities go unavailable and **Peak demand period** falls back to CAISO's demand-peak forecast.
- **Coverage:** the CAISO balancing area covers most of California, including PG&E, SCE and SDG&E territory and CCAs like SJCE and PCE. LADWP, SMUD, IID and some other municipal utilities run their own balancing areas.
- CO2 figures are CAISO's own estimates for generation serving CAISO load, including imports.

## Troubleshooting

- **Setup says it can't connect:** check that Home Assistant can reach `wwwmobile.caiso.com` (DNS, firewall, Pi-hole). CAISO occasionally has short maintenance outages; try again in a few minutes.
- **Forecast sensors unavailable:** `www.caiso.com/outlook/current/netdemand.csv` didn't answer or changed format. The rest keeps working.
- **CO2 intensity index unavailable:** it needs at least 3 days of history from `www.caiso.com/outlook/history/`. Right after setup that takes about a minute. If it stays unavailable, check that Home Assistant can reach that address; failed days are retried every hour.
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
