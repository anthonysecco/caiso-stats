"""Load-shifting binary sensors for CAISO Stats."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CLEAN_CO2,
    CONF_PEAK_PERCENT,
    CONF_RESERVE_RATIO,
    CONF_SURPLUS_BATTERY,
    CONF_SURPLUS_SHARE,
    DEFAULT_OPTIONS,
)
from .coordinator import CaisoConfigEntry, CaisoData
from .entity import CaisoEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CaisoBinaryDescription(BinarySensorEntityDescription):
    """Describes one load-shift signal."""

    is_on_fn: Callable[[CaisoData], bool | None]
    attrs_fn: Callable[[CaisoData, dict[str, Any]], dict[str, Any]]


BINARY_SENSORS: tuple[CaisoBinaryDescription, ...] = (
    CaisoBinaryDescription(
        key="grid_stress",
        translation_key="grid_stress",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: d.grid_stress,
        attrs_fn=lambda d, o: {
            "grid_status": d.grid_status,
            "reserve_ratio": d.reserve_ratio,
            "reserve_ratio_threshold": o[CONF_RESERVE_RATIO],
        },
    ),
    CaisoBinaryDescription(
        key="peak_period",
        translation_key="peak_period",
        is_on_fn=lambda d: d.peak_period,
        attrs_fn=lambda d, o: {
            "net_demand_mw": d.stats.num("CurrentNetDemand"),
            "forecast_peak_mw": d.peak_mw,
            "forecast_peak_time": d.peak_time.isoformat() if d.peak_time else None,
            "peak_percent": o[CONF_PEAK_PERCENT],
        },
    ),
    CaisoBinaryDescription(
        key="clean_energy_now",
        translation_key="clean_energy_now",
        is_on_fn=lambda d: d.clean_now,
        attrs_fn=lambda d, o: {"co2_intensity": d.co2_intensity, "threshold": o[CONF_CLEAN_CO2]},
    ),
    CaisoBinaryDescription(
        key="solar_surplus",
        translation_key="solar_surplus",
        is_on_fn=lambda d: d.solar_surplus,
        attrs_fn=lambda d, o: {
            "batteries_mw": d.stats.num("currentBatteries"),
            "solar_wind_share": d.variable_renewable_share,
            "battery_charging_threshold_mw": o[CONF_SURPLUS_BATTERY],
            "solar_wind_share_threshold": o[CONF_SURPLUS_SHARE],
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
    """A derived load-shifting signal."""

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
