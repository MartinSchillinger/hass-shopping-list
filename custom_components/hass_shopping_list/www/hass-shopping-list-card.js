/**
 * Lovelace cards for hass_shopping_list.
 * - hass-shopping-list-card: shopping list (items, filter, add, edit modal)
 * - hass-shopping-list-stores-card: store catalog management
 * Loaded as one Lovelace module resource (or frontend extra module fallback).
 */
console.info(
  "%c HASS-SHOPPING-LIST-CARD %c loaded ",
  "background:#388e3c;color:#fff;font-weight:bold",
  "background:transparent;color:inherit"
);

function _hslEsc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _hslStoreOptionsHtml(
  stores,
  selectedId,
  { includeEmpty = true, emptyLabel = "Kein Laden" } = {}
) {
  const empty = includeEmpty
    ? `<option value="">${_hslEsc(emptyLabel)}</option>`
    : "";
  return (
    empty +
    (stores || [])
      .map(
        (s) =>
          `<option value="${_hslEsc(s.store_id)}" ${
            s.store_id === selectedId ? "selected" : ""
          }>${_hslEsc(s.name)}</option>`
      )
      .join("")
  );
}

/* ------------------------------------------------------------------ */
/* Shopping list card                                                   */
/* ------------------------------------------------------------------ */

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
    this._editItem = this._editItem || null;
    this._editName = this._editName || "";
    this._editStoreId = this._editStoreId || "";
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
      return;
    }
    // Do not re-render on every hass property update. HA pushes hass very often
    // (any entity state change). Full innerHTML replace would recreate the add
    // / store inputs and steal focus while typing. Card data refreshes via
    // hass_shopping_list_updated → _load() instead.
  }

  getCardSize() {
    return 5;
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

  async _setItemStore(item, storeId) {
    await this._hass.callService("hass_shopping_list", "set_item_store", {
      item_id: item.uid,
      store_id: storeId || null,
    });
  }

  async _renameItem(item, name) {
    const entityId = this._todoEntityId();
    if (!entityId) {
      throw new Error("Keine Todo-Entity für diese Liste gefunden.");
    }
    await this._hass.callService("todo", "update_item", {
      entity_id: entityId,
      item: item.uid,
      rename: name,
      status: item.complete ? "completed" : "needs_action",
    });
  }

  async _saveEdit() {
    const item = this._editItem;
    if (!item) return;
    const name = (this._editName || "").trim();
    if (!name) {
      this._error = "Name darf nicht leer sein.";
      this._render();
      return;
    }
    const nextStore = this._editStoreId || null;
    const prevStore = item.store_id || null;
    await this._withBusy(async () => {
      if (name !== item.name) {
        await this._renameItem(item, name);
      }
      if (nextStore !== prevStore) {
        await this._setItemStore(item, nextStore);
      }
      this._editItem = null;
      this._editName = "";
      this._editStoreId = "";
    });
  }

  _closeEdit() {
    this._editItem = null;
    this._editName = "";
    this._editStoreId = "";
    this._render();
  }

  _openEdit(item) {
    this._editItem = item;
    this._editName = item.name || "";
    this._editStoreId = item.store_id || "";
    this._render();
    requestAnimationFrame(() => {
      const input = this.shadowRoot?.getElementById("editName");
      if (input) {
        input.focus({ preventScroll: true });
        if (typeof input.select === "function") input.select();
      }
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

  /** Sync draft fields from live inputs and remember focus for restore. */
  _captureFocus() {
    const root = this.shadowRoot;
    if (!root) return null;
    const ae = root.activeElement;
    if (!ae || !ae.id) return null;
    if (ae.id === "newName") this._draftName = ae.value;
    if (ae.id === "newStore") this._draftStoreId = ae.value;
    if (ae.id === "editName") this._editName = ae.value;
    if (ae.id === "editStore") this._editStoreId = ae.value;
    return {
      id: ae.id,
      start: typeof ae.selectionStart === "number" ? ae.selectionStart : null,
      end: typeof ae.selectionEnd === "number" ? ae.selectionEnd : null,
    };
  }

  _restoreFocus(focus) {
    if (!focus?.id || !this.shadowRoot) return;
    const el = this.shadowRoot.getElementById(focus.id);
    if (!el) return;
    el.focus({ preventScroll: true });
    if (
      focus.start != null &&
      focus.end != null &&
      typeof el.setSelectionRange === "function"
    ) {
      try {
        el.setSelectionRange(focus.start, focus.end);
      } catch (_err) {
        // Some input types reject setSelectionRange; ignore.
      }
    }
  }

  _render() {
    if (!this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    const focus = this._captureFocus();

    const list = this._list();
    const stores = this._data?.stores || [];
    const storeMap = this._storeMap();
    const items = this._items();
    const title = this._config.title || list?.name || "Einkaufsliste";
    const busy = this._busy ? "is-busy" : "";
    const editing = this._editItem;

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
        button.icon {
          min-height: 36px;
          min-width: 36px;
          padding: 6px;
          flex: 0 0 auto;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
        }
        li.item {
          display: grid;
          grid-template-columns: auto 1fr auto;
          align-items: center;
          column-gap: 10px;
          padding: 10px 0;
          border-bottom: 1px solid var(--divider-color);
        }
        li.item:last-child { border-bottom: none; }
        .check { grid-column: 1; }
        .item-main {
          grid-column: 2;
          min-width: 0;
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 6px 8px;
          cursor: pointer;
          border-radius: 8px;
          padding: 2px 4px;
          margin: -2px -4px;
        }
        .item-main:hover {
          background: var(--secondary-background-color, rgba(0,0,0,0.04));
        }
        .item-main:focus-visible {
          outline: 2px solid var(--primary-color);
          outline-offset: 2px;
        }
        .name {
          min-width: 0;
          word-break: break-word;
          font-size: 1rem;
          line-height: 1.35;
        }
        .name.done {
          text-decoration: line-through;
          opacity: 0.6;
        }
        .remove { grid-column: 3; align-self: start; }
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
        .modal-backdrop {
          position: fixed;
          inset: 0;
          z-index: 1000;
          background: rgba(0, 0, 0, 0.45);
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 16px;
          box-sizing: border-box;
        }
        .modal {
          width: min(100%, 360px);
          background: var(--ha-card-background, var(--card-background-color, #fff));
          color: var(--primary-text-color);
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: 0 8px 28px rgba(0, 0, 0, 0.28);
          padding: 16px;
          border: 1px solid var(--divider-color);
        }
        .modal h3 {
          margin: 0 0 12px;
          font-size: 1.1rem;
          font-weight: 500;
        }
        .modal .field {
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin-bottom: 12px;
        }
        .modal label {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--secondary-text-color);
        }
        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          margin-top: 4px;
        }
        @media (min-width: 480px) {
          .card { padding: 14px 16px 16px; }
          .toolbar.stack-phone { flex-direction: row; }
          .toolbar.stack-phone > * { width: auto; flex: 1 1 140px; }
          .add-row {
            grid-template-columns: minmax(0, 1.4fr) minmax(120px, 0.9fr) auto;
          }
          .add-actions { display: contents; }
        }
        @media (min-width: 600px) {
          .card { padding: 16px 18px 18px; }
          h2 { font-size: 1.3rem; }
        }
      </style>
      <div class="card ${busy}">
        <h2>${_hslEsc(title)}</h2>
        ${
          this._error
            ? `<div class="error">${_hslEsc(this._error)}</div>`
            : ""
        }
        <div class="toolbar stack-phone">
          <select id="listSelect" aria-label="Liste">
            ${(this._data?.lists || [])
              .map(
                (l) =>
                  `<option value="${_hslEsc(l.list_id)}" ${
                    l.list_id === this._config.list_id ? "selected" : ""
                  }>${_hslEsc(l.name)}</option>`
              )
              .join("")}
          </select>
          <select id="filterStore" aria-label="Nach Laden filtern">
            <option value="">All stores</option>
            ${stores
              .map(
                (s) =>
                  `<option value="${_hslEsc(s.store_id)}" ${
                    s.store_id === this._filterStoreId ? "selected" : ""
                  }>${_hslEsc(s.name)}</option>`
              )
              .join("")}
          </select>
        </div>

        <div class="section">
          <div class="section-title">Artikel hinzufügen</div>
          <div class="add-row">
            <input id="newName" type="text" placeholder="Artikel…" value="${_hslEsc(
              this._draftName || ""
            )}" autocomplete="off" enterkeyhint="done" />
            <div class="add-actions">
              <select id="newStore" aria-label="Laden wählen">
                ${_hslStoreOptionsHtml(stores, this._draftStoreId, {
                  emptyLabel: "Kein Laden",
                })}
              </select>
              <button id="addBtn" type="button">Hinzufügen</button>
            </div>
          </div>
          ${
            stores.length === 0
              ? `<div class="hint">Noch keine Läden — die Karte „Läden / Stores“ anlegen, dann hier beim Hinzufügen auswählen.</div>`
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
                  return `<li class="item" data-uid="${_hslEsc(item.uid)}">
                    <input type="checkbox" class="check toggle" ${
                      item.complete ? "checked" : ""
                    } aria-label="Erledigt" />
                    <div class="item-main" role="button" tabindex="0" aria-label="Artikel bearbeiten">
                      <span class="name ${item.complete ? "done" : ""}">${_hslEsc(
                        item.name
                      )}</span>${
                        store
                          ? ` <span class="badge" style="${
                              store.color
                                ? `background:${_hslEsc(store.color)};color:#fff;`
                                : ""
                            }">${_hslEsc(store.name)}</span>`
                          : ""
                      }
                    </div>
                    <button type="button" class="ghost icon remove" aria-label="Entfernen">✕</button>
                  </li>`;
                })
                .join("")}
            </ul>`
          }
        </div>
      </div>
      ${
        editing
          ? `<div class="modal-backdrop" id="editBackdrop" role="presentation">
              <div class="modal" role="dialog" aria-modal="true" aria-labelledby="editTitle">
                <h3 id="editTitle">Artikel bearbeiten</h3>
                <div class="field">
                  <label for="editName">Name</label>
                  <input id="editName" type="text" value="${_hslEsc(
                    this._editName || ""
                  )}" autocomplete="off" enterkeyhint="done" />
                </div>
                <div class="field">
                  <label for="editStore">Laden</label>
                  <select id="editStore">
                    ${_hslStoreOptionsHtml(stores, this._editStoreId || "", {
                      emptyLabel: "Kein Laden",
                    })}
                  </select>
                </div>
                <div class="modal-actions">
                  <button type="button" class="ghost" id="editCancel">Abbrechen</button>
                  <button type="button" id="editSave">Speichern</button>
                </div>
              </div>
            </div>`
          : ""
      }
    `;

    this._bindEvents(items);
    this._restoreFocus(focus);
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
      const main = li.querySelector(".item-main");
      if (main) {
        main.addEventListener("click", () => this._openEdit(item));
        main.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this._openEdit(item);
          }
        });
      }
    });

    const backdrop = root.getElementById("editBackdrop");
    if (backdrop) {
      backdrop.addEventListener("click", (ev) => {
        if (ev.target === backdrop) this._closeEdit();
      });
      const editName = root.getElementById("editName");
      if (editName) {
        editName.addEventListener("input", (ev) => {
          this._editName = ev.target.value;
        });
        editName.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") this._saveEdit();
          if (ev.key === "Escape") this._closeEdit();
        });
      }
      const editStore = root.getElementById("editStore");
      if (editStore) {
        editStore.addEventListener("change", (ev) => {
          this._editStoreId = ev.target.value;
        });
      }
      root
        .getElementById("editCancel")
        ?.addEventListener("click", () => this._closeEdit());
      root
        .getElementById("editSave")
        ?.addEventListener("click", () => this._saveEdit());
    }
  }
}

/* ------------------------------------------------------------------ */
/* Stores management card                                               */
/* ------------------------------------------------------------------ */

class HassShoppingListStoresCard extends HTMLElement {
  static getStubConfig() {
    return { title: "Läden" };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = { ...config };
    this._draftStoreName = this._draftStoreName || "";
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
      return;
    }
    // Do not re-render on every hass property update. HA pushes hass very often
    // (any entity state change). Full innerHTML replace would recreate the add
    // / store inputs and steal focus while typing. Card data refreshes via
    // hass_shopping_list_updated → _load() instead.
  }

  getCardSize() {
    return 3;
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
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._render();
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

  async _addStore() {
    const name = (this._draftStoreName || "").trim();
    if (!name) return;
    await this._withBusy(async () => {
      await this._hass.callService("hass_shopping_list", "add_store", {
        name,
      });
      this._draftStoreName = "";
    });
  }

  async _removeStore(storeId) {
    if (!storeId) return;
    const store = (this._data?.stores || []).find((s) => s.store_id === storeId);
    const label = store?.name || storeId;
    if (!window.confirm(`Laden „${label}“ wirklich löschen?`)) return;
    await this._withBusy(async () => {
      await this._hass.callService("hass_shopping_list", "remove_store", {
        store_id: storeId,
      });
    });
  }

  _captureFocus() {
    const root = this.shadowRoot;
    if (!root) return null;
    const ae = root.activeElement;
    if (!ae || !ae.id) return null;
    if (ae.id === "newStoreName") this._draftStoreName = ae.value;
    return {
      id: ae.id,
      start: typeof ae.selectionStart === "number" ? ae.selectionStart : null,
      end: typeof ae.selectionEnd === "number" ? ae.selectionEnd : null,
    };
  }

  _restoreFocus(focus) {
    if (!focus?.id || !this.shadowRoot) return;
    const el = this.shadowRoot.getElementById(focus.id);
    if (!el) return;
    el.focus({ preventScroll: true });
    if (
      focus.start != null &&
      focus.end != null &&
      typeof el.setSelectionRange === "function"
    ) {
      try {
        el.setSelectionRange(focus.start, focus.end);
      } catch (_err) {
        // Some input types reject setSelectionRange; ignore.
      }
    }
  }

  _render() {
    if (!this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    const focus = this._captureFocus();
    const stores = this._data?.stores || [];
    const title = this._config.title || "Läden";
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
        .toolbar {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 12px;
        }
        .toolbar input[type="text"] {
          flex: 1 1 160px;
          min-width: 0;
        }
        input[type="text"] {
          box-sizing: border-box;
          width: 100%;
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
        .empty, .error, .hint {
          opacity: 0.75;
          padding: 6px 0;
          font-size: 0.9rem;
          line-height: 1.4;
        }
        .error { color: var(--error-color, #c00); opacity: 1; }
        @media (min-width: 600px) {
          .card { padding: 16px 18px 18px; }
          h2 { font-size: 1.3rem; }
        }
      </style>
      <div class="card ${busy}">
        <h2>${_hslEsc(title)}</h2>
        ${
          this._error
            ? `<div class="error">${_hslEsc(this._error)}</div>`
            : ""
        }
        <div class="toolbar">
          <input id="newStoreName" type="text" placeholder="Neuer Laden (z. B. Aldi)" value="${_hslEsc(
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
                (s) => `<div class="store-row" data-store-id="${_hslEsc(
                  s.store_id
                )}">
                <span class="badge" style="${
                  s.color
                    ? `background:${_hslEsc(s.color)};color:#fff;`
                    : ""
                }">${_hslEsc(s.name)}</span>
                <span class="label">${_hslEsc(s.name)}</span>
                <button type="button" class="ghost danger icon store-remove" aria-label="Laden löschen">✕</button>
              </div>`
              )
              .join("")}
          </div>`
        }
        <div class="hint">Läden erscheinen in der Einkaufslisten-Karte als Filter, Badge und Auswahl beim Hinzufügen/Bearbeiten.</div>
      </div>
    `;

    this._bindEvents();
    this._restoreFocus(focus);
  }

  _bindEvents() {
    const root = this.shadowRoot;
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
  }
}

// Guard re-define when HA loads the module more than once (extra_module_url + cache).
if (!customElements.get("hass-shopping-list-card")) {
  customElements.define("hass-shopping-list-card", HassShoppingListCard);
}
if (!customElements.get("hass-shopping-list-stores-card")) {
  customElements.define(
    "hass-shopping-list-stores-card",
    HassShoppingListStoresCard
  );
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
      "Shopping list with stores — Einkaufsliste mit Laden-Zuordnung und Filter (hass-shopping-list). Tip an item to edit name/store.",
    preview: true,
    documentationURL:
      "https://github.com/MartinSchillinger/hass-shopping-list#lovelace-cards--add-to-a-dashboard",
  });
}
if (
  !window.customCards.some(
    (c) => c && c.type === "hass-shopping-list-stores-card"
  )
) {
  window.customCards.push({
    type: "hass-shopping-list-stores-card",
    name: "Läden / Stores (hass-shopping-list)",
    description:
      "Manage stores — Läden anlegen und löschen for hass-shopping-list.",
    preview: true,
    documentationURL:
      "https://github.com/MartinSchillinger/hass-shopping-list#lovelace-cards--add-to-a-dashboard",
  });
}
