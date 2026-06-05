import { chip, esc, qualityKind } from "../styles.js";

const FILTERS = [
  ["all", "Alle"],
  ["err", "Fehler"],
  ["warn", "Warnungen"],
  ["ok", "OK"],
];

// Normalisiert Devices + Combineds zu einer einheitlichen Diagnosezeile.
function rows(status) {
  const out = [];
  for (const d of status.devices || []) {
    const a = d.attrs || {};
    const quality = a.atomic_quality || (a.available ? "ok" : "unavailable");
    out.push({
      kind: "device",
      key: `device:${d.slug}`,
      slug: d.slug,
      name: a.display_name || d.slug,
      type: (d.config && d.config.device_type) || "device",
      state: d.state,
      available: a.available ? "available" : "unavailable",
      missing: (a.missing_sources || []).length,
      reason: (a.degraded_reason || []).join(", ") || "—",
      severity: qualityKind(quality),
      data: d,
    });
  }
  for (const c of status.combineds || []) {
    const a = c.attrs || {};
    const severity = a.degraded ? "warn" : (c.state == null ? "err" : "ok");
    out.push({
      kind: "combined",
      key: `combined:${c.slug}`,
      slug: c.slug,
      name: c.display_name || c.slug,
      type: `combined/${c.output_type || "enum"}`,
      state: c.state,
      available: a.degraded ? "degraded" : "ok",
      missing: (a.missing_sources || []).length,
      reason: a.reason || "—",
      severity,
      data: c,
    });
  }
  return out;
}

const SEV_RANK = { err: 0, warn: 1, ok: 2 };

function detailCard(row, status) {
  const d = row.data;
  const a = d.attrs || {};
  if (row.kind === "device") {
    const slotEntities = a.slot_entities || {};
    const slotStates = a.slot_states || {};
    const slotAvail = a.slot_available || {};
    const slotRows = Object.keys(slotEntities).map((k) => `
      <div class="kv">
        <span class="k">${esc(k)}</span>
        <span class="v">${chip(slotAvail[k] ? "ok" : "err", esc(slotStates[k] ?? "—"))}
        <span class="mono">${esc(slotEntities[k])}</span></span>
      </div>`).join("");
    const missing = (a.missing_sources || []).map((m) => chip("warn", m)).join(" ");
    const reasons = (a.degraded_reason || []).map((r) => chip("warn", r)).join(" ");
    const consumes = (a.consumes || []).map((c) => `<span class="mono">${esc(c)}</span>`).join("<br>");
    const consumedBy = (d.consumed_by || []).map((c) => chip("accent", c)).join(" ");
    const sourceWarn = (d.warnings || []).map((w) => `<li>${esc(w)}</li>`).join("");
    return `
      <div class="card">
        <div class="section-head">
          <h2>${esc(row.name)}</h2>
          ${chip(row.severity, esc(a.atomic_quality || row.available))}
        </div>
        <div class="kv"><span class="k">Sensor</span><span class="v mono">${esc(d.entity_id)}</span></div>
        <div class="kv"><span class="k">State</span><span class="v">${esc(d.state)}</span></div>
        <div class="kv"><span class="k">Powered</span><span class="v">${esc(a.powered)}</span></div>
        <div class="kv"><span class="k">Power state</span><span class="v">${esc(a.power_state)}</span></div>
        <div class="kv"><span class="k">Source</span><span class="v">${esc(a.power_source)}</span></div>
        <div class="kv"><span class="k">watt_disagrees</span><span class="v">${esc(a.watt_disagrees)}</span></div>
        <div class="kv"><span class="k">Last change</span><span class="v">${esc(a.last_powered_change || "—")}</span></div>
        ${missing ? `<div style="margin-top:10px"><div class="k">Fehlende Slots</div><div class="row" style="margin-top:6px">${missing}</div></div>` : ""}
        ${reasons ? `<div style="margin-top:10px"><div class="k">Degraded</div><div class="row" style="margin-top:6px">${reasons}</div></div>` : ""}
        ${sourceWarn ? `<div class="warnbox" style="margin-top:10px">Problematische Quellen:<ul>${sourceWarn}</ul></div>` : ""}
        <h2 style="margin-top:16px">Slots</h2>
        ${slotRows || `<div class="muted">Keine belegten Slots.</div>`}
        <h2 style="margin-top:16px">Versorgung / Abhängigkeiten</h2>
        <div class="kv"><span class="k">consumes</span><span class="v">${consumes || "—"}</span></div>
        <div style="margin-top:8px"><div class="k">Verwendet in Combineds</div><div class="row" style="margin-top:6px">${consumedBy || `<span class="muted">—</span>`}</div></div>
      </div>`;
  }
  // Combined
  const srcEntities = a.source_entities || {};
  const srcStates = a.source_states || {};
  const srcAvail = a.source_available || {};
  const srcRows = Object.keys(srcEntities).map((k) => `
    <div class="kv">
      <span class="k">${esc(k)}</span>
      <span class="v">${chip(srcAvail[k] ? "ok" : "err", esc(srcStates[k] ?? "—"))}
      <span class="mono">${esc(srcEntities[k])}</span></span>
    </div>`).join("");
  const legend = Object.entries(a.code_legend || {})
    .map(([code, label]) => `<div class="kv"><span class="k mono">${esc(code)}</span><span class="v">${esc(label)}</span></div>`)
    .join("");
  const derived = (d.derived || []).map((x) =>
    `<div class="kv"><span class="k">${esc(x.name)}</span><span class="v">${chip(x.state ? "accent" : "info", x.state ? "on" : "off")}</span></div>`).join("");
  return `
    <div class="card">
      <div class="section-head"><h2>${esc(row.name)}</h2>${chip(row.severity, esc(d.output_type))}</div>
      <div class="kv"><span class="k">Sensor</span><span class="v mono">${esc(d.entity_id)}</span></div>
      <div class="kv"><span class="k">Output</span><span class="v">${esc(d.state)}</span></div>
      <div class="kv"><span class="k">Reason</span><span class="v">${esc(a.reason)}</span></div>
      <h2 style="margin-top:16px">Quellen</h2>
      ${srcRows || `<div class="muted">Keine Quellen.</div>`}
      ${legend ? `<h2 style="margin-top:16px">Code-Legende</h2>${legend}` : ""}
      ${derived ? `<h2 style="margin-top:16px">Derived</h2>${derived}` : ""}
    </div>`;
}

