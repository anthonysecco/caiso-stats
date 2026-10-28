"""Low Carbon Energy Now binary sensor for CAISO Stats."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_LOW_CARBON_INDEX, DEFAULT_OPTIONS
from .coordinator import CaisoConfigEntry, CaisoData
from .entity import CaisoEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CaisoBinaryDescription(BinarySensorEntityDescription):
    """Describes one binary sensor."""

    is_on_fn: Callable[[CaisoData], bool | None]
    attrs_fn: Callable[[CaisoData, dict[str, Any]], dict[str, Any]]


BINARY_SENSORS: tuple[CaisoBinaryDescription, ...] = (
    # "Low Carbon Energy Now": the carbon intensity index at or below the threshold; off by default.
    CaisoBinaryDescription(
        key="clean_energy_now",
        translation_key="clean_energy_now",
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: d.low_carbon_now,
        attrs_fn=lambda d, o: {
            "co2_intensity": d.co2_intensity,
            "co2_intensity_index": d.co2_index,
            "index_threshold": o[CONF_LOW_CARBON_INDEX],
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CaisoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(CaisoBinarySensor(coordinator, description) for description in BINARY_SENSORS)


class CaisoBinarySensor(CaisoEntity, BinarySensorEntity):
    """A binary sensor derived from the carbon intensity index."""

    entity_description: CaisoBinaryDescription

    @property
    def is_on(self) -> bool | None:
        """Signal state."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Inputs and thresholds behind the signal."""
        options = {**DEFAULT_OPTIONS, **self.coordinator.config_entry.options}
        return self.entity_description.attrs_fn(self.coordinator.data, options)
