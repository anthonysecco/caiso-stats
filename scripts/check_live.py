"""Fetch CAISO's real feeds and run them through the integration's parsers.

Catches upstream format changes. Run from the repo root: python scripts/check_live.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.caiso_stats.api import CaisoClient, parse_net_demand, parse_stats
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
        stats_text, net_text = await CaisoClient(session).fetch()
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
    data = derive(stats, day, {}, stats.updated)
    w = data.low_window
    window = f"{w.start:%H:%M}-{w.end:%H:%M} avg {w.average_mw:.0f} MW" if w else None
    peak = f"{data.peak_mw:.0f} MW at {data.peak_time:%H:%M}" if data.peak_time else None
    print(
        f"{stats.updated:%Y-%m-%d %H:%M} PT status={data.grid_status} "
        f"demand={stats.num('CurrentSystemDemand'):.0f} MW reserve_ratio={data.reserve_ratio}% "
        f"co2={data.co2_intensity} g/kWh net_demand_peak={peak} "
        f"low_window={window} recommendation={data.recommendation}"
    )
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
