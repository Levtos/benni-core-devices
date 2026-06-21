# Changelog

## 0.4.17 - Fix: True Master UX

- Diagnose and header chips now count and render first-class `status.masters` instead of classifying Combineds with exposed attributes as Masters.
- Import preview shows `master_report` separately from `combined_report`.
- Combined Builder no longer labels attribute-rich Combineds as `Master/Fusion`; Openings and Media Plug Protection remain Combineds in the UI.

## 0.4.16 - FLEET-108/141: Raw-Source Domain Masters

- Add first-class `masters:` import/export support publishing `sensor.<profile>_master_<slug>`.
- Keep Masters raw-source only while allowing Combineds to consume published Master outputs.
- Support `remove_devices`, `remove_combineds`, and `remove_masters` in bulk imports for the domain-master cutover.

## 0.4.15 - FLEET-130/131: Combined Attribute Sources

- Allow Combined sources to read `state_attr(entity, attribute)` via optional `attribute`, matching device bindings.
- Expose `source_attributes` in Combined diagnostics so Master contracts show which sources read states vs attributes.
- Preserve Combined source attributes in the Builder and document the syntax for agents.

## 0.4.14 - FLEET-126: TV Power-Down Sticky Hold

- Stop watt-primary sticky-hold for assumed-state integrations when the integration source freshly reports `off` and the watt meter is already below the on threshold.
- Keep sticky-hold for normal watt-primary devices and for assumed-state media devices that still report an active player state during a short watt dip.
- Add regression coverage so the living TV Atomic no longer holds a phantom `on` after TV/PS5 power-down.

## 0.4.13 - FLEET-91: Promoted Derived Entities

- Allow `derived` binary sensors to target `derived_values` nodes for the rare History/native-HA promotion path.
- Add optional `object_id` overrides for promoted derived binary sensors while keeping derived values attribute-first by default.
- Keep status, bulk-import published output detection, agent schema, and Combined Builder aligned with the promoted entity object ID.

## 0.4.12 - Fix: Panel Cache-Bust Executor

- Move frontend app cache-bust file walking out of the Home Assistant event loop via `hass.async_add_executor_job`.
- Add a focused view setup regression test with Home Assistant stubs.

## 0.4.11 - FLEET-92: Published Output Registry

- Source classification can now use an authoritative `published_outputs` registry, so exact Core Devices outputs are accepted while own-prefix misses are treated as unpublished forward refs.
- Bulk import, status, save warnings, and dry-run reports share the same published-output registry for device, combined, derived binary, and light-group outputs.
- Combined dry-run reports accept published Fusion/Gate sources separately and block unpublished own outputs via `source_blocks`.

## 0.4.10 - FLEET-93: Master UX

- Diagnose distinguishes Master/Fusion entries from regular Combineds with a dedicated filter, stats count, row type, and detail badge.
- Master detail cards show exposed flat attributes directly.
- Header chips, Combined Builder edit/preview, and Import dry-run preview mark Master configs consistently.

## 0.4.9 - FLEET-93: Enum Derived Attributes

- Combined `derived_values` support a new `enum` node with ordered `cases` and `default` for string attributes such as room/window opening states.
- The expression engine can now compare refs to `null`, enabling explicit stale-source detection without weakening existing None propagation.
- Agent briefing, schema, WebSocket catalog, and tests document the new enum-derived contract.

## 0.4.8 — FLEET-89: Master-Fusion Attribute

- Combined `derived_values` can now be explicitly exposed as flat top-level sensor attributes via per-node `expose: true` or top-level `exposed_attributes`.
- Combined sensor attributes keep the existing nested `derived` diagnostics while adding only selected published attributes.
- Bulk-import dry-run reports exposed attributes; agent/catalog text documents the new contract.
- Combined Builder preserves `derived_values` and `exposed_attributes` on save so master configs are not accidentally stripped.
## 0.4.3 — Diagnose-UX: Atomic/Combined-Filter

- **Diagnose-Ansicht:** Die Problemliste kann jetzt zusätzlich nach
  `Alle`/`Atomics`/`Combineds` gefiltert werden. Severity-Filter
  (`Alle`/`Fehler`/`Warnungen`/`OK`) bleiben separat erhalten.
