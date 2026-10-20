"""Parser and derived-signal tests (no Home Assistant instance needed)."""

from __future__ import annotations

from datetime import datetime
import json

import pytest

from custom_components.caiso_stats.api import (
    CaisoError,
    normalize_status,
    parse_net_demand,
    parse_stats,
    worst_status,
)
from custom_components.caiso_stats.const import CAISO_TZ
from custom_components.caiso_stats.coordinator import derive, lowest_window, net_demand_due

SLOT = datetime(2026, 10, 19, 18, 0, tzinfo=CAISO_TZ)


def test_parse_stats(stats_text: str) -> None:
    stats = parse_stats(stats_text)
    assert stats.updated == SLOT
    assert stats.statuses == ["Normal"]
    assert stats.num("CurrentSystemDemand") == 31245
    assert stats.num("currentRenewablesHybrid") is None
    assert stats.num("histDemand") is None  # "52,061 MW" is not a plain number
    assert stats.ts("TodaysPeakDemandTS") == datetime(2026, 10, 19, 17, 55, 40, tzinfo=CAISO_TZ)


def test_parse_stats_bom_and_errors(stats_text: str) -> None:
    assert parse_stats("﻿" + stats_text).num("CurrentNetDemand") == 28542
    with pytest.raises(CaisoError):
        parse_stats("<html>maintenance</html>")
    with pytest.raises(CaisoError):
        parse_stats(json.dumps({"foo": 1}))


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Normal", "normal"),
        ("Flex Alert", "flex_alert"),
        ("EEA Watch", "eea_watch"),
        ("EEA 1", "eea_1"),
        ("Energy Emergency Alert 2", "eea_2"),
        ("EEA3", "eea_3"),
        ("Restricted Maintenance Operations", "rmo"),
        ("Transmission Emergency", "transmission_emergency"),
        ("Something new", "other"),
    ],
)
def test_normalize_status(text: str, slug: str) -> None:
    assert normalize_status(text) == slug


def test_worst_status() -> None:
    assert worst_status([]) == "normal"
    assert worst_status(["Normal", "Flex Alert", "RMO"]) == "flex_alert"
    assert worst_status(["EEA Watch", "EEA 2"]) == "eea_2"


def test_parse_net_demand(net_demand_text: str) -> None:
    day = parse_net_demand(net_demand_text, SLOT)
    assert day.day == SLOT.date()
    assert len(day.points) == 289
    assert day.points[0].time == datetime(2026, 10, 19, 0, 0, tzinfo=CAISO_TZ)
    assert day.points[-1].time == datetime(2026, 10, 20, 0, 0, tzinfo=CAISO_TZ)  # closing row wraps
    assert day.points[0].net_demand == 19862
    assert day.points[-1].net_demand is None and day.points[-1].net_demand_forecast == 22816


def test_net_demand_from_yesterday_just_after_midnight(net_demand_text: str) -> None:
    """At 00:02 CAISO may still serve yesterday's file; actuals then run to 17:55."""
    day = parse_net_demand(net_demand_text, datetime(2026, 10, 20, 0, 2, tzinfo=CAISO_TZ))
    assert day.day == SLOT.date()


def test_parse_net_demand_rejects_other_csv() -> None:
    with pytest.raises(CaisoError):
        parse_net_demand("Time,Solar\n00:00,1\n", SLOT)


def test_derive_from_fixtures(stats_text: str, net_demand_text: str) -> None:
    stats = parse_stats(stats_text)
    data = derive(stats, parse_net_demand(net_demand_text, SLOT), {}, SLOT)
    assert data.grid_status == "normal"
    assert data.reserve_ratio == pytest.approx(329.4, abs=0.1)
    assert data.co2_intensity == pytest.approx(213.5, abs=0.1)
    assert data.clean_percent == pytest.approx((3976 + 1893 + 1104) / 31245 * 100, abs=0.1)
    assert data.peak_mw == 27770
    assert data.peak_time == datetime(2026, 10, 19, 18, 5, tzinfo=CAISO_TZ)
    assert data.grid_stress is False
    assert data.clean_now is False  # 213.5 > 200 g/kWh
    assert data.peak_period is True  # 28542 >= 90% of 27770
    assert data.solar_surplus is False  # batteries discharging 9433 MW
    assert data.recommendation == "avoid"
    window = data.low_window
    assert window is not None
    assert window.end == datetime(2026, 10, 20, 0, 0, tzinfo=CAISO_TZ)
    assert window.start == datetime(2026, 10, 19, 21, 0, tzinfo=CAISO_TZ)


def test_derive_signals(stats_text: str) -> None:
    raw = json.loads(stats_text)
    raw.update(
        gridstatus=["Normal"],
        currentBatteries=-6000,
        currentCo2intensity=0.08,
        CurrentNetDemand=9000,
        CurrentSystemDemand=20000,
    )
    data = derive(parse_stats(json.dumps(raw)), None, {}, SLOT)
    assert data.peak_mw is None and data.low_window is None
    assert data.peak_period is False  # fallback: 20000 < 90% of 31158
    assert data.solar_surplus is True
    assert data.clean_now is True
    assert data.recommendation == "use_now"

    raw.update(gridstatus=["Flex Alert"])
    assert derive(parse_stats(json.dumps(raw)), None, {}, SLOT).recommendation == "avoid"

    raw.update(gridstatus=["Normal"], Current_reserve=1500)  # 130% of required
    data = derive(parse_stats(json.dumps(raw)), None, {}, SLOT)
    assert data.grid_stress is True
    assert derive(parse_stats(json.dumps(raw)), None, {"reserve_ratio_threshold": 120}, SLOT).grid_stress is False


def test_lowest_window_short_remainder(net_demand_text: str) -> None:
    day = parse_net_demand(net_demand_text, SLOT)
    window = lowest_window(day, datetime(2026, 10, 19, 23, 0, tzinfo=CAISO_TZ), 3)
    assert window is not None
    assert window.end == datetime(2026, 10, 20, 0, 0, tzinfo=CAISO_TZ)


@pytest.mark.parametrize(
    ("fetched", "now", "due"),
    [
        (None, (18, 0), True),  # startup or last fetch failed
        ((18, 0), (18, 20), False),  # this hour's forecast revision not out yet
        ((18, 0), (18, 34), False),
        ((18, 0), (18, 35), True),  # revision landed around :28
        ((18, 36), (19, 20), False),
        ((18, 36), (19, 40), True),
    ],
)
def test_net_demand_due(fetched: tuple[int, int] | None, now: tuple[int, int], due: bool) -> None:
    def at(hm: tuple[int, int]) -> datetime:
        return datetime(2026, 10, 19, *hm, tzinfo=CAISO_TZ)

    assert net_demand_due(at(fetched) if fetched else None, at(now)) is due


def test_net_demand_due_new_day() -> None:
    fetched = datetime(2026, 10, 19, 23, 50, tzinfo=CAISO_TZ)
    assert net_demand_due(fetched, datetime(2026, 10, 19, 23, 59, tzinfo=CAISO_TZ)) is False
    assert net_demand_due(fetched, datetime(2026, 10, 20, 0, 5, tzinfo=CAISO_TZ)) is True
