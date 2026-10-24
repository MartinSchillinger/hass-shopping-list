"""Shared fixtures for hass_shopping_list tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_shopping_list.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in tests."""
    return None


@pytest.fixture
async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration and return the config entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="Shopping Lists", data={})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hass_shopping_list._async_register_frontend",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
