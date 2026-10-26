"""Parse SpaceAPI JSON (v15, v14 and best-effort older formats) into a typed model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from homeassistant.util import slugify

# Simple sensor categories: one list of {value, unit, location, name, ...} each.
SIMPLE_SENSOR_CATEGORIES = (
    "temperature",
    "humidity",
    "carbondioxide",
    "barometer",
    "power_consumption",
    "power_generation",
    "network_connections",
    "account_balance",
    "total_member_count",
    "people_now_present",
    "beverage_supply",
)
BINARY_SENSOR_CATEGORIES = ("door_locked",)
RADIATION_TYPES = ("alpha", "beta", "gamma", "beta_gamma")
WIND_PROPERTIES = ("speed", "gust", "direction", "elevation")
TRAFFIC_PROPERTIES = ("bits_per_second", "packets_per_second")

# Fields that are shown as extra state attributes of a measurement.
_EXTRA_ATTRIBUTES = (
    "description",
    "type",
    "machines",
    "names",
    "dead_time",
    "conversion_factor",
    "maximum",
)


@dataclass(slots=True)
class SensorPoint:
    """A single measurement from the ``sensors`` block."""

    key: str
    category: str
    label: str
    value: Any
    unit: str | None = None
    lastchange: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SpaceData:
    """Normalized SpaceAPI data."""

    raw: dict[str, Any]
    space: str
    url: str | None = None
    logo: str | None = None
    api_version: str | None = None
    is_open: bool | None = None
    message: str | None = None
    lastchange: datetime | None = None
    trigger_person: str | None = None
    icon_open: str | None = None
    icon_closed: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_extra: dict[str, Any] = field(default_factory=dict)
    contact: dict[str, Any] = field(default_factory=dict)
    feeds: dict[str, Any] = field(default_factory=dict)
    projects: list[str] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    cams: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    sensors: dict[str, SensorPoint] = field(default_factory=dict)

    @property
    def entity_picture(self) -> str | None:
        """Return the state icon (open/closed) or the logo."""
        if self.is_open is True and self.icon_open:
            return self.icon_open
        if self.is_open is False and self.icon_closed:
            return self.icon_closed
        return self.logo


class InvalidSpaceApiData(ValueError):
    """Raised when a document is not a SpaceAPI document."""


def _str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "open", "yes", "1", "on"):
            return True
        if lowered in ("false", "closed", "no", "0", "off"):
            return False
    return None


def _timestamp(value: Any) -> datetime | None:
    number = _float(value)
    if number is None or number <= 0:
        return None
    # Some endpoints send milliseconds.
    if number > 1e11:
        number /= 1000
    try:
        return datetime.fromtimestamp(number, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _unit(value: Any) -> str | None:
    unit = _str(value)
    if unit is None:
        return None
    # The official schema contains a mis-encoded micro sign ("Âµ"),
    # and some endpoints copied it. Normalize all variants to the Greek mu
    # (U+03BC) that Home Assistant uses for units.
    return unit.replace("Âµ", "μ").replace("µ", "μ").replace("Â°", "°")


def detect_api_version(raw: dict[str, Any]) -> str | None:
    """Return the highest supported API version of a document."""
    versions = [_str(v) for v in _list(raw.get("api_compatibility"))]
    versions = [v for v in versions if v]
    if versions:

        def _key(version: str) -> tuple[float, str]:
            number = _float(version)
            return (number if number is not None else -1.0, version)

        return max(versions, key=_key)
    return _str(raw.get("api"))


def parse_space(raw: Any) -> SpaceData:
    """Parse a SpaceAPI document."""
    if not isinstance(raw, dict):
        raise InvalidSpaceApiData("document is not a JSON object")
    space = _str(raw.get("space"))
    if not space:
        raise InvalidSpaceApiData("missing 'space' field")

    data = SpaceData(
        raw=raw,
        space=space,
        url=_str(raw.get("url")),
        logo=_str(raw.get("logo")),
        api_version=detect_api_version(raw),
    )
    _parse_state(raw, data)
    _parse_location(raw, data)
    _parse_contact(raw, data)
    _parse_feeds(raw, data)
    data.projects = [p for p in (_str(x) for x in _list(raw.get("projects"))) if p]
    data.links = [
        {k: v for k, v in link.items() if k in ("name", "description", "url")}
        for link in _list(raw.get("links"))
        if isinstance(link, dict) and link.get("url")
    ]
    cam = raw.get("cam")
    if isinstance(cam, str):
        cam = [cam]
    data.cams = list(dict.fromkeys(c for c in (_str(x) for x in _list(cam)) if c))
    data.events = [e for e in _list(raw.get("events")) if isinstance(e, dict)]
    data.sensors = parse_sensors(_dict(raw.get("sensors")))
    return data


def _parse_state(raw: dict[str, Any], data: SpaceData) -> None:
    state = _dict(raw.get("state"))
    # v0.12 and older had "open", "status", "lastchange" and "icon" on top level.
    data.is_open = _bool(state.get("open", raw.get("open")))
    data.message = _str(state.get("message", raw.get("status")))
    data.lastchange = _timestamp(state.get("lastchange", raw.get("lastchange")))
    data.trigger_person = _str(state.get("trigger_person"))
    icon = _dict(state.get("icon")) or _dict(raw.get("icon"))
    data.icon_open = _str(icon.get("open"))
    data.icon_closed = _str(icon.get("closed"))


def _parse_location(raw: dict[str, Any], data: SpaceData) -> None:
    location = _dict(raw.get("location"))
    data.address = _str(location.get("address", raw.get("address")))
    data.latitude = _float(location.get("lat", raw.get("lat")))
    data.longitude = _float(location.get("lon", raw.get("lon")))
    if data.latitude is not None and not -90 <= data.latitude <= 90:
        data.latitude = None
    if data.longitude is not None and not -180 <= data.longitude <= 180:
        data.longitude = None
    data.location_extra = {
        key: location[key]
        for key in ("timezone", "country_code", "hint")
        if location.get(key) is not None
    }


def _parse_contact(raw: dict[str, Any], data: SpaceData) -> None:
    contact = _dict(raw.get("contact"))
    parsed: dict[str, Any] = {}
    for key, value in contact.items():
        if key == "keymasters":
            keymasters = [k for k in _list(value) if isinstance(k, dict)]
            if keymasters:
                parsed[key] = keymasters
        elif key == "google":
            # v0.13: {"plus": "..."}
            plus = _str(_dict(value).get("plus"))
            if plus:
                parsed[key] = plus
        elif (text := _str(value)) is not None:
            parsed[key] = text
    data.contact = parsed


def _parse_feeds(raw: dict[str, Any], data: SpaceData) -> None:
    feeds = raw.get("feeds")
    parsed: dict[str, Any] = {}
    if isinstance(feeds, dict):
        for name, feed in feeds.items():
            if isinstance(feed, dict) and _str(feed.get("url")):
                parsed[name] = {
                    k: v for k, v in feed.items() if k in ("type", "url") and v
                }
            elif isinstance(feed, str) and feed:
                parsed[name] = {"url": feed}
    elif isinstance(feeds, list):
        # v0.12: [{"name": ..., "type": ..., "url": ...}]
        for feed in feeds:
            if isinstance(feed, dict) and _str(feed.get("url")):
                name = _str(feed.get("name")) or f"feed_{len(parsed) + 1}"
                parsed[name] = {
                    k: v for k, v in feed.items() if k in ("type", "url") and v
                }
    data.feeds = parsed


def _label(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("location", "name"):
        text = _str(item.get(key))
        if text and text.lower() not in (p.lower() for p in parts):
            parts.append(text)
    return " ".join(parts)


class _PointCollector:
    """Collect sensor points and keep their keys unique and stable."""

    def __init__(self) -> None:
        self.points: dict[str, SensorPoint] = {}

    def add(
        self,
        category: str,
        item: dict[str, Any],
        value: Any,
        unit: str | None,
        index: int,
        extra: dict[str, Any] | None = None,
    ) -> None:
        label = _label(item)
        base = f"{category}_{slugify(label) if label else index + 1}"
        key = base
        counter = 2
        while key in self.points:
            key = f"{base}_{counter}"
            counter += 1
        attributes = {
            attr: item[attr] for attr in _EXTRA_ATTRIBUTES if item.get(attr) is not None
        }
        if extra:
            attributes.update(extra)
        self.points[key] = SensorPoint(
            key=key,
            category=category,
            label=label,
            value=value,
            unit=unit,
            lastchange=_timestamp(item.get("lastchange")),
            attributes=attributes,
        )


def parse_sensors(sensors: dict[str, Any]) -> dict[str, SensorPoint]:
    """Flatten the ``sensors`` block into individual measurement points."""
    collector = _PointCollector()

    for category in SIMPLE_SENSOR_CATEGORIES:
        for index, item in enumerate(_list(sensors.get(category))):
            if not isinstance(item, dict):
                continue
            value = _float(item.get("value"))
            if value is None:
                continue
            collector.add(category, item, value, _unit(item.get("unit")), index)

    for category in BINARY_SENSOR_CATEGORIES:
        for index, item in enumerate(_list(sensors.get(category))):
            if not isinstance(item, dict):
                continue
            value = _bool(item.get("value"))
            if value is None:
                continue
            collector.add(category, item, value, None, index)

    radiation = _dict(sensors.get("radiation"))
    for rad_type in RADIATION_TYPES:
        for index, item in enumerate(_list(radiation.get(rad_type))):
            if not isinstance(item, dict):
                continue
            value = _float(item.get("value"))
            if value is None:
                continue
            collector.add(
                f"radiation_{rad_type}", item, value, _unit(item.get("unit")), index
            )

    for index, item in enumerate(_list(sensors.get("wind"))):
        if not isinstance(item, dict):
            continue
        properties = _dict(item.get("properties"))
        for prop in WIND_PROPERTIES:
            measurement = _dict(properties.get(prop))
            value = _float(measurement.get("value"))
            if value is None:
                continue
            collector.add(
                f"wind_{prop}", item, value, _unit(measurement.get("unit")), index
            )

    for index, item in enumerate(_list(sensors.get("network_traffic"))):
        if not isinstance(item, dict):
            continue
        properties = _dict(item.get("properties"))
        for prop in TRAFFIC_PROPERTIES:
            measurement = _dict(properties.get(prop))
            value = _float(measurement.get("value"))
            if value is None:
                continue
            extra = {}
            if (maximum := _float(measurement.get("maximum"))) is not None:
                extra["maximum"] = maximum
            collector.add(f"network_traffic_{prop}", item, value, None, index, extra)

    return collector.points
