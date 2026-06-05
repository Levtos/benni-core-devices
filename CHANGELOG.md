# Changelog

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

