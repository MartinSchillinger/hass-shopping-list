"""Websocket API for the Lovelace shopping list card."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, websocket_get_data)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get_data",
        vol.Optional("list_id"): str,
    }
)
@websocket_api.async_response
async def websocket_get_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return lists, stores, and items (optionally filtered by list_id)."""
    data = hass.data[DOMAIN].as_dict()
    list_id = msg.get("list_id")
    if list_id:
        data["items"] = [i for i in data["items"] if i["list_id"] == list_id]
        data["lists"] = [lst for lst in data["lists"] if lst["list_id"] == list_id]
    connection.send_result(msg["id"], data)
