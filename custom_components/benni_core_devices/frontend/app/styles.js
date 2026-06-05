export const CSS = `
:host, * { box-sizing: border-box; }
:host {
  --bg: #18191d;
  --panel: #202229;
  --surface: #282b33;
  --surface2: #30343d;
  --line: #3d424c;
  --fg: #f4f5f7;
  --muted: #a7adb8;
  --faint: #737b89;
  --accent: #6ee7b7;
  --blue: #93c5fd;
  --yellow: #facc15;
  --red: #fb7185;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--fg);
}
.app { display: grid; grid-template-columns: 252px 1fr; min-height: 100vh; background: var(--bg); }
.sidebar { background: var(--panel); border-right: 1px solid var(--line); padding: 18px 12px; display: flex; flex-direction: column; gap: 10px; }
.brand { display: flex; align-items: center; gap: 12px; padding: 4px 8px 16px; }
.logo { width: 38px; height: 38px; border-radius: 8px; background: #143b32; color: var(--accent); display: grid; place-items: center; font-size: 22px; }
.brand b { display: block; font-size: 15px; }
.brand small { color: var(--muted); font-size: 11px; }
.nav { display: flex; flex-direction: column; gap: 3px; }
.nav button { display: flex; align-items: center; gap: 10px; width: 100%; border: 0; border-radius: 8px; background: none; color: var(--muted); padding: 10px 11px; cursor: pointer; text-align: left; font-size: 14px; }
.nav button:hover, .nav button.active { background: var(--surface); color: var(--fg); }
.nav button.active { box-shadow: inset 2px 0 0 var(--accent); }
.sb-foot { margin-top: auto; padding: 10px; border-top: 1px solid var(--line); color: var(--faint); font-size: 11px; }
.main { padding: 22px 26px; overflow: auto; }
.head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; flex-wrap: wrap; }
h1 { margin: 0; font-size: 24px; }
.chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip { display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 4px 10px; font-size: 12px; white-space: nowrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--faint); }
.chip.ok { color: var(--accent); } .chip.ok .dot { background: var(--accent); }
.chip.warn { color: var(--yellow); } .chip.warn .dot { background: var(--yellow); }
.chip.info { color: var(--blue); } .chip.info .dot { background: var(--blue); }
.grid { display: grid; gap: 14px; }
.cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 15px; }
.card h2 { margin: 0 0 12px; font-size: 14px; }
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.kv { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--line); }
.kv:last-child { border-bottom: 0; }
.k { color: var(--muted); font-size: 13px; }
.v { font-weight: 600; font-size: 13px; overflow-wrap: anywhere; }
.mono { font-family: ui-monospace, "Cascadia Code", monospace; font-size: 12px; color: var(--blue); }
.muted { color: var(--muted); }
button, select, input, textarea { font: inherit; }
button.btn { background: var(--surface2); border: 1px solid var(--line); color: var(--fg); border-radius: 8px; padding: 8px 12px; cursor: pointer; }
button.btn:hover { border-color: var(--accent); }
button.btn.primary { background: #17463b; color: var(--accent); border-color: #246653; font-weight: 650; }
button.btn.danger { color: var(--red); }
label { display: grid; gap: 5px; color: var(--muted); font-size: 12px; }
input, select, textarea { width: 100%; border: 1px solid var(--line); background: #17191f; color: var(--fg); border-radius: 7px; padding: 8px; min-height: 36px; }
textarea { min-height: 110px; resize: vertical; }
.form { display: grid; gap: 12px; }
.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
.fieldcheck { display: flex; align-items: center; gap: 8px; background: #1d2027; border: 1px solid var(--line); border-radius: 7px; padding: 8px; color: var(--fg); }
.fieldcheck input { width: auto; min-height: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--line); text-align: left; padding: 8px; font-size: 13px; vertical-align: top; }
th { color: var(--muted); font-size: 12px; }
.empty { border: 1px dashed var(--line); border-radius: 8px; color: var(--muted); padding: 22px; text-align: center; }
.toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%); background: var(--surface); border: 1px solid var(--accent); border-radius: 8px; padding: 10px 16px; z-index: 10; }
@media (max-width: 820px) {
  .app { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
  .cols-2, .cols-3, .fields { grid-template-columns: 1fr; }
}
`;

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function chip(kind, label) {
  return `<span class="chip ${esc(kind)}"><span class="dot"></span>${esc(label)}</span>`;
}

