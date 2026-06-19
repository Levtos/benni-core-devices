import { CSS, chip, esc } from "./styles.js";
import { Store } from "./store.js";
import * as diagnose from "./views/diagnose.js";
import * as builder from "./views/builder.js";
import * as combined from "./views/combined.js";
import * as importExport from "./views/import_export.js";

const VIEWS = {
  diagnose: { label: "Diagnose", icon: "mdi:stethoscope", view: diagnose },
  builder: { label: "Atomic Builder", icon: "mdi:cube-outline", view: builder },
  combined: { label: "Combined Builder", icon: "mdi:set-merge", view: combined, expert: true },
  import_export: { label: "Import / Export", icon: "mdi:swap-vertical", view: importExport, expert: true },
};

// Sidebar-Gruppen: Standard (geringe kognitive Last) vs. Experte.
const NAV_GROUPS = [
  { label: null, ids: ["diagnose", "builder"] },
  { label: "Experte", ids: ["combined", "import_export"] },
];

// Views mit Form-Draft, die nicht bei jedem Live-Refresh neu gerendert werden.
const DRAFT_VIEWS = new Set(["builder", "combined", "import_export"]);

class BcdApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._store = new Store();
    this._view = "diagnose";
    this._booted = false;
    this._hass = null;
    this._poll = null;
    this._lastRefresh = null;
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
    this._lastRefresh = new Date();
    this._renderLive();
  }

  _ctx() {
    return {
      hass: this._hass,
      store: this._store,
      refresh: () => this.refresh(),
      rerender: () => this._renderView(),
      navigate: (id) => this._navigate(id),
      toast: (msg) => this._toast(msg),
    };
  }

  _navigate(id) {
    if (!VIEWS[id]) return;
    this._view = id;
    this.shadowRoot.querySelectorAll(".nav button").forEach((b) =>
      b.classList.toggle("active", b.dataset.id === this._view));
    this._renderView();
  }

  _renderShell() {
    const nav = NAV_GROUPS.map((group) => {
      const sep = group.label ? `<div class="sep">${esc(group.label)}</div>` : "";
      const items = group.ids.map((id) => {
        const item = VIEWS[id];
        return `
          <button data-id="${esc(id)}" class="${id === this._view ? "active" : ""}">
            <ha-icon icon="${esc(item.icon)}"></ha-icon>
            <span class="grow">${esc(item.label)}</span>
            ${item.expert ? `<span class="exp-badge">Experte</span>` : ""}
          </button>`;
      }).join("");
      return sep + items;
    }).join("");

    this.shadowRoot.innerHTML = `
      <style>${CSS}</style>
      <div class="app">
        <aside class="sidebar">
          <div class="brand">
            <div class="logo"><ha-icon icon="mdi:atom"></ha-icon></div>
            <div><b>Benni Core Devices</b><small>Atomic-Werkstatt</small></div>
          </div>
          <nav class="nav">${nav}</nav>
          <div class="sb-foot" id="foot">benni_core_devices</div>
        </aside>
        <main class="main">
          <div class="head">
            <div>
              <h1 id="title">Diagnose</h1>
              <div class="sub" id="subtitle"></div>
            </div>
            <div class="chips" id="chips"></div>
          </div>
          <div id="content"></div>
        </main>
      </div>`;
    this.shadowRoot.querySelectorAll(".nav button").forEach((button) =>
      button.addEventListener("click", () => this._navigate(button.dataset.id)));
  }

  _renderLive() {
    const status = this._store.status || {};
    const chips = this.shadowRoot.getElementById("chips");
    if (chips) {
      if (status._error) {
        chips.innerHTML = chip("err", "WS error");
      } else {
        const devices = status.devices || [];
        const combineds = status.combineds || [];
        const masters = combineds.filter((c) => {
          const conf = c.config || {};
          return (conf.exposed_attributes || []).length > 0
            || (conf.derived_values || []).some((d) => d && d.expose);
        });
        const missing = devices.reduce(
          (n, d) => n + ((d.attrs && d.attrs.missing_required) || []).length, 0);
        const degraded = devices.filter((d) => d.attrs && d.attrs.degraded).length;
        const ready = devices.filter(
          (d) => d.attrs && d.attrs.atomic_quality === "ok").length;
        const version = (this._store.catalog && this._store.catalog.version) || "?";
        chips.innerHTML = [
          chip("info", `v${version}`),
          chip("accent", `Route: ${status.profile_label || status.profile || "?"}`),
          chip(devices.length ? "info" : "warn", `Devices ${devices.length}`),
          masters.length ? chip("accent", `Master ${masters.length}`) : "",
          chip("info", `Combined ${combineds.length}`),
          missing ? chip("warn", `Missing ${missing}`) : "",
          degraded ? chip("warn", `Degraded ${degraded}`) : "",
          chip("ok", `Ready ${ready}`),
        ].join("");
      }
    }
    const subtitle = this.shadowRoot.getElementById("subtitle");
    if (subtitle) {
      subtitle.textContent = this._lastRefresh
        ? `Letzte Aktualisierung: ${this._lastRefresh.toLocaleTimeString()}`
        : "";
    }
    const foot = this.shadowRoot.getElementById("foot");
    const version = (this._store.catalog && this._store.catalog.version) || "?";
    if (foot) foot.textContent = `benni_core_devices · v${version}${status.profile ? " · " + status.profile : ""}`;
    const content = this.shadowRoot.getElementById("content");
    if (DRAFT_VIEWS.has(this._view) && content?.dataset.keepDraft === "true") {
      return;
    }
    this._renderView();
  }

  _renderView() {
    const item = VIEWS[this._view] || VIEWS.diagnose;
    const title = this.shadowRoot.getElementById("title");
    const content = this.shadowRoot.getElementById("content");
    if (!content) return;
    content.dataset.keepDraft = "false";
    if (title) title.textContent = item.label;
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
