# Automation and dashboard examples

Replace the `switch.*`, `climate.*` and `notify.*` entities with your own. Each example works on its own; paste it into **Settings → Automations → ⋮ → Edit in YAML**, or into `automations.yaml` without the leading `- `.

Installs from before 0.3.0 keep the older entity IDs `sensor.caiso_co2_intensity_index` and `binary_sensor.caiso_clean_energy_now`; swap those in where these examples use `sensor.caiso_carbon_intensity_index` and `binary_sensor.caiso_low_carbon_energy_now`.

- [Flex Alert / grid notice notifications](#flex-alert--grid-notice-notifications)
- [EV charging when the grid is clean](#ev-charging-when-the-grid-is-clean)
- [Water heater boost when the grid is clean](#water-heater-boost-when-the-grid-is-clean)
- [Ease off during the evening ramp](#ease-off-during-the-evening-ramp)
- [Nudge to start the dishwasher or laundry](#nudge-to-start-the-dishwasher-or-laundry)
- [Pool pump while grid batteries are charging](#pool-pump-while-grid-batteries-are-charging)
- [Dashboard cards](#dashboard-cards)
- [Template ideas](#template-ideas)

## Flex Alert / grid notice notifications

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
        Net demand {{ states('sensor.caiso_net_demand') | int(0) }} MW.
        {% if trigger.to_state.state != 'normal' %}Please minimise use, especially 4–9 pm.{% endif %}
mode: queued
```

## EV charging when the grid is clean

Charge while **Low Carbon Energy Now** is on (enable it first; it's off by default), and pause during any CAISO grid notice. A safety net still finishes charging by morning.

```yaml
alias: "EV: charge on clean power"
triggers:
  - trigger: state
    entity_id: binary_sensor.caiso_low_carbon_energy_now
    to: "on"
    for: "00:10:00"
    id: start
  - trigger: state
    entity_id: binary_sensor.caiso_low_carbon_energy_now
    to: "off"
    for: "00:10:00"
    id: stop
  - trigger: state
    entity_id: sensor.caiso_grid_status
    from: normal
    id: stop
  - trigger: time
    at: "00:30:00"
    id: overnight
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: [start, overnight]
          - condition: state
            entity_id: sensor.caiso_grid_status
            state: normal
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

## Water heater boost when the grid is clean

The [Carbon Intensity Index](../README.md#carbon-intensity-index) is 0 at the cleanest hour of the last 14 days and 100 at the dirtiest. This starts the boost once the grid reaches its cleanest quarter, and stops it if things get dirty again.

```yaml
alias: "Water heater: boost when the grid is clean"
triggers:
  - trigger: numeric_state
    entity_id: sensor.caiso_carbon_intensity_index
    below: 25
    for: "00:10:00"
    id: clean
  - trigger: numeric_state
    entity_id: sensor.caiso_carbon_intensity_index
    above: 50
    id: dirty
actions:
  - action: "switch.turn_{{ 'on' if trigger.id == 'clean' else 'off' }}"
    target:
      entity_id: switch.water_heater_boost
mode: restart
```

## Ease off during the evening ramp

Cool the house a little extra in the mid-afternoon, let it drift while net demand is high, and go back to normal once it falls. Net demand peaks differ by season, so pick the two thresholds from your own `sensor.caiso_net_demand` history.

```yaml
alias: "HVAC: coast through the evening ramp"
triggers:
  - trigger: time
    at: "15:00:00"
    id: precool
  - trigger: numeric_state
    entity_id: sensor.caiso_net_demand
    above: 25000
    for: "00:10:00"
    id: coast
  - trigger: numeric_state
    entity_id: sensor.caiso_net_demand
    below: 22000
    for: "00:10:00"
    id: normal
conditions:
  - condition: state
    entity_id: climate.living_room
    state: cool
actions:
  - action: climate.set_temperature
    target:
      entity_id: climate.living_room
    data:
      temperature: "{{ {'precool': 72, 'coast': 78, 'normal': 75}[trigger.id] }}"
mode: queued
```

## Nudge to start the dishwasher or laundry

```yaml
alias: "Nudge: good time for big appliances"
triggers:
  - trigger: numeric_state
    entity_id: sensor.caiso_carbon_intensity_index
    below: 25
    for: "00:15:00"
conditions:
  - condition: time
    after: "08:00:00"
    before: "21:00:00"
  - condition: state
    entity_id: sensor.caiso_grid_status
    state: normal
actions:
  - action: notify.notify
    data:
      message: >-
        Clean power on the grid right now ({{ states('sensor.caiso_co2_intensity') | int(0) }} g/kWh,
        {{ states('sensor.caiso_renewables') | int(0) }} % renewable). Good time for the dishwasher or laundry.
mode: single
```

## Pool pump while grid batteries are charging

When CAISO's batteries are charging hard, the grid has more solar than it needs. Enable `sensor.caiso_batteries` first; it's off by default. Negative values mean charging.

```yaml
alias: "Pool pump: run on solar surplus"
triggers:
  - trigger: numeric_state
    entity_id: sensor.caiso_batteries
    below: -1000
    for: "00:10:00"
    id: surplus
  - trigger: numeric_state
    entity_id: sensor.caiso_batteries
    above: 0
    for: "00:10:00"
    id: done
actions:
  - action: "switch.turn_{{ 'on' if trigger.id == 'surplus' else 'off' }}"
    target:
      entity_id: switch.pool_pump
mode: restart
```

## Dashboard cards

Grid summary with built-in cards:
```yaml
type: vertical-stack
cards:
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
        entity: sensor.caiso_co2_intensity
  - type: gauge
    entity: sensor.caiso_carbon_intensity_index
    name: Grid carbon vs. last 14 days
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

Today's forecast net demand peak, in MW (enable the Net demand forecast sensor first):
```jinja
{{ state_attr('sensor.caiso_net_demand_forecast', 'forecast') | map(attribute='forecast_mw') | select('number') | max }}
```

Is the grid charging its batteries? (enable the Batteries sensor first)
```jinja
{{ states('sensor.caiso_batteries') | float(0) < 0 }}
```

Fossil share of demand (enable the natural gas, coal and demand sensors first):
```jinja
{{ ((states('sensor.caiso_natural_gas') | float(0) + states('sensor.caiso_coal') | float(0))
    / states('sensor.caiso_demand') | float(1) * 100) | round | int }}
```
