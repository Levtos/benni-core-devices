import { chip, esc } from "../styles.js";

const OP_LABELS = {
  eq: "= (gleich)",
  ne: "≠ (ungleich)",
  unavailable: "unavailable/unknown",
  lt: "< (kleiner)",
  le: "≤",
  gt: "> (größer)",
  ge: "≥",
};

function newDraft(catalog) {
  return {
    slug: "",
    display_name: "",
    output_type: (catalog.combined && catalog.combined.output_types && catalog.combined.output_types[0]) || "enum",
    sources: [],
    rules: [],
    default_output: "",
    default_reason: "",
    code_legend: {},
    derived: [],
  };
}

function draftFromCombined(c) {
  const conf = c.config || {};
  return {
    slug: c.slug || "",
    display_name: c.display_name || conf.display_name || "",
    output_type: conf.output_type || "enum",
    sources: (conf.sources || []).map((s) => ({
      key: s.key || s.role || "", role: s.role || "custom", entity: s.entity || "",
    })),
    rules: (conf.rules || []).map((r) => ({
      source: r.source || "", op: r.op || "eq", value: r.value ?? "",
      output: r.output ?? "", reason: r.reason || "",
    })),
    default_output: conf.default_output ?? "",
    default_reason: conf.default_reason || "",
    code_legend: conf.code_legend || {},
    derived: (conf.derived || []).map((d) => ({
      slug: d.slug || "", name: d.name || "", device_class: d.device_class || "",
      target: d.target || "__output__", op: d.op || "eq", value: d.value ?? "",
    })),
  };
}

function entityOptions(hass) {
  return Object.keys((hass && hass.states) || {}).sort()
    .map((e) => `<option value="${esc(e)}"></option>`).join("");
}

function legendToText(legend) {
  return Object.entries(legend || {}).map(([k, v]) => `${k}=${v}`).join("\n");
}

