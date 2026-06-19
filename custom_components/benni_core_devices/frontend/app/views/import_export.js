import { chip, esc } from "../styles.js";

function newState() {
  return { bulk: "", report: null, exportYaml: "", agentMd: "", agentSchema: "", group: { display_name: "", members: [] } };
}

function reportCard(result) {
  if (!result) return "";
  const rows = (result.report || []).map((r) => {
    const missing = r.missing_required || [];
    const sev = r.derived_sources.length ? "err" : (missing.length ? "warn" : "ok");
    const issues = [
      ...r.derived_sources.map((x) => `<div class="warnbox err" style="margin-top:4px">${esc(x)}</div>`),
      missing.length ? `<div class="warnbox" style="margin-top:4px">Pflichtrollen fehlen: ${esc(missing.join(", "))}</div>` : "",
    ].join("");
    return `<tr>
      <td>${chip(sev, r.accepted ? "akzeptiert" : "blockiert")}</td>
      <td class="mono">${esc(r.entity_id)}</td>
      <td>${esc(r.atomic_class)}</td>
      <td>${issues || `<span class="muted">—</span>`}</td>
    </tr>`;
  }).join("");
  const cRows = (result.combined_report || []).map((r) => {
    const val = r.validation || [];
    const sev = (r.derived_sources && r.derived_sources.length) || val.length ? "err" : (r.accepted ? "ok" : "warn");
    const issues = [
      ...(r.derived_sources || []).map((x) => `<div class="warnbox err" style="margin-top:4px">${esc(x)}</div>`),
      ...val.map((x) => `<div class="warnbox err" style="margin-top:4px">${esc(x)}</div>`),
    ].join("");
    const dv = r.derived_values ? ` · ${r.derived_values} derived` : "";
    const exposed = (r.exposed_attributes || []).length ? ` · attrs: ${(r.exposed_attributes || []).map(esc).join(", ")}` : "";
    return `<tr>
      <td>${chip(sev, r.accepted ? "akzeptiert" : "blockiert")}</td>
      <td class="mono">${esc(r.entity_id)}</td>
      <td>${esc(r.output_type)} · ${esc(r.sources)} Quellen${dv}${exposed}</td>
      <td>${issues || `<span class="muted">—</span>`}</td>
    </tr>`;
  }).join("");
  const anyErr = (result.report || []).some((r) => r.derived_sources.length)
    || (result.combined_report || []).some((r) => r.derived_sources && r.derived_sources.length);
  return `
    <div class="warnbox ${anyErr ? "err" : ""}" style="margin-top:14px; ${anyErr ? "" : "border-color:var(--line);background:#24262f;color:var(--muted)"}">
      <div class="row spread"><b>${result.dry_run ? "Dry-Run Vorschau" : "Import-Ergebnis"}</b>
        <span>${chip("info", `${result.devices} Devices`)} ${chip("info", `${result.combineds ?? 0} Combineds`)} ${chip("info", `${result.groups} Groups`)}</span></div>
    </div>
    ${rows ? `<table style="margin-top:8px"><thead><tr><th>Status</th><th>Entity</th><th>Typ</th><th>Hinweise</th></tr></thead><tbody>${rows}</tbody></table>`
      : `<div class="muted" style="margin-top:8px">Keine Devices im Payload.</div>`}
    ${cRows ? `<h2 style="margin-top:12px;font-size:13px">Combineds</h2><table><thead><tr><th>Status</th><th>Entity</th><th>Output</th><th>Hinweise</th></tr></thead><tbody>${cRows}</tbody></table>` : ""}`;
}

