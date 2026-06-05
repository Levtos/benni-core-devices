import { esc } from "../styles.js";

function newGroupDraft() {
  return { slug: "", display_name: "", members: [], bulk: "" };
}

function lightOptions(hass) {
  return Object.keys((hass && hass.states) || {})
    .filter((entityId) => entityId.startsWith("light."))
    .sort()
    .map((entityId) => `<option value="${esc(entityId)}"></option>`)
    .join("");
}

function syncDraft(root) {
  const form = root.querySelector("#groupForm");
  const bulk = root.querySelector("#bulkForm");
  if (!form || !root._groupDraft) return;
  root._groupDraft.slug = form.elements.slug.value.trim();
  root._groupDraft.display_name = form.elements.display_name.value.trim();
  if (bulk) root._groupDraft.bulk = bulk.elements.payload.value;
}

function addMember(root, value) {
  const entityId = String(value || "").trim();
  if (!entityId || !root._groupDraft || root._groupDraft.members.includes(entityId)) {
    return;
  }
  root._groupDraft.members.push(entityId);
}

function renderMemberPicker(root, ctx) {
  const mount = root.querySelector("#memberPicker");
  if (!mount) return;
  mount.innerHTML = "";

  if (customElements.get("ha-entity-picker")) {
    const picker = document.createElement("ha-entity-picker");
    picker.hass = ctx.hass;
    picker.includeDomains = ["light"];
    picker.allowCustomEntity = true;
    picker.addEventListener("value-changed", (ev) => {
      addMember(root, ev.detail.value);
      picker.value = "";
      renderMembers(root, ctx);
    });
    mount.appendChild(picker);
    return;
  }

  mount.innerHTML = `
    <div class="row">
      <input id="memberInput" list="lights" placeholder="light.kitchen">
      <button class="btn" type="button" id="addMember">Add</button>
      <datalist id="lights">${lightOptions(ctx.hass)}</datalist>
    </div>`;
  const input = mount.querySelector("#memberInput");
  mount.querySelector("#addMember").addEventListener("click", () => {
    addMember(root, input.value);
    input.value = "";
    renderMembers(root, ctx);
  });
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      addMember(root, input.value);
      input.value = "";
      renderMembers(root, ctx);
    }
  });
}

function renderMembers(root, ctx) {
  const list = root.querySelector("#memberList");
  if (!list || !root._groupDraft) return;
  const members = root._groupDraft.members;
  list.innerHTML = members.length
    ? members.map((entityId, index) => `
        <span class="member-chip">
          <span class="mono">${esc(entityId)}</span>
          <button type="button" data-remove-member="${index}" title="Remove">x</button>
        </span>`).join("")
    : `<span class="muted">No members selected.</span>`;
  list.querySelectorAll("[data-remove-member]").forEach((button) => {
    button.addEventListener("click", () => {
      members.splice(Number(button.dataset.removeMember), 1);
      renderMembers(root, ctx);
    });
  });
}

export function render(root, ctx) {
  root.dataset.keepDraft = "true";
  const status = ctx.store.status || {};
  const groups = status.groups || [];
  if (!root._groupDraft) root._groupDraft = newGroupDraft();
  const draft = root._groupDraft;

  root.innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <h2>Light group</h2>
        <form id="groupForm" class="form">
          <label>Name
            <input name="display_name" value="${esc(draft.display_name)}" required>
          </label>
          <label>Slug
            <input name="slug" value="${esc(draft.slug)}">
          </label>
          <label>Members
            <div id="memberPicker"></div>
          </label>
          <div id="memberList" class="member-list"></div>
          <button class="btn primary" type="submit">Save group</button>
        </form>
      </div>
      <div class="card">
        <h2>Bulk import</h2>
        <form id="bulkForm" class="form">
          <textarea name="payload" spellcheck="false">${esc(draft.bulk)}</textarea>
          <button class="btn" type="submit">Import</button>
        </form>
      </div>
    </div>
    <div class="card" style="margin-top:14px">
      <h2>Configured groups</h2>
      ${groups.length ? `<table>
        <thead><tr><th>Slug</th><th>State</th><th>Members</th><th></th></tr></thead>
        <tbody>${groups.map((group) => `
          <tr>
            <td class="mono">${esc(group.slug)}</td>
            <td>${esc(group.state)}</td>
            <td>${esc((group.members || []).join(", "))}</td>
            <td><button class="btn danger" data-remove-group="${esc(group.slug)}">Remove</button></td>
          </tr>
        `).join("")}</tbody>
      </table>` : `<div class="empty">No groups configured.</div>`}
    </div>`;

  renderMemberPicker(root, ctx);
  renderMembers(root, ctx);

  root.querySelectorAll("#groupForm input, #bulkForm textarea").forEach((input) => {
    input.addEventListener("input", () => syncDraft(root));
  });

  root.querySelector("#groupForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    syncDraft(root);
    await ctx.store.setGroup({
      slug: draft.slug || undefined,
      display_name: draft.display_name,
      members: draft.members,
    });
    root._groupDraft = newGroupDraft();
    ctx.toast("Group saved");
    ctx.rerender();
  });

  root.querySelector("#bulkForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    syncDraft(root);
    await ctx.store.bulkImport(draft.bulk);
    root._groupDraft.bulk = "";
    ctx.toast("Import complete");
    ctx.rerender();
  });

  root.querySelectorAll("[data-remove-group]").forEach((button) => {
    button.addEventListener("click", async () => {
      await ctx.store.removeGroup(button.dataset.removeGroup);
      ctx.toast("Group removed");
      ctx.rerender();
    });
  });
}