- **Detail-Auswahl:** Beim Filterwechsel wird die rechte Detailkarte auf den
  sichtbaren Eintrag zurückgesetzt, damit keine weggefilterten Details stehen
  bleiben.

## 0.4.2 — FLEET-54: Attribute-Quellen für Bindings

- **Binding-Contract erweitert:** `sources`/`controls`/`metadata_sources`
  dürfen optional `attribute: <name>` tragen. Dann liest die Integration
  `state_attr(entity, attribute)` statt des Entity-State.
- **DWD-/Weather-Support:** Environment-Rollen können dadurch Werte wie
  `temperature` oder `humidity` direkt aus `weather.dwd_home` verwenden;
  numerische Rollen coercen den Attributwert wie bisher zu Zahlen.
- **Availability/Diagnose:** Fehlende oder `None`-Attribute verhalten sich wie
  fehlende Quellen und erscheinen in `source_available`, `missing_required` und
  `source_attributes`.
- Agent-Schema, Import-Validierung und Tests wurden um `attribute` erweitert.

## 0.4.1 — FLEET-54: datei-basierter MCP-Import

- **Neue arg-lose Services:** `import_file_dry_run` und `import_file_apply`
  lesen `<config>/benni_core_devices/import.yaml` und liefern den bekannten
  `bulk_import`-Report mit `return_response: true` zurück.
- **MCP-sicherer Workflow:** Datei im `export_config`-Format bearbeiten
  (`devices:`, `combineds:`, `light_groups:`), optional `replace: true` für
  Clean Slate setzen, dry-run prüfen, dann explizit apply aufrufen.
- **Geteilte Logik:** Datei-Import, alter `bulk_import`-Service und WS-Import
  nutzen dieselbe HA-freie Parse-/Report-/Apply-Schicht. Fehlende Import-Datei
  erzeugt eine klare Response statt eines Service-Crashes.

## 0.4.0 — Combined v1.0 (Expression / Gate / Health / Latch)

Additiv auf die v0-First-Match-Engine — v0 bleibt unverändert. HA-frei + getestet.

- **`combined_expr.py`** — sichere Mini-Expression-Engine (eigener AST, **kein
  eval/Jinja**): `${refs}`, `+ - * /`, `== != < <= > >=`, `and/or/not`,
  Funktionen `min/max/abs/round/clamp/any/all/not`. None-Propagation + Div0→None.
- **`derived_values[]`** (v1.0) in der Combined-Config — benannte Zwischenwerte,
  vor den Regeln ausgewertet; Regeln/Output dürfen `${name}`/`${self}` nutzen,
  Output kann `"${name}"` sein:
  - `expr` (Zahl), `gate` (Boolean), `health` (`ok|degraded|problem` aus
    Atomic-Quellen), `latch` (Schmitt-Hysterese set/reset + hold, **v1.0b**),
    `previous` (`${self}`, **v1.0b**).
  - `fail_safe` pro Node/Config (`off|open|hold_last|unknown`).
- **Persistenz (v1.0b):** Combineds speichern `last_state` + Node-States (Store),
  für `latch`/`previous`/`hold_last` über Neustarts. **Kein Scheduling** (Timer =
  v1.1).
- **Dry-Run-Validierung:** `bulk_import` prüft v1-Configs (Parse-Fehler,
  unbekannte `${refs}`, Zyklen, `since`/Timer → v1.1-Ablehnung) und meldet pro
  Combined.
- **Shadow-Compare** (`shadow_of`): Attribut `shadow_compare {expected, actual,
  diverges}` für den Strangler-Vergleich gegen alte YAML-Sensoren.
- Katalog + Agent-Briefing um die v1-Node-Typen erweitert.

## 0.3.6 — Fix: Service-Handler-Registrierung

- **Bug:** Services waren mit `lambda call: handler(hass, call)` registriert —
  ein Lambda, das eine Coroutine zurückgibt, erkennt HA nicht als
  Coroutine-Funktion → wird nicht awaited → 500 beim Aufruf.
- **Fix:** Registrierung über `functools.partial(handler, hass)` (von HA als
  Coroutine-Funktion erkannt). `export_config`/`bulk_import` (und die
  Override-Services) funktionieren jetzt via `ha_call_service`/MCP.

