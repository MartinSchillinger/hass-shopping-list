"""Lovelace card + websocket API tests (card surface for Slice 0)."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_shopping_list import _async_register_frontend
from custom_components.hass_shopping_list.const import (
    DOMAIN,
    EVENT_UPDATED,
    FRONTEND_SCRIPT_URL,
)
from custom_components.hass_shopping_list.websocket_api import websocket_get_data

CARD_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "hass_shopping_list"
    / "www"
    / "hass-shopping-list-card.js"
)

# @websocket_api.async_response wraps the coroutine; unwrap for direct calls.
_websocket_get_data = inspect.unwrap(websocket_get_data)


def test_lovelace_card_file_defines_custom_element() -> None:
    """Card JS registers the custom element and store filter UI."""
    assert CARD_PATH.is_file()
    source = CARD_PATH.read_text(encoding="utf-8")

    assert 'customElements.define("hass-shopping-list-card"' in source
    assert 'type: "hass-shopping-list-card"' in source
    assert "window.customCards" in source
    assert "Shopping" in source  # picker search for "shop"
    assert "Einkauf" in source
    assert "hass-shopping-list" in source
    assert 'type: "hass_shopping_list/get_data"' in source
    assert '"hass_shopping_list_updated"' in source
    assert 'id="filterStore"' in source
    assert "All stores" in source
    assert 'class="badge"' in source
    assert 'callService("hass_shopping_list", "add_item"' in source
    # Broken visual editor stub must not be registered (picker falls back to YAML).
    assert "hass-shopping-list-card-editor" not in source


def test_card_preserves_input_focus_across_updates() -> None:
    """Add/store text inputs must not be destroyed by routine hass updates.

    Regression: set hass() used to call _render() on every HA state push,
    replacing shadowRoot.innerHTML and stealing focus while typing.
    """
    source = CARD_PATH.read_text(encoding="utf-8")

    # Focus capture/restore around full re-renders (websocket/_load, UI actions).
    assert "_captureFocus" in source
    assert "_restoreFocus" in source
    assert "this._restoreFocus(focus)" in source

    # hass setter must not re-render once subscribed (data comes via event → _load).
    hass_setter = source.split("set hass(hass)", 1)[1].split(
        "getCardSize(", 1
    )[0]
    assert "this._render()" not in hass_setter
    assert "Do not re-render on every hass property update" in hass_setter

    # Draft inputs update local state only — no _render on each keystroke.
    assert 'newName.addEventListener("input"' in source
    assert 'newStoreName.addEventListener("input"' in source
    assert 'this._draftName = ev.target.value' in source
    assert 'this._draftStoreName = ev.target.value' in source


@pytest.mark.asyncio
async def test_websocket_get_data_for_card(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Card backend: websocket handler returns lists/stores/items."""
    store = await hass.services.async_call(
        DOMAIN,
        "add_store",
        {"name": "Edeka"},
        blocking=True,
        return_response=True,
    )
    lists = await hass.services.async_call(
        DOMAIN, "list_lists", {}, blocking=True, return_response=True
    )
    list_id = lists["lists"][0]["list_id"]
    await hass.services.async_call(
        DOMAIN,
        "add_item",
        {
            "list_id": list_id,
            "name": "Butter",
            "store_id": store["store"]["store_id"],
        },
        blocking=True,
    )

    connection = MagicMock()
    await _websocket_get_data(
        hass, connection, {"id": 1, "type": f"{DOMAIN}/get_data"}
    )
    connection.send_result.assert_called_once()
    _msg_id, result = connection.send_result.call_args.args
    assert _msg_id == 1
    assert any(s["name"] == "Edeka" for s in result["stores"])
    assert any(i["name"] == "Butter" for i in result["items"])
    assert any(lst["list_id"] == list_id for lst in result["lists"])

    connection.reset_mock()
    await _websocket_get_data(
        hass,
        connection,
        {"id": 2, "type": f"{DOMAIN}/get_data", "list_id": list_id},
    )
    _msg_id, result = connection.send_result.call_args.args
    assert all(i["list_id"] == list_id for i in result["items"])
    assert all(lst["list_id"] == list_id for lst in result["lists"])

    connection.reset_mock()
    await _websocket_get_data(
        hass,
        connection,
        {"id": 3, "type": f"{DOMAIN}/get_data", "list_id": "nope"},
    )
    _msg_id, result = connection.send_result.call_args.args
    assert result["lists"] == []
    assert result["items"] == []


@pytest.mark.asyncio
async def test_update_event_fired_for_card_refresh(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Mutations fire hass_shopping_list_updated for the card subscription."""
    events: list[dict] = []

    def _capture(event) -> None:
        events.append(event.data)

    hass.bus.async_listen(EVENT_UPDATED, _capture)

    await hass.services.async_call(
        DOMAIN, "add_store", {"name": "Lidl"}, blocking=True
    )
    await hass.async_block_till_done()

    assert any(e.get("action") == "add_store" for e in events)


@pytest.mark.asyncio
async def test_frontend_card_path_registered(hass: HomeAssistant) -> None:
    """Integration registers the static card URL for Lovelace."""
    mock_http = SimpleNamespace(
        async_register_static_paths=AsyncMock(),
    )
    # HomeAssistant.http is normally set by the http component
    object.__setattr__(hass, "http", mock_http)

    with patch(
        "custom_components.hass_shopping_list.frontend.add_extra_js_url"
    ) as mock_js:
        await _async_register_frontend(hass)

    mock_http.async_register_static_paths.assert_awaited()
    paths = mock_http.async_register_static_paths.await_args.args[0]
    assert paths[0].url_path == f"/{DOMAIN}"
    mock_js.assert_called_once_with(hass, FRONTEND_SCRIPT_URL)
