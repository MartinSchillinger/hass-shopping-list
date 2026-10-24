"""The hass_shopping_list integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_SCRIPT_URL
from .services import async_register_services
from .store import ShoppingListStore
from .websocket_api import async_register_websocket_handlers

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up hass_shopping_list from a config entry."""
    store = ShoppingListStore(hass)
    await store.async_load()
    await store.async_ensure_default_list(owner_user_id=None)

    hass.data[DOMAIN] = store
    entry.runtime_data = store

    async_register_services(hass)
    async_register_websocket_handlers(hass)
    await _async_register_frontend(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.pop(DOMAIN, None)
    return unload_ok


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and auto-load the Lovelace custom card."""
    static_path_key = f"{DOMAIN}_static_registered"
    if hass.data.get(static_path_key):
        return

    www_dir = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                f"/{DOMAIN}",
                str(www_dir),
                cache_headers=False,
            )
        ]
    )
    frontend.add_extra_js_url(hass, FRONTEND_SCRIPT_URL)
    hass.data[static_path_key] = True
    _LOGGER.debug("Registered frontend card at %s", FRONTEND_SCRIPT_URL)
