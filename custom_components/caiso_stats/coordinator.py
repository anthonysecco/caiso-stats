"""Polling coordinator and the carbon intensity index."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CaisoClient, CaisoError, NetDemandDay, Stats, parse_net_demand, parse_stats, worst_status
from .const import (
    CAISO_TZ,
    CONF_INDEX_DAYS,
    CONF_LOW_CARBON_INDEX,
    CONF_SCAN_INTERVAL,
    DEFAULT_OPTIONS,
    DOMAIN,
    HISTORY_RETRY_HOURS,
    LOGGER,
    MAX_INDEX_DAYS,
    MIN_INDEX_DAYS,
    NET_DEMAND_REFRESH_MINUTE,
    scan_interval,
)
from .history import IndexRange, IntensityHistory, co2_index

type CaisoConfigEntry = ConfigEntry[CaisoCoordinator]


@dataclass(slots=True)
class CaisoData:
    """Everything the entities read, refreshed together."""

    stats: Stats
    net_demand: NetDemandDay | None
    net_demand_error: str | None
    grid_status: str
    co2_intensity: float | None
    low_carbon_now: bool | None
    co2_index: int | None = None
    index_range: IndexRange | None = None


def net_demand_due(fetched: datetime | None, now: datetime) -> bool:
    """Whether netdemand.csv needs fetching again.

    `fetched` is the last fetch that returned today's curve (None at startup, after a failure
    or while CAISO still serves yesterday's file). Otherwise refetch on a new Pacific day and
    once an hour, after CAISO revises the next hour's forecast.
    """
    if fetched is None:
        return True
    now, fetched = now.astimezone(CAISO_TZ), fetched.astimezone(CAISO_TZ)
    if fetched.date() != now.date():
        return True
    refresh = now.replace(minute=NET_DEMAND_REFRESH_MINUTE, second=0, microsecond=0)
    if refresh > now:
        refresh -= timedelta(hours=1)
    return fetched < refresh


def derive(
    stats: Stats,
    net_day: NetDemandDay | None,
    options: dict[str, Any],
    index_range: IndexRange | None = None,
) -> CaisoData:
    """Everything the entities read, from one stats snapshot, today's forecast and the CO2 history range."""
    opts = {**DEFAULT_OPTIONS, **options}
    intensity = stats.num("currentCo2intensity")
    co2_intensity = round(intensity * 1000, 1) if intensity is not None else None
    # Low carbon: the index (0 = cleanest hour of recent days) at or below the threshold.
    # Unknown until enough history is in.
    index = co2_index(co2_intensity, index_range)
    low_carbon_now = index <= float(opts[CONF_LOW_CARBON_INDEX]) if index is not None else None

    return CaisoData(
        stats=stats,
        net_demand=net_day,
        net_demand_error=None,
        grid_status=worst_status(stats.statuses),
        co2_intensity=co2_intensity,
        low_carbon_now=low_carbon_now,
        co2_index=index,
        index_range=index_range,
    )


class CaisoCoordinator(DataUpdateCoordinator[CaisoData]):
    """Fetches stats.txt every poll and netdemand.csv about once an hour."""

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
        self._net_day: NetDemandDay | None = None
        self._net_fetched: datetime | None = None
        self.history = IntensityHistory(hass)
        self._backfill_task: asyncio.Task[None] | None = None
        self._backfill_tried: datetime | None = None

    @property
    def index_days(self) -> int:
        """Days of history behind the carbon intensity index."""
        days = int(self.config_entry.options.get(CONF_INDEX_DAYS, DEFAULT_OPTIONS[CONF_INDEX_DAYS]))
        return max(MIN_INDEX_DAYS, min(MAX_INDEX_DAYS, days))

    async def _async_setup(self) -> None:
        """Load the stored CO2 history before the first update."""
        await self.history.async_load()

    def _maybe_backfill(self, now: datetime) -> None:
        """Start downloading missing history days in the background (at most hourly after a failure)."""
        if self._backfill_task is not None and not self._backfill_task.done():
            return
        if self._backfill_tried and now - self._backfill_tried < timedelta(hours=HISTORY_RETRY_HOURS):
            return
        missing = self.history.missing_days(now, self.index_days)
        if not missing:
            return
        self._backfill_tried = now
        self._backfill_task = self.config_entry.async_create_background_task(
            self.hass, self._async_backfill(missing), f"{DOMAIN} CO2 history backfill"
        )

    async def _async_backfill(self, days: list[date]) -> None:
        added = await self.history.async_backfill(self.client, days)
        if added:
            # All in: no retry wait needed. Then refresh the index (and the low-carbon signal
            # built on it) without waiting for the next poll.
            self._backfill_tried = None if len(days) == added else self._backfill_tried
            if self.data is not None:
                now = dt_util.now()
                data = derive(
                    self.data.stats,
                    self._net_day,
                    dict(self.config_entry.options),
                    self.history.window(now, self.index_days),
                )
                data.net_demand_error = self.data.net_demand_error
                self.data = data
                self.async_update_listeners()

    async def _async_update_data(self) -> CaisoData:
        now = dt_util.now()
        try:
            stats_text, net_text = await self.client.fetch(net_demand=net_demand_due(self._net_fetched, now))
            stats = parse_stats(stats_text)
        except CaisoError as err:
            raise UpdateFailed(str(err)) from err
        self.raw_stats = stats_text

        reference = stats.updated or now
        today = reference.astimezone(CAISO_TZ).date()
        net_error: str | None = None
        if isinstance(net_text, CaisoError):
            net_error = str(net_text)
        elif net_text is not None:
            self.raw_net_demand = net_text
            try:
                self._net_day = parse_net_demand(net_text, reference)
            except CaisoError as err:
                net_error = str(err)
            else:
                # Just after midnight CAISO can still serve yesterday's file; keep refetching until it rolls over.
                self._net_fetched = now if self._net_day.day == today else None
        if net_error:
            LOGGER.debug("Net demand forecast unavailable: %s", net_error)
            # Retry next poll; meanwhile keep the last curve only while it's still today's.
            if self._net_day is not None and self._net_day.day != today:
                self._net_day = None

        window = self.history.window(now, self.index_days)
        data = derive(stats, self._net_day, dict(self.config_entry.options), window)
        data.net_demand_error = net_error
        self._maybe_backfill(now)
        return data
