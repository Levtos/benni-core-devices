import { chip, esc } from "../styles.js";

const WATT_ROWS = [
  ["off", "watt_off"],
  ["idle", "watt_idle"],
  ["playing", "watt_playing"],
];

const BLOCKED_SUFFIXES = ["_atomic", "_combined", "_gate"];

function firstType(catalog) {
  return (catalog.device_types && catalog.device_types[0] && catalog.device_types[0].value) || "tv";
}

function defaultFields(catalog, type) {
  const found = (catalog.device_types || []).find((item) => item.value === type);
  return [...((found && found.default_fields) || [])];
}

function newDraft(catalog) {
  const type = firstType(catalog);
  return {
    slug: "",
    display_name: "",
    device_type: type,
    fields: defaultFields(catalog, type),
    slots: {},
    watt_threshold_on: catalog.defaults?.watt_threshold_on ?? 5,
    sticky_hold_seconds: catalog.defaults?.sticky_hold_seconds ?? 30,
    expose_secondary_sensors: false,
    watt_buckets: [],
  };
}

function draftFromDevice(catalog, device) {
  if (!device) return newDraft(catalog);
  const conf = device.config || {};
  const fields = [...(conf.fields || defaultFields(catalog, conf.device_type || firstType(catalog)))];
  const slots = {};
  for (const key of fields) slots[key] = conf[key] || "";
  if (conf.wake_mac) slots.wake_mac = conf.wake_mac;
  return {
    slug: device.slug || "",
    display_name: conf.display_name || "",
    device_type: conf.device_type || firstType(catalog),
    fields,
    slots,
    watt_threshold_on: conf.watt_threshold_on ?? catalog.defaults?.watt_threshold_on ?? 5,
    sticky_hold_seconds: conf.sticky_hold_seconds ?? catalog.defaults?.sticky_hold_seconds ?? 30,
    expose_secondary_sensors: Boolean(conf.expose_secondary_sensors),
    watt_buckets: [...(conf.watt_buckets || [])],
  };
}

function bucketValue(draft, state, key) {
  const bucket = (draft.watt_buckets || []).find((item) => item.state === state);
  if (!bucket) return "";
  return key === "op" ? (bucket.op || "<=") : (bucket.value ?? "");
}

function entityOptions(hass, domains) {
  const set = new Set(domains || []);
  return Object.keys((hass && hass.states) || {})
    .filter((entityId) => !set.size || set.has(entityId.split(".")[0]))
    .sort()
    .map((entityId) => `<option value="${esc(entityId)}"></option>`)
    .join("");
}

// Client-seitige Warnungen für die Preview (Spiegel der Backend-Regeln).
function slotWarnings(draft, slotCatalog, profile) {
  const warnings = [];
  const ownPrefixes = [
    `${profile}_device_`, `${profile}_combined_`, `${profile}_light_group_`,
  ];
  for (const key of draft.fields || []) {
    const spec = slotCatalog[key] || {};
    const val = (draft.slots[key] || "").trim();
    if (!val) {
      warnings.push({ kind: "warn", text: `${key}: aktiviert, aber leer` });
      continue;
    }
    if (spec.kind === "text") continue;
    const objectId = val.includes(".") ? val.split(".")[1] : "";
    const domain = val.includes(".") ? val.split(".")[0] : "";
    if ((spec.domains || []).length && !(spec.domains || []).includes(domain)) {
      warnings.push({ kind: "warn", text: `${key}: falsche Domain (${domain})` });
    }
    if (BLOCKED_SUFFIXES.some((s) => objectId.endsWith(s))
        || ownPrefixes.some((p) => objectId.startsWith(p))) {
      warnings.push({ kind: "err", text: `${key}: abgeleitete/atomic-Quelle (${val})` });
    }
  }
  return warnings;
}

function syncDraftFromForm(root) {
  const form = root.querySelector("#deviceForm");
  const draft = root._draft;
  if (!form || !draft) return;
  draft.display_name = form.elements.display_name.value;
  draft.device_type = form.elements.device_type.value;
  draft.fields = [...form.querySelectorAll('input[name="field"]:checked')].map((i) => i.value);
  draft.watt_threshold_on = Number(form.elements.watt_threshold_on.value || 5);
  draft.sticky_hold_seconds = Number(form.elements.sticky_hold_seconds.value || 30);
  draft.expose_secondary_sensors = form.elements.expose_secondary_sensors.value === "true";
  draft.watt_buckets = WATT_ROWS
    .map(([state, prefix]) => ({
      state,
      op: form.elements[`${prefix}_op`] ? form.elements[`${prefix}_op`].value : "<=",
      value: form.elements[`${prefix}_value`] ? form.elements[`${prefix}_value`].value : "",
    }))
    .filter((item) => item.value !== "")
    .map((item) => ({ state: item.state, op: item.op, value: Number(item.value) }));
}

