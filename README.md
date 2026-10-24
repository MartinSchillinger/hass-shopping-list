# Shopping Lists (stores) for Home Assistant

Custom integration + Lovelace card for **multiple shopping lists** with **per-item store assignment** (e.g. potatoes → Aldi, bacon → Edeka). Filter any list by store. Data stays local in Home Assistant (`.storage/`).

> Slice 0: single-user foundation. Sharing ACL fields exist in storage (`owner_user_id`, `allowed_users`) but enforcement / share UI is Slice 1.

## Features (Slice 0)

- Multiple named lists (create / rename / delete)
- Items: add, complete, delete (via `todo` entity + services)
- Per-item `store_id` with store catalog (add / list / remove)
- One `todo` entity per list (works with HA To-do and automations)
- Responsive Lovelace card (phone-first): items, store badge, store filter, store picker on add, store management
- Local config flow — no cloud

## Install

### HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories  
2. Add `https://github.com/MartinSchillinger/hass-shopping-list` as **Integration**  
3. Install **Shopping Lists (stores)**  
4. Restart Home Assistant  
5. Settings → Devices & services → Add integration → **Shopping Lists (stores)**

The Lovelace card is registered automatically by the integration (`/hass_shopping_list/hass-shopping-list-card.js?v=…`). In **storage mode** (default) it is added as a Lovelace module resource (same path HACS uses). In **YAML mode** it falls back to `frontend.add_extra_js_url`. No manual resource entry needed for storage mode.

### Manual

1. Copy `custom_components/hass_shopping_list/` into your HA `config/custom_components/` directory  
2. Restart Home Assistant  
3. Add the integration via the UI (same as step 5 above)

## Lovelace card — add to a dashboard

Card type: `custom:hass-shopping-list-card`

The integration serves the card at `/hass_shopping_list/hass-shopping-list-card.js` and auto-registers it so Lovelace **awaits** the module before rendering (avoids “Custom element doesn't exist” after restart). The script pushes an entry to `window.customCards` so it appears under **Add card → By card / Nach Karte**.

### Via UI (card picker)

1. Integration must be added (Settings → Devices & services → **Shopping Lists (stores)**), then **restart Home Assistant** once after install/update  
2. Hard-reload the browser (Ctrl+Shift+R / Cmd+Shift+R) so the new JS loads  
3. Dashboard → **Edit** → **Add card** → **By card** / **Nach Karte**  
4. Search **shop**, **Einkauf**, **Laden**, or **hass-shopping-list** — pick **Einkaufsliste / Shopping List …**  
5. Optionally set `title`, `list_id`, `show_completed` → Save  

### Card missing / “Custom element doesn't exist” (recovery)

1. Confirm `custom_components/hass_shopping_list/www/hass-shopping-list-card.js` is present on the HA host (update/pull the integration if not)  
2. **Restart Home Assistant** (Settings → System → Restart)  
3. **Hard-reload** the browser or Companion WebView (Ctrl+Shift+R); on iOS Companion: close the app fully and reopen  
4. Open `http(s)://YOUR-HA/hass_shopping_list/hass-shopping-list-card.js` — expect **HTTP 200** and JavaScript source (not 404)  
5. Settings → Dashboards → **Resources** — look for `/hass_shopping_list/hass-shopping-list-card.js?v=…` type **JavaScript Module**. If missing (YAML mode), add it manually, then hard-reload again  
6. DevTools console: `customElements.get("hass-shopping-list-card")` should be a function; `window.customCards` should list `type: "hass-shopping-list-card"`

If search still finds nothing after that: use Manual YAML (below).

### Via YAML (Manual)

```yaml
views:
  - title: Einkaufen
    path: shopping
    cards:
      - type: custom:hass-shopping-list-card
        title: Einkaufsliste
        # Optional: pin a list id from hass_shopping_list.list_lists
        # list_id: abc123
        show_completed: false
```

If `list_id` is omitted, the card uses the first available list and lets you switch in the toolbar.

### Card usage (short)

| On the card | What it does |
|-------------|--------------|
| List dropdown | Switch shopping list |
| **All stores** / store filter | Show only items for one store |
| Article + **Laden** dropdown + Hinzufügen | Add item with store assignment |
| Checkbox / ✕ | Check off or remove an item |
| Per-item store dropdown | Change store on an existing item (`set_item_store`) |
| **Läden verwalten** | Add stores; delete with confirmation (`add_store` / `remove_store`) |

Phone-first layout: add form stacks vertically on narrow screens; store management is collapsed by default to keep the list reachable.

You can also show the native todo entity (no store UI there):

```yaml
type: todo-list
entity: todo.shopping
```

Store badges and store management only appear on the custom card (todo `description` may mirror `[Aldi]` for readability).
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

GPL-3.0-or-later (see `LICENSE`).
