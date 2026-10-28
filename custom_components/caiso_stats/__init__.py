"""CAISO Stats: California grid conditions from CAISO's Today's Outlook."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, LOGGER
from .coordinator import CaisoConfigEntry, CaisoCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

# Entities earlier versions created that this one no longer provides.
RETIRED_ENTITIES: tuple[tuple[Platform, str], ...] = (
    (Platform.SENSOR, "clean_energy"),  # removed in 0.2.0
    # removed in 0.3.0: the load-shifting signals; the integration now mirrors CAISO's own data
    (Platform.SENSOR, "load_shift_recommendation"),
    (Platform.BINARY_SENSOR, "peak_period"),
    (Platform.BINARY_SENSOR, "grid_stress"),
    (Platform.BINARY_SENSOR, "solar_surplus"),
    (Platform.SENSOR, "reserve_ratio"),
    (Platform.SENSOR, "solar_wind_share"),
    (Platform.SENSOR, "net_demand_peak_time"),
    (Platform.SENSOR, "net_demand_peak_forecast"),
    (Platform.SENSOR, "low_demand_window_start"),
)


def _remove_retired_entities(hass: HomeAssistant, entry: CaisoConfigEntry) -> None:
    registry = er.async_get(hass)
    for platform, key in RETIRED_ENTITIES:
        if entity_id := registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}"):
            LOGGER.info("Removing retired CAISO Stats entity %s", entity_id)
            registry.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: CaisoConfigEntry) -> bool:
    """Set up CAISO Stats from a config entry."""
    coordinator = CaisoCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _remove_retired_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CaisoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
