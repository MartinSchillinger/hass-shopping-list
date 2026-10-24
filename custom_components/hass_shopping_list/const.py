"""Constants for the hass_shopping_list integration."""

from __future__ import annotations

DOMAIN = "hass_shopping_list"

STORAGE_KEY = "hass_shopping_list"
STORAGE_VERSION = 1

ATTR_LIST_ID = "list_id"
ATTR_STORE_ID = "store_id"
ATTR_ITEM_ID = "item_id"
ATTR_NAME = "name"
ATTR_ICON = "icon"
ATTR_COLOR = "color"
ATTR_QUANTITY = "quantity"
ATTR_NOTE = "note"
ATTR_DEFAULT_STORE_ID = "default_store_id"

SERVICE_ADD_ITEM = "add_item"
SERVICE_SET_ITEM_STORE = "set_item_store"
SERVICE_ADD_STORE = "add_store"
SERVICE_LIST_STORES = "list_stores"
SERVICE_REMOVE_STORE = "remove_store"
SERVICE_CREATE_LIST = "create_list"
SERVICE_RENAME_LIST = "rename_list"
SERVICE_DELETE_LIST = "delete_list"
SERVICE_LIST_LISTS = "list_lists"

EVENT_UPDATED = "hass_shopping_list_updated"

FRONTEND_SCRIPT_URL = f"/{DOMAIN}/hass-shopping-list-card.js"
