"""The hass_shopping_list integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    FRONTEND_SCRIPT_PATH,
    INTEGRATION_VERSION,
    versioned_frontend_script_url,
)
from .services import async_register_services
from .store import ShoppingListStore
from .websocket_api import async_register_websocket_handlers

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TODO]

# Config-entry only; async_setup still runs so the card can register once app-wide.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_STATIC_PATH_KEY = f"{DOMAIN}_static_registered"
_FRONTEND_RESOURCE_KEY = f"{DOMAIN}_frontend_resource_registered"


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the integration domain and register the Lovelace card."""
    try:
        await _async_register_frontend(hass)
    except Exception:  # noqa: BLE001 — card wiring must not block domain setup
        _LOGGER.exception(
            "Failed to register the Lovelace shopping card during async_setup"
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up hass_shopping_list from a config entry."""
    store = ShoppingListStore(hass)
    await store.async_load()
    await store.async_ensure_default_list(owner_user_id=None)

    hass.data[DOMAIN] = store
    entry.runtime_data = store

    async_register_services(hass)
    async_register_websocket_handlers(hass)
    # Idempotent: also covers reload / older paths that skip domain async_setup.
    await _async_register_frontend(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.pop(DOMAIN, None)
    return unload_ok


def _lovelace_storage_resources(hass: HomeAssistant) -> Any | None:
    """Return Lovelace storage-mode resources, or None if unavailable / YAML mode.

    HA 2025.2+ stores a LovelaceData dataclass on hass.data['lovelace'];
    older cores used a dict. Storage collections expose ``store``; YAML mode
    does not support create/update.
    """
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None

    resources = getattr(lovelace, "resources", None)
    if resources is None and isinstance(lovelace, dict):
        resources = lovelace.get("resources")
    if resources is None:
        return None

    # YAML ResourceYAMLCollection has no store (or store is None).
    if getattr(resources, "store", None) is None:
        return None
    if not hasattr(resources, "async_create_item"):
        return None
    return resources


async def _async_register_lovelace_resource(
    hass: HomeAssistant, card_url: str
) -> bool:
    """Register or update the card as a Lovelace module resource.

    Lovelace awaits dashboard resources before rendering cards, which avoids
    the cold-start race of ``frontend.add_extra_js_url`` ("Custom element
    doesn't exist"). Returns True when a storage resource was created/updated.
    """
    resources = _lovelace_storage_resources(hass)
    if resources is None:
        return False

    # Ensure collection is loaded before create/update so we never overwrite
    # existing resources with a single new item (HA < eager-load fix).
    if not getattr(resources, "loaded", True):
        if hasattr(resources, "async_load"):
            await resources.async_load()
        elif hasattr(resources, "async_get_info"):
            await resources.async_get_info()

    for item in resources.async_items():
        existing = str(item.get("url", ""))
        if existing.split("?", 1)[0] != FRONTEND_SCRIPT_PATH:
            continue
        if existing != card_url:
            await resources.async_update_item(
                item["id"], {"res_type": "module", "url": card_url}
            )
            _LOGGER.info("Updated Lovelace card resource to %s", card_url)
        return True

    await resources.async_create_item({"res_type": "module", "url": card_url})
    _LOGGER.info("Registered Lovelace card resource at %s", card_url)
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card JS and make Lovelace load it reliably.

    1. Static path so ``/hass_shopping_list/hass-shopping-list-card.js`` is served.
    2. Storage-mode Lovelace resource (HACS-style) — awaited by the dashboard.
    3. Fallback: ``frontend.add_extra_js_url`` for YAML-mode / missing Lovelace.

    If an early call only managed the extra-js fallback, a later call may still
    upgrade to a proper Lovelace resource once ``hass.data['lovelace']`` exists.
    """
    if not hass.data.get(_STATIC_PATH_KEY):
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
        hass.data[_STATIC_PATH_KEY] = True

    if hass.data.get(_FRONTEND_RESOURCE_KEY) == "lovelace":
        return

    card_url = versioned_frontend_script_url(INTEGRATION_VERSION)
    try:
        registered = await _async_register_lovelace_resource(hass, card_url)
    except Exception:  # noqa: BLE001 — never fail setup over card wiring
        _LOGGER.warning(
            "Could not register Lovelace resource for the shopping card; "
            "falling back to frontend.add_extra_js_url",
            exc_info=True,
        )
        registered = False

    if registered:
        hass.data[_FRONTEND_RESOURCE_KEY] = "lovelace"
        return

    if hass.data.get(_FRONTEND_RESOURCE_KEY) == "extra_js":
        return

    # Prefer the public helper; fall back to setdefault if frontend data
    # keys are not initialized yet (partial setups / tests).
    try:
        frontend.add_extra_js_url(hass, card_url)
    except KeyError:
        hass.data.setdefault("frontend_extra_module_url", set()).add(card_url)
    hass.data[_FRONTEND_RESOURCE_KEY] = "extra_js"
    _LOGGER.debug(
        "Registered frontend card module via add_extra_js_url at %s", card_url
    )