## 0.3.5 — Import/Export als HA-Service (MCP-/Agenten-fähig)

- **Neuer Service `benni_core_devices.bulk_import`** (`payload`, `dry_run`,
  `replace`) mit Response → der Import ist jetzt **per `ha_call_service`** (also
  von Claude Code / Codex über MCP) ausführbar, nicht mehr nur übers Panel.
  Default `dry_run=true` (sicher); `replace=true` = Clean-Slate (bestehende
  Devices/Combineds/Groups werden ersetzt statt gemerged).
- **Neuer Service `benni_core_devices.export_config`** (Response: `yaml`).
- Damit ist der Agenten-Workflow end-to-end über MCP fahrbar: export → discover
  → bulk_import dry_run → apply. WS-Commands bleiben unverändert (geteilte
  Logik `run_bulk_import`). `replace`-Option auch im WS-`bulk_import`.
- Nebenfix: Override-Services waren mit falscher Handler-Signatur registriert
  (nie funktionsfähig) — korrigiert.

## 0.3.4 — Combined-Import (Round-Trip)

- **`bulk_import` verarbeitet jetzt auch `combineds:`** (Dict slug → config) —
  zusätzlich zu `devices:`/`light_groups:`. Damit voller Round-Trip mit dem
  bereits vorhandenen `export_config` und Agenten können Combineds im selben
  YAML bauen. Geräte sind beim Import jetzt optional (combined-only möglich).
- Dry-Run-Report zeigt einen separaten **Combined-Abschnitt** (Output-Typ,
  Quellenzahl, blockierte/abgeleitete Quellen, resultierende Entity-ID).
- Agent-Briefing aktualisiert (Combineds via bulk_import ODER `set_combined`).

## 0.3.3 — Fix: Verfügbarkeit bei stabilen Zuständen (alle Pfade)

- **Bug:** Verfügbarkeit wurde über ein **600s-Zeitfenster** (`last_updated`)
  bewertet. Ein lange unveränderter Zustand (Kontakt/Cover/Climate `off`, ein
  stabiler `switch on/off`, ein „off"-Media ohne Watt) hat ein altes
  `last_updated` → fiel fälschlich als „nicht frisch" raus → `available: false`
  + `fail_safe_active`/sticky, obwohl die Quelle gültig war (z. B. Patio-Door-
  Atomic dauerhaft `unavailable`).
- **Fix:** Verfügbarkeit + Integration-Quelle werten jetzt **Wert-Präsenz** aus
  (nicht `unavailable`/`unknown`) — kein Zeitfenster. Betrifft beide Pfade:
  `compute_passthrough`/`compute_numeric` **und** `compute_device`
  (media/audio/console/power).
- **Power-Semantik unverändert:** Entscheidungsreihenfolge Override → Integration
  → Watt → Sticky-Hold, Watt-Buckets, `watt_disagrees`, Boot-Phase bleiben
  identisch (R-DC-Tests grün). Echte Ausfälle (Wert `None`) lösen weiterhin
  Watt-Fallback/Sticky/Fail-Safe aus.
- `consumes` listet jetzt alle konsumierten Entities (Sources + Controls +
  Metadaten), nicht nur Sources.

## 0.3.2 — Agent-Briefing-Generator (Import für LLM-Agenten)

- **Neuer „Agent-Briefing"-Generator** (Import/Export-Seite + WS
  `get_agent_spec`): erzeugt ein selbsterklärendes **Markdown-Briefing + JSON-
  Schema** für eine frische Claude-Code-/Codex-Session mit MCP-Anbindung. Enthält
  Rollenkatalog, Klassen (required/optional/controls + abgeleitete Metadaten,
  Domains, fail_safe, exposed attributes), Blocked-Source-Regeln, Import-YAML-
  Schema + Beispiele, Combined-Config-Schema und den Workflow
  (export → discover via MCP → `bulk_import` dry_run → apply; Combineds via
  `set_combined`) sowie den aktuellen Export als Kontext.
- Ziel: Atomics/Combineds per Import durch einen Agenten bauen lassen; die beiden
  Builder bleiben für manuelle Eingriffe. Reiner Generator — löst keinen Agenten aus.
