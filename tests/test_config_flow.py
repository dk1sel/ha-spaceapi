"""Tests for the SpaceAPI config flow."""

from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.spaceapi.const import (
    CONF_SCAN_INTERVAL,
    CONF_SEARCH,
    CONF_SPACE,
    DIRECTORY_URL,
    DOMAIN,
)

from .conftest import SPACE_URL, setup_entry


async def _start(hass: HomeAssistant) -> dict[str, Any]:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_search_and_select(
    hass: HomeAssistant,
    mock_directory: AiohttpClientMocker,
    space_v15: dict[str, Any],
) -> None:
    """Search the directory, pick a space and create the entry."""
    mock_directory.get(SPACE_URL, json=space_v15)
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SEARCH: "HACK"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"
    assert result["description_placeholders"] == {"search": "HACK", "count": "1"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPACE: SPACE_URL}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Hackspace"
    assert result["data"] == {CONF_URL: SPACE_URL}
    assert result["result"].unique_id == SPACE_URL


async def test_search_lists_all_matches(
    hass: HomeAssistant, mock_directory: AiohttpClientMocker
) -> None:
    """The dropdown contains every case-insensitive match, sorted."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SEARCH: "chaos"}
    )
    assert result["step_id"] == "select"
    selector = result["data_schema"].schema[CONF_SPACE]
    labels = [option["label"] for option in selector.config["options"]]
    assert labels == ["Chaos Computer Club Test", "chaosdorf"]


async def test_search_no_match(
    hass: HomeAssistant, mock_directory: AiohttpClientMocker
) -> None:
    """No hit returns to the first step with an error."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SEARCH: "does-not-exist"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_SEARCH: "no_match"}


async def test_directory_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failing directory shows an error."""
    aioclient_mock.get(DIRECTORY_URL, exc=aiohttp.ClientError())
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SEARCH: "chaos"}
    )
    assert result["errors"] == {"base": "directory_unavailable"}


async def test_missing_input(hass: HomeAssistant) -> None:
    """Neither search nor URL."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "missing_input"}


async def test_manual_url(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    space_v15: dict[str, Any],
) -> None:
    """A URL entered directly skips the search."""
    aioclient_mock.get(SPACE_URL, json=space_v15)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: SPACE_URL, CONF_SEARCH: "ignored"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Hackspace"


async def test_manual_url_invalid(hass: HomeAssistant) -> None:
    """Reject non-http URLs."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "ftp://example.org/x"}
    )
    assert result["errors"] == {CONF_URL: "invalid_url"}


async def test_manual_url_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    space_v15: dict[str, Any],
) -> None:
    """Unreachable endpoint shows an error and can be retried."""
    aioclient_mock.get(SPACE_URL, status=500)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: SPACE_URL}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(SPACE_URL, json=space_v15)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: SPACE_URL}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_url_not_spaceapi(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """JSON without a ``space`` field is rejected."""
    aioclient_mock.get(SPACE_URL, json={"hello": "world"})
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: SPACE_URL}
    )
    assert result["errors"] == {"base": "invalid_api"}


async def test_manual_url_not_json(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """HTML instead of JSON is rejected."""
    aioclient_mock.get(SPACE_URL, text="<html>nope</html>")
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: SPACE_URL}
    )
    assert result["errors"] == {"base": "invalid_api"}


async def test_select_endpoint_broken(
    hass: HomeAssistant, mock_directory: AiohttpClientMocker
) -> None:
    """A broken endpoint picked from the dropdown shows an error on that step."""
    mock_directory.get(SPACE_URL, status=404)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SEARCH: "test hack"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPACE: SPACE_URL}
    )
    assert result["step_id"] == "select"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_aborts(
    hass: HomeAssistant,
    mock_directory: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """The same endpoint cannot be added twice."""
    config_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SEARCH: "Test"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPACE: SPACE_URL}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_aborts_normalized_url(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Upper-case host is treated as the same endpoint."""
    config_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "HTTPS://EXAMPLE.ORG/spaceapi.json"}
    )
    assert result["type"] is FlowResultType.ABORT


async def test_options_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    space_v15: dict[str, Any],
) -> None:
    """Change the polling interval."""
    await setup_entry(hass, config_entry, aioclient_mock, space_v15)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 10}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_SCAN_INTERVAL: 10}
    assert config_entry.runtime_data.update_interval.total_seconds() == 600
