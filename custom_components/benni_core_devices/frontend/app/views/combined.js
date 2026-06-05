import { chip, esc } from "../styles.js";

const OP_LABELS = {
  eq: "= (gleich)", ne: "≠ (ungleich)", unavailable: "unavailable/unknown",
  lt: "< (kleiner)", le: "≤", gt: "> (größer)", ge: "≥",
};

// ── Templates (reine Frontend-Prefills des bestehenden Draft-Modells) ────────
const TEMPLATES = {
  opening: {
    label: "Opening / Fenster", icon: "mdi:window-closed-variant",
    desc: "Open-/Tilt-Kontakt → Code 0/1/2/9 mit Fail-Safe.",
    seed: () => ({
      output_type: "code",
      sources: [
        { key: "open", role: "open_contact", entity: "" },
        { key: "tilt", role: "tilt_contact", entity: "" },
      ],
      rules: [
        { source: "open", op: "unavailable", value: "", output: 9, reason: "open unclear" },
        { source: "open", op: "eq", value: "on", output: 2, reason: "open" },
        { source: "tilt", op: "eq", value: "on", output: 1, reason: "tilted" },
      ],
      default_output: 0, default_reason: "closed",
      code_legend: { 0: "closed", 1: "tilted", 2: "open", 9: "unclear" },
      derived: [
        { slug: "any_open", name: "Any Open", device_class: "opening", target: "open_contact", op: "eq", value: "on" },
        { slug: "any_tilted", name: "Any Tilted", device_class: "opening", target: "tilt_contact", op: "eq", value: "on" },
        { slug: "any_unclear", name: "Any Unclear", device_class: "problem", target: "__output__", op: "eq", value: "9" },
      ],
    }),
  },
  any_active: {
    label: "Any Active", icon: "mdi:checkbox-multiple-marked",
    desc: "Boolean an, sobald eine der Quellen aktiv ist.",
    seed: () => ({
      output_type: "boolean",
      sources: [{ key: "s1", role: "input", entity: "" }],
      rules: [{ source: "s1", op: "eq", value: "on", output: true, reason: "active" }],
      default_output: false, default_reason: "inactive",
      code_legend: {}, derived: [],
    }),
  },
  safety: {
    label: "Safety Gate", icon: "mdi:shield-alert",
    desc: "Boolean/Problem-Gate für eine unsichere Bedingung.",
    seed: () => ({
      output_type: "boolean",
      sources: [{ key: "cond", role: "custom", entity: "" }],
      rules: [{ source: "cond", op: "eq", value: "on", output: true, reason: "unsafe" }],
      default_output: false, default_reason: "safe",
      code_legend: {},
      derived: [{ slug: "unsafe", name: "Unsafe", device_class: "problem", target: "__output__", op: "eq", value: "on" }],
    }),
  },
  custom: {
    label: "Custom / Expert", icon: "mdi:tune-vertical", expert: true,
    desc: "Leeres Vollformular mit Rules, Derived & Legende.",
    seed: () => ({
      output_type: "enum", sources: [], rules: [],
      default_output: "", default_reason: "", code_legend: {}, derived: [],
    }),
  },
};

function blankDraft() {
  return {
    slug: "", display_name: "", output_type: "enum",
    sources: [], rules: [], default_output: "", default_reason: "",
    code_legend: {}, derived: [], _template: null, _expert: false,
  };
}

function draftFromTemplate(id) {
  const seed = TEMPLATES[id].seed();
  return {
    slug: "", display_name: "", _template: id, _expert: id === "custom",
    ...seed,
  };
}

function draftFromCombined(c) {
  const conf = c.config || {};
  return {
    slug: c.slug || "", display_name: c.display_name || conf.display_name || "",
    output_type: conf.output_type || "enum",
    sources: (conf.sources || []).map((s) => ({ key: s.key || s.role || "", role: s.role || "custom", entity: s.entity || "" })),
    rules: (conf.rules || []).map((r) => ({ source: r.source || "", op: r.op || "eq", value: r.value ?? "", output: r.output ?? "", reason: r.reason || "" })),
    default_output: conf.default_output ?? "", default_reason: conf.default_reason || "",
    code_legend: conf.code_legend || {},
    derived: (conf.derived || []).map((dd) => ({ slug: dd.slug || "", name: dd.name || "", device_class: dd.device_class || "", target: dd.target || "__output__", op: dd.op || "eq", value: dd.value ?? "" })),
    _template: "edit", _expert: false,
  };
}

