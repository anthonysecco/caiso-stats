"""Shared fixtures for CAISO Stats tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.caiso_stats.const import NET_DEMAND_URL, STATS_URL

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Read a saved CAISO response (captured 2026-10-19 18:00 PT)."""
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    return


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
