/**
 * Lovelace card for hass_shopping_list — phone-first main control surface.
 * Items, store badges/filter, store picker on add, and store management.
 */
class HassShoppingListCard extends HTMLElement {
  // No visual editor yet — HA falls back to the YAML editor in the picker.
  static getStubConfig() {
    return { list_id: "", title: "Einkaufsliste", show_completed: false };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = { show_completed: false, ...config };
    this._filterStoreId = this._filterStoreId || "";
    this._draftName = this._draftName || "";
    this._draftStoreId = this._draftStoreId || "";
    this._draftStoreName = this._draftStoreName || "";
    this._storesOpen =
      this._storesOpen === undefined ? false : this._storesOpen;
    this._busy = false;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._subscribed) {
      this._subscribed = true;
      this._unsub = hass.connection.subscribeEvents(
        () => this._load(),
        "hass_shopping_list_updated"
      );
      this._load();
    } else {
      this._render();
    }
  }

  getCardSize() {
    return 6;
  }

  disconnectedCallback() {
    if (this._unsub) {
      Promise.resolve(this._unsub).then((unsub) => unsub && unsub());
      this._unsub = null;
      this._subscribed = false;
    }
  }

  async _load() {
    if (!this._hass) return;
    try {
      this._data = await this._hass.connection.sendMessagePromise({
        type: "hass_shopping_list/get_data",
      });
      if (!this._config.list_id && this._data.lists?.length) {
        this._config = { ...this._config, list_id: this._data.lists[0].list_id };
      }
      this._ensureDraftStore();
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._render();
  }

  _list() {
    const listId = this._config?.list_id;
    return (this._data?.lists || []).find((l) => l.list_id === listId) || null;
  }

  _ensureDraftStore() {
    const stores = this._data?.stores || [];
    if (this._draftStoreId && stores.some((s) => s.store_id === this._draftStoreId)) {
      return;
    }
    const list = this._list();
    const defaultId = list?.default_store_id || "";
    if (defaultId && stores.some((s) => s.store_id === defaultId)) {
      this._draftStoreId = defaultId;
    } else if (!this._draftStoreId) {
      this._draftStoreId = "";
    }
  }

  _items() {
    const listId = this._config?.list_id;
    let items = (this._data?.items || []).filter((i) => i.list_id === listId);
    if (!this._config.show_completed) {
      items = items.filter((i) => !i.complete);
    }
    if (this._filterStoreId) {
      items = items.filter((i) => (i.store_id || "") === this._filterStoreId);
    }
    return items;
  }

  _storeMap() {
    const map = {};
    for (const s of this._data?.stores || []) {
      map[s.store_id] = s;
    }
    return map;
  }

  async _withBusy(fn) {
    if (this._busy) return;
    this._busy = true;
    this._render();
    try {
      await fn();
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err);
    } finally {
      this._busy = false;
      await this._load();
    }
  }

  async _addItem() {
    const name = (this._draftName || "").trim();
    if (!name || !this._config.list_id) return;
    await this._withBusy(async () => {
      const data = {
        list_id: this._config.list_id,
        name,
      };
      if (this._draftStoreId) {
        data.store_id = this._draftStoreId;
      }
      await this._hass.callService("hass_shopping_list", "add_item", data);
      this._draftName = "";
    });
  }

  async _addStore() {
    const name = (this._draftStoreName || "").trim();
    if (!name) return;
    const createdName = name;
    await this._withBusy(async () => {
      await this._hass.callService("hass_shopping_list", "add_store", {
        name: createdName,
      });
      this._draftStoreName = "";
      // Prefer the newly created store for the next item add.
      this._pendingSelectStoreName = createdName;
    });
    if (this._pendingSelectStoreName) {
      const created = (this._data?.stores || []).find(
        (s) => s.name === this._pendingSelectStoreName
      );
      if (created) this._draftStoreId = created.store_id;
      this._pendingSelectStoreName = null;
      this._render();
    }
  }

  async _removeStore(storeId) {
    if (!storeId) return;
    const store = this._storeMap()[storeId];
    const label = store?.name || storeId;
    if (!window.confirm(`Laden „${label}“ wirklich löschen?`)) return;
    await this._withBusy(async () => {
      await this._hass.callService("hass_shopping_list", "remove_store", {
        store_id: storeId,
      });
      if (this._draftStoreId === storeId) this._draftStoreId = "";
      if (this._filterStoreId === storeId) this._filterStoreId = "";
    });
  }

  async _setItemStore(item, storeId) {
    await this._withBusy(async () => {
      await this._hass.callService("hass_shopping_list", "set_item_store", {
        item_id: item.uid,
        store_id: storeId || null,
      });
    });
  }

  async _toggle(item) {
    const entityId = this._todoEntityId();
    if (!entityId) {
      this._error = "Keine Todo-Entity für diese Liste gefunden.";
      this._render();
      return;
    }
    await this._withBusy(async () => {
      await this._hass.callService("todo", "update_item", {
        entity_id: entityId,
        item: item.uid,
        status: item.complete ? "needs_action" : "completed",
      });
    });
  }

  async _remove(item) {
    const entityId = this._todoEntityId();
    if (!entityId) {
      this._error = "Keine Todo-Entity für diese Liste gefunden.";
      this._render();
      return;
    }
    await this._withBusy(async () => {
      await this._hass.callService("todo", "remove_item", {
        entity_id: entityId,
        item: [item.uid],
      });
    });
  }

  _todoEntityId() {
    if (this._config.entity) return this._config.entity;
    const states = this._hass?.states || {};
    for (const [eid, state] of Object.entries(states)) {
      if (
        eid.startsWith("todo.") &&
        state.attributes?.list_id === this._config.list_id
      ) {
        return eid;
      }
    }
    return null;
  }

  _storeOptionsHtml(selectedId, { includeEmpty = true, emptyLabel = "Kein Laden" } = {}) {
    const stores = this._data?.stores || [];
    const empty = includeEmpty
      ? `<option value="">${this._esc(emptyLabel)}</option>`
      : "";
    return (
      empty +
      stores
        .map(
          (s) =>
            `<option value="${this._esc(s.store_id)}" ${
              s.store_id === selectedId ? "selected" : ""
            }>${this._esc(s.name)}</option>`
        )
        .join("")
    );
  }

  _render() {
    if (!this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    const list = this._list();
    const stores = this._data?.stores || [];
    const storeMap = this._storeMap();
    const items = this._items();
    const title = this._config.title || list?.name || "Einkaufsliste";
    const busy = this._busy ? "is-busy" : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--ha-font-family-body, Roboto, Noto Sans, sans-serif);
          color: var(--primary-text-color);
          -webkit-tap-highlight-color: transparent;
        }
        .card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, none);
          border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color));
          padding: 12px 12px 14px;
        }
        .card.is-busy { opacity: 0.72; pointer-events: none; }
        h2 {
          margin: 0 0 12px;
          font-size: 1.2rem;
          font-weight: 500;
          letter-spacing: 0.01em;
        }
        .section {
          margin-top: 12px;
        }
        .section-title {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          margin: 0 0 8px;
          font-size: 0.8rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--secondary-text-color);
        }
        .toolbar {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 8px;
        }
        .toolbar.stack-phone {
          flex-direction: column;
        }
        .toolbar.stack-phone > * {
          width: 100%;
          flex: none;
        }
        .add-row {
          display: grid;
          grid-template-columns: 1fr;
          gap: 8px;
          margin-bottom: 4px;
        }
        .add-actions {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 8px;
        }
        select, input[type="text"] {
          box-sizing: border-box;
          width: 100%;
          min-width: 0;
          min-height: 44px;
          padding: 10px 12px;
          border-radius: 10px;
          border: 1px solid var(--divider-color);
          background: var(--input-fill-color, var(--secondary-background-color, transparent));
          color: inherit;
          font: inherit;
          font-size: 1rem;
        }
        button {
          min-height: 44px;
          padding: 10px 14px;
          border-radius: 10px;
          border: none;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
          font: inherit;
          font-size: 0.95rem;
          font-weight: 500;
          cursor: pointer;
          white-space: nowrap;
        }
        button:active { filter: brightness(0.95); }
        button.ghost {
          background: transparent;
          color: var(--primary-color);
          border: 1px solid var(--divider-color);
        }
        button.linkish {
          min-height: auto;
          padding: 4px 6px;
          background: transparent;
          color: var(--primary-color);
          border: none;
          font-size: 0.8rem;
          font-weight: 600;
          text-transform: none;
          letter-spacing: 0;
        }
        button.icon {
          min-height: 36px;
          min-width: 36px;
          padding: 6px;
          flex: 0 0 auto;
        }
        button.danger {
          color: var(--error-color, #c62828);
          border-color: color-mix(in srgb, var(--error-color, #c62828) 35%, var(--divider-color));
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
        }
        li.item {
          display: grid;
          grid-template-columns: auto 1fr auto;
          grid-template-areas:
            "check name remove"
            "check store remove";
          align-items: center;
          column-gap: 10px;
          row-gap: 4px;
          padding: 10px 0;
          border-bottom: 1px solid var(--divider-color);
        }
        li.item:last-child { border-bottom: none; }
        .check { grid-area: check; }
        .name {
          grid-area: name;
          min-width: 0;
          word-break: break-word;
          font-size: 1rem;
          line-height: 1.35;
        }
        .name.done {
          text-decoration: line-through;
          opacity: 0.6;
        }
        .item-store {
          grid-area: store;
          display: flex;
          align-items: center;
          gap: 6px;
          min-width: 0;
        }
        .item-store select {
          min-height: 34px;
          padding: 4px 8px;
          font-size: 0.85rem;
          border-radius: 8px;
        }
        .remove { grid-area: remove; align-self: start; }
        .badge {
          flex: 0 0 auto;
          font-size: 0.75rem;
          line-height: 1.2;
          padding: 3px 8px;
          border-radius: 999px;
          background: var(--secondary-background-color, #eee);
          color: var(--secondary-text-color);
          max-width: 42%;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .store-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .store-row {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 10px;
          border-radius: 10px;
          background: var(--secondary-background-color, rgba(0,0,0,0.04));
        }
        .store-row .label {
          flex: 1;
          min-width: 0;
          word-break: break-word;
          font-size: 0.95rem;
        }
        .stores-panel[hidden] { display: none !important; }
        .empty, .error, .hint {
          opacity: 0.75;
          padding: 6px 0;
          font-size: 0.9rem;
          line-height: 1.4;
        }
        .error { color: var(--error-color, #c00); opacity: 1; }
        input[type="checkbox"] {
          width: 22px;
          height: 22px;
          accent-color: var(--primary-color);
        }
        @media (min-width: 480px) {
          .card { padding: 14px 16px 16px; }
          .toolbar.stack-phone { flex-direction: row; }
          .toolbar.stack-phone > * { width: auto; flex: 1 1 140px; }
          .add-row {
            grid-template-columns: minmax(0, 1.4fr) minmax(120px, 0.9fr) auto;
          }
          .add-actions { display: contents; }
          li.item {
            grid-template-columns: auto 1fr minmax(120px, 0.7fr) auto;
            grid-template-areas: "check name store remove";
          }
        }
        @media (min-width: 600px) {
          .card { padding: 16px 18px 18px; }
          h2 { font-size: 1.3rem; }
        }
      </style>
      <div class="card ${busy}">
        <h2>${this._esc(title)}</h2>
        ${
          this._error
            ? `<div class="error">${this._esc(this._error)}</div>`
            : ""
        }
        <div class="toolbar stack-phone">
          <select id="listSelect" aria-label="Liste">
            ${(this._data?.lists || [])
              .map(
                (l) =>
                  `<option value="${this._esc(l.list_id)}" ${
                    l.list_id === this._config.list_id ? "selected" : ""
                  }>${this._esc(l.name)}</option>`
              )
              .join("")}
          </select>
          <select id="filterStore" aria-label="Nach Laden filtern">
            <option value="">All stores</option>
            ${stores
              .map(
                (s) =>
                  `<option value="${this._esc(s.store_id)}" ${
                    s.store_id === this._filterStoreId ? "selected" : ""
                  }>${this._esc(s.name)}</option>`
              )
              .join("")}
          </select>
        </div>

        <div class="section">
          <div class="section-title">Artikel hinzufügen</div>
          <div class="add-row">
            <input id="newName" type="text" placeholder="Artikel…" value="${this._esc(
              this._draftName || ""
            )}" autocomplete="off" enterkeyhint="done" />
            <div class="add-actions">
              <select id="newStore" aria-label="Laden wählen">
                ${this._storeOptionsHtml(this._draftStoreId, {
                  emptyLabel: "Kein Laden",
                })}
              </select>
              <button id="addBtn" type="button">Hinzufügen</button>
            </div>
          </div>
          ${
            stores.length === 0
              ? `<div class="hint">Noch keine Läden — unten einen anlegen, dann beim Hinzufügen auswählen.</div>`
              : ""
          }
        </div>

        <div class="section">
          <div class="section-title">
            <span>Liste</span>
          </div>
          ${
            items.length === 0
              ? `<div class="empty">Keine Artikel${
                  this._filterStoreId ? " für diesen Laden" : ""
                }.</div>`
              : `<ul>
              ${items
                .map((item) => {
                  const store = item.store_id ? storeMap[item.store_id] : null;
                  const badgeStyle =
                    store?.color
                      ? ` style="border-color:${this._esc(
                          store.color
                        )}; box-shadow: inset 3px 0 0 ${this._esc(store.color)}"`
                      : "";
                  return `<li class="item" data-uid="${this._esc(item.uid)}">
                    <input type="checkbox" class="check toggle" ${
                      item.complete ? "checked" : ""
                    } aria-label="Erledigt" />
                    <span class="name ${item.complete ? "done" : ""}">${this._esc(
                      item.name
                    )}${
                      store
                        ? ` <span class="badge" style="${
                            store.color
                              ? `background:${this._esc(store.color)};color:#fff;`
                              : ""
                          }">${this._esc(store.name)}</span>`
                        : ""
                    }</span>
                    <div class="item-store">
                      <select class="itemStore" aria-label="Laden für Artikel"${badgeStyle}>
                        ${this._storeOptionsHtml(item.store_id || "", {
                          emptyLabel: "Kein Laden",
                        })}
                      </select>
                    </div>
                    <button type="button" class="ghost icon remove" aria-label="Entfernen">✕</button>
                  </li>`;
                })
                .join("")}
            </ul>`
          }
        </div>

        <div class="section">
          <div class="section-title">
            <span>Läden verwalten</span>
            <button type="button" class="linkish" id="toggleStores" aria-expanded="${
              this._storesOpen ? "true" : "false"
            }">${this._storesOpen ? "Ausblenden" : "Anzeigen"}</button>
          </div>
          <div class="stores-panel" id="storesPanel" ${
            this._storesOpen ? "" : "hidden"
          }>
            <div class="toolbar">
              <input id="newStoreName" type="text" placeholder="Neuer Laden (z. B. Aldi)" value="${this._esc(
                this._draftStoreName || ""
              )}" autocomplete="off" enterkeyhint="done" />
              <button id="addStoreBtn" type="button">Laden anlegen</button>
            </div>
            ${
              stores.length === 0
                ? `<div class="empty">Noch keine Läden angelegt.</div>`
                : `<div class="store-list">
                ${stores
                  .map(
                    (s) => `<div class="store-row" data-store-id="${this._esc(
                      s.store_id
                    )}">
                    <span class="badge" style="${
                      s.color
                        ? `background:${this._esc(s.color)};color:#fff;`
                        : ""
                    }">${this._esc(s.name)}</span>
                    <span class="label">${this._esc(s.name)}</span>
                    <button type="button" class="ghost danger icon store-remove" aria-label="Laden löschen">✕</button>
                  </div>`
                  )
                  .join("")}
              </div>`
            }
          </div>
        </div>
      </div>
    `;

    this._bindEvents(items);
  }

  _bindEvents(items) {
    const root = this.shadowRoot;
    const listSelect = root.getElementById("listSelect");
    if (listSelect) {
      listSelect.addEventListener("change", (ev) => {
        this._config = { ...this._config, list_id: ev.target.value };
        this._draftStoreId = "";
        this._ensureDraftStore();
        this._render();
      });
    }
    const filterStore = root.getElementById("filterStore");
    if (filterStore) {
      filterStore.addEventListener("change", (ev) => {
        this._filterStoreId = ev.target.value;
        this._render();
      });
    }
    const newName = root.getElementById("newName");
    if (newName) {
      newName.addEventListener("input", (ev) => {
        this._draftName = ev.target.value;
      });
      newName.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") this._addItem();
      });
    }
    const newStore = root.getElementById("newStore");
    if (newStore) {
      newStore.addEventListener("change", (ev) => {
        this._draftStoreId = ev.target.value;
      });
    }
    const addBtn = root.getElementById("addBtn");
    if (addBtn) addBtn.addEventListener("click", () => this._addItem());

    const toggleStores = root.getElementById("toggleStores");
    if (toggleStores) {
      toggleStores.addEventListener("click", () => {
        this._storesOpen = !this._storesOpen;
        this._render();
      });
    }
    const newStoreName = root.getElementById("newStoreName");
    if (newStoreName) {
      newStoreName.addEventListener("input", (ev) => {
        this._draftStoreName = ev.target.value;
      });
      newStoreName.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") this._addStore();
      });
    }
    const addStoreBtn = root.getElementById("addStoreBtn");
    if (addStoreBtn) {
      addStoreBtn.addEventListener("click", () => this._addStore());
    }
    root.querySelectorAll(".store-row").forEach((row) => {
      const storeId = row.getAttribute("data-store-id");
      row.querySelector(".store-remove")?.addEventListener("click", () =>
        this._removeStore(storeId)
      );
    });

    root.querySelectorAll("li.item").forEach((li) => {
      const uid = li.getAttribute("data-uid");
      const item = items.find((i) => i.uid === uid);
      if (!item) return;
      li.querySelector(".toggle")?.addEventListener("change", () =>
        this._toggle(item)
      );
      li.querySelector(".remove")?.addEventListener("click", () =>
        this._remove(item)
      );
      li.querySelector(".itemStore")?.addEventListener("change", (ev) => {
        const next = ev.target.value || null;
        if ((item.store_id || null) === next) return;
        this._setItemStore(item, next);
      });
    });
  }

  _esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}

// Guard re-define when HA loads the module more than once (extra_module_url + cache).
if (!customElements.get("hass-shopping-list-card")) {
  customElements.define("hass-shopping-list-card", HassShoppingListCard);
}

// Lovelace “Add card” / “Nach Karte” picker reads window.customCards.
window.customCards = window.customCards || [];
if (
  !window.customCards.some((c) => c && c.type === "hass-shopping-list-card")
) {
  window.customCards.push({
    type: "hass-shopping-list-card",
    // Include DE + EN terms so search for “shop”, “einkauf”, “laden” finds it.
    name: "Einkaufsliste / Shopping List (Läden, hass-shopping-list)",
    description:
      "Shopping list with stores — Einkaufsliste mit Laden-Zuordnung, Filter und Laden-Verwaltung (hass-shopping-list).",
    preview: true,
    documentationURL:
      "https://github.com/MartinSchillinger/hass-shopping-list#lovelace-card--add-to-a-dashboard",
  });
}
