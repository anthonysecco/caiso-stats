"""Setup, entities and failure handling."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.caiso_stats.const import DEFAULT_OPTIONS, DOMAIN, NET_DEMAND_URL, STATS_URL


ENABLED_BY_DEFAULT = {
    "sensor.caiso_load_shift_recommendation",
    "binary_sensor.caiso_grid_stress",
    "binary_sensor.caiso_peak_demand_period",
    "binary_sensor.caiso_clean_energy_now",
    "binary_sensor.caiso_solar_surplus",
    "sensor.caiso_grid_status",
    "sensor.caiso_net_demand",
    "sensor.caiso_clean_energy",
    "sensor.caiso_co2_intensity",
    "sensor.caiso_net_demand_peak_time",
    "sensor.caiso_low_demand_window_start",
}


async def _setup(hass: HomeAssistant, enable: tuple[str, ...] = ()) -> MockConfigEntry:
    """Set up the entry, then enable the given disabled-by-default entities and reload."""
    entry = MockConfigEntry(domain=DOMAIN, title="CAISO", data={}, options=dict(DEFAULT_OPTIONS))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if enable:
        registry = er.async_get(hass)
        for entity_id in enable:
            registry.async_update_entity(entity_id, disabled_by=None)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_default_enabled_entities(hass: HomeAssistant, mock_caiso) -> None:
    """Only the load-shifting signals and their key context are enabled on a fresh install."""
    entry = await _setup(hass)
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert {e.entity_id for e in entries if e.disabled_by is None} == ENABLED_BY_DEFAULT
    hidden = er.async_get(hass).async_get("sensor.caiso_unloaded_capacity_10_min")
    assert hidden is not None and hidden.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_setup_creates_entities(hass: HomeAssistant, mock_caiso) -> None:
    entry = await _setup(
        hass, enable=("sensor.caiso_demand", "sensor.caiso_batteries", "sensor.caiso_net_demand_peak_forecast")
    )
    assert entry.state is ConfigEntryState.LOADED

    status = hass.states.get("sensor.caiso_grid_status")
    assert status.state == "normal"
    assert status.attributes["notices"] == ["Normal"]
    assert float(hass.states.get("sensor.caiso_net_demand").state) == 28542

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

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_forecast_feed_down(hass: HomeAssistant, aioclient_mock, stats_text) -> None:
    """Live stats still work when netdemand.csv fails; forecast entities go unavailable."""
    aioclient_mock.get(STATS_URL, text=stats_text)
    aioclient_mock.get(NET_DEMAND_URL, status=503)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert float(hass.states.get("sensor.caiso_net_demand").state) == 28542
    assert hass.states.get("sensor.caiso_net_demand_peak_time").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.caiso_low_demand_window_start").state == STATE_UNAVAILABLE
    # peak period falls back to demand vs. CAISO's forecast demand peak
    assert hass.states.get("binary_sensor.caiso_peak_demand_period").state == "on"


def _csv_fetches(aioclient_mock) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]) == NET_DEMAND_URL)


async def test_forecast_fetched_hourly(hass: HomeAssistant, mock_caiso, freezer) -> None:
    """stats.txt every poll; netdemand.csv again only once CAISO's hourly revision is out."""
    freezer.move_to("2026-10-19 18:00:00-07:00")
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    assert _csv_fetches(mock_caiso) == 1

    freezer.move_to("2026-10-19 18:20:00-07:00")
    await coordinator.async_refresh()
    assert _csv_fetches(mock_caiso) == 1
    assert hass.states.get("sensor.caiso_net_demand_peak_time").state == "2026-10-20T01:05:00+00:00"

    freezer.move_to("2026-10-19 18:40:00-07:00")
    await coordinator.async_refresh()
    assert _csv_fetches(mock_caiso) == 2


async def test_forecast_retried_after_failure(
    hass: HomeAssistant, aioclient_mock, stats_text, net_demand_text, freezer
) -> None:
    """A failed netdemand.csv fetch is retried on the next poll, not an hour later."""
    freezer.move_to("2026-10-19 18:00:00-07:00")
    aioclient_mock.get(STATS_URL, text=stats_text)
    aioclient_mock.get(NET_DEMAND_URL, status=503)
    entry = await _setup(hass)
    assert hass.states.get("sensor.caiso_net_demand_peak_time").state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, text=stats_text)
    aioclient_mock.get(NET_DEMAND_URL, text=net_demand_text)
    freezer.move_to("2026-10-19 18:05:00-07:00")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.caiso_net_demand_peak_time").state == "2026-10-20T01:05:00+00:00"


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
