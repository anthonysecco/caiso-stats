"""Fetch CAISO's real feeds and run them through the integration's parsers.

Catches upstream format changes. Run from the repo root: python scripts/check_live.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.caiso_stats.api import CaisoClient, parse_net_demand, parse_stats  # noqa: E402
from custom_components.caiso_stats.coordinator import derive  # noqa: E402

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
    print(
        f"{stats.updated:%Y-%m-%d %H:%M} status={data.grid_status} demand={stats.num('CurrentSystemDemand')} "
        f"reserve_ratio={data.reserve_ratio}% co2={data.co2_intensity} g/kWh peak={data.peak_mw} "
        f"window={data.low_window} recommendation={data.recommendation}"
    )
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
