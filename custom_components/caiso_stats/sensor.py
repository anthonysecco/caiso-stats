"""Sensors for CAISO Stats."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import GRID_STATUS_OPTIONS
from .coordinator import CaisoConfigEntry, CaisoData
from .entity import CaisoEntity

PARALLEL_UPDATES = 0

UNIT_CO2_RATE = "t/h"
UNIT_CO2_INTENSITY = "g/kWh"
RECOMMENDATION_OPTIONS = ["avoid", "normal", "use_now"]

StateType = str | float | datetime | None


@dataclass(frozen=True, kw_only=True)
class CaisoSensorDescription(SensorEntityDescription):
    """Describes one CAISO sensor."""

    value_fn: Callable[[CaisoData], StateType]
    attrs_fn: Callable[[CaisoData], dict[str, Any]] | None = None
    available_fn: Callable[[CaisoData], bool] = lambda _: True


def _num(key: str) -> Callable[[CaisoData], float | None]:
    return lambda d: d.stats.num(key)


def _ts_attr(name: str, key: str) -> Callable[[CaisoData], dict[str, Any]]:
    def attrs(d: CaisoData) -> dict[str, Any]:
        when = d.stats.ts(key)
        return {name: when.isoformat() if when else None}

    return attrs


def _mw(key: str, field: str, **kwargs: Any) -> CaisoSensorDescription:
    """A MW power sensor read straight from stats.txt."""
    return CaisoSensorDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfPower.MEGA_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_num(field),
        **kwargs,
    )


def _pct(key: str, value_fn: Callable[[CaisoData], float | None], **kwargs: Any) -> CaisoSensorDescription:
    return CaisoSensorDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=value_fn,
        **kwargs,
    )


def _has_forecast(d: CaisoData) -> bool:
    return d.net_demand is not None


def _battery_attrs(d: CaisoData) -> dict[str, Any]:
    mw = d.stats.num("currentBatteries")
    mode = None if mw is None else "charging" if mw < 0 else "discharging" if mw > 0 else "idle"
    return {
        "mode": mode,
        "standalone_mw": d.stats.num("currentBatteriesStandalone"),
        "hybrid_mw": d.stats.num("currentBatteriesHybrid"),
    }


def _forecast_now(d: CaisoData) -> float | None:
    if d.net_demand is None or d.stats.updated is None:
        return None
    past = [p for p in d.net_demand.points if p.time <= d.stats.updated and p.net_demand_forecast is not None]
    return past[-1].net_demand_forecast if past else None


def _forecast_attrs(d: CaisoData) -> dict[str, Any]:
    """Hourly net demand forecast (actuals where known) for charts; not recorded."""
    if d.net_demand is None:
        return {}
    hourly = []
    for p in d.net_demand.points:
        if p.time.minute == 0 and p.time.date() == d.net_demand.day:
            hourly.append(
                {"time": p.time.isoformat(), "forecast_mw": p.net_demand_forecast, "actual_mw": p.net_demand}
            )
    return {"forecast": hourly}


def _window_attrs(d: CaisoData) -> dict[str, Any]:
    w = d.low_window
    return {
        "end": w.end.isoformat() if w else None,
        "average_mw": w.average_mw if w else None,
        "hours": round((w.end - w.start) / timedelta(hours=1), 2) if w else None,
    }


def _recommendation_attrs(d: CaisoData) -> dict[str, Any]:
    return {
        "grid_stress": d.grid_stress,
        "peak_period": d.peak_period,
        "solar_surplus": d.solar_surplus,
        "clean_now": d.clean_now,
    }


SENSORS: tuple[CaisoSensorDescription, ...] = (
    # --- load-shift signal ---
    CaisoSensorDescription(
        key="load_shift_recommendation",
        translation_key="load_shift_recommendation",
        device_class=SensorDeviceClass.ENUM,
        options=RECOMMENDATION_OPTIONS,
        value_fn=lambda d: d.recommendation,
        attrs_fn=_recommendation_attrs,
    ),
    # --- grid ---
    CaisoSensorDescription(
        key="grid_status",
        translation_key="grid_status",
        device_class=SensorDeviceClass.ENUM,
        options=GRID_STATUS_OPTIONS,
        value_fn=lambda d: d.grid_status,
        attrs_fn=lambda d: {"notices": d.stats.statuses},
    ),
    _mw("net_demand", "CurrentNetDemand", attrs_fn=_ts_attr("as_of", "CurrentNetDemandTS")),
    # Grid detail below is disabled by default; the signals read it directly.
    _mw(
        "demand",
        "CurrentSystemDemand",
        attrs_fn=_ts_attr("as_of", "CurrentSystemDemandTS"),
        entity_registry_enabled_default=False,
    ),
    _mw(
        "todays_peak_demand",
        "TodaysPeakDemand",
        attrs_fn=_ts_attr("peak_time", "TodaysPeakDemandTS"),
        entity_registry_enabled_default=False,
    ),
    _mw(
        "forecast_peak_demand_today",
        "todayForecastPeakDemand",
        attrs_fn=_ts_attr("peak_time", "todayForecastPeakDemandTS"),
        entity_registry_enabled_default=False,
    ),
    _mw("forecast_peak_demand_tomorrow", "tomorrowsForecastPeakDemand", entity_registry_enabled_default=False),
    _mw("current_reserve", "Current_reserve", entity_registry_enabled_default=False),
    _mw("required_reserve", "Required_reserve", entity_registry_enabled_default=False),
    _pct("reserve_ratio", lambda d: d.reserve_ratio, entity_registry_enabled_default=False),
    _mw("available_capacity", "AvailableCapacity", entity_registry_enabled_default=False),
    _mw("unloaded_capacity_10m", "Unloaded_capacity_10M", entity_registry_enabled_default=False),
    _mw("unloaded_capacity_1h", "Unloaded_capacity_1H", entity_registry_enabled_default=False),
    _mw("unloaded_capacity_4h", "Unloaded_capacity_4H", entity_registry_enabled_default=False),
    # --- supply mix: clean energy % and CO2 intensity stay enabled, the per-source detail doesn't ---
    _mw("solar", "currentSolar", entity_registry_enabled_default=False),
    _mw("wind", "currentWind", entity_registry_enabled_default=False),
    _mw("geothermal", "currentGeothermal", entity_registry_enabled_default=False),
    _mw("biomass", "currentBiomass", entity_registry_enabled_default=False),
    _mw("biogas", "currentBiogas", entity_registry_enabled_default=False),
    _mw("small_hydro", "currentSmallHydro", entity_registry_enabled_default=False),
    _mw("large_hydro", "currentLargeHydro", entity_registry_enabled_default=False),
    _mw("nuclear", "currentNuclear", entity_registry_enabled_default=False),
    _mw("natural_gas", "currentNaturalGas", entity_registry_enabled_default=False),
    _mw("coal", "currentCoal", entity_registry_enabled_default=False),
    _mw("imports", "currentImports", entity_registry_enabled_default=False),
    _mw("other", "currentOther", entity_registry_enabled_default=False),
    _mw("batteries", "currentBatteries", attrs_fn=_battery_attrs, entity_registry_enabled_default=False),
    _mw("hybrids", "currentHybrids", entity_registry_enabled_default=False),
    _pct("renewables", _num("renewablesPercent"), entity_registry_enabled_default=False),
    _pct("clean_energy", lambda d: d.clean_percent),
    _pct("solar_wind_share", lambda d: d.variable_renewable_share, entity_registry_enabled_default=False),
    CaisoSensorDescription(
        key="co2_emissions",
        translation_key="co2_emissions",
        native_unit_of_measurement=UNIT_CO2_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_num("currentCo2"),
        entity_registry_enabled_default=False,
    ),
    CaisoSensorDescription(
        key="co2_intensity",
        translation_key="co2_intensity",
        native_unit_of_measurement=UNIT_CO2_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.co2_intensity,
    ),
    # --- net demand forecast (netdemand.csv) ---
    CaisoSensorDescription(
        key="net_demand_forecast",
        translation_key="net_demand_forecast",
        native_unit_of_measurement=UnitOfPower.MEGA_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_forecast_now,
        attrs_fn=_forecast_attrs,
        available_fn=_has_forecast,
        entity_registry_enabled_default=False,
    ),
    CaisoSensorDescription(
        key="net_demand_peak_forecast",
        translation_key="net_demand_peak_forecast",
        native_unit_of_measurement=UnitOfPower.MEGA_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.peak_mw,
        available_fn=_has_forecast,
        entity_registry_enabled_default=False,
    ),
    CaisoSensorDescription(
        key="net_demand_peak_time",
        translation_key="net_demand_peak_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.peak_time,
        available_fn=_has_forecast,
    ),
    CaisoSensorDescription(
        key="low_demand_window_start",
        translation_key="low_demand_window_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.low_window.start if d.low_window else None,
        attrs_fn=_window_attrs,
        available_fn=_has_forecast,
    ),
    # --- diagnostics ---
    CaisoSensorDescription(
        key="data_time",
        translation_key="data_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.stats.updated,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CaisoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(CaisoSensor(coordinator, description) for description in SENSORS)


class CaisoSensor(CaisoEntity, SensorEntity):
    """A CAISO value."""

    entity_description: CaisoSensorDescription
    _unrecorded_attributes = frozenset({"forecast", "notices"})

    @property
    def available(self) -> bool:
        """Unavailable when the feed it depends on is."""
        return super().available and self.entity_description.available_fn(self.coordinator.data)

    @property
    def native_value(self) -> StateType:
        """Current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra context for automations and cards."""
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None
