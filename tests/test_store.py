"""Tests for ShoppingListStore persistence and CRUD."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.hass_shopping_list.const import STORAGE_KEY, STORAGE_VERSION
from custom_components.hass_shopping_list.store import (
    DEFAULT_STORE_COLOR,
    ShoppingListStore,
    resolve_store_color,
)


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
    assert reloaded.stores[0]["color"] == "#00a"
    assert len(reloaded.items) == 1
    assert reloaded.items[0]["name"] == "Milk"
    assert reloaded.items[0]["store_id"] == shop["store_id"]


@pytest.mark.asyncio
async def test_update_store_color_and_default(hass: HomeAssistant) -> None:
    """update_store persists color; missing color resolves to default."""
    store = ShoppingListStore(hass)
    await store.async_load()
    shop = await store.async_add_store("Aldi")
    assert shop["color"] is None
    assert resolve_store_color(shop) == DEFAULT_STORE_COLOR

    updated = await store.async_update_store(
        shop["store_id"], name="Aldi Nord", color="#1e88e5"
    )
    assert updated["name"] == "Aldi Nord"
    assert updated["color"] == "#1e88e5"

    reloaded = ShoppingListStore(hass)
    await reloaded.async_load()
    entry = reloaded.get_store(shop["store_id"])
    assert entry["name"] == "Aldi Nord"
    assert entry["color"] == "#1e88e5"
    assert resolve_store_color(entry) == "#1e88e5"

    cleared = await reloaded.async_update_store(shop["store_id"], color=None)
    assert cleared["color"] is None
    assert resolve_store_color(cleared) == DEFAULT_STORE_COLOR


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


@pytest.mark.asyncio
async def test_rename_and_delete_list_persists(hass: HomeAssistant) -> None:
    """Rename/delete list (and cascade items) survive reload."""
    store = ShoppingListStore(hass)
    await store.async_load()
    lst = await store.async_create_list("Temp", owner_user_id="u")
    await store.async_add_item(lst["list_id"], "Eggs")

    renamed = await store.async_rename_list(lst["list_id"], "Renamed")
    assert renamed["name"] == "Renamed"

    reloaded = ShoppingListStore(hass)
    await reloaded.async_load()
    assert reloaded.get_list(lst["list_id"])["name"] == "Renamed"
    assert len(reloaded.items_for_list(lst["list_id"])) == 1

    await reloaded.async_delete_list(lst["list_id"])
    again = ShoppingListStore(hass)
    await again.async_load()
    assert again.get_list(lst["list_id"]) is None
    assert again.items_for_list(lst["list_id"]) == []


@pytest.mark.asyncio
async def test_remove_store_clears_item_and_default(hass: HomeAssistant) -> None:
    """Removing a store clears item store_id and list default_store_id."""
    store = ShoppingListStore(hass)
    await store.async_load()
    shop = await store.async_add_store("Aldi")
    lst = await store.async_create_list(
        "G", owner_user_id="u", default_store_id=shop["store_id"]
    )
    item = await store.async_add_item(lst["list_id"], "Milk")
    assert item["store_id"] == shop["store_id"]

    await store.async_remove_store(shop["store_id"])
    assert store.get_store(shop["store_id"]) is None
    assert store.get_item(item["uid"])["store_id"] is None
    assert store.get_list(lst["list_id"])["default_store_id"] is None


@pytest.mark.asyncio
async def test_ensure_default_list_once(hass: HomeAssistant) -> None:
    """Empty storage gets one default Shopping list; second call is a no-op."""
    store = ShoppingListStore(hass)
    await store.async_load()
    first = await store.async_ensure_default_list(owner_user_id="owner")
    assert first["name"] == "Shopping"
    assert first["owner_user_id"] == "owner"
    assert first["allowed_users"] == []

    second = await store.async_ensure_default_list(owner_user_id="other")
    assert second["list_id"] == first["list_id"]
    assert len(store.lists) == 1


@pytest.mark.asyncio
async def test_add_item_rejects_unknown_store(hass: HomeAssistant) -> None:
    """Unknown store_id raises KeyError."""
    store = ShoppingListStore(hass)
    await store.async_load()
    lst = await store.async_create_list("G", owner_user_id="u")
    with pytest.raises(KeyError, match="Store"):
        await store.async_add_item(lst["list_id"], "X", store_id="missing")
