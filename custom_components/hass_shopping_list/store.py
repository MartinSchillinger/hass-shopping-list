"""Persistence for shopping lists, stores, and items."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import uuid

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import EVENT_UPDATED, STORAGE_KEY, STORAGE_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


class ShoppingListStore:
    """In-memory shopping data backed by HA `.storage/` JSON."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.lists: list[dict[str, Any]] = []
        self.stores: list[dict[str, Any]] = []
        self.items: list[dict[str, Any]] = []
        self._listeners: list[Callable[[], None]] = []

    async def async_load(self) -> None:
        """Load data from disk."""
        data = await self._store.async_load()
        if data is None:
            self.lists = []
            self.stores = []
            self.items = []
            return
        self.lists = list(data.get("lists", []))
        self.stores = list(data.get("stores", []))
        self.items = list(data.get("items", []))

    async def async_save(self) -> None:
        """Persist data to disk."""
        await self._store.async_save(
            {
                "lists": self.lists,
                "stores": self.stores,
                "items": self.items,
            }
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a deep copy of all data (for websocket / services)."""
        return {
            "lists": deepcopy(self.lists),
            "stores": deepcopy(self.stores),
            "items": deepcopy(self.items),
        }

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Add a change listener; returns unsubscribe."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def _async_notify(self, action: str, **extra: Any) -> None:
        """Notify listeners and fire a bus event."""
        for listener in list(self._listeners):
            listener()
        self.hass.bus.async_fire(EVENT_UPDATED, {"action": action, **extra})

    def get_list(self, list_id: str) -> dict[str, Any] | None:
        """Return a list by id."""
        return next((lst for lst in self.lists if lst["list_id"] == list_id), None)

    def get_store(self, store_id: str) -> dict[str, Any] | None:
        """Return a store by id."""
        return next((s for s in self.stores if s["store_id"] == store_id), None)

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        """Return an item by uid."""
        return next((itm for itm in self.items if itm["uid"] == item_id), None)

    def items_for_list(self, list_id: str) -> list[dict[str, Any]]:
        """Return items belonging to a list."""
        return [itm for itm in self.items if itm["list_id"] == list_id]

    def store_name(self, store_id: str | None) -> str | None:
        """Resolve a store display name."""
        if not store_id:
            return None
        store = self.get_store(store_id)
        return store["name"] if store else None

    async def async_create_list(
        self,
        name: str,
        *,
        owner_user_id: str | None = None,
        default_store_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a shopping list (ACL fields present; enforcement is Slice 1)."""
        entry = {
            "list_id": _new_id(),
            "name": name.strip(),
            "created_at": _utc_now_iso(),
            "sort_order": len(self.lists),
            "owner_user_id": owner_user_id,
            "allowed_users": [],
            "default_store_id": default_store_id,
        }
        self.lists.append(entry)
        await self.async_save()
        self._async_notify("create_list", list_id=entry["list_id"])
        return deepcopy(entry)

    async def async_rename_list(self, list_id: str, name: str) -> dict[str, Any]:
        """Rename a shopping list."""
        entry = self.get_list(list_id)
        if entry is None:
            raise KeyError(f"List '{list_id}' not found")
        entry["name"] = name.strip()
        await self.async_save()
        self._async_notify("rename_list", list_id=list_id)
        return deepcopy(entry)

    async def async_delete_list(self, list_id: str) -> None:
        """Delete a list and its items."""
        if self.get_list(list_id) is None:
            raise KeyError(f"List '{list_id}' not found")
        self.lists = [lst for lst in self.lists if lst["list_id"] != list_id]
        self.items = [itm for itm in self.items if itm["list_id"] != list_id]
        await self.async_save()
        self._async_notify("delete_list", list_id=list_id)

    async def async_add_store(
        self,
        name: str,
        *,
        icon: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Add a store to the household catalog."""
        entry = {
            "store_id": _new_id(),
            "name": name.strip(),
            "icon": icon,
            "color": color,
            "sort_order": len(self.stores),
        }
        self.stores.append(entry)
        await self.async_save()
        self._async_notify("add_store", store_id=entry["store_id"])
        return deepcopy(entry)

    async def async_remove_store(self, store_id: str) -> None:
        """Remove a store and clear it from items."""
        if self.get_store(store_id) is None:
            raise KeyError(f"Store '{store_id}' not found")
        self.stores = [s for s in self.stores if s["store_id"] != store_id]
        for itm in self.items:
            if itm.get("store_id") == store_id:
                itm["store_id"] = None
        for lst in self.lists:
            if lst.get("default_store_id") == store_id:
                lst["default_store_id"] = None
        await self.async_save()
        self._async_notify("remove_store", store_id=store_id)

    async def async_add_item(
        self,
        list_id: str,
        name: str,
        *,
        store_id: str | None = None,
        quantity: str | None = None,
        note: str | None = None,
        complete: bool = False,
    ) -> dict[str, Any]:
        """Add an item to a list."""
        lst = self.get_list(list_id)
        if lst is None:
            raise KeyError(f"List '{list_id}' not found")
        if store_id is None:
            store_id = lst.get("default_store_id")
        if store_id is not None and self.get_store(store_id) is None:
            raise KeyError(f"Store '{store_id}' not found")
        entry = {
            "uid": _new_id(),
            "list_id": list_id,
            "name": name.strip(),
            "complete": complete,
            "store_id": store_id,
            "quantity": quantity,
            "note": note,
        }
        self.items.append(entry)
        await self.async_save()
        self._async_notify("add_item", list_id=list_id, item_id=entry["uid"])
        return deepcopy(entry)

    async def async_update_item(
        self, item_id: str, **changes: Any
    ) -> dict[str, Any]:
        """Update fields on an item."""
        item = self.get_item(item_id)
        if item is None:
            raise KeyError(f"Item '{item_id}' not found")
        if "store_id" in changes and changes["store_id"] is not None:
            if self.get_store(changes["store_id"]) is None:
                raise KeyError(f"Store '{changes['store_id']}' not found")
        for key, value in changes.items():
            if key in ("name", "complete", "store_id", "quantity", "note"):
                item[key] = value
        await self.async_save()
        self._async_notify(
            "update_item", list_id=item["list_id"], item_id=item_id
        )
        return deepcopy(item)

    async def async_set_item_store(
        self, item_id: str, store_id: str | None
    ) -> dict[str, Any]:
        """Assign (or clear) a store on an item."""
        return await self.async_update_item(item_id, store_id=store_id)

    async def async_remove_items(self, item_ids: set[str]) -> None:
        """Remove items by uid."""
        missing = item_ids - {itm["uid"] for itm in self.items}
        if missing:
            raise KeyError(f"Items not found: {', '.join(sorted(missing))}")
        list_ids = {
            itm["list_id"] for itm in self.items if itm["uid"] in item_ids
        }
        self.items = [itm for itm in self.items if itm["uid"] not in item_ids]
        await self.async_save()
        for list_id in list_ids:
            self._async_notify("remove_items", list_id=list_id)

    async def async_ensure_default_list(
        self, owner_user_id: str | None = None
    ) -> dict[str, Any]:
        """Create a starter list when storage is empty."""
        if self.lists:
            return deepcopy(self.lists[0])
        return await self.async_create_list(
            "Shopping", owner_user_id=owner_user_id
        )
