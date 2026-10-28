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
# Daily history files (Pacific day, YYYYMMDD); `name` is "co2" or "demand".
HISTORY_URL = "https://www.caiso.com/outlook/history/{day}/{name}.csv"

ATTRIBUTION = "Data from California ISO Today's Outlook (unofficial, not affiliated with CAISO)"
CAISO_TZ = ZoneInfo("America/Los_Angeles")
REQUEST_TIMEOUT = 30  # seconds
# CAISO revises the next hour of netdemand.csv's net demand forecast around :28 past each
# hour (Pacific), so the file is refetched on the first poll after this minute.
NET_DEMAND_REFRESH_MINUTE = 35

# Options
CONF_SCAN_INTERVAL = "scan_interval"  # minutes
CONF_LOW_CARBON_INDEX = "low_carbon_index_threshold"  # carbon intensity index, 0-100
CONF_INDEX_DAYS = "index_days"  # days of history behind the carbon intensity index

DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 60
DEFAULT_LOW_CARBON_INDEX = 25
DEFAULT_INDEX_DAYS = 14
MIN_INDEX_DAYS = 7
MAX_INDEX_DAYS = 30
INDEX_MIN_HISTORY_DAYS = 3  # the index stays unavailable until this many days are stored
HISTORY_PUBLISH_HOUR = 1  # CAISO posts a day's history file just after midnight; ask after 01:00 PT
HISTORY_RETRY_HOURS = 1  # wait this long before retrying days that failed to download

DEFAULT_OPTIONS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_LOW_CARBON_INDEX: DEFAULT_LOW_CARBON_INDEX,
    CONF_INDEX_DAYS: DEFAULT_INDEX_DAYS,
}


def scan_interval(minutes: int) -> timedelta:
    """Clamp the configured interval to the supported range."""
    return timedelta(minutes=max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, int(minutes))))