function legendFromText(text) {
  const out = {};
  for (const line of String(text || "").split("\n")) {
    const idx = line.indexOf("=");
    if (idx > 0) out[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  return out;
}

function sync(root) {
  const f = root.querySelector("#combinedForm");
  const d = root._cdraft;
  if (!f || !d) return;
  d.display_name = f.elements.display_name.value;
  d.slug = f.elements.slug.value.trim();
  d.output_type = f.elements.output_type.value;
  d.default_output = f.elements.default_output.value;
  d.default_reason = f.elements.default_reason.value;
  d.code_legend = legendFromText(f.elements.code_legend.value);
  d.sources = [...root.querySelectorAll("[data-src]")].map((row) => ({
    key: row.querySelector('[name="src_key"]').value.trim(),
    role: row.querySelector('[name="src_role"]').value,
    entity: row.querySelector('[name="src_entity"]').value.trim(),
  })).filter((s) => s.key || s.entity);
  d.rules = [...root.querySelectorAll("[data-rule]")].map((row) => ({
    source: row.querySelector('[name="rule_source"]').value,
    op: row.querySelector('[name="rule_op"]').value,
    value: row.querySelector('[name="rule_value"]').value,
    output: row.querySelector('[name="rule_output"]').value,
    reason: row.querySelector('[name="rule_reason"]').value,
  }));
  d.derived = [...root.querySelectorAll("[data-derived]")].map((row) => ({
    slug: row.querySelector('[name="d_slug"]').value.trim(),
    name: row.querySelector('[name="d_name"]').value.trim(),
    device_class: row.querySelector('[name="d_class"]').value.trim(),
    target: row.querySelector('[name="d_target"]').value,
    op: row.querySelector('[name="d_op"]').value,
    value: row.querySelector('[name="d_value"]').value,
  })).filter((x) => x.slug);
}

function previewCard(draft, status) {
  const profile = status.profile || "benni";
  const entityId = `sensor.${profile}_combined_${draft.slug || "<slug>"}`;
  const live = (status.combineds || []).find((c) => c.slug === draft.slug);
  const a = (live && live.attrs) || {};
  const legend = Object.entries(draft.code_legend || {})
    .map(([k, v]) => `<div class="kv"><span class="k mono">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("");
  return `
    <div class="card">
      <h2>Preview / Output</h2>
      <div class="preview">
        <div class="kv"><span class="k">Entity</span><span class="v mono pv-id">${esc(entityId)}</span></div>
        <div class="kv"><span class="k">Aktueller Output</span><span class="v">${esc(live ? live.state : "—")}</span></div>
        <div class="kv"><span class="k">Reason</span><span class="v">${esc(live ? a.reason : "—")}</span></div>
        <div class="kv"><span class="k">Output-Typ</span><span class="v">${esc(draft.output_type)}</span></div>
      </div>
      ${legend ? `<h2 style="margin-top:14px">Code-Legende</h2>${legend}` : ""}
      ${draft.derived.length ? `<h2 style="margin-top:14px">Derived</h2>${draft.derived.map((x) =>
        `<div class="kv"><span class="k">${esc(x.name || x.slug)}</span><span class="v mono">${esc(x.target)} ${esc(x.op)} ${esc(x.value)}</span></div>`).join("")}` : ""}
    </div>`;
}

export function render(root, ctx) {
  root.dataset.keepDraft = "true";
  const catalog = ctx.store.catalog || {};
  const status = ctx.store.status || {};
  const combineds = status.combineds || [];
  const cc = catalog.combined || {};
  const ops = cc.operators || ["eq", "ne", "unavailable", "lt", "le", "gt", "ge"];
  const outputTypes = cc.output_types || ["enum", "code", "boolean", "number"];
  const roles = cc.roles || ["custom"];

  if (!root._cdraft) root._cdraft = newDraft(catalog);
  const d = root._cdraft;
  const sourceKeys = d.sources.map((s) => s.key || s.role).filter(Boolean);
  const targets = ["__output__", ...sourceKeys, ...roles];

  const opOptions = (sel) => ops.map((o) =>
    `<option value="${esc(o)}" ${o === sel ? "selected" : ""}>${esc(OP_LABELS[o] || o)}</option>`).join("");

  root.innerHTML = `
    <div class="split">
      <div class="card">
        <form id="combinedForm" class="form">
          <div class="section-head">
            <h2>${d.slug ? "Combined bearbeiten" : "Combined anlegen"}</h2>
            <select name="edit_slug" style="max-width:200px">
              <option value="">Neu</option>
              ${combineds.map((c) => `<option value="${esc(c.slug)}" ${c.slug === d.slug ? "selected" : ""}>${esc(c.display_name || c.slug)}</option>`).join("")}
            </select>
          </div>
          <div class="grid cols-3">
            <label>Name<input name="display_name" value="${esc(d.display_name)}" required></label>
            <label>Slug<input name="slug" value="${esc(d.slug)}" placeholder="auto"></label>
            <label>Output Type
              <select name="output_type">
                ${outputTypes.map((t) => `<option value="${esc(t)}" ${t === d.output_type ? "selected" : ""}>${esc(t)}</option>`).join("")}
              </select>
            </label>
          </div>

          <div class="slot-group">
            <h3><ha-icon icon="mdi:import"></ha-icon>Sources</h3>
            <div id="sources">
              ${d.sources.map((s, i) => `
                <div class="rule-row" data-src="${i}" style="grid-template-columns:1fr 1fr 1.6fr 30px">
                  <input name="src_key" value="${esc(s.key)}" placeholder="key">
                  <select name="src_role">${roles.map((r) => `<option value="${esc(r)}" ${r === s.role ? "selected" : ""}>${esc(r)}</option>`).join("")}</select>
                  <input name="src_entity" list="all_entities" value="${esc(s.entity)}" placeholder="entity_id">
                  <button class="btn small danger" type="button" data-del-src="${i}">×</button>
                </div>`).join("") || `<div class="muted">Noch keine Quellen.</div>`}
            </div>
            <button class="btn small" type="button" id="addSource" style="margin-top:8px">+ Quelle</button>
          </div>

          <div class="slot-group">
            <h3><ha-icon icon="mdi:format-list-numbered"></ha-icon>Rules (First-Match-Wins)</h3>
            <div id="rules">
              ${d.rules.map((r, i) => `
                <div class="rule-row" data-rule="${i}">
                  <span class="ord">${i + 1}</span>
                  <select name="rule_source">${sourceKeys.map((k) => `<option value="${esc(k)}" ${k === r.source ? "selected" : ""}>${esc(k)}</option>`).join("")}</select>
                  <select name="rule_op">${opOptions(r.op)}</select>
                  <input name="rule_value" value="${esc(r.value)}" placeholder="Wert">
                  <input name="rule_output" value="${esc(r.output)}" placeholder="Output">
                  <input name="rule_reason" value="${esc(r.reason)}" placeholder="Reason">
                  <button class="btn small danger" type="button" data-del-rule="${i}">×</button>
                </div>`).join("") || `<div class="muted">Noch keine Regeln.</div>`}
            </div>
            <div class="row" style="margin-top:8px">
              <button class="btn small" type="button" id="addRule">+ Regel</button>
              <label style="grid-auto-flow:column; align-items:center">Default Output
                <input name="default_output" value="${esc(d.default_output)}" style="max-width:120px">
              </label>
              <label style="align-items:center">Default Reason
                <input name="default_reason" value="${esc(d.default_reason)}" style="max-width:160px">
              </label>
            </div>
          </div>

          <div class="slot-group">
            <h3><ha-icon icon="mdi:gate"></ha-icon>Derived Binary Sensors</h3>
            <div id="derived">
              ${d.derived.map((x, i) => `
                <div class="rule-row" data-derived="${i}" style="grid-template-columns:1fr 1fr 1fr 1fr .8fr 1fr 30px">
                  <input name="d_slug" value="${esc(x.slug)}" placeholder="slug">
                  <input name="d_name" value="${esc(x.name)}" placeholder="Name">
                  <input name="d_class" value="${esc(x.device_class)}" placeholder="device_class">
                  <select name="d_target">${targets.map((t) => `<option value="${esc(t)}" ${t === x.target ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
                  <select name="d_op">${opOptions(x.op)}</select>
                  <input name="d_value" value="${esc(x.value)}" placeholder="Wert">
                  <button class="btn small danger" type="button" data-del-derived="${i}">×</button>
                </div>`).join("") || `<div class="muted">Keine abgeleiteten Sensoren.</div>`}
            </div>
            <button class="btn small" type="button" id="addDerived" style="margin-top:8px">+ Derived</button>
          </div>

          <label>Code-Legende (eine Zeile pro Code, z. B. <span class="mono">0=closed</span>)
            <textarea name="code_legend" style="min-height:80px">${esc(legendToText(d.code_legend))}</textarea>
          </label>

          <div class="row">
            <button class="btn primary" type="submit">Speichern</button>
            <button class="btn" type="button" id="resetCombined">Neu</button>
            ${d.slug ? `<button class="btn danger" type="button" id="deleteCombined">Löschen</button>` : ""}
          </div>
        </form>
      </div>
      <div id="cPreview">${previewCard(d, status)}</div>
    </div>
    <datalist id="all_entities">${entityOptions(ctx.hass)}</datalist>`;

  const form = root.querySelector("#combinedForm");
  form.elements.edit_slug.addEventListener("change", () => {
    const sel = combineds.find((c) => c.slug === form.elements.edit_slug.value);
    root._cdraft = sel ? draftFromCombined(sel) : newDraft(catalog);
    ctx.rerender();
  });
  // Sync auf Änderungen, die das Layout nicht ändern.
  form.querySelectorAll("input, select, textarea").forEach((el) => {
    if (el.name === "edit_slug") return;
    el.addEventListener("change", () => sync(root));
  });

  root.querySelector("#addSource").addEventListener("click", () => {
    sync(root); d.sources.push({ key: "", role: roles[0], entity: "" }); ctx.rerender();
  });
  root.querySelector("#addRule").addEventListener("click", () => {
    sync(root); d.rules.push({ source: sourceKeys[0] || "", op: "eq", value: "", output: "", reason: "" }); ctx.rerender();
  });
  root.querySelector("#addDerived").addEventListener("click", () => {
    sync(root); d.derived.push({ slug: "", name: "", device_class: "", target: "__output__", op: "eq", value: "" }); ctx.rerender();
  });
  root.querySelectorAll("[data-del-src]").forEach((b) =>
    b.addEventListener("click", () => { sync(root); d.sources.splice(Number(b.dataset.delSrc), 1); ctx.rerender(); }));
  root.querySelectorAll("[data-del-rule]").forEach((b) =>
    b.addEventListener("click", () => { sync(root); d.rules.splice(Number(b.dataset.delRule), 1); ctx.rerender(); }));
  root.querySelectorAll("[data-del-derived]").forEach((b) =>
    b.addEventListener("click", () => { sync(root); d.derived.splice(Number(b.dataset.delDerived), 1); ctx.rerender(); }));

  root.querySelector("#resetCombined").addEventListener("click", () => {
    root._cdraft = newDraft(catalog); ctx.rerender();
  });
  const del = root.querySelector("#deleteCombined");
  if (del) del.addEventListener("click", async () => {
    await ctx.store.removeCombined(d.slug);
    root._cdraft = newDraft(catalog);
    ctx.toast("Combined gelöscht"); ctx.rerender();
  });

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    sync(root);
    if (!d.display_name) { ctx.toast("Name fehlt"); return; }
    await ctx.store.setCombined({
      slug: d.slug || undefined,
      display_name: d.display_name,
      config: {
        output_type: d.output_type,
        sources: d.sources,
        rules: d.rules,
        default_output: d.default_output,
        default_reason: d.default_reason,
        code_legend: d.code_legend,
        derived: d.derived,
      },
    });
    root._cdraft = newDraft(catalog);
    ctx.toast("Combined gespeichert");
    ctx.rerender();
  });
}
