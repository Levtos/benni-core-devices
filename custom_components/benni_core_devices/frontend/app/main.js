import { CSS, chip, esc } from "./styles.js";
import { Store } from "./store.js";
import * as overview from "./views/overview.js";
import * as builder from "./views/builder.js";
import * as groups from "./views/groups.js";

const NAV = [
  { id: "overview", label: "Status", icon: "mdi:devices", view: overview },
  { id: "builder", label: "Device-Builder", icon: "mdi:plus-box", view: builder },
  { id: "groups", label: "Groups & Import", icon: "mdi:lightbulb-group", view: groups },
];

class BcdApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._store = new Store();
    this._view = "overview";
    this._booted = false;
    this._hass = null;
    this._poll = null;
  }

  set hass(value) {
    this._hass = value;
    this._store.hass = value;
    if (!this._booted) this._boot();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._poll = setInterval(() => this.refresh(), 10000);
  }

  disconnectedCallback() {
    clearInterval(this._poll);
  }

  async _boot() {
    this._booted = true;
    this._renderShell();
    await this.refresh();
  }

  async refresh() {
    await this._store.refresh().catch(() => {});
    this._renderLive();
  }

  _ctx() {
    return {
      hass: this._hass,
      store: this._store,
      refresh: () => this.refresh(),
      rerender: () => this._renderView(),
      toast: (msg) => this._toast(msg),
    };
  }

  _renderShell() {
    const nav = NAV.map((item) => `
      <button data-id="${esc(item.id)}" class="${item.id === this._view ? "active" : ""}">
        <ha-icon icon="${esc(item.icon)}"></ha-icon>${esc(item.label)}
      </button>`).join("");
    this.shadowRoot.innerHTML = `
      <style>${CSS}</style>
      <div class="app">
        <aside class="sidebar">
          <div class="brand">
            <div class="logo"><ha-icon icon="mdi:devices"></ha-icon></div>
            <div><b>Benni Core Devices</b><small>Atomic device sensors</small></div>
          </div>
          <nav class="nav">${nav}</nav>
          <div class="sb-foot" id="foot">benni_core_devices</div>
        </aside>
        <main class="main">
          <div class="head">
            <h1 id="title">Status</h1>
            <div class="chips" id="chips"></div>
          </div>
          <div id="content"></div>
        </main>
      </div>`;
    this.shadowRoot.querySelectorAll(".nav button").forEach((button) =>
      button.addEventListener("click", () => {
        this._view = button.dataset.id;
        this.shadowRoot.querySelectorAll(".nav button").forEach((b) =>
          b.classList.toggle("active", b.dataset.id === this._view));
        this._renderView();
      }));
  }

  _renderLive() {
    const status = this._store.status || {};
    const chips = this.shadowRoot.getElementById("chips");
    if (chips) {
      if (status._error) {
        chips.innerHTML = chip("warn", "WS error");
      } else {
        chips.innerHTML = [
          chip("info", `Route: ${status.profile_label || status.profile || "loading"}`),
          chip((status.devices || []).length ? "ok" : "warn", `Devices ${(status.devices || []).length}`),
          chip("info", `Groups ${(status.groups || []).length}`),
        ].join("");
      }
    }
    const foot = this.shadowRoot.getElementById("foot");
    if (foot && status.profile) foot.textContent = `benni_core_devices · ${status.profile}`;
    this._renderView();
  }

  _renderView() {
    const item = NAV.find((n) => n.id === this._view) || NAV[0];
    const title = this.shadowRoot.getElementById("title");
    const content = this.shadowRoot.getElementById("content");
    if (!content) return;
    title.textContent = item.label;
    try {
      item.view.render(content, this._ctx());
    } catch (err) {
      content.innerHTML = `<div class="empty">Render error: ${esc(err.message || err)}</div>`;
    }
  }

  _toast(message) {
    const node = document.createElement("div");
    node.className = "toast";
    node.textContent = message;
    this.shadowRoot.appendChild(node);
    setTimeout(() => node.remove(), 2400);
  }
}

if (!customElements.get("bcd-app")) {
  customElements.define("bcd-app", BcdApp);
}

