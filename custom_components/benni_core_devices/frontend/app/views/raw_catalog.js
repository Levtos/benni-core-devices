import { chip, esc } from "../styles.js";

const DOMAIN_FILTERS = [
  ["", "Alle"],
  ["sensor", "sensor"],
  ["binary_sensor", "binary_sensor"],
  ["media_player", "media_player"],
  ["switch", "switch"],
  ["cover", "cover"],
  ["climate", "climate"],
  ["weather", "weather"],
  ["lock", "lock"],
];

const ROLE_FILTERS = [
  ["", "Alle Rollen"],
  ["power_meter", "power_meter"],
  ["media_player", "media_player"],
  ["opening_contact", "opening_contact"],
  ["switch_actuator", "switch_actuator"],
  ["cover", "cover"],
  ["climate", "climate"],
  ["weather", "weather"],
];

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function objectItems(value) {
  return asArray(value).filter((item) => item && typeof item === "object");
}

function normalizeEntity(row) {
  const roles = asArray(row.candidate_roles).map((role) => String(role));
  const refs = objectItems(row.used_by_contracts);
  const haystack = [
    row.entity_id,
    row.friendly_name,
    row.device_name,
    row.area_name,
    row.integration,
    row.platform,
    roles.join(" "),
  ].map((value) => String(value ?? "")).join(" ").toLowerCase();
  return { ...row, candidate_roles: roles, used_by_contracts: refs, haystack };
}

function roleChips(roles) {
  return roles.length
    ? roles.map((role) => chip("accent", role)).join(" ")
    : `<span class="muted">—</span>`;
}

function usedBySummary(refs) {
  if (!refs.length) return `<span class="muted">—</span>`;
  return refs.map((ref) => chip(ref.contract_kind === "master" ? "accent" : "info", ref.slug || ref.contract_entity_id || "contract")).join(" ");
}

function availableChip(row) {
  return row.available ? chip("ok", "available") : chip("warn", "unavailable");
}

function loadCatalog(root, ctx, filters = {}) {
  if (root._loading) return;
  root._loading = true;
  root._error = null;
  ctx.store.getRawEntityCatalog(filters)
    .then(() => {
      root._loading = false;
      ctx.rerender();
    })
    .catch((err) => {
      root._loading = false;
      root._error = String(err.message || err);
      ctx.rerender();
    });
}

function currentServerFilters(root) {
  return {
    domain: root._domainFilter || undefined,
    search: root._search || undefined,
    only_available: root._onlyAvailable === true,
  };
}

function emptyState() {
  return `
    <div class="hero">
      <div class="hicon"><ha-icon icon="mdi:database-search-outline"></ha-icon></div>
      <h2>Keine Raw Entities gefunden oder Catalog nicht verfügbar.</h2>
      <p>Der Raw Catalog ist nur Inventar und Auswahlhilfe. Er erzeugt keine Sensoren, spiegelt keine Entities und erstellt keine Contracts automatisch.</p>
    </div>`;
}