function renderMemberPicker(root, ctx, st) {
  const mount = root.querySelector("#memberPicker");
  if (!mount) return;
  mount.innerHTML = "";
  const add = (val) => {
    const e = String(val || "").trim();
    if (e && !st.group.members.includes(e)) { st.group.members.push(e); renderMembers(root, st); }
  };
  if (customElements.get("ha-entity-picker")) {
    const picker = document.createElement("ha-entity-picker");
    picker.hass = ctx.hass; picker.includeDomains = ["light"]; picker.allowCustomEntity = true;
    picker.addEventListener("value-changed", (ev) => { add(ev.detail.value); picker.value = ""; });
    mount.appendChild(picker);
    return;
  }
  mount.innerHTML = `<div class="row"><input id="memberInput" placeholder="light.kitchen"><button class="btn" type="button" id="addMember">Add</button></div>`;
  mount.querySelector("#addMember").addEventListener("click", () => { const i = mount.querySelector("#memberInput"); add(i.value); i.value = ""; });
}

function renderMembers(root, st) {
  const list = root.querySelector("#memberList");
  if (!list) return;
  list.innerHTML = st.group.members.length
    ? st.group.members.map((e, idx) => `<span class="member-chip"><span class="mono">${esc(e)}</span><button type="button" data-rm="${idx}">×</button></span>`).join("")
    : `<span class="muted">Keine Mitglieder.</span>`;
  list.querySelectorAll("[data-rm]").forEach((b) =>
    b.addEventListener("click", () => { st.group.members.splice(Number(b.dataset.rm), 1); renderMembers(root, st); }));
}

