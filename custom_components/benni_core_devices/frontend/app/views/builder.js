import { chip, esc } from "../styles.js";

const WATT_ROWS = [["off", "watt_off"], ["idle", "watt_idle"], ["playing", "watt_playing"]];
const BLOCKED_SUFFIXES = ["_atomic", "_combined", "_gate"];

function firstType(catalog) {
  return (catalog.device_types?.[0]?.value) || "tv";
}
function typeInfo(catalog, type) {
  return (catalog.device_types || []).find((t) => t.value === type) || {};
}
function defaultFields(catalog, type) {
  return [...(typeInfo(catalog, type).default_fields || [])];
}
function mainKey(catalog, type) {
  return defaultFields(catalog, type)[0] || Object.keys(catalog.slot_catalog || {})[0] || "";
}

function newDraft(catalog) {
  const type = firstType(catalog);
  const main = mainKey(catalog, type);
  return {
    slug: "", display_name: "", device_type: type,
    fields: main ? [main] : [],
    slots: {},
    watt_threshold_on: catalog.defaults?.watt_threshold_on ?? 5,
    sticky_hold_seconds: catalog.defaults?.sticky_hold_seconds ?? 30,
    expose_secondary_sensors: false,
    watt_buckets: [],
    _touched: false, _submitted: false,
    _showOptional: false, _showPower: false, _showAdvanced: false,
  };
}

function draftFromDevice(catalog, device) {
  if (!device) return newDraft(catalog);
  const conf = device.config || {};
  const type = conf.device_type || firstType(catalog);
  const fields = [...(conf.fields || defaultFields(catalog, type))];
  const slots = {};
  for (const key of fields) slots[key] = conf[key] || "";
  if (conf.wake_mac) slots.wake_mac = conf.wake_mac;
  return {
    slug: device.slug || "", display_name: conf.display_name || "", device_type: type,
    fields, slots,
    watt_threshold_on: conf.watt_threshold_on ?? catalog.defaults?.watt_threshold_on ?? 5,
    sticky_hold_seconds: conf.sticky_hold_seconds ?? catalog.defaults?.sticky_hold_seconds ?? 30,
    expose_secondary_sensors: Boolean(conf.expose_secondary_sensors),
    watt_buckets: [...(conf.watt_buckets || [])],
    _touched: false, _submitted: false,
    _showOptional: true, _showPower: false, _showAdvanced: false,
  };
}

function bucketValue(draft, state, key) {
  const b = (draft.watt_buckets || []).find((x) => x.state === state);
  if (!b) return "";
  return key === "op" ? (b.op || "<=") : (b.value ?? "");
}

function entityOptions(hass, domains) {
  const set = new Set(domains || []);
  return Object.keys((hass && hass.states) || {})
    .filter((e) => !set.size || set.has(e.split(".")[0]))
    .sort().map((e) => `<option value="${esc(e)}"></option>`).join("");
}

function slotWarnings(draft, slotCatalog, profile) {
  const out = [];
  const own = [`${profile}_device_`, `${profile}_combined_`, `${profile}_light_group_`];
  for (const key of draft.fields || []) {
    const spec = slotCatalog[key] || {};
    const val = (draft.slots[key] || "").trim();
    if (!val) { out.push({ kind: "warn", text: `${key}: aktiviert, aber leer` }); continue; }
    if (spec.kind === "text") continue;
    const obj = val.includes(".") ? val.split(".")[1] : "";
    const dom = val.includes(".") ? val.split(".")[0] : "";
    if ((spec.domains || []).length && !(spec.domains || []).includes(dom))
      out.push({ kind: "warn", text: `${key}: falsche Domain (${dom})` });
    if (BLOCKED_SUFFIXES.some((s) => obj.endsWith(s)) || own.some((p) => obj.startsWith(p)))
      out.push({ kind: "err", text: `${key}: abgeleitete/atomic-Quelle (${val})` });
  }
  return out;
}

function readForm(root) {
  const f = root.querySelector("#deviceForm");
  const d = root._draft;
  if (!f || !d) return;
  if (f.elements.display_name) d.display_name = f.elements.display_name.value;
  if (f.elements.watt_threshold_on) d.watt_threshold_on = Number(f.elements.watt_threshold_on.value || 5);
  if (f.elements.sticky_hold_seconds) d.sticky_hold_seconds = Number(f.elements.sticky_hold_seconds.value || 30);
  if (f.elements.expose_secondary_sensors) d.expose_secondary_sensors = f.elements.expose_secondary_sensors.value === "true";
  d.watt_buckets = WATT_ROWS.map(([state, p]) => ({
    state,
    op: f.elements[`${p}_op`] ? f.elements[`${p}_op`].value : "<=",
    value: f.elements[`${p}_value`] ? f.elements[`${p}_value`].value : "",
  })).filter((x) => x.value !== "").map((x) => ({ state: x.state, op: x.op, value: Number(x.value) }));
}