function tableHtml(rows, selectedKey) {
  if (!rows.length) return `<div class="empty">Keine Entities für die aktuellen Filter.</div>`;
  return `
    <table>
      <thead><tr>
        <th>Entity ID</th>
        <th>Friendly Name</th>
        <th>Domain</th>
        <th>State</th>
        <th>Available</th>
        <th>Device Class</th>
        <th>Unit</th>
        <th>Candidate Roles</th>
        <th>Used by Contracts</th>
      </tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr class="clickable ${row.entity_id === selectedKey ? "selected-row" : ""}" data-row="${esc(row.entity_id)}">
            <td><span class="mono">${esc(row.entity_id)}</span></td>
            <td>${esc(row.friendly_name || "—")}</td>
            <td>${esc(row.domain || "—")}</td>
            <td>${esc(row.state ?? "—")}</td>
            <td>${availableChip(row)}</td>
            <td>${esc(row.device_class || "—")}</td>
            <td>${esc(row.unit_of_measurement || "—")}</td>
            <td>${roleChips(row.candidate_roles)}</td>
            <td>${usedBySummary(row.used_by_contracts)}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function usedByRows(row) {
  const refs = row.used_by_contracts || [];
  if (!refs.length) return `<div class="muted">Keine Contracts referenzieren diese Raw Entity.</div>`;
  return `
    <table>
      <thead><tr><th>Contract Entity</th><th>Kind</th><th>Slug</th><th>Role</th><th>Key</th></tr></thead>
      <tbody>
        ${refs.map((ref) => `
          <tr>
            <td><span class="mono">${esc(ref.contract_entity_id || "—")}</span></td>
            <td>${esc(ref.contract_kind || "—")}</td>
            <td>${esc(ref.slug || "—")}</td>
            <td>${esc(ref.role || "—")}</td>
            <td>${esc(ref.key || "—")}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function detailCard(row) {
  if (!row) return `<div class="empty">Entity wählen, um Details zu sehen.</div>`;
  return `
    <div class="card">
      <div class="section-head">
        <h2>${esc(row.friendly_name || row.entity_id)}</h2>
        ${availableChip(row)}
      </div>
      <div class="warnbox" style="margin-bottom:12px">Read-only Raw Catalog. Nur Inventar und Auswahlhilfe; keine Sensor-Erzeugung, keine Spiegelung, keine automatische Contract-Erzeugung. Contract Builder folgt später.</div>
      <div class="kv"><span class="k">Entity ID</span><span class="v mono">${esc(row.entity_id || "—")}</span></div>
      <div class="kv"><span class="k">Friendly Name</span><span class="v">${esc(row.friendly_name || "—")}</span></div>
      <div class="kv"><span class="k">Domain</span><span class="v">${esc(row.domain || "—")}</span></div>
      <div class="kv"><span class="k">State</span><span class="v">${esc(row.state ?? "—")}</span></div>
      <div class="kv"><span class="k">Available</span><span class="v">${availableChip(row)}</span></div>
      <div class="kv"><span class="k">Device Class</span><span class="v">${esc(row.device_class || "—")}</span></div>
      <div class="kv"><span class="k">State Class</span><span class="v">${esc(row.state_class || "—")}</span></div>
      <div class="kv"><span class="k">Unit</span><span class="v">${esc(row.unit_of_measurement || "—")}</span></div>
      <div class="kv"><span class="k">Area</span><span class="v">${esc(row.area_name || row.area_id || "—")}</span></div>
      <div class="kv"><span class="k">Device</span><span class="v">${esc(row.device_name || row.device_id || "—")}</span></div>
      <div class="kv"><span class="k">Integration / Platform</span><span class="v">${esc(row.integration || row.platform || "—")}</span></div>
      <div class="kv"><span class="k">Last Changed</span><span class="v">${esc(row.last_changed || "—")}</span></div>
      <div class="kv"><span class="k">Last Updated</span><span class="v">${esc(row.last_updated || "—")}</span></div>
      <h2 style="margin-top:16px">Candidate Roles</h2>
      <div class="row">${roleChips(row.candidate_roles)}</div>
      <h2 style="margin-top:16px">Used by Contracts</h2>
      ${usedByRows(row)}
    </div>`;
}

function domainSelect(active) {
  return `
    <select id="rawDomainFilter" style="width:auto; min-width:170px">
      ${DOMAIN_FILTERS.map(([id, label]) => `<option value="${esc(id)}" ${active === id ? "selected" : ""}>${esc(label)}</option>`).join("")}
    </select>`;
}

function roleSelect(active) {
  return `
    <select id="rawRoleFilter" style="width:auto; min-width:190px">
      ${ROLE_FILTERS.map(([id, label]) => `<option value="${esc(id)}" ${active === id ? "selected" : ""}>${esc(label)}</option>`).join("")}
    </select>`;
}

export function render(root, ctx) {
  root.dataset.keepDraft = "false";
  const catalog = ctx.store.rawEntityCatalog;

  if (!catalog && !root._loading && !root._error) {
    loadCatalog(root, ctx, currentServerFilters(root));
  }

  if (root._loading && !catalog) {
    root.innerHTML = `<div class="empty">Raw Entity Catalog wird geladen…</div>`;
    return;
  }

  if (root._error && !catalog) {
    root.innerHTML = `
      <div class="warnbox err">Raw Entity Catalog konnte nicht geladen werden: ${esc(root._error)}</div>
      <button class="btn" type="button" id="retryRawCatalog" style="margin-top:12px">Erneut laden</button>`;
    root.querySelector("#retryRawCatalog").addEventListener("click", () => {
      root._error = null;
      loadCatalog(root, ctx, currentServerFilters(root));
      ctx.rerender();
    });
    return;
  }

  const rows = objectItems((catalog || {}).entities).map(normalizeEntity);
  if (!rows.length) {
    root.innerHTML = emptyState();
    return;
  }

  const roleFilter = root._roleFilter || "";
  const clientSearch = String(root._search || "").trim().toLowerCase();
  const visible = rows
    .filter((row) => !roleFilter || row.candidate_roles.includes(roleFilter))
    .filter((row) => !clientSearch || row.haystack.includes(clientSearch))
    .sort((a, b) => String(a.entity_id).localeCompare(String(b.entity_id)));

  if (root._sel && !rows.find((row) => row.entity_id === root._sel)) root._sel = null;
  if (!root._sel && visible.length) root._sel = visible[0].entity_id;
  const selected = rows.find((row) => row.entity_id === root._sel);
  const selectedVisible = visible.some((row) => row.entity_id === root._sel);

  root.innerHTML = `
    <div class="card muted-card" style="margin-bottom:14px">
      <div class="row spread">
        <div class="row"><ha-icon icon="mdi:database-search-outline"></ha-icon>
          <span class="muted" style="font-size:12px">Raw Catalog ist nur Inventar und Auswahlhilfe. Keine neuen Sensoren, keine Spiegelung, keine automatische Contract-Erzeugung.</span></div>
        <button class="btn small" type="button" id="refreshRawCatalog">Aktualisieren</button>
      </div>
    </div>
    <div class="stats">
      <div class="stat accent"><div class="n">${esc(rows.length)}</div><div class="l">Raw Entities</div></div>
      <div class="stat ok"><div class="n">${esc(rows.filter((row) => row.available).length)}</div><div class="l">Available</div></div>
      <div class="stat info"><div class="n">${esc(rows.filter((row) => row.used_by_contracts.length).length)}</div><div class="l">Used by Contracts</div></div>
      <div class="stat accent"><div class="n">${esc(rows.filter((row) => row.candidate_roles.length).length)}</div><div class="l">Role Candidates</div></div>
    </div>
    <div class="diag-toolbar">
      <div class="card">
        <div class="diag-search">
          <ha-icon icon="mdi:magnify"></ha-icon>
          <input id="rawSearch" type="search" autocomplete="off" spellcheck="false"
            placeholder="Suchen nach Entity ID, Friendly Name, Device, Area, Integration oder Candidate Role…"
            value="${esc(root._search || "")}">
        </div>
        <div class="toolbar-foot">
          <div class="left">
            <label class="sort-select">Domain ${domainSelect(root._domainFilter || "")}</label>
            <label class="sort-select">Candidate Role ${roleSelect(roleFilter)}</label>
            <label class="toggle"><input type="checkbox" id="rawOnlyAvailable" ${root._onlyAvailable ? "checked" : ""}> Nur verfügbare</label>
          </div>
          <span class="result-count">${visible.length} ${visible.length === 1 ? "Ergebnis" : "Ergebnisse"}</span>
        </div>
      </div>
    </div>
    <div class="split">
      <div class="card">${tableHtml(visible, root._sel)}</div>
      <div class="diag-detail">${selectedVisible ? "" : `<div class="warnbox filter-hint">Ausgewählte Entity ist durch aktuelle Filter ausgeblendet.</div>`}${detailCard(selected)}</div>
    </div>`;

  const reload = () => {
    ctx.store.rawEntityCatalog = null;
    root._error = null;
    loadCatalog(root, ctx, currentServerFilters(root));
    ctx.rerender();
  };
  root.querySelector("#refreshRawCatalog").addEventListener("click", reload);
  root.querySelector("#rawDomainFilter").addEventListener("change", (ev) => {
    root._domainFilter = ev.target.value;
    reload();
  });
  root.querySelector("#rawRoleFilter").addEventListener("change", (ev) => {
    root._roleFilter = ev.target.value;
    ctx.rerender();
  });
  root.querySelector("#rawOnlyAvailable").addEventListener("change", (ev) => {
    root._onlyAvailable = ev.target.checked;
    reload();
  });
  root.querySelectorAll("[data-row]").forEach((tr) =>
    tr.addEventListener("click", () => {
      root._sel = tr.dataset.row;
      ctx.rerender();
    }));
  const search = root.querySelector("#rawSearch");
  search.addEventListener("input", () => {
    root._search = search.value;
    root._searchFocused = true;
    root._searchCaret = search.selectionStart;
    clearTimeout(root._searchTimer);
    root._searchTimer = setTimeout(() => ctx.rerender(), 180);
  });
  search.addEventListener("blur", () => { root._searchFocused = false; });
  if (root._searchFocused) {
    search.focus();
    const pos = root._searchCaret ?? search.value.length;
    try { search.setSelectionRange(pos, pos); } catch (_err) { /* search input */ }
  }
}
