import { esc } from "../styles.js";

function lightOptions(hass) {
  return Object.keys((hass && hass.states) || {})
    .filter((entityId) => entityId.startsWith("light."))
    .sort()
    .map((entityId) => `<option value="${esc(entityId)}"></option>`)
    .join("");
}

export function render(root, ctx) {
  const status = ctx.store.status || {};
  const groups = status.groups || [];
  root.innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <h2>Light group</h2>
        <form id="groupForm" class="form">
          <label>Name
            <input name="display_name" required>
          </label>
          <label>Slug
            <input name="slug">
          </label>
          <label>Members
            <textarea name="members" list="lights" placeholder="light.kitchen&#10;light.table"></textarea>
            <datalist id="lights">${lightOptions(ctx.hass)}</datalist>
          </label>
          <button class="btn primary" type="submit">Save group</button>
        </form>
      </div>
      <div class="card">
        <h2>Bulk import</h2>
        <form id="bulkForm" class="form">
          <textarea name="payload" spellcheck="false"></textarea>
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

  root.querySelector("#groupForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    const members = form.elements.members.value
      .split(/[\n,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
    await ctx.store.setGroup({
      slug: form.elements.slug.value || undefined,
      display_name: form.elements.display_name.value,
      members,
    });
    form.reset();
    ctx.toast("Group saved");
    ctx.rerender();
  });

  root.querySelector("#bulkForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    await ctx.store.bulkImport(form.elements.payload.value);
    form.reset();
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

