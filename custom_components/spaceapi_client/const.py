"""Constants for the SpaceAPI integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "spaceapi_client"

DIRECTORY_URL: Final = "https://directory.spaceapi.io/"

CONF_SEARCH: Final = "search"
CONF_SPACE: Final = "space"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Polling interval in minutes.
DEFAULT_SCAN_INTERVAL: Final = 5
MIN_SCAN_INTERVAL: Final = 1
MAX_SCAN_INTERVAL: Final = 1440

REQUEST_TIMEOUT: Final = 15
CAMERA_TIMEOUT: Final = 10

EVENT_STATE_CHANGED: Final = "spaceapi_state_changed"

MANUFACTURER: Final = "SpaceAPI"

DEFAULT_UPDATE_INTERVAL: Final = timedelta(minutes=DEFAULT_SCAN_INTERVAL)

# Known contact fields (SpaceAPI v13-v15). Each one becomes a diagnostic sensor.
CONTACT_KEYS: Final = (
    "email",
    "phone",
    "sip",
    "irc",
    "matrix",
    "mastodon",
    "xmpp",
    "mumble",
    "ml",
    "issue_mail",
    "twitter",
    "facebook",
    "identica",
    "foursquare",
    "gopher",
)
