import { chip, esc } from "../styles.js";

const FILTERS = [
  ["all", "Alle"],
  ["masters", "Masters"],
  ["device_master", "Device Masters"],
  ["domain_master", "Domain Masters"],
  ["fusion_context", "Fusion/Context"],
  ["mixed", "Mixed"],
  ["legacy_device", "Legacy Devices"],
  ["legacy_combined", "Legacy Combineds"],
  ["degraded", "Degraded"],
  ["missing", "Missing Required"],
];

const MIGRATION_HINTS = {
  target: "Ziel-Contract",
  legacy_bridge: "Kompatibilitätsbrücke",
  retire_candidate: "späterer Rückbaukandidat",
  unknown: "manuell prüfen",
};

const GROUP_RANK = { masters: 0, legacy_devices: 1, legacy_combineds: 2 };

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function objectItems(value) {
  return asArray(value).filter((item) => item && typeof item === "object");
}

function kindLabel(kind) {
  return {
    device_master: "Device Master",
    domain_master: "Domain Master",
    fusion_context: "Fusion/Context",
    mixed: "Mixed",
    legacy_device: "Legacy Device",
    legacy_combined: "Legacy Combined",
    unknown: "Unknown",
  }[kind] || kind || "unknown";
}

function kindChip(kind) {
  if (kind === "legacy_device" || kind === "legacy_combined") return chip("info", kindLabel(kind));
  if (kind === "unknown") return chip("warn", "Unknown");
  if (kind === "mixed") return chip("warn", "Mixed");
  return chip("accent", kindLabel(kind));
}

function migrationChip(status) {
  if (status === "target") return chip("ok", "target");
  if (status === "retire_candidate") return chip("warn", "retire_candidate");
  if (status === "legacy_bridge") return chip("info", "legacy_bridge");
  return chip("warn", status || "unknown");
}

function qualityChip(row) {
  if (row.degraded) return chip("warn", row.source_quality || "degraded");
  if (row.source_quality === "ok") return chip("ok", "ok");
  return chip("info", row.source_quality || "unknown");
}

function statusText(row) {
  if (row.degraded) return "degraded";
  if (row.missing_required_count > 0) return "missing";
  return "ok";
}

function statusKind(row) {
  if (row.degraded) return "warn";
  if (row.missing_required_count > 0) return "warn";
  return "ok";
}

function flattenCatalog(catalog) {
  const rows = [];
  for (const item of objectItems(catalog.masters)) {
    rows.push({ ...item, group: "masters" });
  }
  for (const item of objectItems(catalog.legacy_devices)) {
    rows.push({ ...item, group: "legacy_devices", contract_kind: "legacy_device" });
  }
  for (const item of objectItems(catalog.legacy_combineds)) {
    rows.push({ ...item, group: "legacy_combineds", contract_kind: "legacy_combined" });
  }
  return rows.map((row) => {
    const sourceText = objectItems(row.sources)
      .map((source) => [source.role, source.key, source.entity, source.attribute].filter(Boolean).join(" "))
      .join(" ");
    return {
      ...row,
      key: `${row.group}:${row.slug}`,
      haystack: [
        row.display_name,
        row.entity_id,
        row.slug,
        row.contract_kind,
        row.migration_status,
        row.source_quality,
        sourceText,
      ].map((value) => String(value ?? "")).join(" ").toLowerCase(),
    };
  });
}

function matchesFilter(row, filter) {
  switch (filter) {
    case "all": return true;
    case "masters": return row.group === "masters";
    case "legacy_device": return row.contract_kind === "legacy_device";
    case "legacy_combined": return row.contract_kind === "legacy_combined";
    case "degraded": return !!row.degraded;
    case "missing": return Number(row.missing_required_count || 0) > 0;
    case "device_master":
    case "domain_master":
    case "fusion_context":
    case "mixed":
      return row.contract_kind === filter;
    default:
      return true;
  }
}

