# Shopping Lists (stores) for Home Assistant

Custom integration + Lovelace cards for **multiple shopping lists** with **per-item store assignment** (e.g. potatoes → Aldi, bacon → Edeka). Filter any list by store. Data stays local in Home Assistant (`.storage/`).

> Slice 0: single-user foundation. Sharing ACL fields exist in storage (`owner_user_id`, `allowed_users`) but enforcement / share UI is Slice 1.

## Features (Slice 0)

- Multiple named lists (create / rename / delete)
- Items: add, complete, delete (via `todo` entity + services)
- Per-item `store_id` with store catalog (add / list / remove)
- One `todo` entity per list (works with HA To-do and automations)
- Two Lovelace cards (same JS module): shopping list + store management
- Local config flow — no cloud

## Install

### HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories  
2. Add `https://github.com/MartinSchillinger/hass-shopping-list` as **Integration**  
3. Install **Shopping Lists (stores)**  
4. Restart Home Assistant  
5. Settings → Devices & services → Add integration → **Shopping Lists (stores)**

The Lovelace cards are registered automatically by the integration (`/hass_shopping_list/hass-shopping-list-card.js?v=…`). In **storage mode** (default) it is added as a Lovelace module resource (same path HACS uses). In **YAML mode** it falls back to `frontend.add_extra_js_url`. No manual resource entry needed for storage mode.

### Manual

1. Copy `custom_components/hass_shopping_list/` into your HA `config/custom_components/` directory  
2. Restart Home Assistant  
3. Add the integration via the UI (same as step 5 above)

## Lovelace cards — add to a dashboard

Both cards ship in one module. Types:

| Card type | Purpose |
|-----------|---------|
| `custom:hass-shopping-list-card` | Shopping list: add items, filter by store, check off / delete, tap item to edit |
| `custom:hass-shopping-list-stores-card` | Manage stores (Läden): add / delete |

The integration serves the script at `/hass_shopping_list/hass-shopping-list-card.js` and auto-registers it so Lovelace **awaits** the module before rendering (avoids “Custom element doesn't exist” after restart). The script pushes entries to `window.customCards` so both appear under **Add card → By card / Nach Karte**.

### Via UI (card picker)

1. Integration must be added (Settings → Devices & services → **Shopping Lists (stores)**), then **restart Home Assistant** once after install/update  
2. Hard-reload the browser (Ctrl+Shift+R / Cmd+Shift+R) so the new JS loads  
3. Dashboard → **Edit** → **Add card** → **By card** / **Nach Karte**  
4. Search:
   - List card: **shop**, **Einkauf**, **Laden**, or **hass-shopping-list**
   - Stores card: **Läden**, **Stores**, or **hass-shopping-list**
5. Optionally set `title` / `list_id` / `show_completed` → Save  

### Card missing / “Custom element doesn't exist” (recovery)

1. Confirm `custom_components/hass_shopping_list/www/hass-shopping-list-card.js` is present on the HA host (update/pull the integration if not)  
2. **Restart Home Assistant** (Settings → System → Restart)  
3. **Hard-reload** the browser or Companion WebView (Ctrl+Shift+R); on iOS Companion: close the app fully and reopen  
4. Open `http(s)://YOUR-HA/hass_shopping_list/hass-shopping-list-card.js` — expect **HTTP 200** and JavaScript source (not 404)  
5. Settings → Dashboards → **Resources** — look for `/hass_shopping_list/hass-shopping-list-card.js?v=…` type **JavaScript Module**. If missing (YAML mode), add it manually, then hard-reload again  
6. DevTools console: `customElements.get("hass-shopping-list-card")` and `customElements.get("hass-shopping-list-stores-card")` should be functions; `window.customCards` should list both types

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
      - type: custom:hass-shopping-list-stores-card
        title: Läden
```

If `list_id` is omitted on the list card, it uses the first available list and lets you switch in the toolbar.

### Shopping list card usage

| On the card | What it does |
|-------------|--------------|
| List dropdown | Switch shopping list |
| **All stores** / store filter | Show only items for one store |
| Article + **Laden** dropdown + Hinzufügen | Add item with store assignment |
| Checkbox / ✕ | Check off or remove an item |
| Tap item name / badge | Open a small modal to edit name and store (Save / Cancel) |

Store badges stay visible on each row. Store catalog management lives on the separate stores card.

### Stores card usage

| On the card | What it does |
|-------------|--------------|
| Name + **Laden anlegen** | Create a store (`add_store`) |
| ✕ on a store row | Delete with confirmation (`remove_store`) |

Phone-first layout: the list add form stacks vertically on narrow screens.

You can also show the native todo entity (no store UI there):

```yaml
type: todo-list
entity: todo.shopping
```

Store badges and store management only appear on the custom cards (todo `description` may mirror `[Aldi]` for readability).
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

## Releases

Every push/merge to `main` runs a free **GitHub Actions** workflow (`.github/workflows/release.yml`) that:

1. Picks the next **SemVer** and creates tag `vX.Y.Z`
2. Opens a **GitHub Release** with auto-generated notes (commits since the previous tag)
3. Writes that version into `custom_components/hass_shopping_list/manifest.json` (the Lovelace card `?v=` cache-buster reads the same field)

**First release:** if no `v*` tags exist yet, the version is **`0.1.0`**.

**Bump rules** (conventional commits, with a safe fallback):

| Commits since last tag | Bump |
|------------------------|------|
| `BREAKING CHANGE:` footer or `type!:` / `type(scope)!:` | major |
| at least one `feat:` / `feat(scope):` | minor |
| anything else (`fix:`, `chore:`, plain English, merge commits, …) | **patch** (default) |

Examples: `feat: add share UI` → minor; `fix: restore input focus` → patch; unclear history → patch.

No paid runners or third-party SaaS — only `GITHUB_TOKEN`, `actions/checkout`, and `softprops/action-gh-release`.

## Roadmap

- **Slice 1:** default-store UX, sharing ACL enforcement, share UI  
- Later: quantity/note polish, Assist intents, optional migration from Core Shopping List

## License

GPL-3.0-or-later (see `LICENSE`).
