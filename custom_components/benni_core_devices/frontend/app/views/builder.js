import { esc } from "../styles.js";

const WATT_ROWS = [
  ["off", "watt_off"],
  ["idle", "watt_idle"],
  ["playing", "watt_playing"],
];

function entityOptions(hass, domains) {
  const set = new Set(domains || []);
  return Object.keys((hass && hass.states) || {})
    .filter((entityId) => !set.size || set.has(entityId.split(".")[0]))
    .sort()
    .map((entityId) => `<option value="${esc(entityId)}"></option>`)
    .join("");
}

function selectedFields(catalog, type) {
  const found = (catalog.device_types || []).find((item) => item.value === type);
  return new Set((found && found.default_fields) || []);
}

function bucketValue(device, state, key) {
  const bucket = ((device && device.config && device.config.watt_buckets) || [])
    .find((item) => item.state === state);
  if (!bucket) return "";
  return key === "op" ? (bucket.op || "<=") : (bucket.value ?? "");
}

export function render(root, ctx) {
  const catalog = ctx.store.catalog || {};
  const status = ctx.store.status || {};
  const devices = status.devices || [];
  const activeSlug = root.dataset.editSlug || "";
  const editing = devices.find((item) => item.slug === activeSlug);
  const editConf = editing ? editing.config : {};
  const type = editConf.device_type || (catalog.device_types && catalog.device_types[0] && catalog.device_types[0].value) || "tv";
  const defaults = selectedFields(catalog, type);
  const activeFields = new Set(editConf.fields || [...defaults]);
  const slotCatalog = catalog.slot_catalog || {};

  root.innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <h2>${editing ? "Update sensor" : "Create sensor"}</h2>
        <form id="deviceForm" class="form">
          <label>Existing
            <select name="edit_slug">
              <option value="">New device</option>
              ${devices.map((device) => `<option value="${esc(device.slug)}" ${device.slug === activeSlug ? "selected" : ""}>${esc(device.config.display_name || device.slug)}</option>`).join("")}
            </select>
          </label>
          <label>Name
            <input name="display_name" value="${esc(editConf.display_name || "")}" required>
          </label>
          <label>Type
            <select name="device_type">
              ${(catalog.device_types || []).map((item) =>
                `<option value="${esc(item.value)}" ${item.value === type ? "selected" : ""}>${esc(item.label)}</option>`).join("")}
            </select>
          </label>
          <div class="fields">
            ${Object.entries(slotCatalog).map(([key, spec]) => `
              <label class="fieldcheck">
                <input type="checkbox" name="field" value="${esc(key)}" ${activeFields.has(key) ? "checked" : ""}>
                <span>${esc(spec.label || key)} <span class="muted mono">${esc((spec.domains || []).join(","))}</span></span>
              </label>`).join("")}
          </div>
          <div id="slots"></div>
          <div class="grid cols-3">
            <label>On threshold W
              <input name="watt_threshold_on" type="number" min="0" max="5000" value="${esc(editConf.watt_threshold_on ?? catalog.defaults?.watt_threshold_on ?? 5)}">
            </label>
            <label>Sticky seconds
              <input name="sticky_hold_seconds" type="number" min="0" max="3600" value="${esc(editConf.sticky_hold_seconds ?? catalog.defaults?.sticky_hold_seconds ?? 30)}">
            </label>
            <label>Secondary sensors
              <select name="expose_secondary_sensors">
                <option value="false" ${editConf.expose_secondary_sensors ? "" : "selected"}>Off</option>
                <option value="true" ${editConf.expose_secondary_sensors ? "selected" : ""}>On</option>
              </select>
            </label>
          </div>
          <div class="card" style="padding:12px">
            <h2>Watt buckets</h2>
            <div class="grid cols-3">
              ${WATT_ROWS.map(([state, prefix]) => `
                <label>${esc(state)}
                  <div class="row">
                    <select name="${prefix}_op" style="max-width:88px">
                      ${(catalog.watt_operators || ["<", "<=", "=", ">", ">="]).map((op) =>
                        `<option value="${esc(op)}" ${bucketValue(editing, state, "op") === op ? "selected" : ""}>${esc(op)}</option>`).join("")}
                    </select>
                    <input name="${prefix}_value" type="number" step="0.1" min="0" value="${esc(bucketValue(editing, state, "value"))}">
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
    const fields = [...form.querySelectorAll('input[name="field"]:checked')].map((input) => input.value);
    slots.innerHTML = fields.map((key) => {
      const spec = slotCatalog[key] || {};
      const value = editConf[key] || "";
      const listId = `entities_${key}`;
      return `<label>${esc(spec.label || key)}
        <input name="slot_${esc(key)}" value="${esc(value)}" list="${esc(listId)}">
        <datalist id="${esc(listId)}">${entityOptions(ctx.hass, spec.domains || [])}</datalist>
      </label>`;
    }).join("");
  };
  renderSlots();

  form.elements.edit_slug.addEventListener("change", () => {
    root.dataset.editSlug = form.elements.edit_slug.value;
    ctx.rerender();
  });
  form.elements.device_type.addEventListener("change", () => {
    delete root.dataset.editSlug;
    const nextDefaults = selectedFields(catalog, form.elements.device_type.value);
    form.querySelectorAll('input[name="field"]').forEach((input) => {
      input.checked = nextDefaults.has(input.value);
    });
    renderSlots();
  });
  form.querySelectorAll('input[name="field"]').forEach((input) =>
    input.addEventListener("change", renderSlots));
  root.querySelector("#resetForm").addEventListener("click", () => {
    delete root.dataset.editSlug;
    ctx.rerender();
  });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fields = [...form.querySelectorAll('input[name="field"]:checked')].map((input) => input.value);
    const slotsPayload = {};
    for (const key of fields) {
      slotsPayload[key] = form.elements[`slot_${key}`]?.value || "";
    }
    const watt_buckets = WATT_ROWS
      .map(([state, prefix]) => ({
        state,
        op: form.elements[`${prefix}_op`].value,
        value: form.elements[`${prefix}_value`].value,
      }))
      .filter((item) => item.value !== "")
      .map((item) => ({ state: item.state, op: item.op, value: Number(item.value) }));
    await ctx.store.setDevice({
      slug: activeSlug || undefined,
      device_type: form.elements.device_type.value,
      display_name: form.elements.display_name.value,
      fields,
      slots: slotsPayload,
      watt_threshold_on: Number(form.elements.watt_threshold_on.value || 5),
      sticky_hold_seconds: Number(form.elements.sticky_hold_seconds.value || 30),
      expose_secondary_sensors: form.elements.expose_secondary_sensors.value === "true",
      watt_buckets,
    });
    delete root.dataset.editSlug;
    ctx.toast("Sensor saved");
    ctx.rerender();
  });
}