function renderPicker(node, ctx, draft, key, spec, onChange) {
  node.innerHTML = "";
  if (spec.kind === "text") {
    const input = document.createElement("input");
    input.value = draft.slots[key] || "";
    input.placeholder = "z. B. 58:96:0A:5E:E9:2E";
    input.addEventListener("input", () => { draft.slots[key] = input.value; draft._touched = true; onChange(); });
    node.appendChild(input);
    return;
  }
  if (customElements.get("ha-entity-picker")) {
    const p = document.createElement("ha-entity-picker");
    p.hass = ctx.hass;
    p.value = draft.slots[key] || "";
    p.includeDomains = spec.domains || [];
    p.allowCustomEntity = true;
    p.addEventListener("value-changed", (ev) => {
      draft.slots[key] = ev.detail.value || "";
      draft._touched = true;
      onChange();
    });
    node.appendChild(p);
    return;
  }
  const input = document.createElement("input");
  const listId = `ent_${key}`;
  input.value = draft.slots[key] || "";
  input.setAttribute("list", listId);
  input.addEventListener("input", () => { draft.slots[key] = input.value; draft._touched = true; onChange(); });
  const dl = document.createElement("datalist");
  dl.id = listId;
  dl.innerHTML = entityOptions(ctx.hass, spec.domains || []);
  node.appendChild(input); node.appendChild(dl);
}

function summaryHtml(draft, status, catalog, showWarn) {
  const profile = status.profile || "benni";
  const entityId = `sensor.${profile}_device_${draft.slug || "<slug>"}`;
  const main = mainKey(catalog, draft.device_type);
  const live = (status.devices || []).find((dd) => dd.slug === draft.slug);
  const a = (live && live.attrs) || {};
  const configured = (draft.fields || []).filter((k) => (draft.slots[k] || "").trim()).length;
  const warns = showWarn ? slotWarnings(draft, catalog.slot_catalog || {}, profile) : [];
  const liveBlock = live ? `
    <div class="summary-line"><ha-icon icon="mdi:power"></ha-icon>powered: <b>${esc(a.powered)}</b></div>
    <div class="summary-line"><ha-icon icon="mdi:flash"></ha-icon>power_state: <b>${esc(a.power_state)}</b></div>
    <div class="summary-line"><ha-icon icon="mdi:check-network"></ha-icon>available: <b>${esc(a.available)}</b> ${chip(a.atomic_quality === "ok" ? "ok" : a.atomic_quality === "degraded" ? "warn" : "err", esc(a.atomic_quality || "—"))}</div>`
    : `<div class="muted" style="font-size:12px">Live-Werte erscheinen nach dem Speichern.</div>`;
  const warnBlock = warns.length
    ? `<div class="warnbox ${warns.some((w) => w.kind === "err") ? "err" : ""}" style="margin-top:12px">${warns.map((w) => `<div>• ${esc(w.text)}</div>`).join("")}</div>`
    : (showWarn ? `<div class="okbox" style="margin-top:12px">Bereit zum Speichern.</div>` : "");
  return `
    <div class="card">
      <h2>Zusammenfassung</h2>
      <div class="preview">
        <div class="summary-line"><ha-icon icon="mdi:identifier"></ha-icon><span class="mono pv-id">${esc(entityId)}</span></div>
        <div class="summary-line"><ha-icon icon="mdi:shape"></ha-icon>Typ: <b>${esc(typeInfo(catalog, draft.device_type).label || draft.device_type)}</b></div>
        <div class="summary-line"><ha-icon icon="mdi:star"></ha-icon>Hauptquelle: <span class="mono">${esc(draft.slots[main] || "—")}</span></div>
        <div class="summary-line"><ha-icon icon="mdi:source-branch"></ha-icon>${configured} Quelle(n) konfiguriert</div>
      </div>
      <div style="margin-top:12px">${liveBlock}</div>
      ${warnBlock}
    </div>`;
}

function refreshSummary(root, ctx) {
  const catalog = ctx.store.catalog || {};
  const status = ctx.store.status || {};
  const d = root._draft;
  const showWarn = !!d.slug || d._submitted || d._touched;
  const mount = root.querySelector("#summaryMount");
  if (mount) mount.innerHTML = summaryHtml(d, status, catalog, showWarn);
}

function slotRow(key, spec, draft, active, withToggle) {
  return `
    <div class="slot-row" data-slot-row="${esc(key)}">
      ${withToggle
        ? `<span class="fieldcheck"><input type="checkbox" data-field="${esc(key)}" ${active ? "checked" : ""}></span>`
        : `<span></span>`}
      <span class="slot-name">${esc(spec.label || key)}<small>${esc((spec.domains || []).join(",") || spec.kind || "")}</small></span>
      <span class="slot-pick" data-slot="${esc(key)}"></span>
    </div>`;
}