- Neuer HA-freier, getesteter Layer `agent_spec.py`.

## 0.3.1 — Versions-Badge + v2.1-Auslieferung

- **Version im Panel sichtbar**: WebSocket-Katalog liefert die Integrations-
  Version (aus dem Manifest); das Panel zeigt sie als Chip oben rechts und im
  Sidebar-Fuß. So ist sofort erkennbar, welcher Stand wirklich deployt ist.
- **Versions-Bump** erzwingt ein echtes HACS-Update: v2 und v2.1 trugen beide
  `0.3.0`, weshalb HACS „keine neue Version" sah und den alten Stand behielt.
  0.3.1 transportiert die v2.1-Korrekturen (abgeleitete Metadaten, klassen-
  gescopte Rollen, eingeengte Domains) zuverlässig auf die Instanz.

## 0.3.0 — Rollenbasierter v2-Rework (Hard-Rework)

Harter Rework: `device_type` + flache Slots → `atomic_class` + `variant` +
`sources[]` / `controls[]` / `metadata_sources[]` + `diagnostics`. Keine
Rückwärtskompatibilität nötig (Integration nicht produktiv).

### Invarianten gewahrt
- `logic.compute_device` (R-DC-01..09, Override, Sticky, Watt-Buckets,
  watt_disagrees, Boot-Phase) **semantisch unverändert** — nur die Input-
  Auflösung wechselt von festen Keys auf Rollen.
- `combined.py` unverändert. `classify_source_entity` blockt weiter
  `*_atomic`/`*_combined`/`*_gate`/eigene Prefixe. Object-ID-Prefixe gleich.

### Neu
- `device_types.py` → `ROLE_CATALOG` (sources/controls/metadata, compute_relevant)
  + `ATOMIC_CLASSES` (media_device, audio_endpoint, console_device, power_device,
  opening, environment, light, cover, climate_device, generic_expert + 3 Beta) mit
  `power_model`, `integration_roles`, `required_roles`/`required_mode`, `fail_safe`.
- `DeviceConfigV2` + `SourceBinding` + Rollen-Auflösung (integration/state/watt/
  numeric role, `missing_required`).
- `logic.compute_passthrough` + `compute_numeric` + `fail_safe`
  (off/open/hold_last/unknown) + `last_state`-Persistenz + `fail_safe_active`.
- `attributes.py` rollenbasiert: `source_roles/entities/states/available`,
  `missing_required`, `degraded(_reason)`, `atomic_quality`, `consumes`,
  `fail_safe_active` + per-Klasse-`extra_attributes`. Metadaten-Default aus
  `primary_state`-Attributen, separate `metadata_sources` möglich (z. B. PS5-Title).
- Coordinator wählt Compute-Pfad über `power_model`.
- WebSocket-Katalog liefert `atomic_classes` + `role_catalog`; `set_device`/Import
  v2 (class/variant/sources/controls/metadata); Dry-Run-Report mit `missing_required`.
- Panel: „Was willst du bauen?" (Klassen-Kacheln → Variante → Pflichtquellen →
  Optional/Controls/Metadaten/Erweitert), Diagnose mit „Missing Required".
- Entry-Version 2 + minimaler `async_migrate_entry` (kein Migrator; verwirft alte
  flache Devices, behält Combineds/Groups).

### v2.1-Korrekturen (Builder-UX)
- **Metadaten werden abgeleitet, nicht zugewiesen:** Titel/App/Quelle/Volume/Mute
  etc. kommen automatisch aus den `primary_state`-Attributen (`RoleSpec.derive_attr`).
  Kein Pflicht-Picker mehr; ein Expert-Disclosure „Abweichende Quelle für einzelne
  Attribute" erlaubt optionale Overrides (z. B. PS5-Titel-Sensor).
- **Rollen pro Klasse gescopt:** `AtomicClassSpec.optional_roles` / `control_roles` /
  `metadata_override_roles`; der Builder zeigt nur diese (voller Katalog nur bei
  `generic_expert`).
- **`primary_state`-Domains pro Klasse eingeengt** (`role_domain_overrides`): TV →
  media_player, plug → switch, console → device_tracker/binary_sensor + sensor.
