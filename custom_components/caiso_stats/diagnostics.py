"""Diagnostics for CAISO Stats (public data only; nothing to redact)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import CaisoConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: CaisoConfigEntry) -> dict[str, Any]:
    """Options, derived values and the last raw payloads."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "derived": None
        if data is None
        else {
            "grid_status": data.grid_status,
            "co2_intensity": data.co2_intensity,
            "co2_intensity_index": data.co2_index,
            "index_window": None
            if data.index_range is None
            else {
                "min": data.index_range.min_g,
                "min_hour": data.index_range.min_at.isoformat(),
                "max": data.index_range.max_g,
                "max_hour": data.index_range.max_at.isoformat(),
                "days": data.index_range.days,
            },
            "low_carbon_now": data.low_carbon_now,
            "net_demand_error": data.net_demand_error,
        },
        "stats": data.stats.raw if data else None,
        "net_demand_csv": coordinator.raw_net_demand,
    }
