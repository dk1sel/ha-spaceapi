"""Webcams of a space (still images from the ``cam`` list)."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import logging

import aiohttp
from homeassistant.components.camera import Camera
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CAMERA_TIMEOUT
from .coordinator import SpaceApiConfigEntry, SpaceApiCoordinator
from .entity import SpaceApiEntity, async_add_dynamic_entities
from .parser import SpaceData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def camera_key(url: str) -> str:
    """Return a stable key for a webcam URL."""
    return "cam_" + hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()[:10]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpaceApiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up webcams."""
    coordinator = entry.runtime_data

    def _factory(data: SpaceData) -> dict[str, Callable[[], Entity]]:
        return {
            camera_key(url): lambda url=url, index=index: SpaceCamera(
                coordinator, url, index
            )
            for index, url in enumerate(data.cams)
        }

    async_add_dynamic_entities(entry, async_add_entities, Platform.CAMERA, _factory)


class SpaceCamera(SpaceApiEntity, Camera):
    """A webcam showing a still image."""

    _attr_translation_key = "webcam"

    def __init__(self, coordinator: SpaceApiCoordinator, url: str, index: int) -> None:
        """Initialize the camera."""
        SpaceApiEntity.__init__(self, coordinator, camera_key(url))
        Camera.__init__(self)
        self._url = url
        self._attr_translation_placeholders = {"number": str(index + 1)}
        self._attr_extra_state_attributes = {"url": url}

    @property
    def available(self) -> bool:
        """Return if the webcam is still listed."""
        return super().available and self._url in self.space.cams

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the webcam."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                self._url, timeout=aiohttp.ClientTimeout(total=CAMERA_TIMEOUT)
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    _LOGGER.debug(
                        "Webcam %s returned %s, not an image", self._url, content_type
                    )
                    return None
                self.content_type = content_type.split(";")[0]
                return await response.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Error fetching webcam %s: %s", self._url, err)
            return None