export function render(root, ctx) {
  root.dataset.keepDraft = "true";
  const catalog = ctx.store.catalog || {};
  const status = ctx.store.status || {};
  const devices = status.devices || [];
  const slotCatalog = catalog.slot_catalog || {};
  if (!root._draft) root._draft = newDraft(catalog);
  const d = root._draft;

  const main = mainKey(catalog, d.device_type);
  const dflt = defaultFields(catalog, d.device_type);
  const optionalKeys = dflt.filter((k) => k !== main);
  const advancedKeys = Object.keys(slotCatalog).filter((k) => k !== main && !dflt.includes(k));
  const active = new Set(d.fields || []);
  if (main && !active.has(main)) { d.fields.push(main); active.add(main); }

  root.innerHTML = `
    <div class="split">
      <div>
        <form id="deviceForm" class="form">
          <div class="row spread" style="margin-bottom:4px">
            <div class="row">
              <button class="btn ${d.slug ? "" : "primary"} small" type="button" id="modeNew">Neues Atomic</button>
              <select id="editPick" style="min-width:200px">
                <option value="">Bestehendes bearbeiten…</option>
                ${devices.map((dev) => `<option value="${esc(dev.slug)}" ${dev.slug === d.slug ? "selected" : ""}>${esc((dev.config && dev.config.display_name) || dev.slug)}</option>`).join("")}
              </select>
            </div>
            ${d.slug ? chip("accent", esc(d.slug)) : chip("info", "Neu")}
          </div>

          <div class="step primary-step">
            <div class="step-head"><span class="num">1</span><div><h3>Gerätetyp &amp; Name</h3><small>Bestimmt Semantik &amp; Hauptquelle</small></div></div>
            <label>Name<input name="display_name" value="${esc(d.display_name)}" placeholder="z. B. Wohnzimmer TV" required></label>
            <div class="type-grid" style="margin-top:10px">
              ${(catalog.device_types || []).map((t) =>
                `<div class="type-card ${t.value === d.device_type ? "active" : ""}" data-type="${esc(t.value)}">${esc(t.label)}</div>`).join("")}
            </div>
          </div>

          <div class="step primary-step">
            <div class="step-head"><span class="num">2</span><div><h3>Hauptquelle</h3><small>${esc((slotCatalog[main] || {}).label || main)}</small></div></div>
            <div class="main-pick" data-slot="${esc(main)}"></div>
          </div>

          <details class="disclosure" ${d._showOptional ? "open" : ""} data-disc="opt">
            <summary>Optionale Quellen <small>· ${optionalKeys.length} verfügbar</small></summary>
            <div class="disclosure-body">
              ${optionalKeys.length ? optionalKeys.map((k) => slotRow(k, slotCatalog[k] || {}, d, active.has(k), true)).join("")
                : `<div class="muted">Für diesen Typ keine typischen Zusatzquellen.</div>`}
            </div>
          </details>

          <details class="disclosure" ${d._showPower ? "open" : ""} data-disc="pow">
            <summary>Power &amp; Fallbacks <small>· Watt-Schwelle, Sticky, Buckets</small></summary>
            <div class="disclosure-body">
              <div class="grid cols-3">
                <label>On-Schwelle W<input name="watt_threshold_on" type="number" min="0" max="5000" value="${esc(d.watt_threshold_on)}"></label>
                <label>Sticky Sek.<input name="sticky_hold_seconds" type="number" min="0" max="3600" value="${esc(d.sticky_hold_seconds)}"></label>
                <label>Sekundär-Sensoren
                  <select name="expose_secondary_sensors">
                    <option value="false" ${d.expose_secondary_sensors ? "" : "selected"}>Aus</option>
                    <option value="true" ${d.expose_secondary_sensors ? "selected" : ""}>An</option>
                  </select>
                </label>
              </div>
              <div style="margin-top:10px"><div class="k">Watt-Buckets (power_state)</div>
                <div class="grid cols-3" style="margin-top:6px">
                  ${WATT_ROWS.map(([state, p]) => `
                    <label>${esc(state)}<div class="row">
                      <select name="${p}_op" style="max-width:80px">
                        ${(catalog.watt_operators || ["<", "<=", "=", ">", ">="]).map((op) =>
                          `<option value="${esc(op)}" ${bucketValue(d, state, "op") === op ? "selected" : ""}>${esc(op)}</option>`).join("")}
                      </select>
                      <input name="${p}_value" type="number" step="0.1" min="0" value="${esc(bucketValue(d, state, "value"))}">
                    </div></label>`).join("")}
                </div>
              </div>
            </div>
          </details>

          <details class="disclosure" ${d._showAdvanced ? "open" : ""} data-disc="adv">
            <summary>Erweitert <small>· alle weiteren Slots (Messwerte, Netzwerk, Wake, Companion)</small></summary>
            <div class="disclosure-body">
              ${advancedKeys.map((k) => slotRow(k, slotCatalog[k] || {}, d, active.has(k), true)).join("")}
            </div>
          </details>

          <div class="row">
            <button class="btn primary" type="submit">${d.slug ? "Speichern" : "Atomic anlegen"}</button>
            <button class="btn" type="button" id="resetForm">${d.slug ? "Abbrechen" : "Zurücksetzen"}</button>
            ${d.slug ? `<button class="btn danger" type="button" id="deleteDevice">Löschen</button>` : ""}
          </div>
        </form>
      </div>
      <div id="summaryMount"></div>
    </div>`;

  const form = root.querySelector("#deviceForm");
  // Picker mounten (Hauptquelle immer, optionale/erweiterte nur wenn aktiv).
  root.querySelectorAll("[data-slot]").forEach((node) => {
    const key = node.dataset.slot;
    const isMain = key === main;
    if (isMain || active.has(key)) {
      renderPicker(node, ctx, d, key, slotCatalog[key] || {}, () => refreshSummary(root, ctx));
    }
  });
  refreshSummary(root, ctx);

  // Mode / Edit
  root.querySelector("#modeNew").addEventListener("click", () => { root._draft = newDraft(catalog); ctx.rerender(); });
  root.querySelector("#editPick").addEventListener("change", (e) => {
    const dev = devices.find((x) => x.slug === e.target.value);
    root._draft = dev ? draftFromDevice(catalog, dev) : newDraft(catalog);
    ctx.rerender();
  });
  // Type cards
  root.querySelectorAll("[data-type]").forEach((c) =>
    c.addEventListener("click", () => {
      readForm(root);
      const t = c.dataset.type;
      if (t === d.device_type) return;
      d.device_type = t;
      const m = mainKey(catalog, t);
      d.fields = m ? [m] : [];
      d.slots = {};
      ctx.rerender();
    }));
  // Field toggles (optional/advanced)
  root.querySelectorAll("[data-field]").forEach((cb) =>
    cb.addEventListener("change", () => {
      readForm(root);
      const key = cb.dataset.field;
      d._touched = true;
      if (cb.checked) { if (!d.fields.includes(key)) d.fields.push(key); }
      else { d.fields = d.fields.filter((k) => k !== key); delete d.slots[key]; }
      ctx.rerender();
    }));
  // Disclosure state persist
  root.querySelectorAll("details[data-disc]").forEach((det) =>
    det.addEventListener("toggle", () => {
      if (det.dataset.disc === "opt") d._showOptional = det.open;
      if (det.dataset.disc === "pow") d._showPower = det.open;
      if (det.dataset.disc === "adv") d._showAdvanced = det.open;
    }));
  // Runtime inputs → update draft + summary
  ["display_name", "watt_threshold_on", "sticky_hold_seconds", "expose_secondary_sensors"].forEach((n) => {
    if (form.elements[n]) form.elements[n].addEventListener("change", () => { readForm(root); refreshSummary(root, ctx); });
  });
  WATT_ROWS.forEach(([, p]) => {
    [`${p}_op`, `${p}_value`].forEach((n) => {
      if (form.elements[n]) form.elements[n].addEventListener("change", () => readForm(root));
    });
  });

  root.querySelector("#resetForm").addEventListener("click", () => { root._draft = newDraft(catalog); ctx.rerender(); });
  const del = root.querySelector("#deleteDevice");
  if (del) del.addEventListener("click", async () => {
    await ctx.store.removeDevice(d.slug);
    root._draft = newDraft(catalog);
    ctx.toast("Atomic gelöscht"); ctx.rerender();
  });

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    readForm(root);
    d._submitted = true;
    if (!d.display_name) { refreshSummary(root, ctx); ctx.toast("Name fehlt"); return; }
    const res = await ctx.store.setDevice({
      slug: d.slug || undefined,
      device_type: d.device_type,
      display_name: d.display_name,
      fields: d.fields,
      slots: d.slots,
      watt_threshold_on: d.watt_threshold_on,
      sticky_hold_seconds: d.sticky_hold_seconds,
      expose_secondary_sensors: d.expose_secondary_sensors,
      watt_buckets: d.watt_buckets,
    });
    root._draft = newDraft(catalog);
    ctx.toast((res && res.warnings && res.warnings.length)
      ? `Gespeichert · ${res.warnings.length} Warnung(en)` : "Atomic gespeichert");
    ctx.rerender();
  });
}
