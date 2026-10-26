"""Data update coordinator for the SpaceAPI integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SpaceApiConnectionError, SpaceApiInvalidResponse, async_fetch_space
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_STATE_CHANGED,
    MIN_SCAN_INTERVAL,
)
from .parser import SpaceData

_LOGGER = logging.getLogger(__name__)

type SpaceApiConfigEntry = ConfigEntry[SpaceApiCoordinator]


class SpaceApiCoordinator(DataUpdateCoordinator[SpaceData]):
    """Poll one SpaceAPI endpoint."""

    config_entry: SpaceApiConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SpaceApiConfigEntry) -> None:
        """Initialize the coordinator."""
        minutes = max(
            MIN_SCAN_INTERVAL,
            int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(minutes=minutes),
        )
        self.url: str = entry.data[CONF_URL]
        self.raw: Any = None
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> SpaceData:
        """Fetch the endpoint."""
        try:
            raw, data = await async_fetch_space(self._session, self.url)
        except SpaceApiConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"url": self.url, "error": str(err)},
            ) from err
        except SpaceApiInvalidResponse as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
                translation_placeholders={"url": self.url, "error": str(err)},
            ) from err

        self.raw = raw
        previous = self.data
        if (
            previous is not None
            and previous.is_open is not None
            and data.is_open is not None
            and previous.is_open != data.is_open
        ):
            self.hass.bus.async_fire(
                EVENT_STATE_CHANGED,
                {
                    "entry_id": self.config_entry.entry_id,
                    "space": data.space,
                    "url": self.url,
                    "open": data.is_open,
                    "previous": previous.is_open,
                },
            )
        return data
