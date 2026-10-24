"""Tests for ShoppingListStore persistence and CRUD."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.hass_shopping_list.const import STORAGE_KEY, STORAGE_VERSION
from custom_components.hass_shopping_list.store import ShoppingListStore


@pytest.mark.asyncio
async def test_store_roundtrip_lists_stores_items(hass: HomeAssistant) -> None:
    """Persisted lists/stores/items reload with ACL schema fields."""
    store = ShoppingListStore(hass)
    await store.async_load()

    lst = await store.async_create_list(
        "Groceries", owner_user_id="user-1", default_store_id=None
    )
    assert lst["owner_user_id"] == "user-1"
    assert lst["allowed_users"] == []
    assert lst["default_store_id"] is None

    shop = await store.async_add_store("Aldi", icon="mdi:store", color="#00a")
    item = await store.async_add_item(
        lst["list_id"], "Milk", store_id=shop["store_id"], quantity="1L"
    )
    assert item["store_id"] == shop["store_id"]
    assert item["complete"] is False

    # Reload from disk via a fresh instance
    reloaded = ShoppingListStore(hass)
    await reloaded.async_load()
    assert len(reloaded.lists) == 1
    assert reloaded.lists[0]["list_id"] == lst["list_id"]
    assert reloaded.lists[0]["allowed_users"] == []
    assert len(reloaded.stores) == 1
    assert reloaded.stores[0]["name"] == "Aldi"
    assert len(reloaded.items) == 1
    assert reloaded.items[0]["name"] == "Milk"
    assert reloaded.items[0]["store_id"] == shop["store_id"]


@pytest.mark.asyncio
async def test_set_item_store_and_list_default(hass: HomeAssistant) -> None:
    """Items pick up list default_store_id; set_item_store updates."""
    store = ShoppingListStore(hass)
    await store.async_load()

    aldi = await store.async_add_store("Aldi")
    edeka = await store.async_add_store("Edeka")
    lst = await store.async_create_list(
        "Weekly", owner_user_id="u", default_store_id=aldi["store_id"]
    )

    item = await store.async_add_item(lst["list_id"], "Potatoes")
    assert item["store_id"] == aldi["store_id"]

    updated = await store.async_set_item_store(item["uid"], edeka["store_id"])
    assert updated["store_id"] == edeka["store_id"]

    cleared = await store.async_set_item_store(item["uid"], None)
    assert cleared["store_id"] is None


@pytest.mark.asyncio
async def test_storage_key_uses_ha_store(hass: HomeAssistant) -> None:
    """Data lands under the expected `.storage` key."""
    store = ShoppingListStore(hass)
    await store.async_load()
    await store.async_create_list("A", owner_user_id="u")

    raw = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await raw.async_load()
    assert data is not None
    assert "lists" in data and "stores" in data and "items" in data
    assert data["lists"][0]["name"] == "A"
