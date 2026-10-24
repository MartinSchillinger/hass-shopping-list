"""Service happy-path tests for hass_shopping_list."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_shopping_list.const import DOMAIN


@pytest.mark.asyncio
async def test_service_happy_path(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """create_list → add_store → add_item → set_item_store → list_stores."""
    create = await hass.services.async_call(
        DOMAIN,
        "create_list",
        {"name": "Party"},
        blocking=True,
        return_response=True,
    )
    list_id = create["list"]["list_id"]
    assert create["list"]["allowed_users"] == []
    assert "owner_user_id" in create["list"]

    store_resp = await hass.services.async_call(
        DOMAIN,
        "add_store",
        {"name": "Rewe", "icon": "mdi:cart"},
        blocking=True,
        return_response=True,
    )
    store_id = store_resp["store"]["store_id"]

    item_resp = await hass.services.async_call(
        DOMAIN,
        "add_item",
        {"list_id": list_id, "name": "Chips", "store_id": store_id},
        blocking=True,
        return_response=True,
    )
    item_id = item_resp["item"]["uid"]
    assert item_resp["item"]["store_id"] == store_id

    other = await hass.services.async_call(
        DOMAIN,
        "add_store",
        {"name": "Aldi"},
        blocking=True,
        return_response=True,
    )
    updated = await hass.services.async_call(
        DOMAIN,
        "set_item_store",
        {"item_id": item_id, "store_id": other["store"]["store_id"]},
        blocking=True,
        return_response=True,
    )
    assert updated["item"]["store_id"] == other["store"]["store_id"]

    stores = await hass.services.async_call(
        DOMAIN,
        "list_stores",
        {},
        blocking=True,
        return_response=True,
    )
    names = {s["name"] for s in stores["stores"]}
    assert names >= {"Rewe", "Aldi"}

    lists = await hass.services.async_call(
        DOMAIN,
        "list_lists",
        {},
        blocking=True,
        return_response=True,
    )
    list_names = {lst["name"] for lst in lists["lists"]}
    assert "Party" in list_names
    # Default list from ensure_default_list
    assert "Shopping" in list_names


@pytest.mark.asyncio
async def test_add_item_invalid_list_raises(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """add_item with unknown list_id raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "add_item",
            {"list_id": "missing", "name": "X"},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_todo_entity_created_per_list(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Each list gets a todo entity with shopping_items attributes."""
    await hass.async_block_till_done()
    todo_entities = [
        eid for eid in hass.states.async_entity_ids("todo") if eid.startswith("todo.")
    ]
    assert todo_entities, "expected at least the default Shopping todo entity"

    state = hass.states.get(todo_entities[0])
    assert state is not None
    assert "list_id" in state.attributes
    assert "shopping_items" in state.attributes
    assert "stores" in state.attributes


@pytest.mark.asyncio
async def test_rename_and_delete_list_services(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """rename_list / delete_list service happy path."""
    created = await hass.services.async_call(
        DOMAIN,
        "create_list",
        {"name": "Temp"},
        blocking=True,
        return_response=True,
    )
    list_id = created["list"]["list_id"]

    renamed = await hass.services.async_call(
        DOMAIN,
        "rename_list",
        {"list_id": list_id, "name": "Temp 2"},
        blocking=True,
        return_response=True,
    )
    assert renamed["list"]["name"] == "Temp 2"

    await hass.services.async_call(
        DOMAIN,
        "add_item",
        {"list_id": list_id, "name": "Gone"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "delete_list", {"list_id": list_id}, blocking=True
    )

    lists = await hass.services.async_call(
        DOMAIN, "list_lists", {}, blocking=True, return_response=True
    )
    assert all(lst["list_id"] != list_id for lst in lists["lists"])


@pytest.mark.asyncio
async def test_remove_store_service(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """remove_store drops the store from list_stores."""
    store_resp = await hass.services.async_call(
        DOMAIN,
        "add_store",
        {"name": "Netto"},
        blocking=True,
        return_response=True,
    )
    store_id = store_resp["store"]["store_id"]

    await hass.services.async_call(
        DOMAIN, "remove_store", {"store_id": store_id}, blocking=True
    )
    stores = await hass.services.async_call(
        DOMAIN, "list_stores", {}, blocking=True, return_response=True
    )
    assert all(s["store_id"] != store_id for s in stores["stores"])


@pytest.mark.asyncio
async def test_set_item_store_invalid_item_raises(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """set_item_store with unknown item_id raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_item_store",
            {"item_id": "missing", "store_id": None},
            blocking=True,
        )
