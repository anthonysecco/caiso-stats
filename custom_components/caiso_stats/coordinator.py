"""Polling coordinator and the derived load-shifting signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CaisoClient, CaisoError, NetDemandDay, Stats, parse_net_demand, parse_stats, worst_status
from .const import (
    CONF_CLEAN_CO2,
    CONF_PEAK_PERCENT,
    CONF_RESERVE_RATIO,
    CONF_SCAN_INTERVAL,
    CONF_SURPLUS_BATTERY,
    CONF_SURPLUS_SHARE,
    CONF_WINDOW_HOURS,
    DEFAULT_OPTIONS,
    DOMAIN,
    LOGGER,
    scan_interval,
)

type CaisoConfigEntry = ConfigEntry[CaisoCoordinator]


@dataclass(slots=True)
class Window:
    """A stretch of the net demand forecast."""

    start: datetime
    end: datetime
    average_mw: float


@dataclass(slots=True)
class CaisoData:
    """Everything the entities read, refreshed together."""

    stats: Stats
    net_demand: NetDemandDay | None
    net_demand_error: str | None
    grid_status: str
    reserve_ratio: float | None
    co2_intensity: float | None
    clean_percent: float | None
    variable_renewable_share: float | None
    peak_mw: float | None
    peak_time: datetime | None
    low_window: Window | None
    grid_stress: bool
    clean_now: bool | None
    peak_period: bool | None
    solar_surplus: bool | None
    recommendation: str


def _ratio(num: float | None, den: float | None) -> float | None:
    if num is None or not den:
        return None
    return round(num / den * 100, 1)


def _sum(*values: float | None) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def lowest_window(day: NetDemandDay, start: datetime, hours: float) -> Window | None:
    """Lowest-average `hours`-long stretch of the forecast from `start` to the end of the day."""
    pts = [
        p
        for p in day.points
        if p.time >= start - timedelta(minutes=5) and p.time.date() == day.day and p.net_demand_forecast is not None
    ]
    if len(pts) < 2:
        return None
    step = pts[1].time - pts[0].time
    size = max(1, min(len(pts), round(timedelta(hours=hours) / step)))
    best_i, best_avg = 0, float("inf")
    for i in range(len(pts) - size + 1):
        avg = sum(p.net_demand_forecast for p in pts[i : i + size]) / size  # type: ignore[misc]
        if avg < best_avg:
            best_i, best_avg = i, avg
    chunk = pts[best_i : best_i + size]
    return Window(start=chunk[0].time, end=chunk[-1].time + step, average_mw=round(best_avg))


def derive(stats: Stats, net_day: NetDemandDay | None, options: dict[str, Any], now: datetime) -> CaisoData:
    """Compute every derived value from one stats snapshot and today's forecast."""
    opts = {**DEFAULT_OPTIONS, **options}
    demand = stats.num("CurrentSystemDemand")
    net_demand = stats.num("CurrentNetDemand")

    reserve_ratio = _ratio(stats.num("Current_reserve"), stats.num("Required_reserve"))
    intensity = stats.num("currentCo2intensity")
    co2_intensity = round(intensity * 1000, 1) if intensity is not None else None
    clean = _sum(stats.num("currentRenewables"), stats.num("currentLargeHydro"), stats.num("currentNuclear"))
    clean_percent = _ratio(clean, demand)
    vre_share = _ratio(_sum(stats.num("currentSolar"), stats.num("currentWind")), demand)

    peak_mw = peak_time = low_window = None
    if net_day is not None:
        forecast = [p for p in net_day.points if p.net_demand_forecast is not None and p.time.date() == net_day.day]
        if forecast:
            top = max(forecast, key=lambda p: p.net_demand_forecast)  # type: ignore[arg-type,return-value]
            peak_mw, peak_time = top.net_demand_forecast, top.time
        low_window = lowest_window(net_day, stats.updated or now, float(opts[CONF_WINDOW_HOURS]))

    status = worst_status(stats.statuses)
    grid_stress = status != "normal" or (
        reserve_ratio is not None and reserve_ratio < float(opts[CONF_RESERVE_RATIO])
    )
    clean_now = co2_intensity <= float(opts[CONF_CLEAN_CO2]) if co2_intensity is not None else None

    # Peak: compare net demand with today's forecast net-demand peak; without the
    # forecast file, fall back to demand vs. CAISO's forecast demand peak.
    share = float(opts[CONF_PEAK_PERCENT]) / 100
    if peak_mw and net_demand is not None:
        peak_period: bool | None = net_demand >= share * peak_mw
    elif stats.num("todayForecastPeakDemand") and demand is not None:
        peak_period = demand >= share * stats.num("todayForecastPeakDemand")  # type: ignore[operator]
    else:
        peak_period = None

    batteries = stats.num("currentBatteries")
    surplus_flags = [
        batteries is not None and batteries <= -float(opts[CONF_SURPLUS_BATTERY]),
        vre_share is not None and vre_share >= float(opts[CONF_SURPLUS_SHARE]),
    ]
    solar_surplus = any(surplus_flags) if (batteries is not None or vre_share is not None) else None

    if grid_stress or peak_period:
        recommendation = "avoid"
    elif solar_surplus or clean_now:
        recommendation = "use_now"
    else:
        recommendation = "normal"

    return CaisoData(
        stats=stats,
        net_demand=net_day,
        net_demand_error=None,
        grid_status=status,
        reserve_ratio=reserve_ratio,
        co2_intensity=co2_intensity,
        clean_percent=clean_percent,
        variable_renewable_share=vre_share,
        peak_mw=peak_mw,
        peak_time=peak_time,
        low_window=low_window,
        grid_stress=grid_stress,
        clean_now=clean_now,
        peak_period=peak_period,
        solar_surplus=solar_surplus,
        recommendation=recommendation,
    )


class CaisoCoordinator(DataUpdateCoordinator[CaisoData]):
    """Fetches stats.txt and netdemand.csv together on one schedule."""

    config_entry: CaisoConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CaisoConfigEntry) -> None:
        """Set up from the entry's options."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=scan_interval(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_OPTIONS[CONF_SCAN_INTERVAL])),
        )
        self.client = CaisoClient(async_get_clientsession(hass))
        self.raw_stats: str | None = None
        self.raw_net_demand: str | None = None

    async def _async_update_data(self) -> CaisoData:
        try:
            stats_text, net_text = await self.client.fetch()
            stats = parse_stats(stats_text)
        except CaisoError as err:
            raise UpdateFailed(str(err)) from err
        self.raw_stats = stats_text

        now = dt_util.now()
        net_day: NetDemandDay | None = None
        net_error: str | None = None
        if isinstance(net_text, CaisoError):
            net_error = str(net_text)
        else:
            self.raw_net_demand = net_text
            try:
                net_day = parse_net_demand(net_text, stats.updated or now)
            except CaisoError as err:
                net_error = str(err)
        if net_error:
            LOGGER.debug("Net demand forecast unavailable: %s", net_error)

        data = derive(stats, net_day, dict(self.config_entry.options), now)
        data.net_demand_error = net_error
        return data
