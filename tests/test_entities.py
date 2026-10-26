"""Tests for the entities created from SpaceAPI data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.camera import async_get_image
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_PICTURE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.spaceapi_client.const import DOMAIN
from custom_components.spaceapi_client.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import SPACE_URL, load_fixture_json, setup_entry


async def test_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """One device per space with the website as configuration URL."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert (DOMAIN, SPACE_URL) in device.identifiers
    assert device.name == "Test Hackspace"
    assert device.configuration_url == "https://example.org"
    assert device.model == "SpaceAPI v15"


async def test_open_binary_sensor(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
) -> None:
    """Open state with message, lastchange and icon."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    state = hass.states.get("binary_sensor.test_hackspace_open")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == "door"
    assert state.attributes["message"] == "Open until midnight"
    assert state.attributes["trigger_person"] == "Alice"
    assert state.attributes[ATTR_ENTITY_PICTURE] == "https://example.org/open.png"

    assert hass.states.get("sensor.test_hackspace_status_message").state == (
        "Open until midnight"
    )
    assert hass.states.get("sensor.test_hackspace_last_status_change").state == (
        "2023-11-14T22:13:20+00:00"
    )


async def test_door_locked(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
) -> None:
    """door_locked=true means the lock entity is off (locked)."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    state = hass.states.get("binary_sensor.test_hackspace_door_lock_front_door")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == "lock"


