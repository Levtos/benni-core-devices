import { esc } from "../styles.js";

const WATT_ROWS = [
  ["off", "watt_off"],
  ["idle", "watt_idle"],
  ["playing", "watt_playing"],
];

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
  for (const key of fields) {
    slots[key] = conf[key] || "";
  }
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

function syncDraftFromForm(root) {
  const form = root.querySelector("#deviceForm");
  const draft = root._draft;
  if (!form || !draft) return;
  draft.display_name = form.elements.display_name.value;
  draft.device_type = form.elements.device_type.value;
  draft.fields = [...form.querySelectorAll('input[name="field"]:checked')].map((input) => input.value);
  draft.watt_threshold_on = Number(form.elements.watt_threshold_on.value || 5);
  draft.sticky_hold_seconds = Number(form.elements.sticky_hold_seconds.value || 30);
  draft.expose_secondary_sensors = form.elements.expose_secondary_sensors.value === "true";
  draft.watt_buckets = WATT_ROWS
    .map(([state, prefix]) => ({
      state,
      op: form.elements[`${prefix}_op`].value,
      value: form.elements[`${prefix}_value`].value,
    }))
    .filter((item) => item.value !== "")
    .map((item) => ({ state: item.state, op: item.op, value: Number(item.value) }));
}

function renderEntityPicker(node, ctx, draft, key, spec) {
  node.innerHTML = "";
  const label = document.createElement("label");
  label.textContent = spec.label || key;
  node.appendChild(label);

  if (customElements.get("ha-entity-picker")) {
    const picker = document.createElement("ha-entity-picker");
    picker.hass = ctx.hass;
    picker.value = draft.slots[key] || "";
    picker.includeDomains = spec.domains || [];
    picker.allowCustomEntity = true;
    picker.addEventListener("value-changed", (ev) => {
      draft.slots[key] = ev.detail.value || "";
    });
    label.appendChild(picker);
    return;
  }

  const input = document.createElement("input");
  const listId = `entities_${key}`;
  input.name = `slot_${key}`;
  input.value = draft.slots[key] || "";
  input.setAttribute("list", listId);
  input.addEventListener("input", () => {
    draft.slots[key] = input.value;
  });
  const datalist = document.createElement("datalist");
  datalist.id = listId;
  datalist.innerHTML = entityOptions(ctx.hass, spec.domains || []);
  label.appendChild(input);
  label.appendChild(datalist);
}

export function render(root, ctx) {
  root.dataset.keepDraft = "true";
  const catalog = ctx.store.catalog || {};
  const status = ctx.store.status || {};
  const devices = status.devices || [];
  const slotCatalog = catalog.slot_catalog || {};

  if (!root._draft) {
    root._draft = newDraft(catalog);
  }
  const draft = root._draft;
  const activeFields = new Set(draft.fields || []);

  root.innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <h2>${draft.slug ? "Update sensor" : "Create sensor"}</h2>
        <form id="deviceForm" class="form">
          <label>Existing
            <select name="edit_slug">
              <option value="">New device</option>
              ${devices.map((device) => `<option value="${esc(device.slug)}" ${device.slug === draft.slug ? "selected" : ""}>${esc(device.config.display_name || device.slug)}</option>`).join("")}
            </select>
          </label>
          <label>Name
            <input name="display_name" value="${esc(draft.display_name)}" required>
          </label>
          <label>Type
            <select name="device_type">
              ${(catalog.device_types || []).map((item) =>
                `<option value="${esc(item.value)}" ${item.value === draft.device_type ? "selected" : ""}>${esc(item.label)}</option>`).join("")}
            </select>
          </label>
          <div class="fields">
            ${Object.entries(slotCatalog).map(([key, spec]) => `
              <label class="fieldcheck">
                <input type="checkbox" name="field" value="${esc(key)}" ${activeFields.has(key) ? "checked" : ""}>
                <span>${esc(spec.label || key)} <span class="muted mono">${esc((spec.domains || []).join(","))}</span></span>
              </label>`).join("")}
          </div>
          <div id="slots" class="slot-list"></div>
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
          <div class="subpanel">
            <h2>Watt buckets</h2>
            <div class="grid cols-3">
              ${WATT_ROWS.map(([state, prefix]) => `
                <label>${esc(state)}
                  <div class="row">
                    <select name="${prefix}_op" style="max-width:88px">
                      ${(catalog.watt_operators || ["<", "<=", "=", ">", ">="]).map((op) =>
                        `<option value="${esc(op)}" ${bucketValue(draft, state, "op") === op ? "selected" : ""}>${esc(op)}</option>`).join("")}
                    </select>
                    <input name="${prefix}_value" type="number" step="0.1" min="0" value="${esc(bucketValue(draft, state, "value"))}">
                  </div>
                </label>`).join("")}
            </div>
          </div>
          <div class="row">
            <button class="btn primary" type="submit">Save sensor</button>
            <button class="btn" type="button" id="resetForm">New</button>
          </div>
        </form>
      </div>
      <div class="card">
        <h2>Current devices</h2>
        ${devices.length ? `<table>
          <thead><tr><th>Slug</th><th>Type</th><th>State</th></tr></thead>
          <tbody>${devices.map((device) => `
            <tr><td class="mono">${esc(device.slug)}</td><td>${esc(device.config.device_type)}</td><td>${esc(device.state)}</td></tr>
          `).join("")}</tbody>
        </table>` : `<div class="empty">No devices configured.</div>`}
      </div>
    </div>`;

  const form = root.querySelector("#deviceForm");
  const slots = root.querySelector("#slots");
  const renderSlots = () => {
    syncDraftFromForm(root);
    slots.innerHTML = (draft.fields || []).map((key) => `
      <div class="entity-slot" data-slot="${esc(key)}"></div>
    `).join("");
    slots.querySelectorAll("[data-slot]").forEach((node) => {
      const key = node.dataset.slot;
      renderEntityPicker(node, ctx, draft, key, slotCatalog[key] || {});
    });
  };
  renderSlots();

  form.elements.edit_slug.addEventListener("change", () => {
    const selected = devices.find((device) => device.slug === form.elements.edit_slug.value);
    root._draft = draftFromDevice(catalog, selected);
    ctx.rerender();
  });
  form.elements.device_type.addEventListener("change", () => {
    syncDraftFromForm(root);
    draft.slug = "";
    draft.device_type = form.elements.device_type.value;
    draft.fields = defaultFields(catalog, draft.device_type);
    draft.slots = {};
    ctx.rerender();
  });
  form.querySelectorAll('input[name="field"]').forEach((input) =>
    input.addEventListener("change", renderSlots));
  form.querySelectorAll("input, select").forEach((input) => {
    if (input.name !== "field" && input.name !== "edit_slug" && input.name !== "device_type") {
      input.addEventListener("input", () => syncDraftFromForm(root));
      input.addEventListener("change", () => syncDraftFromForm(root));
    }
  });
  root.querySelector("#resetForm").addEventListener("click", () => {
    root._draft = newDraft(catalog);
    ctx.rerender();
  });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    syncDraftFromForm(root);
    await ctx.store.setDevice({
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
    ctx.toast("Sensor saved");
    ctx.rerender();
  });
}
