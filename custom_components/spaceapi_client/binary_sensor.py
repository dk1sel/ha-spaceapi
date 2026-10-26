"""Binary sensors for the SpaceAPI integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SpaceApiConfigEntry, SpaceApiCoordinator
from .entity import SpaceApiEntity, async_add_dynamic_entities
from .parser import BINARY_SENSOR_CATEGORIES, SensorPoint, SpaceData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpaceApiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data

    def _factory(data: SpaceData) -> dict[str, Callable[[], Entity]]:
        entities: dict[str, Callable[[], Entity]] = {
            "open": lambda: SpaceOpenBinarySensor(coordinator)
        }
        for key, point in data.sensors.items():
            if point.category in BINARY_SENSOR_CATEGORIES:
                entities[key] = lambda key=key: SpacePointBinarySensor(coordinator, key)
        return entities

    async_add_dynamic_entities(
        entry, async_add_entities, Platform.BINARY_SENSOR, _factory
    )


class SpaceOpenBinarySensor(SpaceApiEntity, BinarySensorEntity):
    """Whether the space is open."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_translation_key = "open"

    def __init__(self, coordinator: SpaceApiCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "open")

    @property
    def is_on(self) -> bool | None:
        """Return true if the space is open."""
        return self.space.is_open

    @property
    def entity_picture(self) -> str | None:
        """Return the open/closed icon or the space logo."""
        return self.space.entity_picture

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the status message and other state details."""
        data = self.space
        attrs: dict[str, Any] = {}
        if data.message:
            attrs["message"] = data.message
        if data.lastchange:
            attrs["lastchange"] = data.lastchange.isoformat()
        if data.trigger_person:
            attrs["trigger_person"] = data.trigger_person
        return attrs


class SpacePointBinarySensor(SpaceApiEntity, BinarySensorEntity):
    """A boolean value from the sensors block (``door_locked``)."""

    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, coordinator: SpaceApiCoordinator, key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"sensor_{key}")
        self._key = key
        point = coordinator.data.sensors[key]
        self._attr_translation_key = point.category
        self._attr_translation_placeholders = {
            "label": f" {point.label}" if point.label else ""
        }

    @property
    def _point(self) -> SensorPoint | None:
        return self.space.sensors.get(self._key)

    @property
    def available(self) -> bool:
        """Return if the measurement is still reported."""
        return super().available and self._point is not None

    @property
    def is_on(self) -> bool | None:
        """Return true if unlocked (device class lock: on means unlocked)."""
        point = self._point
        if point is None:
            return None
        return not point.value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        point = self._point
        if point is None:
            return None
        attrs = dict(point.attributes)
        if point.lastchange:
            attrs["lastchange"] = point.lastchange.isoformat()
        return attrs
