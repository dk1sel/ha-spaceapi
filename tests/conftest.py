"""Fixtures for SpaceAPI tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any

from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.spaceapi.const import DIRECTORY_URL, DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
SPACE_URL = "https://example.org/spaceapi.json"


def load_fixture_json(name: str) -> Any:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable custom integrations in all tests."""
    yield


@pytest.fixture
def space_v15() -> dict[str, Any]:
    """Return a v15 document."""
    return load_fixture_json("v15.json")


@pytest.fixture
def mock_directory(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock the SpaceAPI directory."""
    aioclient_mock.get(DIRECTORY_URL, json=load_fixture_json("directory.json"))
    return aioclient_mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry for the test space."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Hackspace",
        unique_id=SPACE_URL,
        data={CONF_URL: SPACE_URL},
    )


async def setup_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    document: Any,
) -> None:
    """Mock the endpoint and set up the entry."""
    aioclient_mock.get(entry.data[CONF_URL], json=document)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
