import { chip, esc, qualityKind } from "../styles.js";

// QoL-Patch: Suche, gruppierte Filter (Typ/Status/Kategorie), Sticky-Leiste +
// Sticky-Detailpanel, Sortier-Dropdown und optionale Kategorie-Gruppierung.
// Optik/Struktur sowie die bestehende Auswahl-/Detail-Logik bleiben erhalten.

const TYPE_FILTERS = [
  ["all", "Alle"],
  ["device", "Atomics"],
  ["combined", "Combineds"],
];

const STATUS_FILTERS = [
  ["all", "Alle"],
  ["err", "Fehler"],
  ["missing", "Missing"],
  ["degraded", "Degraded"],
  ["warn", "Warnungen"],
  ["ok", "OK"],
  ["available", "Available"],
];

const CATEGORY_FILTERS = [
  ["all", "Alle"],
  ["bad", "Bad"],
  ["klima", "Klima"],
  ["fenster", "Fenster/Türen"],
  ["praesenz", "Präsenz"],
  ["medien", "Medien"],
  ["strom", "Strom/Plug"],
  ["wetter", "Wetter/DWD"],
  ["licht", "Licht"],
  ["system", "System"],
  ["sonstige", "Sonstige"],
];

const CAT_LABEL = Object.fromEntries(CATEGORY_FILTERS.map(([k, l]) => [k, l]));

const SORT_OPTIONS = [
  ["attention", "Aufmerksamkeit zuerst"],
  ["name", "Name A–Z"],
  ["category", "Kategorie"],
  ["type", "Typ"],
  ["status", "Status"],
];

const SEV_RANK = { err: 0, warn: 1, ok: 2 };

// Kategorie heuristisch aus Name + Typ ableiten (Raum „Bad" schlägt Funktion,
// danach funktionale Kategorien). Keine sichere Erkennung → "sonstige".
function categorize(name, type) {
  const s = `${name} ${type}`.toLowerCase();
  const has = (re) => re.test(s);
  if (has(/\bbad\b|\bbath|dusche|\bwc\b|toilet/)) return "bad";
  if (has(/dwd|warnstufe|wetter|weather|forecast|regen|niederschlag|unwetter/)) return "wetter";
  if (has(/klima|thermostat|temperat|heiz|hvac|humid|feucht|dew|taupunkt|co2|climate|environment/)) return "klima";
  if (has(/licht|light|lampe|\blamp|strip|\bled\b|leuchte|dimmer/)) return "licht";
  if (has(/fenster|t(ü|ue)r|window|door|kontakt|contact|opening|rollo|cover|blind|rolll?aden/)) return "fenster";
  if (has(/media|medien|\btv\b|apple ?tv|sonos|player|audio|sound|\bavr\b|ps5|console|konsole|spiel|cast|musik/)) return "medien";
  if (has(/strom|plug|steckdose|power|\bwatt|socket|energie|energy|verbrauch|appliance|wasch|trockner|sp(ü|ue)l|kaffee|coffee/)) return "strom";
  if (has(/pr(ä|ae)senz|presence|anwesen|motion|bewegung|occupanc|person|\bhome\b|\baway\b|abwesen/)) return "praesenz";
  if (has(/system|update|\bsun\b|\bcore\b|version|diagnos|status/)) return "system";
  return "sonstige";
}

function rows(status) {
  const out = [];
  for (const d of status.devices || []) {
    const a = d.attrs || {};
    const quality = a.atomic_quality || (a.available ? "ok" : "unavailable");
    const cat = categorize(a.display_name || d.slug, (d.config && d.config.atomic_class) || "device");
    const row = {
      kind: "device", key: `device:${d.slug}`, slug: d.slug,
      name: a.display_name || d.slug,
      type: (d.config && d.config.atomic_class) || "device",
      state: d.state,
      available: a.available ? "available" : "unavailable",
      missing: (a.missing_required || []).length,
      reason: (a.degraded_reason || []).join(", ") || "—",
      severity: qualityKind(quality),
      degraded: (a.degraded_reason || []).length > 0 || quality === "degraded" || a.degraded === true,
      availGood: !!a.available,
      cat, catLabel: CAT_LABEL[cat],
      sources: a.source_entities || {},
      entityId: d.entity_id,
      data: d,
    };
    row.haystack = buildHaystack(row);
    out.push(row);
  }
  for (const c of status.combineds || []) {
    const a = c.attrs || {};
    const severity = a.degraded ? "warn" : (c.state == null ? "err" : "ok");
    const cat = categorize(c.display_name || c.slug, `combined ${c.output_type || ""}`);
    const row = {
      kind: "combined", key: `combined:${c.slug}`, slug: c.slug,
      name: c.display_name || c.slug,
      type: `combined/${c.output_type || "enum"}`,
      state: c.state,
      available: a.degraded ? "degraded" : "ok",
      missing: (a.missing_sources || []).length,
      reason: a.reason || "—",
      severity,
      degraded: !!a.degraded,
      availGood: !a.degraded && c.state != null,
      cat, catLabel: CAT_LABEL[cat],
      sources: a.source_entities || {},
      entityId: c.entity_id,
      data: c,
    };
    row.haystack = buildHaystack(row);
    out.push(row);
  }
  return out;
}

