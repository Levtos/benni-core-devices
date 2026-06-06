# Changelog

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

