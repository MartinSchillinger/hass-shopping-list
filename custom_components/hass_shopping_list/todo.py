"""Todo platform — one TodoListEntity per shopping list."""

from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .store import ShoppingListStore


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up todo entities for each shopping list."""
    data: ShoppingListStore = hass.data[DOMAIN]
    known: dict[str, ShoppingListTodoEntity] = {}

    @callback
    def _sync_entities() -> None:
        to_add: list[ShoppingListTodoEntity] = []
        current_ids = {lst["list_id"] for lst in data.lists}

        for lst in data.lists:
            list_id = lst["list_id"]
            if list_id in known:
                entity = known[list_id]
                if entity.name != lst["name"]:
                    entity.set_list_name(lst["name"])
                    entity.async_write_ha_state()
                continue
            entity = ShoppingListTodoEntity(
                data,
                list_id=list_id,
                name=lst["name"],
                config_entry_id=config_entry.entry_id,
            )
            known[list_id] = entity
            to_add.append(entity)

        if to_add:
            async_add_entities(to_add)

        for list_id in list(known):
            if list_id not in current_ids:
                entity = known.pop(list_id)
                # force_remove: drop registry-backed state so the entity disappears
                hass.async_create_task(entity.async_remove(force_remove=True))

    _sync_entities()
    config_entry.async_on_unload(data.async_add_listener(_sync_entities))


class ShoppingListTodoEntity(TodoListEntity):
    """Todo entity backed by ShoppingListStore for one list."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self,
        data: ShoppingListStore,
        *,
        list_id: str,
        name: str,
        config_entry_id: str,
    ) -> None:
        """Initialize the entity."""
        self._data = data
        self._list_id = list_id
        self._attr_name = name
        self._attr_unique_id = f"{config_entry_id}_{list_id}"

    @property
    def list_id(self) -> str:
        """Return the shopping list id."""
        return self._list_id

    def set_list_name(self, name: str) -> None:
        """Update the entity display name."""
        self._attr_name = name

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose list/store metadata for the custom card."""
        lst = self._data.get_list(self._list_id) or {}
        items = []
        for itm in self._data.items_for_list(self._list_id):
            items.append(
                {
                    "uid": itm["uid"],
                    "name": itm["name"],
                    "complete": itm["complete"],
                    "store_id": itm.get("store_id"),
                    "store_name": self._data.store_name(itm.get("store_id")),
                    "quantity": itm.get("quantity"),
                    "note": itm.get("note"),
                }
            )
        return {
            "list_id": self._list_id,
            "default_store_id": lst.get("default_store_id"),
            "owner_user_id": lst.get("owner_user_id"),
            "allowed_users": lst.get("allowed_users", []),
            "stores": self._data.as_dict()["stores"],
            "shopping_items": items,
        }

    @property
    def todo_items(self) -> list[TodoItem]:
        """Map store items to TodoItem (store mirrored in description)."""
        results: list[TodoItem] = []
        for itm in self._data.items_for_list(self._list_id):
            status = (
                TodoItemStatus.COMPLETED
                if itm["complete"]
                else TodoItemStatus.NEEDS_ACTION
            )
            store_name = self._data.store_name(itm.get("store_id"))
            description_parts: list[str] = []
            if store_name:
                description_parts.append(f"[{store_name}]")
            if itm.get("note"):
                description_parts.append(str(itm["note"]))
            results.append(
                TodoItem(
                    uid=itm["uid"],
                    summary=itm["name"],
                    status=status,
                    description=" ".join(description_parts) or None,
                )
            )
        return results

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item via the todo platform."""
        try:
            await self._data.async_add_item(
                self._list_id,
                item.summary or "",
                complete=item.status == TodoItemStatus.COMPLETED,
                note=item.description,
            )
        except KeyError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item via the todo platform."""
        try:
            await self._data.async_update_item(
                item.uid or "",
                name=item.summary,
                complete=item.status == TodoItemStatus.COMPLETED,
                note=item.description,
            )
        except KeyError as err:
            raise HomeAssistantError(
                f"Shopping list item '{item.uid}' was not found"
            ) from err

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items via the todo platform."""
        try:
            await self._data.async_remove_items(set(uids))
        except KeyError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_added_to_hass(self) -> None:
        """Register for store updates."""
        self.async_on_remove(
            self._data.async_add_listener(self.async_write_ha_state)
        )
