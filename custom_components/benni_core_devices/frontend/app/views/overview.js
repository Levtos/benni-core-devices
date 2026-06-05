import { chip, esc } from "../styles.js";

function attrsRows(attrs) {
  return Object.entries(attrs || {}).map(([key, value]) => `
    <div class="kv"><span class="k">${esc(key)}</span><span class="v">${esc(value)}</span></div>
  `).join("");
}

export function render(root, ctx) {
  const status = ctx.store.status;
  if (!status || status._error) {
    root.innerHTML = `<div class="empty">Status is not available yet.</div>`;
    return;
  }
  const devices = status.devices || [];
  const groups = status.groups || [];
  root.innerHTML = `
    <div class="grid cols-3">
      <div class="card"><h2>Route</h2><div class="kv"><span class="k">Profile</span><span class="v">${esc(status.profile_label || status.profile)}</span></div></div>
      <div class="card"><h2>Devices</h2><div class="kv"><span class="k">Configured</span><span class="v">${devices.length}</span></div></div>
      <div class="card"><h2>Groups</h2><div class="kv"><span class="k">Configured</span><span class="v">${groups.length}</span></div></div>
    </div>
    <div class="grid" style="margin-top:14px">
      ${devices.length ? devices.map((device) => {
        const attrs = device.attrs || {};
        return `<div class="card">
          <div class="row" style="justify-content:space-between">
            <h2>${esc(device.config.display_name || device.slug)}</h2>
            <div class="row">
              ${chip(attrs.available ? "ok" : "warn", attrs.available ? "available" : "unavailable")}
              ${chip(attrs.powered ? "ok" : "info", attrs.powered ? "powered" : "off")}
              <button class="btn danger" data-remove="${esc(device.slug)}">Remove</button>
            </div>
          </div>
          <div class="grid cols-2">
            <div>
              <div class="kv"><span class="k">Sensor</span><span class="v mono">sensor.${esc(status.profile)}_device_${esc(device.slug)}</span></div>
              <div class="kv"><span class="k">State</span><span class="v">${esc(device.state)}</span></div>
              <div class="kv"><span class="k">Type</span><span class="v">${esc(device.config.device_type)}</span></div>
              <div class="kv"><span class="k">Power state</span><span class="v">${esc(attrs.power_state)}</span></div>
              <div class="kv"><span class="k">Source</span><span class="v">${esc(attrs.power_source)}</span></div>
            </div>
            <div>${attrsRows(attrs)}</div>
          </div>
        </div>`;
      }).join("") : `<div class="empty">No devices configured.</div>`}
    </div>`;

  root.querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", async () => {
      await ctx.store.removeDevice(button.dataset.remove);
      ctx.toast("Device removed");
      ctx.rerender();
    });
  });
}

