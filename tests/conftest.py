"""Shared fixtures for CAISO Stats tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from custom_components.caiso_stats import api, history
from custom_components.caiso_stats.const import CAISO_TZ, HISTORY_URL, NET_DEMAND_URL, STATS_URL

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_DAY = date(2026, 10, 19)  # the day stats.txt and netdemand.csv were captured


def load_fixture(name: str) -> str:
    """Read a saved CAISO response (captured 2026-10-19 18:00 PT)."""
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    return


@pytest.fixture(autouse=True)
def history_files(aioclient_mock, monkeypatch) -> None:
    """Every past day's history answers with one real CAISO day (Oct 13, 2026); no retry waits.

    Registered for the 32 days before both the fixture day and the real date, so tests with and
    without a frozen clock find them.
    """
    monkeypatch.setattr(api, "HISTORY_RETRY_SECONDS", 0)
    monkeypatch.setattr(history, "FETCH_SPACING_SECONDS", 0)
    co2, demand = load_fixture("history_co2.csv"), load_fixture("history_demand.csv")
    today = datetime.now(CAISO_TZ).date()
    days = {anchor - timedelta(days=i) for anchor in (FIXTURE_DAY, today) for i in range(1, 33)}
    for day in sorted(days):
        stamp = day.strftime("%Y%m%d")
        aioclient_mock.get(HISTORY_URL.format(day=stamp, name="co2"), text=co2)
        aioclient_mock.get(HISTORY_URL.format(day=stamp, name="demand"), text=demand)


@pytest.fixture
def stats_text() -> str:
    """stats.txt fixture."""
    return load_fixture("stats.txt")


@pytest.fixture
def net_demand_text() -> str:
    """netdemand.csv fixture."""
    return load_fixture("netdemand.csv")


@pytest.fixture
def mock_caiso(aioclient_mock, stats_text, net_demand_text):
    """Both feeds answer with the saved fixtures."""
    aioclient_mock.get(STATS_URL, text=stats_text)
    aioclient_mock.get(NET_DEMAND_URL, text=net_demand_text)
    return aioclient_mock