function renderEntityPicker(node, ctx, draft, key, spec) {
  node.innerHTML = "";
  if (spec.kind === "text") {
    const input = document.createElement("input");
    input.value = draft.slots[key] || "";
    input.placeholder = "z. B. 58:96:0A:5E:E9:2E";
    input.addEventListener("input", () => { draft.slots[key] = input.value; });
    node.appendChild(input);
    return;
  }
  if (customElements.get("ha-entity-picker")) {
    const picker = document.createElement("ha-entity-picker");
    picker.hass = ctx.hass;
    picker.value = draft.slots[key] || "";
    picker.includeDomains = spec.domains || [];
    picker.allowCustomEntity = true;
    picker.addEventListener("value-changed", (ev) => {
      draft.slots[key] = ev.detail.value || "";
      ctx.rerender();
    });
    node.appendChild(picker);
    return;
  }
  const input = document.createElement("input");
  const listId = `entities_${key}`;
  input.value = draft.slots[key] || "";
  input.setAttribute("list", listId);
  input.addEventListener("input", () => { draft.slots[key] = input.value; });
  const datalist = document.createElement("datalist");
  datalist.id = listId;
  datalist.innerHTML = entityOptions(ctx.hass, spec.domains || []);
  node.appendChild(input);
  node.appendChild(datalist);
}

function previewCard(draft, status, warnings) {
  const profile = status.profile || "benni";
  const entityId = `sensor.${profile}_device_${draft.slug || "<slug>"}`;
  const live = (status.devices || []).find((d) => d.slug === draft.slug);
  const a = (live && live.attrs) || {};
  const slotEntities = a.slot_entities || draft.slots;
  const warnHtml = warnings.length
    ? `<div class="warnbox ${warnings.some((w) => w.kind === "err") ? "err" : ""}">
        Warnungen:<ul>${warnings.map((w) => `<li>${esc(w.text)}</li>`).join("")}</ul></div>`
    : `<div class="muted" style="font-size:12px">Keine Warnungen.</div>`;
  return `
    <div class="card">
      <h2>Preview</h2>
      <div class="preview">
        <div class="kv"><span class="k">Entity</span><span class="v mono pv-id">${esc(entityId)}</span></div>
        <div class="kv"><span class="k">powered</span><span class="v">${esc(live ? a.powered : "—")}</span></div>
        <div class="kv"><span class="k">power_state</span><span class="v">${esc(live ? a.power_state : "—")}</span></div>
        <div class="kv"><span class="k">available</span><span class="v">${esc(live ? a.available : "—")}</span></div>
      </div>
      <h2 style="margin-top:14px">Slots</h2>
      ${Object.keys(slotEntities).length
        ? Object.entries(slotEntities).map(([k, v]) =>
            `<div class="kv"><span class="k">${esc(k)}</span><span class="v mono">${esc(v || "—")}</span></div>`).join("")
        : `<div class="muted">Keine Slots belegt.</div>`}
      <div style="margin-top:14px">${warnHtml}</div>
    </div>`;
}

