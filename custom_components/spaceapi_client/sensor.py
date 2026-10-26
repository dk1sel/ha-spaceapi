"""Sensors for the SpaceAPI integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfDataRate,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CONTACT_KEYS
from .coordinator import SpaceApiConfigEntry, SpaceApiCoordinator
from .entity import SpaceApiEntity, async_add_dynamic_entities
from .parser import BINARY_SENSOR_CATEGORIES, SensorPoint, SpaceData

PARALLEL_UPDATES = 0

MAX_STATE_LENGTH = 255


def _truncate(value: str | None) -> str | None:
    if value is None or len(value) <= MAX_STATE_LENGTH:
        return value
    return value[: MAX_STATE_LENGTH - 1] + "…"


@dataclass(frozen=True, kw_only=True)
class SpaceSensorEntityDescription(SensorEntityDescription):
    """Describe a sensor computed from the space data."""

    value_fn: Callable[[SpaceData], StateType | datetime]
    exists_fn: Callable[[SpaceData], bool] = lambda _: True
    attrs_fn: Callable[[SpaceData], dict[str, Any]] | None = None
    picture_fn: Callable[[SpaceData], str | None] | None = None


SPACE_SENSORS: tuple[SpaceSensorEntityDescription, ...] = (
    SpaceSensorEntityDescription(
        key="message",
        translation_key="message",
        value_fn=lambda d: _truncate(d.message),
        exists_fn=lambda d: d.message is not None or d.is_open is not None,
        attrs_fn=lambda d: {"message": d.message} if d.message else {},
    ),
    SpaceSensorEntityDescription(
        key="lastchange",
        translation_key="lastchange",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.lastchange,
        exists_fn=lambda d: d.lastchange is not None,
    ),
    SpaceSensorEntityDescription(
        key="website",
        translation_key="website",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _truncate(d.url),
        exists_fn=lambda d: d.url is not None,
        attrs_fn=lambda d: {"url": d.url, "logo": d.logo},
        picture_fn=lambda d: d.logo,
    ),
    SpaceSensorEntityDescription(
        key="api_version",
        translation_key="api_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.api_version,
        attrs_fn=lambda d: {
            "api_compatibility": d.raw.get("api_compatibility"),
            "api": d.raw.get("api"),
        },
    ),
    SpaceSensorEntityDescription(
        key="address",
        translation_key="address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _truncate(d.address),
        exists_fn=lambda d: d.address is not None,
        attrs_fn=lambda d: {
            "address": d.address,
            "latitude": d.latitude,
            "longitude": d.longitude,
            **d.location_extra,
        },
    ),
    SpaceSensorEntityDescription(
        key="feeds",
        translation_key="feeds",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.feeds),
        exists_fn=lambda d: bool(d.feeds),
        attrs_fn=lambda d: {name: feed.get("url") for name, feed in d.feeds.items()},
    ),
    SpaceSensorEntityDescription(
        key="projects",
        translation_key="projects",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.projects),
        exists_fn=lambda d: bool(d.projects),
        attrs_fn=lambda d: {"projects": d.projects},
    ),
    SpaceSensorEntityDescription(
        key="links",
        translation_key="links",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.links),
        exists_fn=lambda d: bool(d.links),
        attrs_fn=lambda d: {"links": d.links},
    ),
    SpaceSensorEntityDescription(
        key="keymasters",
        translation_key="keymasters",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.contact.get("keymasters", [])),
        exists_fn=lambda d: bool(d.contact.get("keymasters")),
        attrs_fn=lambda d: {"keymasters": d.contact.get("keymasters", [])},
    ),
    SpaceSensorEntityDescription(
        key="last_event",
        translation_key="last_event",
        value_fn=lambda d: _truncate(_last_event_text(d)),
        exists_fn=lambda d: bool(d.events),
        attrs_fn=lambda d: {"events": d.events[-10:]},
    ),
    *(
        SpaceSensorEntityDescription(
            key=f"contact_{contact}",
            translation_key=f"contact_{contact}",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda d, c=contact: _truncate(d.contact.get(c)),
            exists_fn=lambda d, c=contact: isinstance(d.contact.get(c), str),
        )
        for contact in CONTACT_KEYS
    ),
)


def _last_event_text(data: SpaceData) -> str | None:
    if not data.events:
        return None
    event = max(data.events, key=lambda e: e.get("timestamp") or 0)
    parts = [str(event[k]) for k in ("name", "type") if event.get(k)]
    return " ".join(parts) or None


@dataclass(frozen=True, slots=True)
class _PointMeta:
    device_class: SensorDeviceClass | None = None
    unit: str | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    factor: float = 1.0


# Keys are upper-cased units without degree sign ("°C", "C" and "°c" all match).
_TEMPERATURE_UNITS = {
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
    "K": UnitOfTemperature.KELVIN,
}


def _temperature_unit(unit: str | None) -> UnitOfTemperature | None:
    if unit is None:
        return None
    return _TEMPERATURE_UNITS.get(unit.replace("°", "").strip().upper())


_SPEED_UNITS = {
    "m/s": UnitOfSpeed.METERS_PER_SECOND,
    "km/h": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "kn": UnitOfSpeed.KNOTS,
}


def _point_meta(point: SensorPoint) -> _PointMeta:
    """Map a SpaceAPI measurement to device class, unit and state class."""
    category, unit = point.category, point.unit
    match category:
        case "temperature" if (temp := _temperature_unit(unit)) is not None:
            return _PointMeta(SensorDeviceClass.TEMPERATURE, temp)
        case "humidity":
            return _PointMeta(SensorDeviceClass.HUMIDITY, PERCENTAGE)
        case "carbondioxide" if unit == "vol%":
            return _PointMeta(
                SensorDeviceClass.CO2, CONCENTRATION_PARTS_PER_MILLION, factor=10000
            )
        case "carbondioxide":
            return _PointMeta(SensorDeviceClass.CO2, CONCENTRATION_PARTS_PER_MILLION)
        case "barometer":
            return _PointMeta(
                SensorDeviceClass.ATMOSPHERIC_PRESSURE, UnitOfPressure.HPA
            )
        case "power_consumption" | "power_generation" if unit == "VA":
            return _PointMeta(
                SensorDeviceClass.APPARENT_POWER, UnitOfApparentPower.VOLT_AMPERE
            )
        case "power_consumption" | "power_generation":
            return _PointMeta(SensorDeviceClass.POWER, UnitOfPower.WATT)
        case "wind_speed" | "wind_gust" if unit in _SPEED_UNITS:
            return _PointMeta(SensorDeviceClass.WIND_SPEED, _SPEED_UNITS[unit])
        case "wind_direction":
            return _PointMeta(
                SensorDeviceClass.WIND_DIRECTION,
                DEGREE,
                SensorStateClass.MEASUREMENT_ANGLE,
            )
        case "wind_elevation":
            return _PointMeta(SensorDeviceClass.DISTANCE, UnitOfLength.METERS, None)
        case "account_balance":
            return _PointMeta(SensorDeviceClass.MONETARY, unit, SensorStateClass.TOTAL)
        case "network_traffic_bits_per_second":
            return _PointMeta(
                SensorDeviceClass.DATA_RATE, UnitOfDataRate.BITS_PER_SECOND
            )
        case "network_traffic_packets_per_second":
            return _PointMeta(unit="p/s")
        case "network_connections" | "total_member_count" | "people_now_present":
            return _PointMeta()
    return _PointMeta(unit=unit)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpaceApiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data

    def _factory(data: SpaceData) -> dict[str, Callable[[], Entity]]:
        entities: dict[str, Callable[[], Entity]] = {}
        for description in SPACE_SENSORS:
            if description.exists_fn(data):
                entities[description.key] = lambda d=description: SpaceSensor(
                    coordinator, d
                )
        for key, point in data.sensors.items():
            if point.category not in BINARY_SENSOR_CATEGORIES:
                entities[f"sensor_{key}"] = lambda key=key: SpacePointSensor(
                    coordinator, key
                )
        return entities

    async_add_dynamic_entities(entry, async_add_entities, _factory)


class SpaceSensor(SpaceApiEntity, SensorEntity):
    """A sensor computed from the space data."""

    entity_description: SpaceSensorEntityDescription

    def __init__(
        self,
        coordinator: SpaceApiCoordinator,
        description: SpaceSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return if the value is still reported."""
        return super().available and self.entity_description.exists_fn(self.space)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value_fn(self.space)

    @property
    def entity_picture(self) -> str | None:
        """Return a picture, if any."""
        if self.entity_description.picture_fn is None:
            return None
        return self.entity_description.picture_fn(self.space)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return {
            key: value
            for key, value in self.entity_description.attrs_fn(self.space).items()
            if value is not None
        }


class SpacePointSensor(SpaceApiEntity, SensorEntity):
    """A measurement from the ``sensors`` block."""

    def __init__(self, coordinator: SpaceApiCoordinator, key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"sensor_{key}")
        self._key = key
        point = coordinator.data.sensors[key]
        meta = _point_meta(point)
        self._factor = meta.factor
        self._attr_translation_key = point.category
        self._attr_translation_placeholders = {
            "label": f" {point.label}" if point.label else ""
        }
        self._attr_device_class = meta.device_class
        self._attr_native_unit_of_measurement = meta.unit
        self._attr_state_class = meta.state_class

    @property
    def _point(self) -> SensorPoint | None:
        return self.space.sensors.get(self._key)

    @property
    def available(self) -> bool:
        """Return if the measurement is still reported."""
        return super().available and self._point is not None

    @property
    def native_value(self) -> float | None:
        """Return the measured value."""
        point = self._point
        if point is None:
            return None
        return point.value * self._factor

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        point = self._point
        if point is None:
            return None
        attrs = dict(point.attributes)
        if point.unit and point.unit != self._attr_native_unit_of_measurement:
            attrs["original_unit"] = point.unit
        if point.lastchange:
            attrs["lastchange"] = point.lastchange.isoformat()
        return attrs