function entityOptions(hass) {
  return Object.keys((hass && hass.states) || {}).sort().map((e) => `<option value="${esc(e)}"></option>`).join("");
}
function legendToText(l) { return Object.entries(l || {}).map(([k, v]) => `${k}=${v}`).join("\n"); }
function legendFromText(t) {
  const out = {};
  for (const line of String(t || "").split("\n")) { const i = line.indexOf("="); if (i > 0) out[line.slice(0, i).trim()] = line.slice(i + 1).trim(); }
  return out;
}

function sync(root) {
  const f = root.querySelector("#combinedForm");
  const d = root._cdraft;
  if (!f || !d) return;
  if (f.elements.display_name) d.display_name = f.elements.display_name.value;
  if (f.elements.slug) d.slug = f.elements.slug.value.trim();
  if (f.elements.output_type) d.output_type = f.elements.output_type.value;
  if (f.elements.default_output) d.default_output = f.elements.default_output.value;
  if (f.elements.default_reason) d.default_reason = f.elements.default_reason.value;
  const legendEl = root.querySelector('[name="code_legend"]');
  if (legendEl) d.code_legend = legendFromText(legendEl.value);
  // Sources (immer sichtbar)
  const srcRows = [...root.querySelectorAll("[data-src]")];
  if (srcRows.length || root.querySelector("#sources")) {
    d.sources = srcRows.map((row) => ({
      key: row.querySelector('[name="src_key"]') ? row.querySelector('[name="src_key"]').value.trim() : row.dataset.key,
      role: row.querySelector('[name="src_role"]') ? row.querySelector('[name="src_role"]').value : (row.dataset.role || "custom"),
      entity: row.querySelector('[name="src_entity"]').value.trim(),
    })).filter((s) => s.key || s.entity);
  }
  // Rules nur wenn Expert-Editor sichtbar (sonst Template-Regeln behalten)
  if (root.querySelector("#rules")) {
    d.rules = [...root.querySelectorAll("[data-rule]")].map((row) => ({
      source: row.querySelector('[name="rule_source"]').value,
      op: row.querySelector('[name="rule_op"]').value,
      value: row.querySelector('[name="rule_value"]').value,
      output: row.querySelector('[name="rule_output"]').value,
      reason: row.querySelector('[name="rule_reason"]').value,
    }));
  }
  if (root.querySelector("#derived")) {
    d.derived = [...root.querySelectorAll("[data-derived]")].map((row) => ({
      slug: row.querySelector('[name="d_slug"]').value.trim(),
      name: row.querySelector('[name="d_name"]').value.trim(),
      device_class: row.querySelector('[name="d_class"]').value.trim(),
      target: row.querySelector('[name="d_target"]').value,
      op: row.querySelector('[name="d_op"]').value,
      value: row.querySelector('[name="d_value"]').value,
    })).filter((x) => x.slug);
  }
}

// Any-Active: Regeln aus den aktuellen Quellen ableiten (eine Quelle = on → true).
function normalizeForSave(d) {
  if (d._template === "any_active") {
    d.rules = d.sources.filter((s) => s.key).map((s) => ({ source: s.key, op: "eq", value: "on", output: true, reason: "active" }));
  }
}

