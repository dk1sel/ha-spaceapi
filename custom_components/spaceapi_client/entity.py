"""Base entity for the SpaceAPI integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from pathlib import Path

from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, MANUFACTURER
from .coordinator import SpaceApiConfigEntry, SpaceApiCoordinator
from .parser import SpaceData


def _load_english_names() -> dict[str, dict[str, str]]:
    """Read the English entity names (module import runs in the executor)."""
    path = Path(__file__).parent / "translations" / "en.json"
    entities = json.loads(path.read_text(encoding="utf-8")).get("entity", {})
    return {
        platform: {key: value["name"] for key, value in keys.items()}
        for platform, keys in entities.items()
    }


# Entity IDs are always built from the English names, whatever language the
# Home Assistant instance uses. The friendly name stays translated.
ENGLISH_NAMES = _load_english_names()


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

    def set_english_entity_id(self, platform: Platform) -> None:
        """Suggest an entity ID built from the English name.

        Only used for new entities; IDs already in the registry are kept.
        """
        key = self.translation_key
        if key is None:
            return
        name = ENGLISH_NAMES.get(platform, {}).get(key)
        if name is None:
            return
        try:
            name = name.format(**(self.translation_placeholders or {}))
        except (KeyError, IndexError, ValueError):
            return
        data = self.coordinator.data
        device = data.space if data else self.coordinator.config_entry.title
        object_id = slugify(f"{device} {name}")
        if object_id:
            self.entity_id = f"{platform}.{object_id}"

    @property
    def space(self) -> SpaceData:
        """Return the current data."""
        return self.coordinator.data


def async_add_dynamic_entities(
    entry: SpaceApiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    platform: Platform,
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
                entity = make()
                if isinstance(entity, SpaceApiEntity):
                    entity.set_english_entity_id(platform)
                new.append(entity)
        if new:
            async_add_entities(new)

    _check()
    entry.async_on_unload(coordinator.async_add_listener(_check))
