# Shopping Lists (stores) for Home Assistant

Custom integration + Lovelace card for **multiple shopping lists** with **per-item store assignment** (e.g. potatoes → Aldi, bacon → Edeka). Filter any list by store. Data stays local in Home Assistant (`.storage/`).

> Slice 0: single-user foundation. Sharing ACL fields exist in storage (`owner_user_id`, `allowed_users`) but enforcement / share UI is Slice 1.

## Features (Slice 0)

- Multiple named lists (create / rename / delete)
- Items: add, complete, delete (via `todo` entity + services)
- Per-item `store_id` with store catalog (add / list / remove)
- One `todo` entity per list (works with HA To-do and automations)
- Minimal responsive Lovelace card: items, store badge, store filter
- Local config flow — no cloud

## Install

### HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories  
2. Add `https://github.com/MartinSchillinger/hass-shopping-list` as **Integration**  
3. Install **Shopping Lists (stores)**  
4. Restart Home Assistant  
5. Settings → Devices & services → Add integration → **Shopping Lists (stores)**

The Lovelace card is registered automatically by the integration (`/hass_shopping_list/hass-shopping-list-card.js`).

### Manual

1. Copy `custom_components/hass_shopping_list/` into your HA `config/custom_components/` directory  
2. Restart Home Assistant  
3. Add the integration via the UI (same as step 5 above)

## Example dashboard

```yaml
views:
  - title: Shopping
    path: shopping
    cards:
      - type: custom:hass-shopping-list-card
        title: Groceries
        # Optional: pin a list id from hass_shopping_list.list_lists
        # list_id: abc123
        show_completed: false
```

If `list_id` is omitted, the card uses the first available list and lets you switch in the toolbar.

You can also show the native todo entity:

```yaml
type: todo-list
entity: todo.shopping
```

Store badges only appear on the custom card (or via item `description` mirroring like `[Aldi]`).

## Services

Domain: `hass_shopping_list`

| Service | Description |
|---------|-------------|
| `add_item` | Add item (`list_id`, `name`, optional `store_id`, `quantity`, `note`) |
| `set_item_store` | Set/clear store on an item (`item_id`, `store_id`) |
| `add_store` | Add store (`name`, optional `icon`, `color`) |
| `list_stores` | Return store catalog (response-only) |
| `remove_store` | Remove store and clear it from items |
| `create_list` | Create list (`name`, optional `default_store_id`) |
| `rename_list` | Rename list |
| `delete_list` | Delete list and its items |
| `list_lists` | Return lists (response-only) |

Standard `todo.*` services work on each list entity for create / update / delete / complete.

### Examples

```yaml
service: hass_shopping_list.add_store
data:
  name: Aldi
  icon: mdi:store
```

```yaml
service: hass_shopping_list.add_item
data:
  list_id: YOUR_LIST_ID
  name: Milk
  store_id: YOUR_STORE_ID
```

```yaml
service: hass_shopping_list.set_item_store
data:
  item_id: YOUR_ITEM_UID
  store_id: YOUR_STORE_ID
```

## Data model (storage)

Persisted under `.storage/hass_shopping_list`:

- **lists** — `list_id`, `name`, `owner_user_id`, `allowed_users`, `default_store_id`, …
- **stores** — `store_id`, `name`, optional `icon` / `color`
- **items** — `uid`, `list_id`, `name`, `complete`, `store_id`, optional `quantity` / `note`

## Development

```bash
pip install -r requirements_test.txt
pytest
```

## Roadmap

- **Slice 1:** default-store UX, sharing ACL enforcement, share UI  
- Later: quantity/note polish, Assist intents, optional migration from Core Shopping List

## License

MIT (see repository license when published).