async def test_measurements(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Every measurement gets an entity with device class and unit."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)

    expected = {
        "sensor.test_hackspace_temperature_lounge": ("21.5", "temperature", "°C"),
        "sensor.test_hackspace_temperature_workshop_ceiling": (
            "18.0",
            "temperature",
            "°C",
        ),
        "sensor.test_hackspace_humidity_lounge": ("45.0", "humidity", "%"),
        "sensor.test_hackspace_carbon_dioxide_lounge": (
            "500.0",
            "carbon_dioxide",
            "ppm",
        ),
        "sensor.test_hackspace_air_pressure_roof": (
            "1013.2",
            "atmospheric_pressure",
            "hPa",
        ),
        "sensor.test_hackspace_power_consumption_main": ("350.0", "power", "W"),
        "sensor.test_hackspace_power_generation_roof_solar": (
            "120.0",
            "apparent_power",
            "VA",
        ),
        # HA converts m/s to the metric default km/h.
        "sensor.test_hackspace_wind_speed_roof": ("12.6", "wind_speed", "km/h"),
        "sensor.test_hackspace_wind_gust_roof": ("25.2", "wind_speed", "km/h"),
        "sensor.test_hackspace_wind_direction_roof": ("270.0", "wind_direction", "°"),
        "sensor.test_hackspace_gamma_radiation_lab": ("0.12", None, "μSv/h"),
        "sensor.test_hackspace_network_connections_space": ("12.0", None, None),
        "sensor.test_hackspace_account_balance_bank": ("1234.56", "monetary", "EUR"),
        "sensor.test_hackspace_members": ("42.0", None, None),
        "sensor.test_hackspace_people_present": ("3.0", None, None),
        "sensor.test_hackspace_beverage_supply_club_mate": ("24.0", None, "btl"),
        "sensor.test_hackspace_network_traffic": ("1000000.0", "data_rate", "bit/s"),
        "sensor.test_hackspace_network_packets": ("500.0", None, "p/s"),
    }
    for entity_id, (value, device_class, unit) in expected.items():
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == value, entity_id
        assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class, entity_id
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit, entity_id

    # The Fahrenheit sensor in the same room keeps its own entity; HA converts
    # it to the system unit.
    assert hass.states.get("sensor.test_hackspace_temperature_lounge_2") is not None

    people = hass.states.get("sensor.test_hackspace_people_present")
    assert people.attributes["names"] == ["Alice", "Bob", "Carol"]
    traffic = hass.states.get("sensor.test_hackspace_network_traffic")
    assert traffic.attributes["maximum"] == 100000000

    entry = entity_registry.async_get("sensor.test_hackspace_temperature_lounge")
    assert entry.unique_id == f"{SPACE_URL}_sensor_temperature_lounge"


async def test_master_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Logo, URL, address, contacts, feeds, projects and links."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)

    website = hass.states.get("sensor.test_hackspace_website")
    assert website.state == "https://example.org"
    assert website.attributes[ATTR_ENTITY_PICTURE] == "https://example.org/logo.png"
    assert entity_registry.async_get(website.entity_id).entity_category == "diagnostic"

    address = hass.states.get("sensor.test_hackspace_address")
    assert address.state.startswith("Teststraße 1")
    assert address.attributes["timezone"] == "Europe/Berlin"

    assert hass.states.get("sensor.test_hackspace_e_mail").state == "info@example.org"
    assert hass.states.get("sensor.test_hackspace_matrix").state == "#space:example.org"
    assert (
        hass.states.get("sensor.test_hackspace_mastodon").state == "@space@chaos.social"
    )
    assert hass.states.get("sensor.test_hackspace_irc").state.startswith("ircs://")
    assert hass.states.get("sensor.test_hackspace_phone") is not None
    assert hass.states.get("sensor.test_hackspace_twitter") is None
    assert hass.states.get("sensor.test_hackspace_keymasters").state == "1"

    feeds = hass.states.get("sensor.test_hackspace_feeds")
    assert feeds.state == "2"
    assert feeds.attributes["calendar"] == "https://example.org/cal.ics"
    assert hass.states.get("sensor.test_hackspace_projects").attributes["projects"] == [
        "https://github.com/example"
    ]
    assert hass.states.get("sensor.test_hackspace_links").state == "1"
    assert hass.states.get("sensor.test_hackspace_api_version").state == "15"
    assert hass.states.get("sensor.test_hackspace_last_event").state == "Bob check-out"


async def test_location_tracker(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
) -> None:
    """The space appears on the map."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    state = hass.states.get("device_tracker.test_hackspace_location")
    assert state is not None
    assert state.attributes["latitude"] == 52.52
    assert state.attributes["longitude"] == 13.405
    assert state.attributes["source_type"] == "gps"


async def test_webcams(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
) -> None:
    """Each webcam becomes a camera that returns a still image."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    assert hass.states.get("camera.test_hackspace_webcam_1") is not None
    assert hass.states.get("camera.test_hackspace_webcam_2") is not None

    aioclient_mock.get(
        "https://example.org/cam1.jpg",
        content=b"JPEGDATA",
        headers={"Content-Type": "image/jpeg"},
    )
    image = await async_get_image(hass, "camera.test_hackspace_webcam_1")
    assert image.content == b"JPEGDATA"
    assert image.content_type == "image/jpeg"


async def test_old_api_version(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A v0.13 endpoint is set up best-effort."""
    url = "http://old.example/status.json"
    entry = MockConfigEntry(
        domain=DOMAIN, title="Old School Space", unique_id=url, data={"url": url}
    )
    await setup_entry(hass, entry, aioclient_mock, load_fixture_json("v013.json"))
    state = hass.states.get("binary_sensor.old_school_space_open")
    assert state.state == STATE_UNKNOWN
    assert hass.states.get("sensor.old_school_space_api_version").state == "0.13"
    assert (
        hass.states.get("device_tracker.old_school_space_location").attributes[
            "latitude"
        ]
        == 50.0
    )
    assert hass.states.get("camera.old_school_space_webcam_1") is not None


async def test_very_old_api_version(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A v0.12 endpoint with top-level ``open``."""
    url = "http://ancient.example/status.json"
    entry = MockConfigEntry(
        domain=DOMAIN, title="Ancient Space", unique_id=url, data={"url": url}
    )
    await setup_entry(hass, entry, aioclient_mock, load_fixture_json("v012.json"))
    state = hass.states.get("binary_sensor.ancient_space_open")
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Come in!"
    assert state.attributes[ATTR_ENTITY_PICTURE] == "http://ancient.example/o.png"


async def test_v14(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A v14 endpoint."""
    url = "https://fourteen.example/api"
    entry = MockConfigEntry(
        domain=DOMAIN, title="Fourteen Space", unique_id=url, data={"url": url}
    )
    await setup_entry(hass, entry, aioclient_mock, load_fixture_json("v14.json"))
    assert hass.states.get("binary_sensor.fourteen_space_open").state == STATE_OFF
    assert hass.states.get("sensor.fourteen_space_temperature_hall").state == "20.0"
    assert hass.states.get("sensor.fourteen_space_twitter").state == "@fourteen"


async def test_diagnostics(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
) -> None:
    """Diagnostics contain the raw API data."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    result = await async_get_config_entry_diagnostics(hass, config_entry)
    assert result["raw"] == space_v15
    assert result["api_version"] == "15"
    assert result["entry"]["data"] == {"url": SPACE_URL}
    assert "temperature_lounge" in result["sensor_keys"]


async def test_entity_ids_english_in_german_instance(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
) -> None:
    """Entity IDs stay English; friendly names follow the instance language."""
    hass.config.language = "de"
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)

    expected = {
        "binary_sensor.test_hackspace_open": "Test Hackspace Geöffnet",
        "binary_sensor.test_hackspace_door_lock_front_door": (
            "Test Hackspace Türschloss Front door"
        ),
        "sensor.test_hackspace_status_message": "Test Hackspace Statusmeldung",
        "sensor.test_hackspace_temperature_lounge": "Test Hackspace Temperatur Lounge",
        "sensor.test_hackspace_air_pressure_roof": "Test Hackspace Luftdruck Roof",
        "sensor.test_hackspace_people_present": "Test Hackspace Anwesende Personen",
        "sensor.test_hackspace_e_mail": "Test Hackspace E-Mail",
        "camera.test_hackspace_webcam_1": "Test Hackspace Webcam 1",
        "device_tracker.test_hackspace_location": "Test Hackspace Standort",
    }
    for entity_id, friendly_name in expected.items():
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.attributes["friendly_name"] == friendly_name
    assert not [
        state.entity_id
        for state in hass.states.async_all()
        if any(
            word in state.entity_id for word in ("geoffnet", "temperatur_", "standort")
        )
    ]
