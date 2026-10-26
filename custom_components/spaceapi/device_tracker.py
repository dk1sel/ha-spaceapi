"""Location of a space on the Home Assistant map."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SpaceApiConfigEntry, SpaceApiCoordinator
from .entity import SpaceApiEntity, async_add_dynamic_entities
from .parser import SpaceData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpaceApiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the location tracker."""
    coordinator = entry.runtime_data

    def _factory(data: SpaceData) -> dict[str, Callable[[], Entity]]:
        if data.latitude is None or data.longitude is None:
            return {}
        return {"location": lambda: SpaceLocation(coordinator)}

    async_add_dynamic_entities(entry, async_add_entities, _factory)


class SpaceLocation(SpaceApiEntity, TrackerEntity):
    """The space as a GPS point on the map."""

    _attr_translation_key = "location"
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator: SpaceApiCoordinator) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, "location")

    @property
    def available(self) -> bool:
        """Return if a position is known."""
        return super().available and self.space.latitude is not None

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        return self.space.latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        return self.space.longitude

    @property
    def entity_picture(self) -> str | None:
        """Show the space logo on the map."""
        return self.space.entity_picture
