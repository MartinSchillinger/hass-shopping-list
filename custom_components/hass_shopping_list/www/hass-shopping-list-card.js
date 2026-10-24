/**
 * Minimal responsive Lovelace card for hass_shopping_list.
 * Shows items for a list with store badges and a store filter.
 */
class HassShoppingListCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("hass-shopping-list-card-editor");
  }

  static getStubConfig() {
    return { list_id: "", title: "Shopping" };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = { show_completed: false, ...config };
    this._filterStoreId = this._filterStoreId || "";
    this._draftName = "";
    this._draftStoreId = "";
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
    return 4;
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

  async _addItem() {
    const name = (this._draftName || "").trim();
    if (!name || !this._config.list_id) return;
    const data = {
      list_id: this._config.list_id,
      name,
    };
    if (this._draftStoreId) {
      data.store_id = this._draftStoreId;
    }
    await this._hass.callService("hass_shopping_list", "add_item", data);
    this._draftName = "";
    await this._load();
  }

  async _toggle(item) {
    await this._hass.callService("todo", "update_item", {
      entity_id: this._todoEntityId(),
      item: item.uid,
      status: item.complete ? "needs_action" : "completed",
    });
    await this._load();
  }

  async _remove(item) {
    await this._hass.callService("todo", "remove_item", {
      entity_id: this._todoEntityId(),
      item: [item.uid],
    });
    await this._load();
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

  _render() {
    if (!this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    const list = this._list();
    const stores = this._data?.stores || [];
    const storeMap = this._storeMap();
    const items = this._items();
    const title = this._config.title || list?.name || "Shopping";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--ha-font-family-body, Roboto, sans-serif);
          color: var(--primary-text-color);
        }
        .card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, none);
          border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color));
          padding: 12px 14px 14px;
        }
        h2 {
          margin: 0 0 10px;
          font-size: 1.15rem;
          font-weight: 500;
        }
        .toolbar {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 10px;
        }
        select, input[type="text"] {
          flex: 1 1 120px;
          min-width: 0;
          padding: 8px 10px;
          border-radius: 8px;
          border: 1px solid var(--divider-color);
          background: var(--input-fill-color, transparent);
          color: inherit;
          font: inherit;
        }
        button {
          padding: 8px 12px;
          border-radius: 8px;
          border: none;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
          font: inherit;
          cursor: pointer;
        }
        button.ghost {
          background: transparent;
          color: var(--primary-color);
          border: 1px solid var(--divider-color);
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
        }
        li {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 0;
          border-bottom: 1px solid var(--divider-color);
        }
        li:last-child { border-bottom: none; }
        .name {
          flex: 1;
          min-width: 0;
          word-break: break-word;
        }
        .name.done {
          text-decoration: line-through;
          opacity: 0.6;
        }
        .badge {
          flex: 0 0 auto;
          font-size: 0.75rem;
          line-height: 1.2;
          padding: 3px 8px;
          border-radius: 999px;
          background: var(--secondary-background-color, #eee);
          color: var(--secondary-text-color);
          max-width: 40%;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .empty, .error {
          opacity: 0.7;
          padding: 8px 0;
          font-size: 0.9rem;
        }
        .error { color: var(--error-color, #c00); }
        input[type="checkbox"] {
          width: 18px;
          height: 18px;
          accent-color: var(--primary-color);
        }
        @media (min-width: 600px) {
          .card { padding: 16px 18px 18px; }
          h2 { font-size: 1.25rem; }
        }
      </style>
      <div class="card">
        <h2>${this._esc(title)}</h2>
        ${
          this._error
            ? `<div class="error">${this._esc(this._error)}</div>`
            : ""
        }
        <div class="toolbar">
          <select id="listSelect" aria-label="List">
            ${(this._data?.lists || [])
              .map(
                (l) =>
                  `<option value="${this._esc(l.list_id)}" ${
                    l.list_id === this._config.list_id ? "selected" : ""
                  }>${this._esc(l.name)}</option>`
              )
              .join("")}
          </select>
          <select id="filterStore" aria-label="Filter by store">
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
        <div class="toolbar">
          <input id="newName" type="text" placeholder="Add item" value="${this._esc(
            this._draftName || ""
          )}" />
          <select id="newStore" aria-label="Store">
            <option value="">No store</option>
            ${stores
              .map(
                (s) =>
                  `<option value="${this._esc(s.store_id)}" ${
                    s.store_id === this._draftStoreId ? "selected" : ""
                  }>${this._esc(s.name)}</option>`
              )
              .join("")}
          </select>
          <button id="addBtn" type="button">Add</button>
        </div>
        ${
          items.length === 0
            ? `<div class="empty">No items${
                this._filterStoreId ? " for this store" : ""
              }.</div>`
            : `<ul>
            ${items
              .map((item) => {
                const store = item.store_id ? storeMap[item.store_id] : null;
                const badge = store
                  ? `<span class="badge" style="${
                      store.color ? `background:${this._esc(store.color)};color:#fff;` : ""
                    }">${this._esc(store.name)}</span>`
                  : "";
                return `<li data-uid="${this._esc(item.uid)}">
                  <input type="checkbox" class="toggle" ${
                    item.complete ? "checked" : ""
                  } aria-label="Complete" />
                  <span class="name ${item.complete ? "done" : ""}">${this._esc(
                    item.name
                  )}</span>
                  ${badge}
                  <button type="button" class="ghost remove" aria-label="Remove">✕</button>
                </li>`;
              })
              .join("")}
          </ul>`
        }
      </div>
    `;

    const listSelect = this.shadowRoot.getElementById("listSelect");
    if (listSelect) {
      listSelect.addEventListener("change", (ev) => {
        this._config = { ...this._config, list_id: ev.target.value };
        this._render();
      });
    }
    const filterStore = this.shadowRoot.getElementById("filterStore");
    if (filterStore) {
      filterStore.addEventListener("change", (ev) => {
        this._filterStoreId = ev.target.value;
        this._render();
      });
    }
    const newName = this.shadowRoot.getElementById("newName");
    if (newName) {
      newName.addEventListener("input", (ev) => {
        this._draftName = ev.target.value;
      });
      newName.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") this._addItem();
      });
    }
    const newStore = this.shadowRoot.getElementById("newStore");
    if (newStore) {
      newStore.addEventListener("change", (ev) => {
        this._draftStoreId = ev.target.value;
      });
    }
    const addBtn = this.shadowRoot.getElementById("addBtn");
    if (addBtn) addBtn.addEventListener("click", () => this._addItem());

    this.shadowRoot.querySelectorAll("li").forEach((li) => {
      const uid = li.getAttribute("data-uid");
      const item = items.find((i) => i.uid === uid);
      if (!item) return;
      li.querySelector(".toggle")?.addEventListener("change", () => this._toggle(item));
      li.querySelector(".remove")?.addEventListener("click", () => this._remove(item));
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

customElements.define("hass-shopping-list-card", HassShoppingListCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hass-shopping-list-card",
  name: "Shopping List (stores)",
  description: "Multi-list shopping with per-item store badges and filter.",
});
