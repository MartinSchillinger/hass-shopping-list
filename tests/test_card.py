"""Lovelace card + websocket API tests (card surface for Slice 0)."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_shopping_list import (
    _async_register_frontend,
    _lovelace_storage_resources,
)
from custom_components.hass_shopping_list.const import (
    DOMAIN,
    EVENT_UPDATED,
    FRONTEND_SCRIPT_PATH,
    INTEGRATION_VERSION,
    versioned_frontend_script_url,
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
    """Card JS registers list + stores elements and picker metadata."""
    assert CARD_PATH.is_file()
    source = CARD_PATH.read_text(encoding="utf-8")

    assert 'customElements.define("hass-shopping-list-card"' in source
    assert "HassShoppingListStoresCard" in source
    assert 'customElements.define(\n    "hass-shopping-list-stores-card"' in source
    assert 'type: "hass-shopping-list-card"' in source
    assert 'type: "hass-shopping-list-stores-card"' in source
    assert "window.customCards" in source
    assert "Shopping" in source  # picker search for "shop"
    assert "Einkauf" in source
    assert "Läden" in source or "Laden" in source
    assert "Stores" in source
    assert "hass-shopping-list" in source
    assert 'type: "hass_shopping_list/get_data"' in source
    assert '"hass_shopping_list_updated"' in source
    assert 'id="filterStore"' in source
    assert "All stores" in source
    assert 'class="badge"' in source
    assert 'callService("hass_shopping_list", "add_item"' in source
    assert 'callService("hass_shopping_list", "add_store"' in source
    assert 'callService("hass_shopping_list", "update_store"' in source
    # Edit modal on the list card (no per-row store dropdown).
    assert 'id="editName"' in source
    assert 'id="editStore"' in source
    assert 'id="editSave"' in source
    assert "itemStore" not in source
    assert "Läden verwalten" not in source
    # Store colors: curated palette + contrast-aware badges.
    assert "HSL_STORE_PALETTE" in source
    assert "_hslBadgeStyle" in source
    assert "_hslContrastText" in source
    assert '"newStoreColor"' in source
    assert '"editStoreColor"' in source
    assert 'id="editStoreSave"' in source
    assert "HSL_DEFAULT_STORE_COLOR" in source
    assert "_hslPaletteHtml" in source
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

    # Both cards: hass setter must not re-render once subscribed.
    assert source.count("Do not re-render on every hass property update") >= 2
    for marker in (
        "class HassShoppingListCard extends HTMLElement",
        "class HassShoppingListStoresCard extends HTMLElement",
    ):
        block = source.split(marker, 1)[1]
        hass_setter = block.split("set hass(hass)", 1)[1].split(
            "getCardSize(", 1
        )[0]
        assert "this._render()" not in hass_setter

    # Draft inputs update local state only — no _render on each keystroke.
    assert 'newName.addEventListener("input"' in source
    assert 'newStoreName.addEventListener("input"' in source
    assert 'this._draftName = ev.target.value' in source
    assert 'this._draftStoreName = ev.target.value' in source
    assert 'this._editName = ev.target.value' in source
    assert 'this._editStoreName = ev.target.value' in source


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
async def test_frontend_card_path_registered_yaml_fallback(
    hass: HomeAssistant,
) -> None:
    """Without Lovelace storage resources, fall back to add_extra_js_url."""
    mock_http = SimpleNamespace(
        async_register_static_paths=AsyncMock(),
    )
    object.__setattr__(hass, "http", mock_http)
    hass.data.pop(f"{DOMAIN}_static_registered", None)
    hass.data.pop(f"{DOMAIN}_frontend_resource_registered", None)
    hass.data.pop("lovelace", None)

    expected = versioned_frontend_script_url(INTEGRATION_VERSION)
    with patch(
        "custom_components.hass_shopping_list.frontend.add_extra_js_url"
    ) as mock_js:
        await _async_register_frontend(hass)

    mock_http.async_register_static_paths.assert_awaited()
    paths = mock_http.async_register_static_paths.await_args.args[0]
    assert paths[0].url_path == f"/{DOMAIN}"
    mock_js.assert_called_once_with(hass, expected)
    assert hass.data[f"{DOMAIN}_frontend_resource_registered"] == "extra_js"
    # Second call is idempotent (no duplicate static/module registration).
    with patch(
        "custom_components.hass_shopping_list.frontend.add_extra_js_url"
    ) as mock_js2:
        await _async_register_frontend(hass)
    mock_js2.assert_not_called()
    assert mock_http.async_register_static_paths.await_count == 1


@pytest.mark.asyncio
async def test_frontend_registers_lovelace_storage_resource(
    hass: HomeAssistant,
) -> None:
    """Storage-mode Lovelace gets a module resource (awaited by the dashboard)."""
    mock_http = SimpleNamespace(
        async_register_static_paths=AsyncMock(),
    )
    object.__setattr__(hass, "http", mock_http)
    hass.data.pop(f"{DOMAIN}_static_registered", None)
    hass.data.pop(f"{DOMAIN}_frontend_resource_registered", None)

    resources = SimpleNamespace(
        loaded=True,
        store=SimpleNamespace(key="lovelace_resources", version=1),
        async_items=MagicMock(return_value=[]),
        async_create_item=AsyncMock(),
        async_update_item=AsyncMock(),
        async_load=AsyncMock(),
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources, resource_mode="storage")

    expected = versioned_frontend_script_url(INTEGRATION_VERSION)
    with patch(
        "custom_components.hass_shopping_list.frontend.add_extra_js_url"
    ) as mock_js:
        await _async_register_frontend(hass)

    mock_js.assert_not_called()
    resources.async_create_item.assert_awaited_once_with(
        {"res_type": "module", "url": expected}
    )
    assert hass.data[f"{DOMAIN}_frontend_resource_registered"] == "lovelace"


@pytest.mark.asyncio
async def test_frontend_updates_stale_lovelace_resource(
    hass: HomeAssistant,
) -> None:
    """Existing resource URL is updated when the integration version changes."""
    mock_http = SimpleNamespace(
        async_register_static_paths=AsyncMock(),
    )
    object.__setattr__(hass, "http", mock_http)
    hass.data.pop(f"{DOMAIN}_static_registered", None)
    hass.data.pop(f"{DOMAIN}_frontend_resource_registered", None)

    resources = SimpleNamespace(
        loaded=False,
        store=SimpleNamespace(key="lovelace_resources", version=1),
        async_items=MagicMock(
            return_value=[
                {
                    "id": "res1",
                    "url": f"{FRONTEND_SCRIPT_PATH}?v=0.0.1",
                    "type": "module",
                }
            ]
        ),
        async_create_item=AsyncMock(),
        async_update_item=AsyncMock(),
        async_load=AsyncMock(),
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources, resource_mode="storage")

    expected = versioned_frontend_script_url(INTEGRATION_VERSION)
    await _async_register_frontend(hass)

    resources.async_load.assert_awaited()
    resources.async_update_item.assert_awaited_once_with(
        "res1", {"res_type": "module", "url": expected}
    )
    resources.async_create_item.assert_not_called()


def test_lovelace_storage_resources_skips_yaml_mode(hass: HomeAssistant) -> None:
    """YAML resource collections (no store) are not treated as writable."""
    yaml_resources = SimpleNamespace(loaded=True, store=None, async_items=list)
    hass.data["lovelace"] = SimpleNamespace(resources=yaml_resources)
    assert _lovelace_storage_resources(hass) is None

    hass.data["lovelace"] = {"resources": None}
    assert _lovelace_storage_resources(hass) is None


def test_versioned_frontend_script_url() -> None:
    """Cache-bust query uses the manifest version."""
    url = versioned_frontend_script_url("9.9.9")
    assert url == f"{FRONTEND_SCRIPT_PATH}?v=9.9.9"
    assert INTEGRATION_VERSION
    assert versioned_frontend_script_url().endswith(f"?v={INTEGRATION_VERSION}")
