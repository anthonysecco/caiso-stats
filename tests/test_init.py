"""Setup, entities and failure handling."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.caiso_stats.const import DEFAULT_OPTIONS, DOMAIN, NET_DEMAND_URL, STATS_URL


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="CAISO", data={}, options=dict(DEFAULT_OPTIONS))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_creates_entities(hass: HomeAssistant, mock_caiso) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    status = hass.states.get("sensor.caiso_grid_status")
    assert status.state == "normal"
    assert status.attributes["notices"] == ["Normal"]

    demand = hass.states.get("sensor.caiso_demand")
    assert float(demand.state) == 31245
    assert demand.attributes["unit_of_measurement"] == "MW"
    assert demand.attributes["device_class"] == "power"
    assert demand.attributes["state_class"] == "measurement"

    assert float(hass.states.get("sensor.caiso_co2_intensity").state) == 213.5
    assert hass.states.get("sensor.caiso_co2_intensity").attributes["unit_of_measurement"] == "g/kWh"
    assert hass.states.get("sensor.caiso_batteries").attributes["mode"] == "discharging"
    assert float(hass.states.get("sensor.caiso_net_demand_peak_forecast").state) == 27770
    assert hass.states.get("sensor.caiso_net_demand_peak_time").state == "2026-10-20T01:05:00+00:00"
    assert hass.states.get("sensor.caiso_load_shift_recommendation").state == "avoid"
    assert hass.states.get("binary_sensor.caiso_grid_stress").state == "off"
    assert hass.states.get("binary_sensor.caiso_peak_demand_period").state == "on"
    assert hass.states.get("binary_sensor.caiso_clean_energy_now").state == "off"
    assert hass.states.get("binary_sensor.caiso_solar_surplus").state == "off"

    registry = er.async_get(hass)
    hidden = registry.async_get("sensor.caiso_unloaded_capacity_10_min")
    assert hidden is not None and hidden.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_forecast_feed_down(hass: HomeAssistant, aioclient_mock, stats_text) -> None:
    """Live stats still work when netdemand.csv fails; forecast entities go unavailable."""
    aioclient_mock.get(STATS_URL, text=stats_text)
    aioclient_mock.get(NET_DEMAND_URL, status=503)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert float(hass.states.get("sensor.caiso_demand").state) == 31245
    assert hass.states.get("sensor.caiso_net_demand_peak_forecast").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.caiso_low_demand_window_start").state == STATE_UNAVAILABLE
    # peak period falls back to demand vs. CAISO's forecast demand peak
    assert hass.states.get("binary_sensor.caiso_peak_demand_period").state == "on"


async def test_stats_feed_down_retries(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(STATS_URL, status=500)
    aioclient_mock.get(NET_DEMAND_URL, status=500)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_diagnostics(hass: HomeAssistant, mock_caiso) -> None:
    from custom_components.caiso_stats.diagnostics import async_get_config_entry_diagnostics

    entry = await _setup(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["derived"]["recommendation"] == "avoid"
    assert diag["stats"]["CurrentSystemDemand"] == 31245
