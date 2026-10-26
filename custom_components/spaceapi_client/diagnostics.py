"""Diagnostics for the SpaceAPI integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import SpaceApiConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SpaceApiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with the raw API response (public data, no secrets)."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "last_update_success": coordinator.last_update_success,
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None
        ),
        "api_version": data.api_version if data else None,
        "sensor_keys": sorted(data.sensors) if data else [],
        "raw": coordinator.raw,
    }
