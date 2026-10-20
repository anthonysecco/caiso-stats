"""Constants for CAISO Stats."""

from __future__ import annotations

from datetime import timedelta
import logging
from zoneinfo import ZoneInfo

DOMAIN = "caiso_stats"
LOGGER = logging.getLogger(__package__)

STATS_URL = "https://wwwmobile.caiso.com/outlook/SP/stats.txt"
NET_DEMAND_URL = "https://www.caiso.com/outlook/current/netdemand.csv"
OUTLOOK_URL = "https://www.caiso.com/todays-outlook"

ATTRIBUTION = "Data from California ISO Today's Outlook (unofficial, not affiliated with CAISO)"
CAISO_TZ = ZoneInfo("America/Los_Angeles")
REQUEST_TIMEOUT = 30  # seconds

# Options
CONF_SCAN_INTERVAL = "scan_interval"  # minutes
CONF_CLEAN_CO2 = "clean_co2_threshold"  # g/kWh
CONF_PEAK_PERCENT = "peak_percent"  # % of today's forecast net-demand peak
CONF_RESERVE_RATIO = "reserve_ratio_threshold"  # % of required reserve
CONF_WINDOW_HOURS = "window_hours"
CONF_SURPLUS_BATTERY = "surplus_battery_mw"  # MW of battery charging
CONF_SURPLUS_SHARE = "surplus_share"  # % of demand met by solar + wind

DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 60
DEFAULT_CLEAN_CO2 = 200
DEFAULT_PEAK_PERCENT = 90
DEFAULT_RESERVE_RATIO = 150
DEFAULT_WINDOW_HOURS = 3
DEFAULT_SURPLUS_BATTERY = 1000
DEFAULT_SURPLUS_SHARE = 50

DEFAULT_OPTIONS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_CLEAN_CO2: DEFAULT_CLEAN_CO2,
    CONF_PEAK_PERCENT: DEFAULT_PEAK_PERCENT,
    CONF_RESERVE_RATIO: DEFAULT_RESERVE_RATIO,
    CONF_WINDOW_HOURS: DEFAULT_WINDOW_HOURS,
    CONF_SURPLUS_BATTERY: DEFAULT_SURPLUS_BATTERY,
    CONF_SURPLUS_SHARE: DEFAULT_SURPLUS_SHARE,
}


def scan_interval(minutes: int) -> timedelta:
    """Clamp the configured interval to the supported range."""
    return timedelta(minutes=max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, int(minutes))))
