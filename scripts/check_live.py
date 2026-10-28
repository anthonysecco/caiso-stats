"""Fetch CAISO's real feeds and run them through the integration's parsers.

Catches upstream format changes. Run from the repo root: python scripts/check_live.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.caiso_stats.api import CaisoClient, CaisoError, DayIntensity, parse_net_demand, parse_stats
from custom_components.caiso_stats.const import CAISO_TZ
from custom_components.caiso_stats.coordinator import derive

REQUIRED = (
    "CurrentSystemDemand",
    "CurrentNetDemand",
    "Current_reserve",
    "Required_reserve",
    "currentSolar",
    "currentWind",
    "currentNaturalGas",
    "currentBatteries",
    "currentCo2intensity",
    "renewablesPercent",
    "todayForecastPeakDemand",
)


async def main() -> int:
    async with aiohttp.ClientSession() as session:
        client = CaisoClient(session)
        stats_text, net_text = await client.fetch()
        # Two days back is always published (yesterday appears just after midnight PT).
        history_day = datetime.now(CAISO_TZ).date() - timedelta(days=2)
        try:
            past: DayIntensity | CaisoError = await client.history_day(history_day)
        except CaisoError as err:
            past = err
    stats = parse_stats(stats_text)
    missing = [k for k in REQUIRED if stats.num(k) is None]
    problems = [f"stats.txt missing/non-numeric: {', '.join(missing)}"] if missing else []
    if stats.updated is None:
        problems.append("stats.txt slotDate did not parse")
    day = None
    if isinstance(net_text, Exception):
        problems.append(f"netdemand.csv: {net_text}")
    else:
        day = parse_net_demand(net_text, stats.updated)
        if len(day.points) < 280:
            problems.append(f"netdemand.csv has only {len(day.points)} rows")
    data = derive(stats, day, {})
    print(
        f"{stats.updated:%Y-%m-%d %H:%M} PT status={data.grid_status} "
        f"demand={stats.num('CurrentSystemDemand'):.0f} MW net_demand={stats.num('CurrentNetDemand'):.0f} MW "
        f"co2={data.co2_intensity} g/kWh forecast_rows={len(day.points) if day else None}"
    )
    if isinstance(past, CaisoError):
        problems.append(f"history {history_day}: {past}")
    else:
        print(
            f"history {history_day}: cleanest {past.min_g} g/kWh at {past.min_hour}:00, "
            f"dirtiest {past.max_g} g/kWh at {past.max_hour}:00 ({past.hours} hours)"
        )
        if past.hours < 20:
            problems.append(f"history {history_day} has only {past.hours} complete hours")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
