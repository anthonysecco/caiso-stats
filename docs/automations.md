# Automation and dashboard examples

Replace the `switch.*`, `climate.*` and `notify.*` entities with your own. Each example works on its own; paste it into **Settings → Automations → ⋮ → Edit in YAML**, or into `automations.yaml` without the leading `- `.

- [Flex Alert / grid stress notifications](#flex-alert--grid-stress-notifications)
- [EV charging that follows the grid](#ev-charging-that-follows-the-grid)
- [Water heater boost in the low-demand window](#water-heater-boost-in-the-low-demand-window)
- [Pre-cool before the evening peak](#pre-cool-before-the-evening-peak)
- [Nudge to start the dishwasher or laundry](#nudge-to-start-the-dishwasher-or-laundry)
- [Run when the grid is at its cleanest](#run-when-the-grid-is-at-its-cleanest)
- [Pool pump only on surplus](#pool-pump-only-on-surplus)
- [Dashboard cards](#dashboard-cards)
- [Template ideas](#template-ideas)

## Flex Alert / grid stress notifications

```yaml
alias: "Grid: status changed"
triggers:
  - trigger: state
    entity_id: sensor.caiso_grid_status
    not_to: [unavailable, unknown]
    not_from: [unavailable, unknown]
actions:
  - action: notify.notify
    data:
      title: >-
        {{ 'California grid back to normal' if trigger.to_state.state == 'normal'
           else 'California grid: ' ~ state_translated('sensor.caiso_grid_status') }}
      message: >-
        Reserve ratio {{ state_attr('binary_sensor.caiso_grid_stress', 'reserve_ratio') | float(0) | round | int }} %,
        net demand {{ states('sensor.caiso_net_demand') | int(0) }} MW.
        {% if trigger.to_state.state != 'normal' %}Please minimise use, especially 4–9 pm.{% endif %}
mode: queued
```

## EV charging that follows the grid

Charge on `use_now`, stop on `avoid`, and leave the charger alone otherwise. A safety net still finishes charging by morning.

```yaml
alias: "EV: follow CAISO signal"
triggers:
  - trigger: state
    entity_id: sensor.caiso_load_shift_recommendation
    to: use_now
    id: start
  - trigger: state
    entity_id: sensor.caiso_load_shift_recommendation
    to: avoid
    id: stop
  - trigger: time
    at: "00:30:00"
    id: overnight
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: [start, overnight]
        sequence:
          - action: switch.turn_on
            target:
              entity_id: switch.ev_charger
      - conditions:
          - condition: trigger
            id: stop
        sequence:
          - action: switch.turn_off
            target:
              entity_id: switch.ev_charger
mode: single
```

## Water heater boost in the low-demand window

`sensor.caiso_low_demand_window_start` is a timestamp, so a time trigger can fire on it directly.

```yaml
alias: "Water heater: boost in CAISO low-demand window"
triggers:
  - trigger: time
    at: sensor.caiso_low_demand_window_start
conditions:
  - condition: state
    entity_id: binary_sensor.caiso_grid_stress
    state: "off"
actions:
  - action: water_heater.set_operation_mode
    target:
      entity_id: water_heater.tank
    data:
      operation_mode: high_demand
  - delay:
      hours: "{{ state_attr('sensor.caiso_low_demand_window_start', 'hours') | float(3) }}"
  - action: water_heater.set_operation_mode
    target:
      entity_id: water_heater.tank
    data:
      operation_mode: heat_pump
mode: restart
```

## Pre-cool before the evening peak

Cool the house a little extra two hours before the forecast net demand peak, then coast through it.

```yaml
alias: "HVAC: pre-cool before grid peak"
triggers:
  - trigger: template
    value_template: >-
      {% set peak = states('sensor.caiso_net_demand_peak_time') | as_datetime %}
      {{ peak is not none and now() >= peak - timedelta(hours=2) and now() < peak }}
conditions:
  - condition: state
    entity_id: climate.living_room
    state: cool
  - condition: numeric_state
    entity_id: weather.home
    attribute: temperature
    above: 85
actions:
  - action: climate.set_temperature
    target:
      entity_id: climate.living_room
    data:
      temperature: 72
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.caiso_peak_demand_period
        to: "on"
    timeout: "02:30:00"
  - action: climate.set_temperature
    target:
      entity_id: climate.living_room
    data:
      temperature: 78
mode: single
```

## Nudge to start the dishwasher or laundry

```yaml
alias: "Nudge: good time for big appliances"
triggers:
  - trigger: state
    entity_id: sensor.caiso_load_shift_recommendation
    to: use_now
    for: "00:15:00"
conditions:
  - condition: time
    after: "08:00:00"
    before: "21:00:00"
actions:
  - action: notify.notify
    data:
      message: >-
        Clean power on the grid right now ({{ states('sensor.caiso_co2_intensity') | int(0) }} g/kWh,
        {{ states('sensor.caiso_renewables') | int(0) }} % renewable). Good time for the dishwasher or laundry.
mode: single
```

## Run when the grid is at its cleanest

The [CO2 intensity index](../README.md#co2-intensity-index) is 0 at the cleanest hour of the last 14 days and 100 at the dirtiest. This starts the water heater boost once the grid reaches its cleanest quarter, and stops it if things get dirty again.

```yaml
alias: "Water heater: boost when the grid is clean"
triggers:
  - trigger: numeric_state
    entity_id: sensor.caiso_co2_intensity_index
    below: 25
    for: "00:10:00"
    id: clean
  - trigger: numeric_state
    entity_id: sensor.caiso_co2_intensity_index
    above: 50
    id: dirty
actions:
  - action: "switch.turn_{{ 'on' if trigger.id == 'clean' else 'off' }}"
    target:
      entity_id: switch.water_heater_boost
mode: restart
```

## Pool pump only on surplus

```yaml
alias: "Pool pump: run on solar surplus"
triggers:
  - trigger: state
    entity_id: binary_sensor.caiso_solar_surplus
actions:
  - action: "switch.turn_{{ 'on' if trigger.to_state.state == 'on' else 'off' }}"
    target:
      entity_id: switch.pool_pump
mode: restart
```

## Dashboard cards

Grid summary with built-in cards:
```yaml
type: vertical-stack
cards:
  - type: tile
    entity: sensor.caiso_load_shift_recommendation
    features_position: bottom
  - type: grid
    columns: 2
    square: false
    cards:
      - type: tile
        entity: sensor.caiso_grid_status
      - type: tile
        entity: sensor.caiso_renewables
      - type: tile
        entity: sensor.caiso_net_demand
      - type: tile
        entity: sensor.caiso_low_demand_window_start
  - type: gauge
    entity: sensor.caiso_co2_intensity_index
    name: Grid CO2 vs. last 14 days
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 35
      red: 70
  - type: history-graph
    hours_to_show: 24
    entities:
      - entity: sensor.caiso_net_demand
      - entity: sensor.caiso_co2_intensity
```

Net demand forecast vs. actual, with [ApexCharts Card](https://github.com/RomRider/apexcharts-card) (also from HACS). Enable `sensor.caiso_net_demand_forecast` first; it's off by default.
```yaml
type: custom:apexcharts-card
header:
  show: true
  title: CAISO net demand today
graph_span: 24h
span:
  start: day
now:
  show: true
series:
  - entity: sensor.caiso_net_demand_forecast
    name: Forecast
    data_generator: |
      return entity.attributes.forecast.map(p => [new Date(p.time).getTime(), p.forecast_mw]);
  - entity: sensor.caiso_net_demand_forecast
    name: Actual
    data_generator: |
      return entity.attributes.forecast.filter(p => p.actual_mw !== null)
        .map(p => [new Date(p.time).getTime(), p.actual_mw]);
```

## Template ideas

Minutes until the forecast peak:
```jinja
{{ ((as_datetime(states('sensor.caiso_net_demand_peak_time')) - now()).total_seconds() / 60) | round(0) }}
```

Is the grid charging its batteries?
```jinja
{{ state_attr('binary_sensor.caiso_solar_surplus', 'batteries_mw') | float(0) < 0 }}
```

Fossil share of demand (enable the natural gas, coal and demand sensors first):
```jinja
{{ ((states('sensor.caiso_natural_gas') | float(0) + states('sensor.caiso_coal') | float(0))
    / states('sensor.caiso_demand') | float(1) * 100) | round | int }}
```
