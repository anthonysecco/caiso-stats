"""Client and parsers for CAISO's public Today's Outlook feeds.

Both feeds are free and need no key:
- stats.txt: a JSON snapshot behind CAISO's mobile app (grid status, demand,
  reserves, supply mix, CO2), refreshed every 5 minutes. It is undocumented, so
  every field is read defensively.
- netdemand.csv: today's 5-minute demand / net demand curve, including CAISO's
  net demand forecast for the rest of the day (times are Pacific).
- history/YYYYMMDD/co2.csv and demand.csv: a past day's 5-minute CO2 (t/h by source)
  and demand, used for the CO2 intensity index's 14-day range.
"""

from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import io
import json
from typing import Any

import aiohttp

from .const import CAISO_TZ, HISTORY_URL, NET_DEMAND_URL, REQUEST_TIMEOUT, STATS_URL

USER_AGENT = "HomeAssistant-CAISO-Stats (+https://github.com/anthonysecco/caiso-stats)"
HISTORY_ATTEMPTS = 3
HISTORY_RETRY_SECONDS = 2.0  # tests set this to 0


class CaisoError(Exception):
    """A feed could not be fetched or understood."""


# --- grid status ---------------------------------------------------------------

GRID_STATUS_OPTIONS = [
    "normal",
    "rmo",
    "flex_alert",
    "eea_watch",
    "transmission_emergency",
    "eea_1",
    "eea_2",
    "eea_3",
    "other",
]
_SEVERITY = {s: i for i, s in enumerate(GRID_STATUS_OPTIONS)}
_SEVERITY["other"] = _SEVERITY["rmo"]  # unknown notices rank just above normal


def normalize_status(text: str) -> str:
    """Map one CAISO grid notice to a stable slug."""
    t = " ".join(str(text).lower().replace("-", " ").split())
    if not t or t == "normal" or t.startswith("normal "):
        return "normal"
    if "flex" in t:
        return "flex_alert"
    if "watch" in t:
        return "eea_watch"
    for level in ("3", "2", "1"):
        if f"eea {level}" in t or f"eea{level}" in t or f"emergency alert {level}" in t:
            return f"eea_{level}"
    if "transmission" in t:
        return "transmission_emergency"
    if "restricted maintenance" in t or t == "rmo" or t.startswith("rmo "):
        return "rmo"
    return "other"


def worst_status(statuses: list[str]) -> str:
    """Most severe slug among the reported notices ("normal" if none)."""
    slugs = [normalize_status(s) for s in statuses] or ["normal"]
    return max(slugs, key=lambda s: _SEVERITY[s])


# --- stats.txt -------------------------------------------------------------------


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _pacific(value: Any, fmt: str) -> datetime | None:
    try:
        return datetime.strptime(str(value).strip(), fmt).replace(tzinfo=CAISO_TZ)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class Stats:
    """Parsed stats.txt snapshot."""

    raw: dict[str, Any]
    updated: datetime | None
    statuses: list[str]

    def num(self, key: str) -> float | None:
        """Numeric field, or None when missing/non-numeric."""
        return _number(self.raw.get(key))

    def ts(self, key: str) -> datetime | None:
        """A yyyymmddHHMMSS Pacific timestamp field."""
        return _pacific(self.raw.get(key), "%Y%m%d%H%M%S")


def parse_stats(text: str) -> Stats:
    """Parse stats.txt (JSON, sometimes with a BOM)."""
    try:
        raw = json.loads(text.lstrip("﻿"))
    except ValueError as err:
        raise CaisoError(f"stats.txt is not valid JSON: {err}") from err
    if not isinstance(raw, dict) or "CurrentSystemDemand" not in raw:
        raise CaisoError("stats.txt did not contain the expected fields")
    status = raw.get("gridstatus")
    if isinstance(status, str):
        statuses = [status]
    elif isinstance(status, list):
        statuses = [str(s) for s in status if s]
    else:
        statuses = []
    return Stats(raw=raw, updated=_pacific(raw.get("slotDate"), "%m/%d/%Y %H:%M"), statuses=statuses)


# --- netdemand.csv --------------------------------------------------------------


@dataclass(slots=True)
class NetDemandPoint:
    """One 5-minute row of netdemand.csv."""

    time: datetime
    demand: float | None
    net_demand: float | None
    net_demand_forecast: float | None


@dataclass(slots=True)
class NetDemandDay:
    """Today's net demand curve."""

    day: date
    points: list[NetDemandPoint] = field(default_factory=list)


