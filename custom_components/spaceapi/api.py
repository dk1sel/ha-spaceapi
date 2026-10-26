"""HTTP helpers for the SpaceAPI integration."""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import DIRECTORY_URL, REQUEST_TIMEOUT
from .parser import SpaceData, parse_space

_HEADERS = {"Accept": "application/json"}


class SpaceApiError(Exception):
    """Base error."""


class SpaceApiConnectionError(SpaceApiError):
    """The endpoint could not be reached or returned an HTTP error."""


class SpaceApiInvalidResponse(SpaceApiError):
    """The endpoint returned something that is not a SpaceAPI document."""


async def async_fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
    """Fetch and decode a JSON document."""
    try:
        async with session.get(
            url,
            headers=_HEADERS,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            response.raise_for_status()
            # Many endpoints serve JSON as text/plain or text/html.
            return await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise SpaceApiConnectionError(str(err) or type(err).__name__) from err
    except ValueError as err:
        raise SpaceApiInvalidResponse(f"invalid JSON: {err}") from err


async def async_fetch_space(
    session: aiohttp.ClientSession, url: str
) -> tuple[Any, SpaceData]:
    """Fetch a SpaceAPI endpoint and return raw and parsed data."""
    raw = await async_fetch_json(session, url)
    try:
        return raw, parse_space(raw)
    except ValueError as err:
        raise SpaceApiInvalidResponse(str(err)) from err


async def async_fetch_directory(session: aiohttp.ClientSession) -> dict[str, str]:
    """Fetch the SpaceAPI directory as ``{space name: endpoint url}``."""
    raw = await async_fetch_json(session, DIRECTORY_URL)
    if not isinstance(raw, dict):
        raise SpaceApiInvalidResponse("directory is not a JSON object")
    return {
        str(name): url.strip()
        for name, url in raw.items()
        if isinstance(url, str) and url.strip()
    }


def search_directory(directory: dict[str, str], query: str) -> dict[str, str]:
    """Return directory entries whose name contains ``query`` (case-insensitive)."""
    needle = query.strip().casefold()
    if not needle:
        return {}
    return dict(
        sorted(
            (
                (name, url)
                for name, url in directory.items()
                if needle in name.casefold()
            ),
            key=lambda item: item[0].casefold(),
        )
    )