export function render(root, ctx) {
  root.dataset.keepDraft = "true";
  const status = ctx.store.status || {};
  const groups = status.groups || [];
  if (!root._ie) root._ie = newState();
  const st = root._ie;

  root.innerHTML = `
    <div class="card muted-card" style="margin-bottom:14px">
      <div class="row"><ha-icon icon="mdi:shield-account"></ha-icon>
        <span class="muted" style="font-size:12px">Admin-Bereich. Bulk-Import erwartet <b>rohe HA-Entities</b>. Quellen wie <span class="mono">*_atomic</span>/<span class="mono">*_combined</span>/<span class="mono">*_gate</span> werden im Dry-Run markiert und blockiert.</span></div>
    </div>
    <div class="split">
      <div class="card">
        <h2>Bulk Import</h2>
        <textarea id="bulk" spellcheck="false" placeholder="- slug: tv&#10;  atomic_class: media_device&#10;  variant: tv&#10;  sources:&#10;    - role: primary_state&#10;      entity: media_player.living_lgtv">${esc(st.bulk)}</textarea>
        <div class="row" style="margin-top:10px">
          <button class="btn" type="button" id="dryRun">Dry Run / Vorschau</button>
          <button class="btn primary" type="button" id="doImport">Import ausführen</button>
        </div>
        <div id="reportMount">${reportCard(st.report)}</div>
      </div>
      <div class="card">
        <h2>Export</h2>
        <p class="muted" style="font-size:12px; margin:0 0 10px">Aktuelle Builder-Konfiguration als YAML (Devices, Combineds, Groups).</p>
        <button class="btn" type="button" id="doExport">Konfiguration exportieren</button>
        ${st.exportYaml ? `<textarea readonly style="margin-top:10px; min-height:220px">${esc(st.exportYaml)}</textarea>` : ""}
      </div>
    </div>

    <div class="card" style="margin-top:14px">
      <div class="section-head"><h2>Für Agenten (Claude Code / Codex)</h2>
        <button class="btn" type="button" id="genSpec">Briefing generieren</button></div>
      <p class="muted" style="font-size:12px; margin:0 0 10px">
        Erzeugt ein selbsterklärendes Briefing (Markdown + JSON-Schema) für eine frische
        Agentensession mit MCP-Anbindung — Rollen, Klassen, Import-Schema, Workflow (Dry-Run → Apply)
        und den aktuellen Export. Builder bleiben für manuelle Eingriffe.</p>
      ${st.agentMd ? `
        <label>Briefing (Markdown) <button class="btn small" type="button" id="copyMd">Kopieren</button>
          <textarea id="agentMd" readonly style="min-height:240px">${esc(st.agentMd)}</textarea></label>
        <label style="margin-top:10px">JSON-Schema <button class="btn small" type="button" id="copySchema">Kopieren</button>
          <textarea id="agentSchema" readonly style="min-height:140px">${esc(st.agentSchema)}</textarea></label>` : ""}
    </div>

    <details class="disclosure" style="margin-top:14px">
      <summary>Light Groups <small>· untergeordnet</small></summary>
      <div class="disclosure-body">
        <div class="split">
          <div>
            <form id="groupForm" class="form">
              <label>Name<input name="display_name" value="${esc(st.group.display_name)}"></label>
              <label>Members<div id="memberPicker"></div></label>
              <div id="memberList" class="member-list"></div>
              <button class="btn primary" type="submit">Gruppe speichern</button>
            </form>
          </div>
          <div>
            ${groups.length ? `<table><thead><tr><th>Slug</th><th>State</th><th></th></tr></thead><tbody>${groups.map((g) => `
              <tr><td class="mono">${esc(g.slug)}</td><td>${esc(g.state)}</td>
              <td><button class="btn small danger" data-rm-group="${esc(g.slug)}">Remove</button></td></tr>`).join("")}</tbody></table>`
              : `<div class="empty">Keine Gruppen.</div>`}
          </div>
        </div>
      </div>
    </details>`;

  const bulk = root.querySelector("#bulk");
  bulk.addEventListener("input", () => { st.bulk = bulk.value; });

  const runImport = async (dryRun) => {
    st.bulk = bulk.value;
    try {
      const res = await ctx.store.bulkImport(st.bulk, dryRun);
      st.report = res;
      root.querySelector("#reportMount").innerHTML = reportCard(res);
      ctx.toast(dryRun ? "Dry-Run fertig" : `Importiert: ${res.devices} Devices`);
      if (!dryRun) ctx.rerender();
    } catch (err) {
      root.querySelector("#reportMount").innerHTML = `<div class="warnbox err" style="margin-top:14px">${esc(err.message || err)}</div>`;
    }
  };
  root.querySelector("#dryRun").addEventListener("click", () => runImport(true));
  root.querySelector("#doImport").addEventListener("click", () => runImport(false));

  root.querySelector("#doExport").addEventListener("click", async () => {
    try { const res = await ctx.store.exportConfig(); st.exportYaml = res.yaml || ""; ctx.rerender(); }
    catch (err) { ctx.toast("Export fehlgeschlagen"); }
  });

  root.querySelector("#genSpec").addEventListener("click", async () => {
    try {
      const res = await ctx.store.agentSpec();
      st.agentMd = res.markdown || "";
      st.agentSchema = JSON.stringify(res.json_schema || {}, null, 2);
      ctx.rerender();
      ctx.toast(`Briefing generiert (v${res.version || "?"})`);
    } catch (err) { ctx.toast("Briefing fehlgeschlagen"); }
  });
  const copyTo = (sel, text) => {
    const b = root.querySelector(sel);
    if (b) b.addEventListener("click", () => {
      try { navigator.clipboard.writeText(text); ctx.toast("Kopiert"); }
      catch (e) { const ta = root.querySelector(sel === "#copyMd" ? "#agentMd" : "#agentSchema"); if (ta) { ta.select(); document.execCommand("copy"); ctx.toast("Kopiert"); } }
    });
  };
  copyTo("#copyMd", st.agentMd);
  copyTo("#copySchema", st.agentSchema);

  renderMemberPicker(root, ctx, st);
  renderMembers(root, st);
  const gf = root.querySelector("#groupForm");
  gf.elements.display_name.addEventListener("input", () => { st.group.display_name = gf.elements.display_name.value; });
  gf.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    st.group.display_name = gf.elements.display_name.value.trim();
    if (!st.group.display_name || !st.group.members.length) { ctx.toast("Name + Members nötig"); return; }
    await ctx.store.setGroup({ display_name: st.group.display_name, members: st.group.members });
    st.group = { display_name: "", members: [] };
    ctx.toast("Gruppe gespeichert"); ctx.rerender();
  });
  root.querySelectorAll("[data-rm-group]").forEach((b) =>
    b.addEventListener("click", async () => { await ctx.store.removeGroup(b.dataset.rmGroup); ctx.toast("Gruppe entfernt"); ctx.rerender(); }));
}