function loadCatalog(root, ctx) {
  if (root._loading) return;
  root._loading = true;
  root._error = null;
  ctx.store.getContractCatalog()
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

function filterBar(active) {
  return `
    <div class="filters" aria-label="Contract Filter">
      ${FILTERS.map(([id, label]) =>
        `<button data-filter="${esc(id)}" class="${active === id ? "active" : ""}">${esc(label)}</button>`
      ).join("")}
    </div>`;
}

function tableHtml(rows, selectedKey) {
  if (!rows.length) return `<div class="empty">Keine Einträge für die aktuellen Filter.</div>`;
  return `
    <table>
      <thead><tr>
        <th>Name / Entity ID</th>
        <th>Kind</th>
        <th>Migration</th>
        <th>Status</th>
        <th>Sources</th>
        <th>Missing</th>
        <th>Attributes</th>
        <th>Source Quality</th>
      </tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr class="clickable ${row.key === selectedKey ? "selected-row" : ""}" data-row="${esc(row.key)}">
            <td><b>${esc(row.display_name || row.slug)}</b><br><span class="mono">${esc(row.entity_id)}</span></td>
            <td>${kindChip(row.contract_kind)}</td>
            <td>${migrationChip(row.migration_status)}</td>
            <td class="s-${statusKind(row)}">${esc(statusText(row))}</td>
            <td>${esc(row.source_count ?? 0)}</td>
            <td>${esc(row.missing_required_count ?? 0)}</td>
            <td>${esc(row.attribute_count ?? 0)}</td>
            <td>${qualityChip(row)}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function sourceRows(row) {
  const sources = objectItems(row.sources);
  if (!sources.length) return `<div class="muted">Keine Quellen im Contract Catalog.</div>`;
  return `
    <table>
      <thead><tr><th>Role</th><th>Entity</th><th>Required</th></tr></thead>
      <tbody>
        ${sources.map((source) => `
          <tr>
            <td>${esc(source.role || source.key || "custom")}</td>
            <td><span class="mono">${esc(source.entity || "—")}</span>${source.attribute ? `<br><span class="muted">${esc(source.attribute)}</span>` : ""}</td>
            <td>${source.required ? chip("warn", "required") : chip("info", "optional")}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function listBlock(items, emptyText) {
  const values = asArray(items);
  if (!values.length) return `<span class="muted">${esc(emptyText)}</span>`;
  return values.map((item) => `<span class="mono">${esc(item)}</span>`).join("<br>");
}

function detailCard(row) {
  if (!row) return `<div class="empty">Contract wählen, um Details zu sehen.</div>`;
  const reasons = asArray(row.degraded_reason).map((reason) => chip("warn", reason)).join(" ");
  const hint = MIGRATION_HINTS[row.migration_status] || MIGRATION_HINTS.unknown;
  return `
    <div class="card">
      <div class="section-head">
        <h2>${esc(row.display_name || row.slug)}</h2>
        ${kindChip(row.contract_kind)}
      </div>
      <div class="okbox" style="margin-bottom:12px">Read-only Contract Catalog. Editor folgt später.</div>
      <div class="kv"><span class="k">Display Name</span><span class="v">${esc(row.display_name || "—")}</span></div>
      <div class="kv"><span class="k">Entity ID</span><span class="v mono">${esc(row.entity_id || "—")}</span></div>
      <div class="kv"><span class="k">Slug</span><span class="v mono">${esc(row.slug || "—")}</span></div>
      <div class="kv"><span class="k">Contract Kind</span><span class="v">${kindChip(row.contract_kind)}</span></div>
      <div class="kv"><span class="k">Migration Status</span><span class="v">${migrationChip(row.migration_status)}<br><span class="muted">${esc(hint)}</span></span></div>
      <div class="kv"><span class="k">Source Quality</span><span class="v">${qualityChip(row)}</span></div>
      <div class="kv"><span class="k">Degraded</span><span class="v">${row.degraded ? chip("warn", "true") : chip("ok", "false")}</span></div>
      ${reasons ? `<div style="margin-top:10px"><div class="k">Degraded Reason</div><div class="row" style="margin-top:6px">${reasons}</div></div>` : ""}
      <h2 style="margin-top:16px">Sources</h2>
      ${sourceRows(row)}
      <h2 style="margin-top:16px">Contract Refs</h2>
      <div>${listBlock(row.contract_refs, "Keine Contract-Referenzen erkannt.")}</div>
      <h2 style="margin-top:16px">Legacy Aliases</h2>
      <div>${listBlock(row.legacy_aliases, "Keine Legacy-Aliase hinterlegt.")}</div>
    </div>`;
}

function emptyCatalog() {
  return `
    <div class="hero">
      <div class="hicon"><ha-icon icon="mdi:file-tree-outline"></ha-icon></div>
      <h2>Noch keine Contracts gefunden oder Catalog nicht verfügbar.</h2>
      <p>Masters/Contracts sind der Zielpfad. Legacy Devices und Legacy Combineds werden hier nur read-only sichtbar gemacht.</p>
    </div>`;
}

export function render(root, ctx) {
  root.dataset.keepDraft = "false";
  const catalog = ctx.store.contractCatalog;

  if (!catalog && !root._loading && !root._error) {
    loadCatalog(root, ctx);
  }

  if (root._loading && !catalog) {
    root.innerHTML = `<div class="empty">Contract Catalog wird geladen…</div>`;
    return;
  }

  if (root._error && !catalog) {
    root.innerHTML = `
      <div class="warnbox err">Contract Catalog konnte nicht geladen werden: ${esc(root._error)}</div>
      <button class="btn" type="button" id="retryContracts" style="margin-top:12px">Erneut laden</button>`;
    root.querySelector("#retryContracts").addEventListener("click", () => {
      root._error = null;
      loadCatalog(root, ctx);
      ctx.rerender();
    });
    return;
  }

  const rows = flattenCatalog(catalog || {});
  if (!rows.length) {
    root.innerHTML = emptyCatalog();
    return;
  }

  const filter = root._contractFilter || "all";
  const query = String(root._contractSearch || "").trim().toLowerCase();
  const visible = rows
    .filter((row) => matchesFilter(row, filter))
    .filter((row) => !query || row.haystack.includes(query))
    .sort((a, b) => {
      const ag = (GROUP_RANK[a.group] ?? 9) - (GROUP_RANK[b.group] ?? 9);
      return ag || String(a.display_name || a.slug).localeCompare(String(b.display_name || b.slug));
    });

  if (root._sel && !rows.find((row) => row.key === root._sel)) root._sel = null;
  if (!root._sel && visible.length) root._sel = visible[0].key;
  const selected = rows.find((row) => row.key === root._sel);
  const selectedVisible = visible.some((row) => row.key === root._sel);

  root.innerHTML = `
    <div class="card muted-card" style="margin-bottom:14px">
      <div class="row spread">
        <div class="row"><ha-icon icon="mdi:file-tree-outline"></ha-icon>
          <span class="muted" style="font-size:12px">Masters/Contracts sind der Zielpfad. Legacy Devices und Legacy Combineds sind nur Kompatibilitätsbrücken oder Retire-Kandidaten.</span></div>
        <button class="btn small" type="button" id="refreshContracts">Aktualisieren</button>
      </div>
    </div>
    <div class="stats">
      <div class="stat accent"><div class="n">${esc(asArray(catalog.masters).length)}</div><div class="l">Masters</div></div>
      <div class="stat info"><div class="n">${esc(asArray(catalog.legacy_devices).length)}</div><div class="l">Legacy Devices</div></div>
      <div class="stat info"><div class="n">${esc(asArray(catalog.legacy_combineds).length)}</div><div class="l">Legacy Combineds</div></div>
      <div class="stat ${rows.some((row) => row.degraded) ? "warn" : "ok"}"><div class="n">${esc(rows.filter((row) => row.degraded).length)}</div><div class="l">Degraded</div></div>
      <div class="stat ${rows.some((row) => row.missing_required_count > 0) ? "warn" : "ok"}"><div class="n">${esc(rows.filter((row) => row.missing_required_count > 0).length)}</div><div class="l">Missing Required</div></div>
    </div>
    <div class="diag-toolbar">
      <div class="card">
        <div class="diag-search">
          <ha-icon icon="mdi:magnify"></ha-icon>
          <input id="contractSearch" type="search" autocomplete="off" spellcheck="false"
            placeholder="Suchen nach Name, Entity ID, Slug oder Source Entity…"
            value="${esc(root._contractSearch || "")}">
        </div>
        <div class="filter-group">
          <span class="fg-label">Typ</span>
          ${filterBar(filter)}
        </div>
        <div class="toolbar-foot">
          <span class="result-count">${visible.length} ${visible.length === 1 ? "Ergebnis" : "Ergebnisse"}</span>
          <span class="muted" style="font-size:12px">Read-only · keine Edit- oder Apply-Aktionen</span>
        </div>
      </div>
    </div>
    <div class="split">
      <div class="card">${tableHtml(visible, root._sel)}</div>
      <div class="diag-detail">${selectedVisible ? "" : `<div class="warnbox filter-hint">Ausgewählter Contract ist durch aktuelle Filter ausgeblendet.</div>`}${detailCard(selected)}</div>
    </div>`;

  root.querySelector("#refreshContracts").addEventListener("click", () => {
    ctx.store.contractCatalog = null;
    root._error = null;
    loadCatalog(root, ctx);
    ctx.rerender();
  });
  root.querySelectorAll("[data-filter]").forEach((button) =>
    button.addEventListener("click", () => {
      root._contractFilter = button.dataset.filter;
      ctx.rerender();
    }));
  root.querySelectorAll("[data-row]").forEach((tr) =>
    tr.addEventListener("click", () => {
      root._sel = tr.dataset.row;
      ctx.rerender();
    }));
  const search = root.querySelector("#contractSearch");
  search.addEventListener("input", () => {
    root._contractSearch = search.value;
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
