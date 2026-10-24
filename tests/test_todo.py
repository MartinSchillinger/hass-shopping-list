"""Todo entity tests — one entity per list with CRUD/complete."""

from __future__ import annotations

import pytest
from homeassistant.components.todo import TodoItemStatus
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_shopping_list.const import DOMAIN


def _todo_entities(hass: HomeAssistant) -> list[str]:
    return sorted(
        eid for eid in hass.states.async_entity_ids("todo") if eid.startswith("todo.")
    )


def _entity_for_list(hass: HomeAssistant, list_id: str) -> str:
    for eid in _todo_entities(hass):
        state = hass.states.get(eid)
        if state and state.attributes.get("list_id") == list_id:
            return eid
    raise AssertionError(f"No todo entity for list_id={list_id}")


@pytest.mark.asyncio
async def test_todo_entity_created_and_removed_with_list(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Creating/deleting a list adds/removes its todo entity."""
    await hass.async_block_till_done()
    before = set(_todo_entities(hass))
    assert before, "default Shopping list should expose a todo entity"

    created = await hass.services.async_call(
        DOMAIN,
        "create_list",
        {"name": "Hardware"},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    list_id = created["list"]["list_id"]
    after_create = set(_todo_entities(hass))
    assert len(after_create) == len(before) + 1

    entity_id = _entity_for_list(hass, list_id)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Hardware" or "Hardware" in (state.attributes.get("friendly_name") or state.name)

    await hass.services.async_call(
        DOMAIN,
        "delete_list",
        {"list_id": list_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entity_id not in _todo_entities(hass)


@pytest.mark.asyncio
async def test_todo_rename_updates_entity_name(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Renaming a list updates the todo entity display name."""
    created = await hass.services.async_call(
        DOMAIN,
        "create_list",
        {"name": "Old Name"},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    list_id = created["list"]["list_id"]
    entity_id = _entity_for_list(hass, list_id)

    await hass.services.async_call(
        DOMAIN,
        "rename_list",
        {"list_id": list_id, "name": "New Name"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    friendly = state.attributes.get("friendly_name") or state.name
    assert "New Name" in friendly


@pytest.mark.asyncio
async def test_todo_create_update_complete_delete_items(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Todo platform create / update (complete) / delete works per list."""
    lists = await hass.services.async_call(
        DOMAIN, "list_lists", {}, blocking=True, return_response=True
    )
    list_id = next(lst["list_id"] for lst in lists["lists"] if lst["name"] == "Shopping")
    entity_id = _entity_for_list(hass, list_id)

    await hass.services.async_call(
        "todo",
        "add_item",
        {"entity_id": entity_id, "item": "Bread"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    shopping_items = state.attributes["shopping_items"]
    assert any(i["name"] == "Bread" and not i["complete"] for i in shopping_items)
    item = next(i for i in shopping_items if i["name"] == "Bread")

    await hass.services.async_call(
        "todo",
        "update_item",
        {
            "entity_id": entity_id,
            "item": item["uid"],
            "status": TodoItemStatus.COMPLETED,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    item = next(i for i in state.attributes["shopping_items"] if i["uid"] == item["uid"])
    assert item["complete"] is True

    # Store badge metadata mirrored for the custom card
    store = await hass.services.async_call(
        DOMAIN,
        "add_store",
        {"name": "Aldi"},
        blocking=True,
        return_response=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "set_item_store",
        {"item_id": item["uid"], "store_id": store["store"]["store_id"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    item = next(i for i in state.attributes["shopping_items"] if i["uid"] == item["uid"])
    assert item["store_id"] == store["store"]["store_id"]
    assert item["store_name"] == "Aldi"

    await hass.services.async_call(
        "todo",
        "remove_item",
        {"entity_id": entity_id, "item": [item["uid"]]},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert all(i["uid"] != item["uid"] for i in state.attributes["shopping_items"])
