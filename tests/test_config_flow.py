"""Config flow tests for hass_shopping_list."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_shopping_list.const import DOMAIN


@pytest.fixture
def skip_frontend_registration():
    """Avoid registering the card JS during config-flow-only tests."""
    with patch(
        "custom_components.hass_shopping_list._async_register_frontend",
        return_value=None,
    ):
        yield


@pytest.mark.asyncio
async def test_config_flow_user_form(
    hass: HomeAssistant, skip_frontend_registration: None
) -> None:
    """User step shows a form with no cloud fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    # Local-only: empty schema (confirm-style), no cloud credentials
    assert result.get("data_schema") is None or len(result["data_schema"].schema) == 0


@pytest.mark.asyncio
async def test_config_flow_user_creates_entry(
    hass: HomeAssistant, skip_frontend_registration: None
) -> None:
    """Submitting the user step creates a single local config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "custom_components.hass_shopping_list.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Shopping Lists"
    assert result2["data"] == {}
    assert result2["result"].unique_id == DOMAIN
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.asyncio
async def test_config_flow_abort_if_already_configured(
    hass: HomeAssistant, skip_frontend_registration: None
) -> None:
    """Second setup aborts — only one integration instance."""
    entry = MockConfigEntry(domain=DOMAIN, title="Shopping Lists", data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