function previewCard(d, status) {
  const profile = status.profile || "benni";
  const entityId = `sensor.${profile}_combined_${d.slug || "<slug>"}`;
  const live = (status.combineds || []).find((c) => c.slug === d.slug);
  const a = (live && live.attrs) || {};
  const legend = d.output_type === "code"
    ? Object.entries(d.code_legend || {}).map(([k, v]) => `<div class="kv"><span class="k mono">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")
    : "";
  return `
    <div class="card">
      <h2>Preview / Output</h2>
      <div class="preview">
        <div class="summary-line"><ha-icon icon="mdi:identifier"></ha-icon><span class="mono pv-id">${esc(entityId)}</span></div>
        <div class="summary-line"><ha-icon icon="mdi:export"></ha-icon>Output-Typ: <b>${esc(d.output_type)}</b></div>
        <div class="summary-line"><ha-icon icon="mdi:numeric"></ha-icon>Aktuell: <b>${esc(live ? live.state : "—")}</b></div>
        <div class="summary-line"><ha-icon icon="mdi:comment-text-outline"></ha-icon>Reason: ${esc(live ? a.reason : "—")}</div>
        <div class="summary-line"><ha-icon icon="mdi:source-branch"></ha-icon>${(d.sources || []).filter((s) => s.entity).length} Quelle(n)</div>
      </div>
      ${legend ? `<h2 style="margin-top:14px">Code-Legende</h2>${legend}` : ""}
      ${(d.derived || []).length ? `<h2 style="margin-top:14px">Derived</h2>${d.derived.map((x) => `<div class="kv"><span class="k">${esc(x.name || x.slug)}</span><span class="v mono">${esc(x.target)} ${esc(x.op)} ${esc(x.value)}</span></div>`).join("")}` : ""}
    </div>`;
}

function opOptions(ops, sel) {
  return ops.map((o) => `<option value="${esc(o)}" ${o === sel ? "selected" : ""}>${esc(OP_LABELS[o] || o)}</option>`).join("");
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
  if (!root._cdraft) root._cdraft = blankDraft();
  const d = root._cdraft;

  // ── Template-Auswahl (Einstieg für neue Combineds) ──────────────────────
  if (!d._template) {
    root.innerHTML = `
      <div class="card">
        <div class="section-head">
          <h2>Combined erstellen — Vorlage wählen</h2>
          <select id="editPick" style="min-width:200px">
            <option value="">Bestehendes bearbeiten…</option>
            ${combineds.map((c) => `<option value="${esc(c.slug)}">${esc(c.display_name || c.slug)}</option>`).join("")}
          </select>
        </div>
        <div class="tpl-grid">
          ${Object.entries(TEMPLATES).map(([id, t]) => `
            <div class="tpl-card ${t.expert ? "expert" : ""}" data-tpl="${esc(id)}">
              <div class="tpl-icon"><ha-icon icon="${esc(t.icon)}"></ha-icon></div>
              <h3>${esc(t.label)} ${t.expert ? chip("info", "Expert") : ""}</h3>
              <p>${esc(t.desc)}</p>
            </div>`).join("")}
        </div>
      </div>`;
    root.querySelectorAll("[data-tpl]").forEach((c) =>
      c.addEventListener("click", () => { root._cdraft = draftFromTemplate(c.dataset.tpl); ctx.rerender(); }));
    root.querySelector("#editPick").addEventListener("change", (e) => {
      const sel = combineds.find((c) => c.slug === e.target.value);
      if (sel) { root._cdraft = draftFromCombined(sel); ctx.rerender(); }
    });
    return;
  }

  const tplLabel = (TEMPLATES[d._template] && TEMPLATES[d._template].label) || (d._template === "edit" ? "Bearbeiten" : d._template);
  const showLegend = d.output_type === "code";
  const sourceKeys = d.sources.map((s) => s.key || s.role).filter(Boolean);
  const targets = ["__output__", ...sourceKeys, ...roles];
  const canAddSource = d._template === "any_active" || d._template === "custom" || d._expert;

  root.innerHTML = `
    <div class="split">
      <div>
        <form id="combinedForm" class="form">
          <div class="row spread">
            <div class="row">
              <button class="btn small" type="button" id="backTpl">‹ Vorlage</button>
              ${chip(d._template === "custom" ? "info" : "accent", esc(tplLabel))}
            </div>
            ${d.slug ? chip("accent", esc(d.slug)) : chip("info", "Neu")}
          </div>

          <div class="step primary-step">
            <div class="step-head"><span class="num">1</span><div><h3>Basics</h3><small>Name &amp; Slug</small></div></div>
            <div class="grid cols-2">
              <label>Name<input name="display_name" value="${esc(d.display_name)}" placeholder="z. B. Wohnzimmer Fenster" required></label>
              <label>Slug<input name="slug" value="${esc(d.slug)}" placeholder="auto"></label>
            </div>
          </div>

          <div class="step">
            <div class="step-head"><span class="num">2</span><div><h3>Quellen</h3><small>Roh-Entities zuordnen</small></div></div>
            <div id="sources">
              ${d.sources.map((s, i) => `
                <div class="slot-row" data-src="${i}" data-key="${esc(s.key)}" data-role="${esc(s.role)}" style="grid-template-columns:1fr 1.6fr ${canAddSource ? "30px" : "0"}">
                  <span class="slot-name">${esc(s.role)}<small>${esc(s.key)}</small></span>
                  <span><input name="src_entity" list="all_entities" value="${esc(s.entity)}" placeholder="entity_id"></span>
                  ${canAddSource ? `<button class="btn small danger" type="button" data-del-src="${i}">×</button>` : "<span></span>"}
                </div>`).join("") || `<div class="muted">Noch keine Quellen.</div>`}
            </div>
            ${canAddSource ? `<button class="btn small" type="button" id="addSource" style="margin-top:8px">+ Quelle</button>` : ""}
          </div>

          <details class="disclosure" ${d._expert ? "open" : ""} data-disc="expert">
            <summary>Experten-Regeln <small>· First-Match-Wins, Output-Typ, Default</small></summary>
            <div class="disclosure-body">
              <label style="max-width:220px">Output-Typ
                <select name="output_type">${outputTypes.map((t) => `<option value="${esc(t)}" ${t === d.output_type ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
              </label>
              <div id="rules" style="margin-top:10px">
                ${d.rules.map((r, i) => `
                  <div class="rule-row" data-rule="${i}">
                    <span class="ord">${i + 1}</span>
                    <select name="rule_source">${sourceKeys.map((k) => `<option value="${esc(k)}" ${k === r.source ? "selected" : ""}>${esc(k)}</option>`).join("")}</select>
                    <select name="rule_op">${opOptions(ops, r.op)}</select>
                    <input name="rule_value" value="${esc(r.value)}" placeholder="Wert">
                    <input name="rule_output" value="${esc(r.output)}" placeholder="Output">
                    <input name="rule_reason" value="${esc(r.reason)}" placeholder="Reason">
                    <button class="btn small danger" type="button" data-del-rule="${i}">×</button>
                  </div>`).join("") || `<div class="muted">Keine Regeln.</div>`}
              </div>
              <div class="row" style="margin-top:8px">
                <button class="btn small" type="button" id="addRule">+ Regel</button>
                <label style="align-items:center">Default Output<input name="default_output" value="${esc(d.default_output)}" style="max-width:110px"></label>
                <label style="align-items:center">Default Reason<input name="default_reason" value="${esc(d.default_reason)}" style="max-width:150px"></label>
              </div>
              ${showLegend ? `<label style="margin-top:10px">Code-Legende (eine Zeile pro Code, z. B. <span class="mono">0=closed</span>)
                <textarea name="code_legend" style="min-height:80px">${esc(legendToText(d.code_legend))}</textarea></label>` : ""}
            </div>
          </details>

          <details class="disclosure" data-disc="derived">
            <summary>Derived Binary Sensors <small>· ${d.derived.length} definiert</small></summary>
            <div class="disclosure-body">
              <div id="derived">
                ${d.derived.map((x, i) => `
                  <div class="rule-row" data-derived="${i}" style="grid-template-columns:1fr 1fr 1fr 1fr .8fr 1fr 30px">
                    <input name="d_slug" value="${esc(x.slug)}" placeholder="slug">
                    <input name="d_name" value="${esc(x.name)}" placeholder="Name">
                    <input name="d_class" value="${esc(x.device_class)}" placeholder="device_class">
                    <select name="d_target">${targets.map((t) => `<option value="${esc(t)}" ${t === x.target ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
                    <select name="d_op">${opOptions(ops, x.op)}</select>
                    <input name="d_value" value="${esc(x.value)}" placeholder="Wert">
                    <button class="btn small danger" type="button" data-del-derived="${i}">×</button>
                  </div>`).join("") || `<div class="muted">Keine abgeleiteten Sensoren.</div>`}
              </div>
              <button class="btn small" type="button" id="addDerived" style="margin-top:8px">+ Derived</button>
            </div>
          </details>

          <div class="row">
            <button class="btn primary" type="submit">Speichern</button>
            <button class="btn" type="button" id="resetC">Neu</button>
            ${d.slug ? `<button class="btn danger" type="button" id="deleteC">Löschen</button>` : ""}
          </div>
        </form>
      </div>
      <div id="cPreview">${previewCard(d, status)}</div>
    </div>
    <datalist id="all_entities">${entityOptions(ctx.hass)}</datalist>`;

  const form = root.querySelector("#combinedForm");
  const refreshPreview = () => { sync(root); root.querySelector("#cPreview").innerHTML = previewCard(root._cdraft, status); };

  root.querySelector("#backTpl").addEventListener("click", () => { root._cdraft = blankDraft(); ctx.rerender(); });
  form.querySelectorAll("input, select, textarea").forEach((el) =>
    el.addEventListener("change", () => refreshPreview()));
  root.querySelectorAll("details[data-disc]").forEach((det) =>
    det.addEventListener("toggle", () => { if (det.dataset.disc === "expert") d._expert = det.open; }));

  const addSource = root.querySelector("#addSource");
  if (addSource) addSource.addEventListener("click", () => {
    sync(root);
    const n = d.sources.length + 1;
    const role = d._template === "any_active" ? "input" : "custom";
    d.sources.push({ key: `s${n}`, role, entity: "" });
    ctx.rerender();
  });
  root.querySelectorAll("[data-del-src]").forEach((b) =>
    b.addEventListener("click", () => { sync(root); d.sources.splice(Number(b.dataset.delSrc), 1); ctx.rerender(); }));
  const addRule = root.querySelector("#addRule");
  if (addRule) addRule.addEventListener("click", () => { sync(root); d.rules.push({ source: sourceKeys[0] || "", op: "eq", value: "", output: "", reason: "" }); ctx.rerender(); });
  root.querySelectorAll("[data-del-rule]").forEach((b) =>
    b.addEventListener("click", () => { sync(root); d.rules.splice(Number(b.dataset.delRule), 1); ctx.rerender(); }));
  const addDerived = root.querySelector("#addDerived");
  if (addDerived) addDerived.addEventListener("click", () => { sync(root); d.derived.push({ slug: "", name: "", device_class: "", target: "__output__", op: "eq", value: "" }); ctx.rerender(); });
  root.querySelectorAll("[data-del-derived]").forEach((b) =>
    b.addEventListener("click", () => { sync(root); d.derived.splice(Number(b.dataset.delDerived), 1); ctx.rerender(); }));

  root.querySelector("#resetC").addEventListener("click", () => { root._cdraft = blankDraft(); ctx.rerender(); });
  const del = root.querySelector("#deleteC");
  if (del) del.addEventListener("click", async () => { await ctx.store.removeCombined(d.slug); root._cdraft = blankDraft(); ctx.toast("Combined gelöscht"); ctx.rerender(); });

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    sync(root);
    if (!d.display_name) { ctx.toast("Name fehlt"); return; }
    normalizeForSave(d);
    await ctx.store.setCombined({
      slug: d.slug || undefined,
      display_name: d.display_name,
      config: {
        output_type: d.output_type, sources: d.sources, rules: d.rules,
        default_output: d.default_output, default_reason: d.default_reason,
        code_legend: d.code_legend, derived: d.derived,
      },
    });
    root._cdraft = blankDraft();
    ctx.toast("Combined gespeichert");
    ctx.rerender();
  });
}
