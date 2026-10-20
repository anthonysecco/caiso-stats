"""CAISO Stats: California grid conditions and load-shifting signals."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, LOGGER
from .coordinator import CaisoConfigEntry, CaisoCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

# Sensors earlier versions created that this one no longer provides.
RETIRED_SENSOR_KEYS = ("clean_energy",)  # removed in 0.2.0


def _remove_retired_entities(hass: HomeAssistant, entry: CaisoConfigEntry) -> None:
    registry = er.async_get(hass)
    for key in RETIRED_SENSOR_KEYS:
        if entity_id := registry.async_get_entity_id(Platform.SENSOR, DOMAIN, f"{entry.entry_id}_{key}"):
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