def parse_net_demand(text: str, reference: datetime) -> NetDemandDay:
    """Parse netdemand.csv. `reference` (Pacific, usually the stats slot time) picks the date.

    The file has no date column: rows run 00:00..23:55 plus a closing 00:00. Just after
    midnight CAISO can still be serving yesterday's file, which shows up as actuals
    "later" in the day than the reference time.
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    rows = []
    for row in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        try:
            clock = datetime.strptime(row.get("time", ""), "%H:%M").time()
        except ValueError:
            continue
        rows.append((clock, row))
    if not rows or "net demand forecast" not in rows[0][1]:
        raise CaisoError("netdemand.csv did not contain the expected columns")

    reference = reference.astimezone(CAISO_TZ)
    day = reference.date()
    last_actual = max((c for c, r in rows[:-1] if _number(r.get("net demand")) is not None), default=None)
    ref_minutes = reference.hour * 60 + reference.minute
    if last_actual is not None and last_actual.hour * 60 + last_actual.minute - ref_minutes > 60:
        day -= timedelta(days=1)

    points: list[NetDemandPoint] = []
    offset = 0
    previous: time | None = None
    for clock, row in rows:
        if previous is not None and clock < previous:
            offset += 1
        previous = clock
        when = datetime.combine(day + timedelta(days=offset), clock, tzinfo=CAISO_TZ)
        points.append(
            NetDemandPoint(
                time=when,
                demand=_number(row.get("current demand")),
                net_demand=_number(row.get("net demand")),
                net_demand_forecast=_number(row.get("net demand forecast")),
            )
        )
    return NetDemandDay(day=day, points=points)


# --- HTTP ------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class DayIntensity:
    """Cleanest and dirtiest hour of one Pacific day (hourly-average CO2 intensity, g/kWh)."""

    min_g: float
    min_hour: int
    max_g: float
    max_hour: int
    hours: int


def _first_rows(text: str) -> dict[str, dict[str, str]]:
    """CSV rows keyed by their HH:MM time, stopping where the clock wraps (the closing 00:00)."""
    rows: dict[str, dict[str, str]] = {}
    previous = ""
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        clock = row.get("time", "")
        if len(clock) != 5 or clock[2] != ":":
            continue
        if clock < previous:
            break
        previous = clock
        rows.setdefault(clock, row)
    return rows


def parse_day_intensity(co2_text: str, demand_text: str) -> DayIntensity:
    """Hourly-average CO2 intensity from a day's history co2.csv and demand.csv.

    Intensity = total CO2 (metric t/h, every "... CO2" column) / current demand (MW), the same
    definition as stats.txt's currentCo2intensity. Hours need at least half their 5-minute rows.
    """
    co2_rows, demand_rows = _first_rows(co2_text), _first_rows(demand_text)
    if not co2_rows or not demand_rows or not any(k.endswith("co2") for k in next(iter(co2_rows.values()))):
        raise CaisoError("history files did not contain the expected columns")
    samples: dict[int, list[float]] = {}
    for clock, row in co2_rows.items():
        demand = _number(demand_rows.get(clock, {}).get("current demand"))
        values = [_number(v) for k, v in row.items() if k.endswith("co2")]
        if not demand or demand <= 0 or all(v is None for v in values):
            continue
        tonnes = sum(v for v in values if v is not None)
        samples.setdefault(int(clock[:2]), []).append(tonnes / demand * 1000)
    hourly = {h: sum(v) / len(v) for h, v in samples.items() if len(v) >= 6}
    if not hourly:
        raise CaisoError("history files had no complete hours")
    low = min(hourly, key=lambda h: hourly[h])
    high = max(hourly, key=lambda h: hourly[h])
    return DayIntensity(round(hourly[low], 1), low, round(hourly[high], 1), high, len(hourly))


class CaisoClient:
    """Fetches CAISO's feeds with one shared timeout."""

    def __init__(self, session: aiohttp.ClientSession, timeout: float = REQUEST_TIMEOUT) -> None:
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _get(self, url: str) -> str:
        try:
            async with self._session.get(
                url, timeout=self._timeout, headers={"User-Agent": USER_AGENT}
            ) as resp:
                resp.raise_for_status()
                return await resp.text(encoding="utf-8")
        except TimeoutError as err:
            raise CaisoError(f"Timed out fetching {url}") from err
        except aiohttp.ClientError as err:
            raise CaisoError(f"Error fetching {url}: {err}") from err

    async def stats_text(self) -> str:
        """Raw stats.txt."""
        return await self._get(STATS_URL)

    async def net_demand_text(self) -> str:
        """Raw netdemand.csv."""
        return await self._get(NET_DEMAND_URL)

    async def history_day(self, day: date) -> DayIntensity:
        """A past day's hourly CO2 intensity range, from its co2.csv and demand.csv.

        CAISO's file server drops connections now and then, so each file gets a few tries.
        """
        texts = []
        for name in ("co2", "demand"):
            url = HISTORY_URL.format(day=day.strftime("%Y%m%d"), name=name)
            for attempt in range(HISTORY_ATTEMPTS):
                try:
                    texts.append(await self._get(url))
                    break
                except CaisoError:
                    if attempt == HISTORY_ATTEMPTS - 1:
                        raise
                    await asyncio.sleep(HISTORY_RETRY_SECONDS * (attempt + 1))
        return parse_day_intensity(*texts)

    async def fetch(self, net_demand: bool = True) -> tuple[str, str | CaisoError | None]:
        """stats.txt, plus netdemand.csv in parallel unless `net_demand` is False (then None).

        stats.txt errors raise; a net demand error is returned.
        """
        if not net_demand:
            return await self.stats_text(), None
        stats, net = await asyncio.gather(self.stats_text(), self.net_demand_text(), return_exceptions=True)
        if isinstance(stats, BaseException):
            raise stats if isinstance(stats, CaisoError) else CaisoError(str(stats))
        if isinstance(net, BaseException):
            net = net if isinstance(net, CaisoError) else CaisoError(str(net))
        return stats, net
