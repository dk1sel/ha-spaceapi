"""Base entity for the SpaceAPI integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SpaceApiConfigEntry, SpaceApiCoordinator
from .parser import SpaceData


class SpaceApiEntity(CoordinatorEntity[SpaceApiCoordinator]):
    """Common base for all SpaceAPI entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SpaceApiCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        base_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_id}_{key}"
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, base_id)},
            name=data.space if data else entry.title,
            manufacturer=MANUFACTURER,
            model=f"SpaceAPI v{data.api_version}"
            if data and data.api_version
            else "SpaceAPI",
            configuration_url=(data.url if data and data.url else None),
        )

    @property
    def space(self) -> SpaceData:
        """Return the current data."""
        return self.coordinator.data


def async_add_dynamic_entities(
    entry: SpaceApiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[SpaceData], Mapping[str, Callable[[], Entity]]],
) -> None:
    """Add entities now and whenever new keys appear in later updates."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    def _check() -> None:
        if coordinator.data is None:
            return
        new: list[Entity] = []
        for key, make in factory(coordinator.data).items():
            if key not in known:
                known.add(key)
                new.append(make())
        if new:
            async_add_entities(new)

    _check()
    entry.async_on_unload(coordinator.async_add_listener(_check))
