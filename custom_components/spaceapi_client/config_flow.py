"""Config flow for the SpaceAPI integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol
from yarl import URL

from .api import (
    SpaceApiConnectionError,
    SpaceApiInvalidResponse,
    async_fetch_directory,
    async_fetch_space,
    search_directory,
)
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SEARCH,
    CONF_SPACE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import SpaceApiConfigEntry

_LOGGER = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Normalize an endpoint URL for use as unique ID."""
    parsed = URL(url.strip())
    if parsed.scheme:
        parsed = parsed.with_scheme(parsed.scheme.lower())
    if parsed.host:
        parsed = parsed.with_host(parsed.host.lower())
    return str(parsed)


def _valid_http_url(url: str) -> bool:
    try:
        parsed = URL(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.host)


class SpaceApiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SpaceAPI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._matches: dict[str, str] = {}
        self._search: str = ""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SpaceApiConfigEntry,
    ) -> SpaceApiOptionsFlow:
        """Return the options flow."""
        return SpaceApiOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: search the directory or enter an endpoint URL."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = (user_input.get(CONF_URL) or "").strip()
            search = (user_input.get(CONF_SEARCH) or "").strip()
            self._search = search
            if url:
                if not _valid_http_url(url):
                    errors[CONF_URL] = "invalid_url"
                else:
                    result, error = await self._async_try_create(url)
                    if result is not None:
                        return result
                    errors["base"] = error
            elif search:
                session = async_get_clientsession(self.hass)
                try:
                    directory = await async_fetch_directory(session)
                except (SpaceApiConnectionError, SpaceApiInvalidResponse) as err:
                    _LOGGER.debug("Directory not available: %s", err)
                    errors["base"] = "directory_unavailable"
                else:
                    self._matches = search_directory(directory, search)
                    if self._matches:
                        return await self.async_step_select()
                    errors[CONF_SEARCH] = "no_match"
            else:
                errors["base"] = "missing_input"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_SEARCH): TextSelector(),
                        vol.Optional(CONF_URL): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.URL)
                        ),
                    }
                ),
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: pick one of the matching spaces."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_SPACE]
            result, error = await self._async_try_create(url)
            if result is not None:
                return result
            errors["base"] = error

        options = [
            SelectOptionDict(value=url, label=name)
            for name, url in self._matches.items()
        ]
        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SPACE, default=options[0]["value"]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            description_placeholders={
                "search": self._search,
                "count": str(len(options)),
            },
            errors=errors,
        )

    async def _async_try_create(self, url: str) -> tuple[ConfigFlowResult | None, str]:
        """Validate an endpoint and create the entry."""
        await self.async_set_unique_id(normalize_url(url))
        self._abort_if_unique_id_configured()
        session = async_get_clientsession(self.hass)
        try:
            _, data = await async_fetch_space(session, url)
        except SpaceApiConnectionError as err:
            _LOGGER.debug("Cannot connect to %s: %s", url, err)
            return None, "cannot_connect"
        except SpaceApiInvalidResponse as err:
            _LOGGER.debug("Invalid SpaceAPI document at %s: %s", url, err)
            return None, "invalid_api"
        return self.async_create_entry(title=data.space, data={CONF_URL: url}), ""


class SpaceApiOptionsFlow(OptionsFlowWithReload):
    """Options: polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    )
                }
            ),
        )
