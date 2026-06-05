export const CSS = `
:host, * { box-sizing: border-box; }
:host {
  /* Dracula-inspirierte Palette */
  --bg: #1c1d26;
  --panel: #282a36;
  --surface: #2d2f3d;
  --surface2: #343746;
  --line: #414458;
  --line-soft: #34374a;
  --fg: #f8f8f2;
  --muted: #b6bad2;
  --faint: #6272a4;
  --purple: #bd93f9;
  --purple-soft: #2c2546;
  --teal: #8be9fd;
  --green: #50fa7b;
  --amber: #ffb86c;
  --yellow: #f1fa8c;
  --red: #ff5555;
  --pink: #ff79c6;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--fg);
}
.app { display: grid; grid-template-columns: 246px 1fr; min-height: 100vh; background: var(--bg); }

/* Sidebar */
.sidebar { background: var(--panel); border-right: 1px solid var(--line); padding: 18px 12px; display: flex; flex-direction: column; gap: 8px; }
.brand { display: flex; align-items: center; gap: 12px; padding: 4px 8px 16px; }
.logo { width: 38px; height: 38px; border-radius: 10px; background: var(--purple-soft); color: var(--purple); display: grid; place-items: center; font-size: 22px; }
.brand b { display: block; font-size: 15px; }
.brand small { color: var(--faint); font-size: 11px; }
.nav { display: flex; flex-direction: column; gap: 3px; }
.nav button { display: flex; align-items: center; gap: 10px; width: 100%; border: 0; border-radius: 9px; background: none; color: var(--muted); padding: 10px 11px; cursor: pointer; text-align: left; font-size: 14px; }
.nav button:hover { background: var(--surface); color: var(--fg); }
.nav button.active { background: var(--purple-soft); color: var(--purple); box-shadow: inset 2px 0 0 var(--purple); }
.nav .sep { margin: 8px 6px 4px; color: var(--faint); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.sb-foot { margin-top: auto; padding: 10px; border-top: 1px solid var(--line); color: var(--faint); font-size: 11px; }

/* Main */
.main { padding: 22px 26px; overflow: auto; }
.head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; flex-wrap: wrap; }
.head h1 { margin: 0; font-size: 23px; }
.head .sub { color: var(--faint); font-size: 12px; margin-top: 3px; }
.chips { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }

/* Chips / Badges */
.chip { display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 4px 10px; font-size: 12px; white-space: nowrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--faint); }
.chip.ok { color: var(--green); border-color: #2c5138; } .chip.ok .dot { background: var(--green); }
.chip.warn { color: var(--amber); border-color: #5b4327; } .chip.warn .dot { background: var(--amber); }
.chip.err { color: var(--red); border-color: #5a2b2f; } .chip.err .dot { background: var(--red); }
.chip.info { color: var(--teal); border-color: #2a4a55; } .chip.info .dot { background: var(--teal); }
.chip.accent { color: var(--purple); border-color: #3c2f5e; } .chip.accent .dot { background: var(--purple); }

/* Stat tiles */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 18px; }
.stat { background: var(--surface); border: 1px solid var(--line); border-radius: 11px; padding: 14px 16px; }
.stat .n { font-size: 26px; font-weight: 700; line-height: 1.1; }
.stat .l { color: var(--muted); font-size: 12px; margin-top: 4px; }
.stat .s { color: var(--faint); font-size: 11px; }
.stat.ok .n { color: var(--green); }
.stat.warn .n { color: var(--amber); }
.stat.err .n { color: var(--red); }
.stat.accent .n { color: var(--purple); }
.stat.info .n { color: var(--teal); }

/* Layout helpers */
.grid { display: grid; gap: 14px; }
.cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.split { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; align-items: start; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 11px; padding: 16px; }
.card h2 { margin: 0 0 12px; font-size: 14px; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.section-head h2 { margin: 0; }
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.spread { justify-content: space-between; }
.muted { color: var(--muted); }
.faint { color: var(--faint); }
.mono { font-family: ui-monospace, "Cascadia Code", monospace; font-size: 12px; color: var(--teal); overflow-wrap: anywhere; }

/* Key/Value */
.kv { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--line-soft); }
.kv:last-child { border-bottom: 0; }
.k { color: var(--muted); font-size: 13px; }
.v { font-weight: 600; font-size: 13px; overflow-wrap: anywhere; text-align: right; }

/* Tabs */
.tabs { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 14px; border-bottom: 1px solid var(--line); }
.tabs button { border: 0; background: none; color: var(--muted); padding: 9px 13px; cursor: pointer; font-size: 13px; border-bottom: 2px solid transparent; margin-bottom: -1px; }
.tabs button:hover { color: var(--fg); }
.tabs button.active { color: var(--purple); border-bottom-color: var(--purple); }

/* Filter pills */
.filters { display: flex; gap: 6px; flex-wrap: wrap; }
.filters button { border: 1px solid var(--line); background: var(--surface2); color: var(--muted); border-radius: 999px; padding: 5px 12px; cursor: pointer; font-size: 12px; }
.filters button.active { color: var(--purple); border-color: var(--purple); background: var(--purple-soft); }

/* Forms */
button, select, input, textarea { font: inherit; }
button.btn { background: var(--surface2); border: 1px solid var(--line); color: var(--fg); border-radius: 9px; padding: 8px 13px; cursor: pointer; }
button.btn:hover { border-color: var(--purple); }
button.btn.primary { background: var(--purple-soft); color: var(--purple); border-color: #4a3a73; font-weight: 650; }
button.btn.danger { color: var(--red); }
button.btn.small { padding: 5px 9px; font-size: 12px; }
label { display: grid; gap: 5px; color: var(--muted); font-size: 12px; }
input, select, textarea { width: 100%; border: 1px solid var(--line); background: #1b1c25; color: var(--fg); border-radius: 8px; padding: 8px; min-height: 36px; }
textarea { min-height: 120px; resize: vertical; font-family: ui-monospace, "Cascadia Code", monospace; font-size: 12px; }
.form { display: grid; gap: 12px; }

/* Slot section (builder) */
.slot-group { border: 1px solid var(--line); border-radius: 10px; padding: 12px; background: #24262f; margin-bottom: 10px; }
.slot-group > h3 { margin: 0 0 10px; font-size: 13px; color: var(--purple); display: flex; align-items: center; gap: 8px; }
.slot-row { display: grid; grid-template-columns: 26px 1fr 1.3fr auto; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--line-soft); }
.slot-row:last-child { border-bottom: 0; }
.slot-row .slot-name { font-size: 13px; }
.slot-row .slot-name small { display: block; color: var(--faint); font-size: 10px; }
.slot-row ha-entity-picker { width: 100%; --mdc-theme-surface: #1b1c25; --mdc-theme-on-surface: var(--fg); }
.slot-state { font-size: 11px; text-align: right; }
.fieldcheck { display: inline-flex; align-items: center; }
.fieldcheck input { width: auto; min-height: auto; }

/* Preview panel */
.preview { background: #1b1c25; border: 1px solid var(--line); border-radius: 10px; padding: 12px; }
.preview .pv-id { color: var(--purple); }

/* Tables */
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--line-soft); text-align: left; padding: 9px 8px; font-size: 13px; vertical-align: top; }
th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
tr.clickable { cursor: pointer; }
tr.clickable:hover td { background: rgba(189, 147, 249, .06); }
tr.selected-row td { background: rgba(189, 147, 249, .12); }
td.s-err { color: var(--red); } td.s-warn { color: var(--amber); } td.s-ok { color: var(--green); }

/* Member chips */
.member-list { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.member-chip { display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--line); background: #24262f; border-radius: 999px; padding: 5px 8px 5px 10px; max-width: 100%; }
.member-chip button { border: 0; background: var(--surface2); color: var(--muted); width: 22px; height: 22px; border-radius: 50%; cursor: pointer; line-height: 1; }
.member-chip button:hover { color: var(--red); }

/* Rules editor */
.rule-row { display: grid; grid-template-columns: 24px 1.1fr 1fr 1fr .9fr 1.2fr 30px; gap: 7px; align-items: center; padding: 6px 0; }
.rule-row .ord { color: var(--faint); font-size: 12px; text-align: center; }

/* Warnings box */
.warnbox { border: 1px solid #5b4327; background: #2a2418; border-radius: 9px; padding: 10px 12px; color: var(--amber); font-size: 12px; }
.warnbox.err { border-color: #5a2b2f; background: #2a1a1c; color: var(--red); }
.warnbox ul { margin: 6px 0 0; padding-left: 18px; }

.empty { border: 1px dashed var(--line); border-radius: 10px; color: var(--muted); padding: 22px; text-align: center; }
.toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%); background: var(--surface); border: 1px solid var(--purple); border-radius: 9px; padding: 10px 16px; z-index: 10; }

@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
  .cols-2, .cols-3, .split { grid-template-columns: 1fr; }
  .slot-row, .rule-row { grid-template-columns: 1fr; }
}
`;

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function chip(kind, label) {
  return `<span class="chip ${esc(kind)}"><span class="dot"></span>${esc(label)}</span>`;
}

// Mappt eine atomic_quality / Verfügbarkeit auf eine Severity-Klasse.
export function qualityKind(quality) {
  if (quality === "unavailable") return "err";
  if (quality === "degraded") return "warn";
  return "ok";
}