// Suchbarer Index: Name, Entity-ID, Typ, Kategorie, State, Reason, Quell-Entities.
function buildHaystack(r) {
  const src = Object.values(r.sources || {}).join(" ");
  return [r.name, r.entityId, r.type, r.catLabel, r.state, r.reason, src]
    .map((x) => String(x ?? "")).join(" ").toLowerCase();
}

function matchesStatus(r, f) {
  switch (f) {
    case "all": return true;
    case "err": return r.severity === "err";
    case "missing": return r.missing > 0;
    case "degraded": return r.degraded;
    case "warn": return r.severity === "warn";
    case "ok": return r.severity === "ok";
    case "available": return r.availGood;
    default: return true;
  }
}

function attentionRank(r) {
  if (r.severity === "err") return 0;
  if (r.missing > 0) return 1;
  if (r.degraded) return 2;
  if (r.severity === "warn") return 3;
  return 4;
}

const SORTERS = {
  attention: (a, b) => (attentionRank(a) - attentionRank(b)) || a.name.localeCompare(b.name),
  name: (a, b) => a.name.localeCompare(b.name),
  category: (a, b) => a.catLabel.localeCompare(b.catLabel) || a.name.localeCompare(b.name),
  type: (a, b) => a.type.localeCompare(b.type) || a.name.localeCompare(b.name),
  status: (a, b) => (SEV_RANK[a.severity] - SEV_RANK[b.severity]) || a.name.localeCompare(b.name),
};

function emptyState() {
  return `
    <div class="hero">
      <div class="hicon"><ha-icon icon="mdi:atom-variant"></ha-icon></div>
      <h2>Noch keine Atomics angelegt</h2>
      <p>Diese Werkstatt verwandelt rohe Entities in saubere Device-Atomics und Combined-Logiken. Starte mit deinem ersten Atomic — der Rest folgt geführt.</p>
      <div class="actions">
        <button class="btn primary big" data-go="builder"><ha-icon icon="mdi:plus"></ha-icon> Atomic anlegen</button>
        <button class="btn big" data-go="import_export">Import starten</button>
        <button class="btn ghost big" data-go="combined">Combined später erstellen</button>
      </div>
    </div>`;
}

