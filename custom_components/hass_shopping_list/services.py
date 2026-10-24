"""Service registration for hass_shopping_list."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_COLOR,
    ATTR_DEFAULT_STORE_ID,
    ATTR_ICON,
    ATTR_ITEM_ID,
    ATTR_LIST_ID,
    ATTR_NAME,
    ATTR_NOTE,
    ATTR_QUANTITY,
    ATTR_STORE_ID,
    DOMAIN,
    SERVICE_ADD_ITEM,
    SERVICE_ADD_STORE,
    SERVICE_CREATE_LIST,
    SERVICE_DELETE_LIST,
    SERVICE_LIST_LISTS,
    SERVICE_LIST_STORES,
    SERVICE_REMOVE_STORE,
    SERVICE_RENAME_LIST,
    SERVICE_SET_ITEM_STORE,
)
from .store import ShoppingListStore


def _store(hass: HomeAssistant) -> ShoppingListStore:
    return hass.data[DOMAIN]


async def _async_add_item(call: ServiceCall) -> dict[str, Any]:
    data = _store(call.hass)
    try:
        item = await data.async_add_item(
            call.data[ATTR_LIST_ID],
            call.data[ATTR_NAME],
            store_id=call.data.get(ATTR_STORE_ID),
            quantity=call.data.get(ATTR_QUANTITY),
            note=call.data.get(ATTR_NOTE),
        )
    except KeyError as err:
        raise ServiceValidationError(str(err)) from err
    return {"item": item}


async def _async_set_item_store(call: ServiceCall) -> dict[str, Any]:
    data = _store(call.hass)
    try:
        item = await data.async_set_item_store(
            call.data[ATTR_ITEM_ID],
            call.data.get(ATTR_STORE_ID),
        )
    except KeyError as err:
        raise ServiceValidationError(str(err)) from err
    return {"item": item}


async def _async_add_store(call: ServiceCall) -> dict[str, Any]:
    data = _store(call.hass)
    store = await data.async_add_store(
        call.data[ATTR_NAME],
        icon=call.data.get(ATTR_ICON),
        color=call.data.get(ATTR_COLOR),
    )
    return {"store": store}


async def _async_list_stores(call: ServiceCall) -> dict[str, Any]:
    return {"stores": _store(call.hass).as_dict()["stores"]}


async def _async_remove_store(call: ServiceCall) -> None:
    try:
        await _store(call.hass).async_remove_store(call.data[ATTR_STORE_ID])
    except KeyError as err:
        raise ServiceValidationError(str(err)) from err


async def _async_create_list(call: ServiceCall) -> dict[str, Any]:
    data = _store(call.hass)
    try:
        entry = await data.async_create_list(
            call.data[ATTR_NAME],
            owner_user_id=call.context.user_id,
            default_store_id=call.data.get(ATTR_DEFAULT_STORE_ID),
        )
    except KeyError as err:
        raise ServiceValidationError(str(err)) from err
    return {"list": entry}


async def _async_rename_list(call: ServiceCall) -> dict[str, Any]:
    try:
        entry = await _store(call.hass).async_rename_list(
            call.data[ATTR_LIST_ID], call.data[ATTR_NAME]
        )
    except KeyError as err:
        raise ServiceValidationError(str(err)) from err
    return {"list": entry}


async def _async_delete_list(call: ServiceCall) -> None:
    try:
        await _store(call.hass).async_delete_list(call.data[ATTR_LIST_ID])
    except KeyError as err:
        raise ServiceValidationError(str(err)) from err


async def _async_list_lists(call: ServiceCall) -> dict[str, Any]:
    return {"lists": _store(call.hass).as_dict()["lists"]}


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_ITEM):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_ITEM,
        _async_add_item,
        schema=vol.Schema(
            {
                vol.Required(ATTR_LIST_ID): cv.string,
                vol.Required(ATTR_NAME): cv.string,
                vol.Optional(ATTR_STORE_ID): vol.Any(cv.string, None),
                vol.Optional(ATTR_QUANTITY): vol.Any(cv.string, None),
                vol.Optional(ATTR_NOTE): vol.Any(cv.string, None),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ITEM_STORE,
        _async_set_item_store,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ITEM_ID): cv.string,
                vol.Optional(ATTR_STORE_ID): vol.Any(cv.string, None),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_STORE,
        _async_add_store,
        schema=vol.Schema(
            {
                vol.Required(ATTR_NAME): cv.string,
                vol.Optional(ATTR_ICON): vol.Any(cv.string, None),
                vol.Optional(ATTR_COLOR): vol.Any(cv.string, None),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_STORES,
        _async_list_stores,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_STORE,
        _async_remove_store,
        schema=vol.Schema({vol.Required(ATTR_STORE_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_LIST,
        _async_create_list,
        schema=vol.Schema(
            {
                vol.Required(ATTR_NAME): cv.string,
                vol.Optional(ATTR_DEFAULT_STORE_ID): vol.Any(cv.string, None),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RENAME_LIST,
        _async_rename_list,
        schema=vol.Schema(
            {
                vol.Required(ATTR_LIST_ID): cv.string,
                vol.Required(ATTR_NAME): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_LIST,
        _async_delete_list,
        schema=vol.Schema({vol.Required(ATTR_LIST_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_LISTS,
        _async_list_lists,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
