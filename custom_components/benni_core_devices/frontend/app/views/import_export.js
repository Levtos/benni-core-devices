import { chip, esc } from "../styles.js";

function newState() {
  return { bulk: "", report: null, exportYaml: "", group: { display_name: "", members: [] } };
}

function reportCard(result) {
  if (!result) return "";
  const rows = (result.report || []).map((r) => {
    const sev = r.derived_sources.length ? "err" : (r.missing_entities.length ? "warn" : "ok");
    const issues = [
      ...r.derived_sources.map((x) => `<div class="warnbox err" style="margin-top:4px">${esc(x)}</div>`),
      r.missing_entities.length ? `<div class="warnbox" style="margin-top:4px">Leere Slots: ${esc(r.missing_entities.join(", "))}</div>` : "",
      r.unknown_slots.length ? `<div class="warnbox" style="margin-top:4px">Unbekannte Slots: ${esc(r.unknown_slots.join(", "))}</div>` : "",
    ].join("");
    return `<tr>
      <td>${chip(sev, r.accepted ? "akzeptiert" : "blockiert")}</td>
      <td class="mono">${esc(r.entity_id)}</td>
      <td>${esc(r.device_type)}</td>
      <td>${issues || `<span class="muted">—</span>`}</td>
    </tr>`;
  }).join("");
  return `
    <div class="card" style="margin-top:14px">
      <div class="section-head">
        <h2>${result.dry_run ? "Dry-Run Vorschau" : "Import-Ergebnis"}</h2>
        <div class="row">${chip("info", `${result.devices} Devices`)}${chip("info", `${result.groups} Groups`)}</div>
      </div>
      ${rows ? `<table><thead><tr><th>Status</th><th>Entity</th><th>Typ</th><th>Hinweise</th></tr></thead><tbody>${rows}</tbody></table>`
        : `<div class="muted">Keine Devices im Payload.</div>`}
    </div>`;
}

function renderMemberPicker(root, ctx, st) {
  const mount = root.querySelector("#memberPicker");
  if (!mount) return;
  mount.innerHTML = "";
  const add = (val) => {
    const e = String(val || "").trim();
    if (e && !st.group.members.includes(e)) { st.group.members.push(e); renderMembers(root, ctx, st); }
  };
  if (customElements.get("ha-entity-picker")) {
    const picker = document.createElement("ha-entity-picker");
    picker.hass = ctx.hass;
    picker.includeDomains = ["light"];
    picker.allowCustomEntity = true;
    picker.addEventListener("value-changed", (ev) => { add(ev.detail.value); picker.value = ""; });
    mount.appendChild(picker);
    return;
  }
  mount.innerHTML = `<div class="row"><input id="memberInput" placeholder="light.kitchen"><button class="btn" type="button" id="addMember">Add</button></div>`;
  mount.querySelector("#addMember").addEventListener("click", () => {
    const i = mount.querySelector("#memberInput"); add(i.value); i.value = "";
  });
}

function renderMembers(root, ctx, st) {
  const list = root.querySelector("#memberList");
  if (!list) return;
  list.innerHTML = st.group.members.length
    ? st.group.members.map((e, idx) =>
        `<span class="member-chip"><span class="mono">${esc(e)}</span><button type="button" data-rm="${idx}">×</button></span>`).join("")
    : `<span class="muted">Keine Mitglieder.</span>`;
  list.querySelectorAll("[data-rm]").forEach((b) =>
    b.addEventListener("click", () => { st.group.members.splice(Number(b.dataset.rm), 1); renderMembers(root, ctx, st); }));
}

export function render(root, ctx) {
  root.dataset.keepDraft = "true";
  const status = ctx.store.status || {};
  const groups = status.groups || [];
  if (!root._ie) root._ie = newState();
  const st = root._ie;

  root.innerHTML = `
    <div class="split">
      <div class="card">
        <h2>Bulk Import</h2>
        <p class="muted" style="font-size:12px; margin:0 0 10px">
          Nur rohe HA-Entities. <span class="mono">*_atomic</span>/<span class="mono">*_combined</span>/derived werden im Dry-Run markiert.
        </p>
        <textarea id="bulk" spellcheck="false" placeholder="- slug: tv&#10;  device_type: tv&#10;  integration_entity: media_player.living_lgtv">${esc(st.bulk)}</textarea>
        <div class="row" style="margin-top:10px">
          <button class="btn" type="button" id="dryRun">Dry Run / Vorschau</button>
          <button class="btn primary" type="button" id="doImport">Import</button>
        </div>
        <div id="reportMount">${reportCard(st.report)}</div>
      </div>
      <div class="card">
        <h2>Export</h2>
        <p class="muted" style="font-size:12px; margin:0 0 10px">Aktuelle Builder-Konfiguration (Devices, Combineds, Groups).</p>
        <button class="btn" type="button" id="doExport">Konfiguration exportieren</button>
        ${st.exportYaml ? `<textarea readonly style="margin-top:10px; min-height:200px">${esc(st.exportYaml)}</textarea>` : ""}
      </div>
    </div>

    <div class="card" style="margin-top:14px">
      <details>
        <summary style="cursor:pointer; color:var(--muted)">Light Groups (untergeordnet)</summary>
        <div class="split" style="margin-top:12px">
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
      </details>
    </div>`;

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
      root.querySelector("#reportMount").innerHTML =
        `<div class="warnbox err" style="margin-top:14px">${esc(err.message || err)}</div>`;
    }
  };
  root.querySelector("#dryRun").addEventListener("click", () => runImport(true));
  root.querySelector("#doImport").addEventListener("click", () => runImport(false));

  root.querySelector("#doExport").addEventListener("click", async () => {
    try {
      const res = await ctx.store.exportConfig();
      st.exportYaml = res.yaml || "";
      ctx.rerender();
    } catch (err) {
      ctx.toast("Export fehlgeschlagen");
    }
  });

  renderMemberPicker(root, ctx, st);
  renderMembers(root, ctx, st);
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
    b.addEventListener("click", async () => {
      await ctx.store.removeGroup(b.dataset.rmGroup); ctx.toast("Gruppe entfernt"); ctx.rerender();
    }));
}
