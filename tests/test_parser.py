"""Tests for the SpaceAPI parser (all API versions)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.spaceapi_client.parser import InvalidSpaceApiData, parse_space

from .conftest import load_fixture_json


def test_parse_v15() -> None:
    """Full v15 document."""
    data = parse_space(load_fixture_json("v15.json"))
    assert data.space == "Test Hackspace"
    assert data.api_version == "15"
    assert data.is_open is True
    assert data.message == "Open until midnight"
    assert data.lastchange == datetime.fromtimestamp(1700000000, tz=UTC)
    assert data.entity_picture == "https://example.org/open.png"
    assert (data.latitude, data.longitude) == (52.52, 13.405)
    assert data.contact["matrix"] == "#space:example.org"
    assert len(data.cams) == 2
    assert set(data.feeds) == {"blog", "calendar"}

    keys = set(data.sensors)
    assert {
        "temperature_lounge",
        "temperature_lounge_2",
        "temperature_workshop_ceiling",
        "door_locked_front_door",
        "wind_speed_roof",
        "wind_direction_roof",
        "radiation_gamma_lab",
        "network_traffic_bits_per_second_1",
        "people_now_present_1",
        "beverage_supply_club_mate",
    } <= keys
    assert data.sensors["temperature_workshop_ceiling"].label == "Workshop Ceiling"
    assert data.sensors["people_now_present_1"].attributes["names"] == [
        "Alice",
        "Bob",
        "Carol",
    ]
    assert data.sensors["radiation_gamma_lab"].unit == "μSv/h"


def test_parse_v14() -> None:
    """v14 document with both ``api`` and ``api_compatibility``."""
    data = parse_space(load_fixture_json("v14.json"))
    assert data.api_version == "14"
    assert data.is_open is False
    assert data.entity_picture == "https://fourteen.example/logo.svg"


def test_parse_v013() -> None:
    """v0.13: ``api`` field, string coordinates, ``state.icon``, open = null."""
    data = parse_space(load_fixture_json("v013.json"))
    assert data.api_version == "0.13"
    assert data.is_open is None
    assert data.icon_open == "http://old.example/o.png"
    assert data.latitude == 50.0
    assert data.contact["google"] == "+oldspace"
    assert data.sensors == {}


def test_parse_v012() -> None:
    """v0.12: open/status/lastchange/icon/lat/lon on top level, feeds as list."""
    data = parse_space(load_fixture_json("v012.json"))
    assert data.api_version == "0.12"
    assert data.is_open is True
    assert data.message == "Come in!"
    assert data.lastchange == datetime.fromtimestamp(1300000000, tz=UTC)
    assert data.entity_picture == "http://ancient.example/o.png"
    assert data.address == "Ancient Alley 2"
    assert (data.latitude, data.longitude) == (51.0, 7.0)
    assert data.feeds == {"blog": {"type": "rss", "url": "http://ancient.example/rss"}}


@pytest.mark.parametrize("document", [[], "x", {}, {"space": ""}, {"state": {}}])
def test_invalid(document: object) -> None:
    """Non-SpaceAPI documents raise."""
    with pytest.raises(InvalidSpaceApiData):
        parse_space(document)


def test_robust_against_garbage() -> None:
    """Wrongly typed fields are ignored instead of crashing."""
    data = parse_space(
        {
            "space": "Messy",
            "state": "open",
            "location": [],
            "contact": "nope",
            "sensors": {
                "temperature": [{"value": "n/a"}, "x", {"value": "19.5", "unit": "°C"}],
                "wind": [{"properties": "bad"}],
                "radiation": [],
            },
            "cam": "https://messy.example/cam.jpg",
            "projects": "https://x",
            "links": [{"name": "no url"}],
        }
    )
    assert data.is_open is None
    assert list(data.sensors) == ["temperature_3"]
    assert data.sensors["temperature_3"].value == 19.5
    assert data.cams == ["https://messy.example/cam.jpg"]
    assert data.projects == []
    assert data.links == []


def test_temperature_unit_variants() -> None:
    """Units like "C" or "°c" still map to Celsius."""
    from custom_components.spaceapi_client.sensor import _point_meta

    data = parse_space(
        {
            "space": "Units",
            "sensors": {
                "temperature": [
                    {"value": 20, "unit": "C", "location": "a"},
                    {"value": 20, "unit": "°c", "location": "b"},
                    {"value": 20, "unit": "°Rø", "location": "c"},
                ]
            },
        }
    )
    metas = [_point_meta(point) for point in data.sensors.values()]
    assert [m.unit for m in metas] == ["°C", "°C", "°Rø"]
    assert metas[2].device_class is None