export function render(root, ctx) {
  root.dataset.keepDraft = "true";
  const catalog = ctx.store.catalog || {};
  const status = ctx.store.status || {};
  const devices = status.devices || [];
  const slotCatalog = catalog.slot_catalog || {};
  const slotGroups = catalog.slot_groups || [];

  if (!root._draft) root._draft = newDraft(catalog);
  const draft = root._draft;
  const active = new Set(draft.fields || []);
  const warnings = slotWarnings(draft, slotCatalog, status.profile || "benni");

  const groupHtml = slotGroups.map((g) => {
    const keys = Object.keys(slotCatalog).filter((k) => (slotCatalog[k].group || "basics") === g.key);
    if (!keys.length) return "";
    return `
      <div class="slot-group">
        <h3><ha-icon icon="mdi:tune-variant"></ha-icon>${esc(g.label)}</h3>
        ${keys.map((key) => {
          const spec = slotCatalog[key];
          return `
            <div class="slot-row" data-slot-row="${esc(key)}">
              <span class="fieldcheck"><input type="checkbox" name="field" value="${esc(key)}" ${active.has(key) ? "checked" : ""}></span>
              <span class="slot-name">${esc(spec.label || key)}<small>${esc((spec.domains || []).join(",") || spec.kind)}</small></span>
              <span class="slot-pick" data-slot="${esc(key)}"></span>
              <span></span>
            </div>`;
        }).join("")}
      </div>`;
  }).join("");

  root.innerHTML = `
    <div class="split">
      <div class="card">
        <div class="section-head">
          <h2>${draft.slug ? "Atomic bearbeiten" : "Atomic anlegen"}</h2>
          <span class="chip ${draft.slug ? "accent" : "info"}"><span class="dot"></span>${draft.slug ? esc(draft.slug) : "Neu"}</span>
        </div>
        <form id="deviceForm" class="form">
          <div class="grid cols-2">
            <label>Bestehend
              <select name="edit_slug">
                <option value="">Neues Device</option>
                ${devices.map((d) => `<option value="${esc(d.slug)}" ${d.slug === draft.slug ? "selected" : ""}>${esc((d.config && d.config.display_name) || d.slug)}</option>`).join("")}
              </select>
            </label>
            <label>Typ
              <select name="device_type">
                ${(catalog.device_types || []).map((item) =>
                  `<option value="${esc(item.value)}" ${item.value === draft.device_type ? "selected" : ""}>${esc(item.label)}</option>`).join("")}
              </select>
            </label>
          </div>
          <label>Name
            <input name="display_name" value="${esc(draft.display_name)}" required>
          </label>
          ${groupHtml}
          <div class="slot-group">
            <h3><ha-icon icon="mdi:cog"></ha-icon>Advanced</h3>
            <div class="grid cols-3">
              <label>On threshold W
                <input name="watt_threshold_on" type="number" min="0" max="5000" value="${esc(draft.watt_threshold_on)}">
              </label>
              <label>Sticky seconds
                <input name="sticky_hold_seconds" type="number" min="0" max="3600" value="${esc(draft.sticky_hold_seconds)}">
              </label>
              <label>Secondary sensors
                <select name="expose_secondary_sensors">
                  <option value="false" ${draft.expose_secondary_sensors ? "" : "selected"}>Off</option>
                  <option value="true" ${draft.expose_secondary_sensors ? "selected" : ""}>On</option>
                </select>
              </label>
            </div>
            <div style="margin-top:10px"><div class="k">Watt buckets</div>
              <div class="grid cols-3" style="margin-top:6px">
                ${WATT_ROWS.map(([state, prefix]) => `
                  <label>${esc(state)}
                    <div class="row">
                      <select name="${prefix}_op" style="max-width:84px">
                        ${(catalog.watt_operators || ["<", "<=", "=", ">", ">="]).map((op) =>
                          `<option value="${esc(op)}" ${bucketValue(draft, state, "op") === op ? "selected" : ""}>${esc(op)}</option>`).join("")}
                      </select>
                      <input name="${prefix}_value" type="number" step="0.1" min="0" value="${esc(bucketValue(draft, state, "value"))}">
                    </div>
                  </label>`).join("")}
              </div>
            </div>
          </div>
          <div class="row">
            <button class="btn primary" type="submit">${draft.slug ? "Speichern" : "Anlegen"}</button>
            <button class="btn" type="button" id="resetForm">${draft.slug ? "Abbrechen" : "Neu"}</button>
            ${draft.slug ? `<button class="btn danger" type="button" id="deleteDevice">Löschen</button>` : ""}
          </div>
        </form>
      </div>
      <div id="previewMount">${previewCard(draft, status, warnings)}</div>
    </div>`;

  const form = root.querySelector("#deviceForm");
  const refreshPickers = () => {
    syncDraftFromForm(root);
    root.querySelectorAll("[data-slot-row]").forEach((rowNode) => {
      const key = rowNode.dataset.slotRow;
      const pick = rowNode.querySelector(`[data-slot="${key}"]`);
      const checked = active.has(key);
      if (pick) pick.innerHTML = "";
      if (checked && pick) renderEntityPicker(pick, ctx, draft, key, slotCatalog[key] || {});
    });
  };
  refreshPickers();

  form.elements.edit_slug.addEventListener("change", () => {
    const selected = devices.find((d) => d.slug === form.elements.edit_slug.value);
    root._draft = draftFromDevice(catalog, selected);
    ctx.rerender();
  });
  form.elements.device_type.addEventListener("change", () => {
    syncDraftFromForm(root);
    draft.device_type = form.elements.device_type.value;
    draft.fields = defaultFields(catalog, draft.device_type);
    draft.slots = {};
    ctx.rerender();
  });
  form.querySelectorAll('input[name="field"]').forEach((input) =>
    input.addEventListener("change", () => { syncDraftFromForm(root); ctx.rerender(); }));
  form.querySelectorAll("input, select").forEach((input) => {
    if (!["field", "edit_slug", "device_type"].includes(input.name)) {
      input.addEventListener("change", () => { syncDraftFromForm(root); });
    }
  });
  root.querySelector("#resetForm").addEventListener("click", () => {
    root._draft = newDraft(catalog);
    ctx.rerender();
  });
  const del = root.querySelector("#deleteDevice");
  if (del) del.addEventListener("click", async () => {
    await ctx.store.removeDevice(draft.slug);
    root._draft = newDraft(catalog);
    ctx.toast("Device gelöscht");
    ctx.rerender();
  });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    syncDraftFromForm(root);
    const res = await ctx.store.setDevice({
      slug: draft.slug || undefined,
      device_type: draft.device_type,
      display_name: draft.display_name,
      fields: draft.fields,
      slots: draft.slots,
      watt_threshold_on: draft.watt_threshold_on,
      sticky_hold_seconds: draft.sticky_hold_seconds,
      expose_secondary_sensors: draft.expose_secondary_sensors,
      watt_buckets: draft.watt_buckets,
    });
    root._draft = newDraft(catalog);
    ctx.toast((res && res.warnings && res.warnings.length)
      ? `Gespeichert · ${res.warnings.length} Warnung(en)` : "Atomic gespeichert");
    ctx.rerender();
  });
}