export function render(root, ctx) {
  const status = ctx.store.status;
  if (!status || status._error) {
    root.innerHTML = `<div class="empty">Status ist noch nicht verfügbar.</div>`;
    return;
  }
  const all = rows(status).sort((a, b) =>
    (SEV_RANK[a.severity] - SEV_RANK[b.severity]) || a.name.localeCompare(b.name));
  const filter = root._filter || "all";
  const devices = status.devices || [];
  const combineds = status.combineds || [];
  const missing = devices.reduce((n, d) => n + ((d.attrs && d.attrs.missing_sources) || []).length, 0);
  const degraded = devices.filter((d) => d.attrs && d.attrs.degraded).length;
  const ready = all.filter((r) => r.severity === "ok").length;
  const errors = all.filter((r) => r.severity === "err").length;

  const visible = all.filter((r) => filter === "all" || r.severity === filter);
  if (root._sel && !all.find((r) => r.key === root._sel)) root._sel = null;
  if (!root._sel && visible.length) root._sel = visible[0].key;
  const selected = all.find((r) => r.key === root._sel);

  root.innerHTML = `
    <div class="stats">
      <div class="stat accent"><div class="n">${devices.length}</div><div class="l">Devices</div></div>
      <div class="stat info"><div class="n">${combineds.length}</div><div class="l">Combineds</div></div>
      <div class="stat warn"><div class="n">${missing}</div><div class="l">Missing Sources</div></div>
      <div class="stat ${degraded ? "warn" : "ok"}"><div class="n">${degraded}</div><div class="l">Degraded</div></div>
      <div class="stat ok"><div class="n">${ready}</div><div class="l">Ready</div></div>
      <div class="stat ${errors ? "err" : "ok"}"><div class="n">${errors}</div><div class="l">Fehler</div></div>
    </div>
    <div class="split">
      <div class="card">
        <div class="section-head">
          <h2>Atomics &amp; Combineds</h2>
          <div class="filters">
            ${FILTERS.map(([id, label]) =>
              `<button data-filter="${id}" class="${filter === id ? "active" : ""}">${esc(label)}</button>`).join("")}
          </div>
        </div>
        ${visible.length ? `<table>
          <thead><tr><th>Name</th><th>Typ</th><th>State</th><th>Avail</th><th>Missing</th><th>Reason</th></tr></thead>
          <tbody>${visible.map((r) => `
            <tr class="clickable ${r.key === root._sel ? "selected-row" : ""}" data-row="${esc(r.key)}">
              <td>${esc(r.name)}</td>
              <td class="muted">${esc(r.type)}</td>
              <td>${esc(r.state)}</td>
              <td class="s-${r.severity}">${esc(r.available)}</td>
              <td>${r.missing ? chip("warn", r.missing) : "0"}</td>
              <td class="muted">${esc(r.reason)}</td>
            </tr>`).join("")}</tbody>
        </table>` : `<div class="empty">Keine Einträge für diesen Filter.</div>`}
      </div>
      <div id="detail">${selected ? detailCard(selected, status) : `<div class="empty">Eintrag wählen.</div>`}</div>
    </div>`;

  root.querySelectorAll("[data-filter]").forEach((b) =>
    b.addEventListener("click", () => { root._filter = b.dataset.filter; ctx.rerender(); }));
  root.querySelectorAll("[data-row]").forEach((tr) =>
    tr.addEventListener("click", () => { root._sel = tr.dataset.row; ctx.rerender(); }));
}
