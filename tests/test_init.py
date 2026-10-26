"""Tests for setup, coordinator and the state-change event."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import Event, HomeAssistant
from homeassistant.loader import async_get_integration
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.spaceapi_client.const import EVENT_STATE_CHANGED

from .conftest import SPACE_URL, setup_entry

OPEN_ENTITY = "binary_sensor.test_hackspace_open"


async def _refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
    **response: Any,
) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(SPACE_URL, **response)
    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
) -> None:
    """Entry sets up and unloads."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.update_interval == timedelta(minutes=5)
    assert hass.states.get(OPEN_ENTITY).state == STATE_ON

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_unreachable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """First refresh failing puts the entry into retry."""
    aioclient_mock.get(SPACE_URL, exc=aiohttp.ClientError())
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unavailable_and_recover(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """API outage makes entities unavailable, recovery restores them."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)

    await _refresh(hass, freezer, aioclient_mock, exc=TimeoutError())
    assert hass.states.get(OPEN_ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.test_hackspace_temperature_lounge").state == (
        STATE_UNAVAILABLE
    )

    await _refresh(hass, freezer, aioclient_mock, json={"no": "space"})
    assert hass.states.get(OPEN_ENTITY).state == STATE_UNAVAILABLE

    await _refresh(hass, freezer, aioclient_mock, json=space_v15)
    assert hass.states.get(OPEN_ENTITY).state == STATE_ON


async def test_state_changed_event(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """The event fires on open/closed changes, but not on the first fetch."""
    events: list[Event] = async_capture_events(hass, EVENT_STATE_CHANGED)
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    assert events == []

    # Same state again: no event.
    await _refresh(hass, freezer, aioclient_mock, json=space_v15)
    assert events == []

    closed = {**space_v15, "state": {**space_v15["state"], "open": False}}
    await _refresh(hass, freezer, aioclient_mock, json=closed)
    assert hass.states.get(OPEN_ENTITY).state == STATE_OFF
    assert len(events) == 1
    assert events[0].data == {
        "entry_id": config_entry.entry_id,
        "space": "Test Hackspace",
        "url": SPACE_URL,
        "open": False,
        "previous": True,
    }

    # Outage in between does not produce an event; the change after it does.
    await _refresh(hass, freezer, aioclient_mock, exc=aiohttp.ClientError())
    await _refresh(hass, freezer, aioclient_mock, json=space_v15)
    assert len(events) == 2
    assert events[1].data["open"] is True
    assert events[1].data["previous"] is False


async def test_no_event_for_unknown_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A change to/from ``null`` is not an open/closed change."""
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)
    unknown = {**space_v15, "state": {"open": None}}
    await _refresh(hass, freezer, aioclient_mock, json=unknown)
    assert events == []


async def test_new_sensors_are_added(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Measurements that appear later become new entities; vanished ones go unavailable."""
    minimal = {"space": "Test Hackspace", "state": {"open": True}}
    await setup_entry(hass, config_entry, aioclient_mock, minimal)
    assert hass.states.get("sensor.test_hackspace_temperature_lounge") is None

    await _refresh(hass, freezer, aioclient_mock, json=space_v15)
    assert hass.states.get("sensor.test_hackspace_temperature_lounge").state == "21.5"

    await _refresh(hass, freezer, aioclient_mock, json=minimal)
    assert hass.states.get("sensor.test_hackspace_temperature_lounge").state == (
        STATE_UNAVAILABLE
    )


async def test_brand_icon(hass: HomeAssistant) -> None:
    """The integration ships its own icon in brand/."""
    integration = await async_get_integration(hass, "spaceapi_client")
    assert integration.has_branding
