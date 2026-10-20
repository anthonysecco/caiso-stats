"""Config and options flow for CAISO Stats."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode
import voluptuous as vol

from .api import CaisoClient, CaisoError, parse_stats
from .const import (
    CONF_CLEAN_CO2,
    CONF_INDEX_DAYS,
    CONF_PEAK_PERCENT,
    CONF_RESERVE_RATIO,
    CONF_SCAN_INTERVAL,
    CONF_SURPLUS_BATTERY,
    CONF_SURPLUS_SHARE,
    CONF_WINDOW_HOURS,
    DEFAULT_OPTIONS,
    DOMAIN,
    LOGGER,
    MAX_INDEX_DAYS,
    MAX_SCAN_INTERVAL,
    MIN_INDEX_DAYS,
    MIN_SCAN_INTERVAL,
)
from .coordinator import CaisoConfigEntry


def _number(minimum: float, maximum: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=step, unit_of_measurement=unit, mode=NumberSelectorMode.BOX
        )
    )


OPTION_FIELDS = {
    CONF_SCAN_INTERVAL: _number(MIN_SCAN_INTERVAL, MAX_SCAN_INTERVAL, 1, "min"),
    CONF_CLEAN_CO2: _number(0, 1000, 5, "g/kWh"),
    CONF_PEAK_PERCENT: _number(50, 100, 1, "%"),
    CONF_RESERVE_RATIO: _number(100, 500, 5, "%"),
    CONF_SURPLUS_BATTERY: _number(0, 20000, 100, "MW"),
    CONF_SURPLUS_SHARE: _number(10, 150, 5, "%"),
    CONF_WINDOW_HOURS: _number(0.5, 12, 0.5, "h"),
    CONF_INDEX_DAYS: _number(MIN_INDEX_DAYS, MAX_INDEX_DAYS, 1, "d"),
}


def options_schema(current: dict[str, Any]) -> vol.Schema:
    """Options form, pre-filled with the current values."""
    values = {**DEFAULT_OPTIONS, **current}
    return vol.Schema({vol.Required(key, default=values[key]): field for key, field in OPTION_FIELDS.items()})


class CaisoStatsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add CAISO Stats (one per installation; no credentials needed)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm, then check that CAISO answers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = CaisoClient(async_get_clientsession(self.hass))
            try:
                parse_stats(await client.stats_text())
            except CaisoError as err:
                LOGGER.warning("CAISO stats.txt check failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="CAISO", data={}, options=dict(DEFAULT_OPTIONS))
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: CaisoConfigEntry) -> CaisoStatsOptionsFlow:
        """Thresholds and polling interval."""
        return CaisoStatsOptionsFlow()


class CaisoStatsOptionsFlow(OptionsFlowWithReload):
    """Edit polling interval and load-shift thresholds; the entry reloads on save."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show or save the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=options_schema(dict(self.config_entry.options)))
