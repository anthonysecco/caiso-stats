"""CO2 intensity history behind the 0-100 CO2 intensity index.

Index = (current intensity - lowest hour) / (highest hour - lowest hour) x 100, clamped to 0-100,
where the lowest and highest hours are hourly-average intensities over the last N complete days
(default 14). Only each day's cleanest and dirtiest hour is stored, in HA storage, so restarts
don't download anything again; a fresh install backfills the window from CAISO's daily files.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import CaisoClient, CaisoError, DayIntensity
from .const import (
    CAISO_TZ,
    DOMAIN,
    HISTORY_PUBLISH_HOUR,
    INDEX_MIN_HISTORY_DAYS,
    LOGGER,
    MAX_INDEX_DAYS,
)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.co2_intensity_history"
FETCH_SPACING_SECONDS = 1.0  # pause between days during a backfill; tests set this to 0


@dataclass(slots=True, frozen=True)
class IndexRange:
    """Cleanest and dirtiest hour in the index window."""

    min_g: float
    min_at: datetime
    max_g: float
    max_at: datetime
    days: int


def co2_index(current: float | None, window: IndexRange | None) -> int | None:
    """Where `current` sits between the window's cleanest (0) and dirtiest (100) hour."""
    if current is None or window is None or window.max_g <= window.min_g:
        return None
    share = (current - window.min_g) / (window.max_g - window.min_g)
    return round(max(0.0, min(1.0, share)) * 100)


def _hour_start(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), CAISO_TZ)


class IntensityHistory:
    """Each past day's cleanest and dirtiest hour, persisted across restarts."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Bind to HA storage (call async_load before use)."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.days: dict[date, DayIntensity] = {}

    async def async_load(self) -> None:
        """Read stored days; a missing or damaged file just means a fresh backfill."""
        data = await self._store.async_load() or {}
        for key, value in (data.get("days") or {}).items():
            try:
                self.days[date.fromisoformat(key)] = DayIntensity(**value)
            except (TypeError, ValueError):
                continue

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "days": {
                    d.isoformat(): {
                        "min_g": v.min_g,
                        "min_hour": v.min_hour,
                        "max_g": v.max_g,
                        "max_hour": v.max_hour,
                        "hours": v.hours,
                    }
                    for d, v in sorted(self.days.items())
                }
            }
        )

    def missing_days(self, now: datetime, window_days: int) -> list[date]:
        """Complete days in the window not stored yet, newest first.

        Yesterday counts only once CAISO has had time to publish it (after HISTORY_PUBLISH_HOUR PT).
        """
        local = now.astimezone(CAISO_TZ)
        newest = local.date() - timedelta(days=1 if local.hour >= HISTORY_PUBLISH_HOUR else 2)
        today = local.date()
        wanted = [today - timedelta(days=i) for i in range(1, window_days + 1)]
        return [d for d in wanted if d <= newest and d not in self.days]

    def window(self, now: datetime, window_days: int) -> IndexRange | None:
        """Lowest and highest hour over the last `window_days` complete days (None until enough days)."""
        today = now.astimezone(CAISO_TZ).date()
        first = today - timedelta(days=window_days)
        days = {d: v for d, v in self.days.items() if first <= d < today}
        if len(days) < INDEX_MIN_HISTORY_DAYS:
            return None
        low_day = min(days, key=lambda d: days[d].min_g)
        high_day = max(days, key=lambda d: days[d].max_g)
        return IndexRange(
            min_g=days[low_day].min_g,
            min_at=_hour_start(low_day, days[low_day].min_hour),
            max_g=days[high_day].max_g,
            max_at=_hour_start(high_day, days[high_day].max_hour),
            days=len(days),
        )

    async def async_backfill(self, client: CaisoClient, days: list[date]) -> int:
        """Download the given days one at a time; returns how many were added. Failures are retried later."""
        added = 0
        for i, day in enumerate(days):
            if i:
                await asyncio.sleep(FETCH_SPACING_SECONDS)
            try:
                self.days[day] = await client.history_day(day)
            except CaisoError as err:
                LOGGER.debug("CO2 history for %s not available yet: %s", day, err)
                continue
            added += 1
        if self.days:
            oldest = max(self.days) - timedelta(days=MAX_INDEX_DAYS + 1)
            for stale in [d for d in self.days if d < oldest]:
                del self.days[stale]
        if added:
            await self._async_save()
        return added
