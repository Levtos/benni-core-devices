import { chip, esc } from "../styles.js";

const WATT_ROWS = [["off", "watt_off"], ["idle", "watt_idle"], ["playing", "watt_playing"]];
const BLOCKED = ["_atomic", "_combined", "_gate"];

function classInfo(catalog, ac) {
  return (catalog.atomic_classes || []).find((c) => c.value === ac) || {};
}
function firstClass(catalog) {
  return (catalog.atomic_classes && catalog.atomic_classes[0] && catalog.atomic_classes[0].value) || "media_device";
}

function newDraft(catalog) {
  const ac = firstClass(catalog);
  const ci = classInfo(catalog, ac);
  return {
    slug: "", display_name: "", atomic_class: ac, variant: (ci.variants || [])[0] || "",
    roles: {}, fail_safe: ci.fail_safe || "hold_last",
    watt_threshold_on: catalog.defaults?.watt_threshold_on ?? 5,
    sticky_hold_seconds: catalog.defaults?.sticky_hold_seconds ?? 30,
    expose_secondary_sensors: false, watt_buckets: [],
    _touched: false, _submitted: false,
    _showOpt: false, _showCtrl: false, _showMeta: false, _showAdv: false,
  };
}

function draftFromDevice(catalog, device) {
  if (!device) return newDraft(catalog);
  const conf = device.config || {};
  const roles = {};
  for (const bucket of ["sources", "controls", "metadata_sources"]) {
    for (const b of conf[bucket] || []) {
      if (b && b.role) roles[b.role] = b.entity || b.value || "";
    }
  }
  const ci = classInfo(catalog, conf.atomic_class);
  const diag = conf.diagnostics || {};
  return {
    slug: device.slug || "", display_name: conf.display_name || "",
    atomic_class: conf.atomic_class || firstClass(catalog), variant: conf.variant || (ci.variants || [])[0] || "",
    roles, fail_safe: diag.fail_safe || conf.fail_safe || ci.fail_safe || "hold_last",
    watt_threshold_on: conf.watt_threshold_on ?? catalog.defaults?.watt_threshold_on ?? 5,
    sticky_hold_seconds: conf.sticky_hold_seconds ?? catalog.defaults?.sticky_hold_seconds ?? 30,
    expose_secondary_sensors: Boolean(conf.expose_secondary_sensors),
    watt_buckets: [...(conf.watt_buckets || [])],
    _touched: false, _submitted: false,
    _showOpt: true, _showCtrl: false, _showMeta: false, _showAdv: false,
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
    .filter((e) => !set.size || set.has(e.split(".")[0])).sort()
    .map((e) => `<option value="${esc(e)}"></option>`).join("");
}

function roleWarnings(draft, roleCatalog, ci, profile) {
  const out = [];
  const own = [`${profile}_device_`, `${profile}_combined_`, `${profile}_light_group_`];
  const req = ci.required_roles || [];
  const present = req.filter((r) => (draft.roles[r] || "").trim());
  if (ci.required_mode === "any") {
    if (req.length && !present.length) out.push({ kind: "warn", text: `Pflicht: mindestens eine von ${req.join(", ")}` });
  } else {
    for (const r of req) if (!(draft.roles[r] || "").trim()) out.push({ kind: "warn", text: `Pflichtrolle leer: ${r}` });
  }
  for (const [role, v0] of Object.entries(draft.roles)) {
    const val = (v0 || "").trim();
    if (!val) continue;
    const spec = roleCatalog[role] || {};
    if (spec.kind === "text") continue;
    const dom = val.includes(".") ? val.split(".")[0] : "";
    const obj = val.includes(".") ? val.split(".")[1] : "";
    if ((spec.domains || []).length && !(spec.domains || []).includes(dom))
      out.push({ kind: "warn", text: `${role}: falsche Domain (${dom})` });
    if (BLOCKED.some((s) => obj.endsWith(s)) || own.some((p) => obj.startsWith(p)))
      out.push({ kind: "err", text: `${role}: abgeleitete/atomic-Quelle (${val})` });
  }
  return out;
}

function readForm(root) {
  const f = root.querySelector("#deviceForm");
  const d = root._draft;
  if (!f || !d) return;
  if (f.elements.display_name) d.display_name = f.elements.display_name.value;
  if (f.elements.variant) d.variant = f.elements.variant.value;
  if (f.elements.fail_safe) d.fail_safe = f.elements.fail_safe.value;
  if (f.elements.watt_threshold_on) d.watt_threshold_on = Number(f.elements.watt_threshold_on.value || 5);
  if (f.elements.sticky_hold_seconds) d.sticky_hold_seconds = Number(f.elements.sticky_hold_seconds.value || 30);
  if (f.elements.expose_secondary_sensors) d.expose_secondary_sensors = f.elements.expose_secondary_sensors.value === "true";
  d.watt_buckets = WATT_ROWS.map(([state, p]) => ({
    state, op: f.elements[`${p}_op`] ? f.elements[`${p}_op`].value : "<=",
    value: f.elements[`${p}_value`] ? f.elements[`${p}_value`].value : "",
  })).filter((x) => x.value !== "").map((x) => ({ state: x.state, op: x.op, value: Number(x.value) }));
}

function renderPicker(node, ctx, draft, role, spec, onChange) {
  node.innerHTML = "";
  if (spec.kind === "text") {
    const input = document.createElement("input");
    input.value = draft.roles[role] || "";
    input.placeholder = "z. B. 58:96:0A:5E:E9:2E";
    input.addEventListener("input", () => { draft.roles[role] = input.value; draft._touched = true; onChange(); });
    node.appendChild(input);
    return;
  }
  if (customElements.get("ha-entity-picker")) {
    const p = document.createElement("ha-entity-picker");
    p.hass = ctx.hass;
    p.value = draft.roles[role] || "";
    p.includeDomains = spec.domains || [];
    p.allowCustomEntity = true;
    p.addEventListener("value-changed", (ev) => { draft.roles[role] = ev.detail.value || ""; draft._touched = true; onChange(); });
    node.appendChild(p);
    return;
  }
  const input = document.createElement("input");
  const listId = `ent_${role}`;
  input.value = draft.roles[role] || "";
  input.setAttribute("list", listId);
  input.addEventListener("input", () => { draft.roles[role] = input.value; draft._touched = true; onChange(); });
  const dl = document.createElement("datalist");
  dl.id = listId;
  dl.innerHTML = entityOptions(ctx.hass, spec.domains || []);
  node.appendChild(input); node.appendChild(dl);
}

function summaryHtml(draft, status, catalog, showWarn) {
  const profile = status.profile || "benni";
  const roleCatalog = catalog.role_catalog || {};
  const ci = classInfo(catalog, draft.atomic_class);
  const entityId = `sensor.${profile}_device_${draft.slug || "<slug>"}`;
  const integ = (ci.integration_roles || [])[0];
  const live = (status.devices || []).find((dd) => dd.slug === draft.slug);
  const a = (live && live.attrs) || {};
  const configured = Object.values(draft.roles).filter((v) => (v || "").trim()).length;
  const warns = showWarn ? roleWarnings(draft, roleCatalog, ci, profile) : [];
  const liveBlock = live ? `
    <div class="summary-line"><ha-icon icon="mdi:power"></ha-icon>powered: <b>${esc(a.powered)}</b></div>
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
        <div class="summary-line"><ha-icon icon="mdi:shape"></ha-icon>${esc(ci.label || draft.atomic_class)} · <b>${esc(draft.variant)}</b></div>
        <div class="summary-line"><ha-icon icon="mdi:star"></ha-icon>Hauptquelle: <span class="mono">${esc(draft.roles[integ] || "—")}</span></div>
        <div class="summary-line"><ha-icon icon="mdi:source-branch"></ha-icon>${configured} Quelle(n) · fail_safe <b>${esc(draft.fail_safe)}</b></div>
      </div>
      <div style="margin-top:12px">${liveBlock}</div>
      ${warnBlock}
    </div>`;
}

function refreshSummary(root, ctx) {
  const mount = root.querySelector("#summaryMount");
  const d = root._draft;
  const showWarn = !!d.slug || d._submitted || d._touched;
  if (mount) mount.innerHTML = summaryHtml(d, ctx.store.status || {}, ctx.store.catalog || {}, showWarn);
}

function roleRow(role, spec) {
  return `
    <div class="slot-row" data-role-row="${esc(role)}">
      <span></span>
      <span class="slot-name">${esc(spec.label || role)}<small>${esc((spec.domains || []).join(",") || spec.kind || "")}</small></span>
      <span class="role-pick" data-role="${esc(role)}"></span>
    </div>`;
}

export function render(root, ctx) {
  root.dataset.keepDraft = "true";
  const catalog = ctx.store.catalog || {};
  const status = ctx.store.status || {};
  const devices = status.devices || [];
  const roleCatalog = catalog.role_catalog || {};
  if (!root._draft) root._draft = newDraft(catalog);
  const d = root._draft;
  const ci = classInfo(catalog, d.atomic_class);

  const required = ci.required_roles || [];
  const sourceRoles = Object.keys(roleCatalog).filter((r) => roleCatalog[r].bucket === "sources");
  const optionalSources = sourceRoles.filter((r) => !required.includes(r));
  const controlRoles = Object.keys(roleCatalog).filter((r) => roleCatalog[r].bucket === "controls");
  const metaRoles = Object.keys(roleCatalog).filter((r) => roleCatalog[r].bucket === "metadata_sources");
  const isWattModel = ci.power_model === "integration_watt_sticky";

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
            <div class="step-head"><span class="num">1</span><div><h3>Was willst du bauen?</h3><small>Geräteklasse &amp; Variante</small></div></div>
            <label>Name<input name="display_name" value="${esc(d.display_name)}" placeholder="z. B. Wohnzimmer TV" required></label>
            <div class="type-grid" style="margin-top:10px">
              ${(catalog.atomic_classes || []).map((c) =>
                `<div class="type-card ${c.value === d.atomic_class ? "active" : ""}" data-class="${esc(c.value)}" title="${esc(c.power_model)}">
                  <ha-icon icon="${esc(c.icon || "mdi:shape")}"></ha-icon><div>${esc(c.label)}${c.beta ? " ·β" : ""}</div></div>`).join("")}
            </div>
            ${(ci.variants || []).length ? `<label style="margin-top:10px">Variante
              <select name="variant">${(ci.variants || []).map((v) => `<option value="${esc(v)}" ${v === d.variant ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>` : ""}
          </div>

          <div class="step primary-step">
            <div class="step-head"><span class="num">2</span><div><h3>Pflichtquellen</h3><small>${ci.required_mode === "any" ? "eine genügt" : "alle erforderlich"}: ${esc(required.join(", "))}</small></div></div>
            ${required.map((r) => roleRow(r, roleCatalog[r] || {})).join("") || `<div class="muted">Keine Pflichtrollen.</div>`}
          </div>

          <details class="disclosure" ${d._showOpt ? "open" : ""} data-disc="opt">
            <summary>Optionale Quellen <small>· ${optionalSources.length} Rollen</small></summary>
            <div class="disclosure-body">${optionalSources.map((r) => roleRow(r, roleCatalog[r] || {})).join("")}</div>
          </details>

          <details class="disclosure" ${d._showCtrl ? "open" : ""} data-disc="ctrl">
            <summary>Controls <small>· Capability-Entities (Attribut-only)</small></summary>
            <div class="disclosure-body">${controlRoles.map((r) => roleRow(r, roleCatalog[r] || {})).join("")}</div>
          </details>

          <details class="disclosure" ${d._showMeta ? "open" : ""} data-disc="meta">
            <summary>Metadaten <small>· Attribut-Anreicherung aus separater Entity</small></summary>
            <div class="disclosure-body">${metaRoles.map((r) => roleRow(r, roleCatalog[r] || {})).join("")}</div>
          </details>

          <details class="disclosure" ${d._showAdv ? "open" : ""} data-disc="adv">
            <summary>Erweitert <small>· Fail-Safe${isWattModel ? " · Power & Fallbacks" : ""}</small></summary>
            <div class="disclosure-body">
              <label style="max-width:240px">Fail-Safe
                <select name="fail_safe">${(catalog.fail_safe_choices || ["off", "open", "hold_last", "unknown"]).map((fs) => `<option value="${esc(fs)}" ${fs === d.fail_safe ? "selected" : ""}>${esc(fs)}</option>`).join("")}</select></label>
              ${isWattModel ? `
                <div class="grid cols-3" style="margin-top:10px">
                  <label>On-Schwelle W<input name="watt_threshold_on" type="number" min="0" max="5000" value="${esc(d.watt_threshold_on)}"></label>
                  <label>Sticky Sek.<input name="sticky_hold_seconds" type="number" min="0" max="3600" value="${esc(d.sticky_hold_seconds)}"></label>
                  <label>Sekundär-Sensoren<select name="expose_secondary_sensors">
                    <option value="false" ${d.expose_secondary_sensors ? "" : "selected"}>Aus</option>
                    <option value="true" ${d.expose_secondary_sensors ? "selected" : ""}>An</option></select></label>
                </div>
                <div style="margin-top:10px"><div class="k">Watt-Buckets (power_state)</div>
                  <div class="grid cols-3" style="margin-top:6px">
                    ${WATT_ROWS.map(([state, p]) => `<label>${esc(state)}<div class="row">
                      <select name="${p}_op" style="max-width:80px">${(["<", "<=", "=", ">", ">="]).map((op) => `<option value="${esc(op)}" ${bucketValue(d, state, "op") === op ? "selected" : ""}>${esc(op)}</option>`).join("")}</select>
                      <input name="${p}_value" type="number" step="0.1" min="0" value="${esc(bucketValue(d, state, "value"))}"></div></label>`).join("")}
                  </div>
                </div>` : ""}
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
  root.querySelectorAll("[data-role]").forEach((node) =>
    renderPicker(node, ctx, d, node.dataset.role, roleCatalog[node.dataset.role] || {}, () => refreshSummary(root, ctx)));
  refreshSummary(root, ctx);

  root.querySelector("#modeNew").addEventListener("click", () => { root._draft = newDraft(catalog); ctx.rerender(); });
  root.querySelector("#editPick").addEventListener("change", (e) => {
    const dev = devices.find((x) => x.slug === e.target.value);
    root._draft = dev ? draftFromDevice(catalog, dev) : newDraft(catalog);
    ctx.rerender();
  });
  root.querySelectorAll("[data-class]").forEach((c) =>
    c.addEventListener("click", () => {
      readForm(root);
      const ac = c.dataset.class;
      if (ac === d.atomic_class) return;
      d.atomic_class = ac;
      const nci = classInfo(catalog, ac);
      d.variant = (nci.variants || [])[0] || "";
      d.fail_safe = nci.fail_safe || "hold_last";
      d.roles = {};
      ctx.rerender();
    }));
  root.querySelectorAll("details[data-disc]").forEach((det) =>
    det.addEventListener("toggle", () => {
      const m = { opt: "_showOpt", ctrl: "_showCtrl", meta: "_showMeta", adv: "_showAdv" };
      if (m[det.dataset.disc]) d[m[det.dataset.disc]] = det.open;
    }));
  ["display_name", "variant", "fail_safe", "watt_threshold_on", "sticky_hold_seconds", "expose_secondary_sensors"].forEach((n) => {
    if (form.elements[n]) form.elements[n].addEventListener("change", () => { readForm(root); refreshSummary(root, ctx); });
  });
  WATT_ROWS.forEach(([, p]) => [`${p}_op`, `${p}_value`].forEach((n) => {
    if (form.elements[n]) form.elements[n].addEventListener("change", () => readForm(root));
  }));

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
    const sources = [], controls = [], metadata = [];
    for (const [role, v0] of Object.entries(d.roles)) {
      const val = (v0 || "").trim();
      if (!val) continue;
      const spec = roleCatalog[role] || {};
      const binding = { role };
      if (spec.kind === "text") binding.value = val; else binding.entity = val;
      (spec.bucket === "controls" ? controls : spec.bucket === "metadata_sources" ? metadata : sources).push(binding);
    }
    const res = await ctx.store.setDevice({
      slug: d.slug || undefined,
      atomic_class: d.atomic_class, variant: d.variant, display_name: d.display_name,
      sources, controls, metadata_sources: metadata,
      fail_safe: d.fail_safe,
      watt_threshold_on: d.watt_threshold_on, sticky_hold_seconds: d.sticky_hold_seconds,
      expose_secondary_sensors: d.expose_secondary_sensors, watt_buckets: d.watt_buckets,
    });
    root._draft = newDraft(catalog);
    ctx.toast((res && res.warnings && res.warnings.length) ? `Gespeichert · ${res.warnings.length} Warnung(en)` : "Atomic gespeichert");
    ctx.rerender();
  });
}