function detailCard(row) {
  const d = row.data;
  const a = d.attrs || {};
  if (row.kind === "device") {
    const slotEntities = a.source_entities || {};
    const slotStates = a.source_states || {};
    const slotAvail = a.source_available || {};
    const slotRows = Object.keys(slotEntities).map((k) => `
      <div class="kv"><span class="k">${esc(k)}</span>
        <span class="v">${chip(slotAvail[k] ? "ok" : "err", esc(slotStates[k] ?? "—"))}
        <span class="mono">${esc(slotEntities[k])}</span></span></div>`).join("");
    const missing = (a.missing_required || []).map((m) => chip("warn", m)).join(" ");
    const reasons = (a.degraded_reason || []).map((r) => chip("warn", r)).join(" ");
    const consumes = (a.consumes || []).map((c) => `<span class="mono">${esc(c)}</span>`).join("<br>");
    const consumedBy = (d.consumed_by || []).map((c) => chip("accent", c)).join(" ");
    const sourceWarn = (d.warnings || []).map((w) => `<li>${esc(w)}</li>`).join("");
    return `
      <div class="card">
        <div class="section-head"><h2>${esc(row.name)}</h2>${chip(row.severity, esc(a.atomic_quality || row.available))}</div>
        <div class="kv"><span class="k">Sensor</span><span class="v mono">${esc(d.entity_id)}</span></div>
        <div class="kv"><span class="k">State</span><span class="v">${esc(d.state)}</span></div>
        <div class="kv"><span class="k">Powered</span><span class="v">${esc(a.powered)}</span></div>
        <div class="kv"><span class="k">Power state</span><span class="v">${esc(a.power_state)}</span></div>
        <div class="kv"><span class="k">Source</span><span class="v">${esc(a.power_source)}</span></div>
        <div class="kv"><span class="k">watt_disagrees</span><span class="v">${esc(a.watt_disagrees)}</span></div>
        ${missing ? `<div style="margin-top:10px"><div class="k">Fehlende Pflichtrollen</div><div class="row" style="margin-top:6px">${missing}</div></div>` : ""}
        ${reasons ? `<div style="margin-top:10px"><div class="k">Degraded</div><div class="row" style="margin-top:6px">${reasons}</div></div>` : ""}
        ${sourceWarn ? `<div class="warnbox" style="margin-top:10px">Problematische Quellen:<ul>${sourceWarn}</ul></div>` : ""}
        <h2 style="margin-top:16px">Quellen</h2>
        ${slotRows || `<div class="muted">Keine belegten Quellen.</div>`}
        <h2 style="margin-top:16px">Versorgung / Abhängigkeiten</h2>
        <div class="kv"><span class="k">consumes</span><span class="v">${consumes || "—"}</span></div>
        <div style="margin-top:8px"><div class="k">Verwendet in Combineds</div><div class="row" style="margin-top:6px">${consumedBy || `<span class="muted">—</span>`}</div></div>
      </div>`;
  }
  const srcEntities = a.source_entities || {};
  const srcStates = a.source_states || {};
  const srcAvail = a.source_available || {};
  const srcRows = Object.keys(srcEntities).map((k) => `
    <div class="kv"><span class="k">${esc(k)}</span>
      <span class="v">${chip(srcAvail[k] ? "ok" : "err", esc(srcStates[k] ?? "—"))}
      <span class="mono">${esc(srcEntities[k])}</span></span></div>`).join("");
  const legend = Object.entries(a.code_legend || {})
    .map(([code, label]) => `<div class="kv"><span class="k mono">${esc(code)}</span><span class="v">${esc(label)}</span></div>`).join("");
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

const ROW_TPL = (r, selKey) => `
  <tr class="clickable ${r.key === selKey ? "selected-row" : ""}" data-row="${esc(r.key)}">
    <td>${esc(r.name)}</td>
    <td class="muted">${esc(r.type)}</td>
    <td>${esc(r.state)}</td>
    <td class="s-${r.severity}">${esc(r.available)}</td>
    <td>${r.missing ? chip("warn", r.missing) : "0"}</td>
    <td class="muted">${esc(r.reason)}</td>
  </tr>`;

function tableHtml(visible, grouped, collapsed, selKey) {
  const head = `<thead><tr><th>Name</th><th>Typ</th><th>State</th><th>Avail</th><th>Missing</th><th>Reason</th></tr></thead>`;
  if (!grouped) {
    return `<table>${head}<tbody>${visible.map((r) => ROW_TPL(r, selKey)).join("")}</tbody></table>`;
  }
  // Gruppiert: pro Kategorie ein <tbody> mit klickbarer, einklappbarer Kopfzeile.
  const order = CATEGORY_FILTERS.map(([k]) => k).filter((k) => k !== "all");
  const byCat = new Map();
  for (const r of visible) {
    if (!byCat.has(r.cat)) byCat.set(r.cat, []);
    byCat.get(r.cat).push(r);
  }
  const groups = order.filter((k) => byCat.has(k)).map((k) => {
    const list = byCat.get(k);
    const isOpen = !collapsed.has(k);
    const body = isOpen ? list.map((r) => ROW_TPL(r, selKey)).join("") : "";
    return `<tbody>
      <tr class="group-row ${isOpen ? "open" : ""}" data-cat="${esc(k)}">
        <td colspan="6">${esc(CAT_LABEL[k])}<span class="cnt">(${list.length})</span></td>
      </tr>${body}</tbody>`;
  }).join("");
  return `<table>${head}${groups}</table>`;
}

export function render(root, ctx) {
  const status = ctx.store.status;
  if (!status || status._error) {
    root.innerHTML = `<div class="empty">Status ist noch nicht verfügbar.</div>`;
    return;
  }
  const devices = status.devices || [];
  const combineds = status.combineds || [];

  // Empty-State: freundlicher Einstieg statt nackter Nullen.
  if (!devices.length && !combineds.length) {
    root.innerHTML = `
      ${emptyState()}
      <div class="stats secondary" style="margin-top:18px">
        <div class="stat"><div class="n">0</div><div class="l">Devices</div></div>
        <div class="stat"><div class="n">0</div><div class="l">Combineds</div></div>
        <div class="stat"><div class="n">0</div><div class="l">Ready</div></div>
      </div>`;
    root.querySelectorAll("[data-go]").forEach((b) =>
      b.addEventListener("click", () => ctx.navigate(b.dataset.go)));
    return;
  }

  // State (auf root, überlebt Re-Render + Live-Poll).
  const statusFilter = root._filter || "all";
  const typeFilter = root._typeFilter || "all";
  const catFilter = root._catFilter || "all";
  const sort = root._sort || "attention";
  const grouped = root._group === true;
  if (!(root._collapsed instanceof Set)) root._collapsed = new Set();
  const query = (root._search || "").trim().toLowerCase();

  const all = rows(status).sort(SORTERS[sort] || SORTERS.attention);

  const missing = devices.reduce((n, d) => n + ((d.attrs && d.attrs.missing_required) || []).length, 0);
  const degraded = devices.filter((d) => d.attrs && d.attrs.degraded).length;
  const ready = all.filter((r) => r.severity === "ok").length;
  const errors = all.filter((r) => r.severity === "err").length;
  const attention = all.filter((r) => r.severity !== "ok").length;

  const visible = all.filter((r) =>
    (typeFilter === "all" || r.kind === typeFilter) &&
    matchesStatus(r, statusFilter) &&
    (catFilter === "all" || r.cat === catFilter) &&
    (query === "" || r.haystack.includes(query)));

  // Auswahl stabil halten: nur löschen, wenn die Entität wirklich verschwunden
  // ist (nicht bloß weggefiltert). Initiale Auswahl = erste sichtbare Zeile.
  if (root._sel && !all.find((r) => r.key === root._sel)) root._sel = null;
  if (!root._sel && visible.length) root._sel = visible[0].key;
  const selectedRow = all.find((r) => r.key === root._sel);
  const selectedVisible = !!visible.find((r) => r.key === root._sel);

  const attentionBanner = attention
    ? `<div class="warnbox" style="margin-bottom:14px"><b>${attention}</b> Atomic(s) brauchen Aufmerksamkeit — oben in der Liste.</div>`
    : `<div class="okbox" style="margin-bottom:14px">Alles in Ordnung — keine fehlenden oder degradierten Quellen.</div>`;

  const chipRow = (label, items, attr, active) => `
    <div class="filter-group">
      <span class="fg-label">${esc(label)}</span>
      <div class="filters" aria-label="${esc(label)}">
        ${items.map(([id, lbl]) =>
          `<button data-${attr}="${id}" class="${active === id ? "active" : ""}">${esc(lbl)}</button>`).join("")}
      </div>
    </div>`;

  const detailInner = selectedRow
    ? `${selectedVisible ? "" : `<div class="warnbox filter-hint">Ausgewählte Entität ist durch aktuelle Filter ausgeblendet.</div>`}
       ${detailCard(selectedRow)}`
    : `<div class="empty">Eintrag wählen, um Details zu sehen.</div>`;

  root.innerHTML = `
    <div class="stats">
      <div class="stat accent"><div class="n">${devices.length}</div><div class="l">Devices</div></div>
      <div class="stat info"><div class="n">${combineds.length}</div><div class="l">Combineds</div></div>
      <div class="stat ${missing ? "warn" : "ok"}"><div class="n">${missing}</div><div class="l">Missing Required</div></div>
      <div class="stat ${degraded ? "warn" : "ok"}"><div class="n">${degraded}</div><div class="l">Degraded</div></div>
      <div class="stat ok"><div class="n">${ready}</div><div class="l">Ready</div></div>
      <div class="stat ${errors ? "err" : "ok"}"><div class="n">${errors}</div><div class="l">Fehler</div></div>
    </div>
    ${attentionBanner}
    <div class="diag-toolbar">
      <div class="card">
        <div class="diag-search">
          <ha-icon icon="mdi:magnify"></ha-icon>
          <input id="diag-search-input" type="search" autocomplete="off" spellcheck="false"
            placeholder="Suchen nach Name, Entity ID, Reason oder Quelle…"
            value="${esc(root._search || "")}">
        </div>
        ${chipRow("Typ", TYPE_FILTERS, "type-filter", typeFilter)}
        ${chipRow("Status", STATUS_FILTERS, "filter", statusFilter)}
        ${chipRow("Kategorie", CATEGORY_FILTERS, "cat-filter", catFilter)}
        <div class="toolbar-foot">
          <div class="left">
            <label class="sort-select">Sortierung
              <select id="diag-sort">
                ${SORT_OPTIONS.map(([id, lbl]) =>
                  `<option value="${id}" ${sort === id ? "selected" : ""}>${esc(lbl)}</option>`).join("")}
              </select>
            </label>
            <label class="toggle"><input type="checkbox" id="diag-group" ${grouped ? "checked" : ""}> Nach Kategorie gruppieren</label>
          </div>
          <span class="result-count">${visible.length} ${visible.length === 1 ? "Ergebnis" : "Ergebnisse"}</span>
        </div>
      </div>
    </div>
    <div class="split">
      <div class="card">
        ${visible.length ? tableHtml(visible, grouped, root._collapsed, root._sel)
          : `<div class="empty">Keine Einträge für die aktuellen Filter.</div>`}
      </div>
      <div id="detail" class="diag-detail">${detailInner}</div>
    </div>`;

  // Detail-Panel-Höhe an die Sticky-Leiste koppeln (Viewport-relativ scrollbar).
  const tb = root.querySelector(".diag-toolbar");
  if (tb) root.style.setProperty("--toolbar-h", `${tb.offsetHeight}px`);

  // Filter-Chips
  root.querySelectorAll("[data-filter]").forEach((b) =>
    b.addEventListener("click", () => { root._filter = b.dataset.filter; ctx.rerender(); }));
  root.querySelectorAll("[data-type-filter]").forEach((b) =>
    b.addEventListener("click", () => { root._typeFilter = b.dataset.typeFilter; ctx.rerender(); }));
  root.querySelectorAll("[data-cat-filter]").forEach((b) =>
    b.addEventListener("click", () => { root._catFilter = b.dataset.catFilter; ctx.rerender(); }));

  // Sortierung + Gruppierung
  const sortSel = root.querySelector("#diag-sort");
  if (sortSel) sortSel.addEventListener("change", () => { root._sort = sortSel.value; ctx.rerender(); });
  const groupChk = root.querySelector("#diag-group");
  if (groupChk) groupChk.addEventListener("change", () => { root._group = groupChk.checked; ctx.rerender(); });

  // Kategorie-Gruppen ein-/ausklappen
  root.querySelectorAll("tr.group-row").forEach((tr) =>
    tr.addEventListener("click", () => {
      const k = tr.dataset.cat;
      if (root._collapsed.has(k)) root._collapsed.delete(k); else root._collapsed.add(k);
      ctx.rerender();
    }));

  // Zeilen-Auswahl
  root.querySelectorAll("[data-row]").forEach((tr) =>
    tr.addEventListener("click", () => { root._sel = tr.dataset.row; ctx.rerender(); }));

  // Live-Suche mit Debounce; Fokus + Cursor über Re-Render hinweg erhalten.
  const search = root.querySelector("#diag-search-input");
  if (search) {
    search.addEventListener("input", () => {
      root._search = search.value;
      root._searchFocused = true;
      root._searchCaret = search.selectionStart;
      clearTimeout(root._searchTimer);
      root._searchTimer = setTimeout(() => ctx.rerender(), 200);
    });
    search.addEventListener("blur", () => { root._searchFocused = false; });
    if (root._searchFocused) {
      search.focus();
      const pos = root._searchCaret ?? search.value.length;
      try { search.setSelectionRange(pos, pos); } catch (_e) { /* search input */ }
    }
  }
}