- **Console:** `online`/`offline` zu truthy/falsy ergänzt.
- Wording: Detail-Panel „Slots" → „Quellen".

### Hinweise
- Alte `CONF_*_ENTITY`-Konstanten bleiben als isolierte Legacy-Konstanten in
  `const.py` (ungenutzt) — verhindert Import-Brüche.

## 0.2.0 — Rich Atomic Contract, Diagnose & Combined Builder v0

Rework (Weg C). Additiv, keine Breaking Changes — bestehende Device-Configs und
`sensor.<profile>_device_<slug>` bleiben stabil. Die bestehende Power-Logik
(`logic.compute_device`, R-DC-01..09) ist unverändert.

### Backend
- **Rich Device-Atomic Contract**: neuer pure Attribut-Layer `attributes.py`.
  Jeder Device-Sensor exponiert nun generische Slot-Diagnose: `slot_entities`,
  `slot_states`, `slot_available`, `slot_roles`, `slot_last_changed`,
  `missing_sources`, `degraded`, `degraded_reason`, `atomic_quality`, `consumes`.
  Bestehende Standard-/Typ-Attribute bleiben erhalten.
- **Neue Slots** (alle optional/additiv): `current_sensor`, `voltage_sensor`,
  `energy_sensor`, `network_switch_entity`, `wake_button_entity`,
  `remote_entity`, `companion_media_player`, `companion_tracker` sowie der
  Text-Slot `wake_mac` (keine Entity — wird nicht als State gelesen).
- **Reiche TV-/Media-Attribute**: `media_player_state`, `current_app`, `source`,
  `media_title`, `media_content_type`, `volume_level`, `is_volume_muted`, plus
  `switch_state`, `network_access_state`, `remote_state`, Companion-States,
  `current`/`voltage`/`energy`, `wake_supported`/`wake_mac`.
- **Slot-Gruppen** (`basics`/`power`/`media_network`/`measurements`/`advanced`)
  für die gruppierte Builder-UX.
- **Source-Classifier** (`classify_source_entity`): warnt/markiert
  `*_atomic`/`*_combined`/`*_gate` und integrationseigene Quellen.
- **Combined Builder v0**: neue pure Engine `combined.py` (First-Match-Wins,
  Operatoren eq/ne/unavailable/numerisch, Default-Regel, Reason, Output-Typen
  enum/code/boolean/number, abgeleitete Binary-Sensoren). Neuer
  `CombinedCoordinator`, `sensor.<profile>_combined_<slug>` und
  `binary_sensor.<profile>_combined_<slug>_<derived>`.
- **WebSocket**: Status um Diagnose-Felder, Combineds, Reverse-Lookup
  (`consumed_by`) und Source-Warnungen erweitert; neue Commands `set_combined`,
  `remove_combined`, `export_config`; `bulk_import` mit `dry_run`-Report
  (akzeptiert/blockiert, unbekannte Slots, leere/fehlende Entities, derived
  Quellen, resultierende Entity-IDs).

### Frontend (Vanilla, Dracula-inspiriert)
- Neue Navigation: **Diagnose · Atomic Builder · Combined Builder · Import/Export**.
- Diagnose-Startseite: Kennzahlen, gefilterte Problemliste (Alle/Fehler/
  Warnungen/OK), Detailkarte mit Slots, Konflikten, Versorgung/Consumer.
- Atomic Builder nach Fachbereichen gruppiert, mit Live-Preview und Warnungen.
- Combined Builder mit Sources/Rules/Derived/Preview.
- Import/Export mit Dry-Run-Vorschau, Validierungswarnungen und YAML-Export;
  Light-Groups bleiben erhalten, jetzt untergeordnet.

### Kompatibilität
- Config-Entry-Version unverändert (1). Neue Options-Sektion `combineds` und neue
  Slot-Keys werden mit Defaults gelesen — alte Einträge funktionieren weiter.

## 0.1.0

- Extract `benni_core_devices` from the Toolbox into a standalone integration.
- Keep the HA-free device compute logic and device type catalog aligned with the source module.
- Add profile routing for `benni` and `eltern`.
- Add WebSocket API and custom panel for device/group CRUD.
- Register standalone services `set_override` and `clear_override`.

