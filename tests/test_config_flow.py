"""Config and options flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.caiso_stats.const import DEFAULT_OPTIONS, DOMAIN, STATS_URL


async def test_user_flow(hass: HomeAssistant, mock_caiso) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "CAISO"
    assert result["options"] == DEFAULT_OPTIONS


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(STATS_URL, text="<html>down for maintenance</html>")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_single_instance(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data={}, options=dict(DEFAULT_OPTIONS)).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass: HomeAssistant, mock_caiso) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=dict(DEFAULT_OPTIONS))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    new = {**DEFAULT_OPTIONS, "scan_interval": 5, "clean_co2_threshold": 250}
    result = await hass.config_entries.options.async_configure(result["flow_id"], new)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["clean_co2_threshold"] == 250
    # reloaded with the new threshold: 213.5 g/kWh now counts as clean
    assert hass.states.get("binary_sensor.caiso_clean_energy_now").state == "on"
