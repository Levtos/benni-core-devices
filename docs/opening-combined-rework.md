# Opening Combined Logic as Rework Reference

Stand: 2026-06-05

Quelle: `D:\Dokumente\GitHub\einhornzentrale\packages\combined\openings.yaml`

Diese Notiz fasst die aktuelle Opening-/Window-Combined-Logik aus der Einhornzentrale zusammen. Sie ist relevant fuer das `benni_core_devices`-Rework, weil sie zeigt, was dem aktuellen Device-Atomic-Vertrag noch fehlt: reichhaltige Raw-Slot-Auswertung, Source-State-Attribute, Availability, Fail-Safe-Semantik und abgeleitete Policy-Flags.

## Schichtmodell

Die bestehende Logik besteht aus zwei Schichten:

1. Raw-Entity -> Atomic
   - Quelle: `packages\atomics\z2m_openings.yaml`
   - Beispiel: `binary_sensor.living_window_left_open_contact` wird zu `binary_sensor.living_window_left_open_atomic`.
   - Das Atomic normalisiert den Zustand und haengt Metadaten an.

2. Atomic -> Combined
   - Quelle: `packages\combined\openings.yaml`
   - Beispiel: mehrere `*_open_atomic` und `*_tilt_atomic` werden zu `sensor.opening_state_combined`.
   - Der Combined-Sensor erzeugt einen kompakten Gesamtzustand plus fachliche Attribute und Gate-Sensoren.

Wichtig fuer `benni_core_devices`: Beim Import oder Device-Builder duerfen nicht die YAML-Atomics referenziert werden. Die Integration muss Raw-Entities als Slots konsumieren und daraus selbst den Atomic-Sensor mit Attributen erzeugen.

## Atomic-Vertrag

Ein Opening-Atomic konsumiert genau eine Raw-Entity und erzeugt daraus einen normalisierten Binary-Sensor.

Beispiel:

```yaml
- name: Living Window Left Open Atomic
  unique_id: living_window_left_open_atomic
  device_class: opening
  state: "{{ states('binary_sensor.living_window_left_open_contact') != 'off' }}"
  attributes:
    source: binary_sensor.living_window_left_open_contact
    source_state: "{{ states('binary_sensor.living_window_left_open_contact') }}"
    contact_type: open
    fail_safe: open
    availability: "{{ 'available' if states('binary_sensor.living_window_left_open_contact') in ['on', 'off'] else 'unavailable' }}"
```

Semantik:

- `source`: Raw-Entity, die der Atomic kapselt.
- `source_state`: Originalzustand der Raw-Entity.
- `contact_type`: fachliche Rolle, z. B. `open` oder `tilt`.
- `fail_safe`: Verhalten bei unsicherem Zustand.
- `availability`: eigene Availability-Auswertung, getrennt vom finalen State.

Bei Open-Kontakten gilt aktuell Fail-Safe Open:

```yaml
state: "{{ states('binary_sensor.*_open_contact') != 'off' }}"
```

Damit werden `unknown`, `unavailable` oder andere Nicht-`off`-Zustaende im State als offen behandelt. Gleichzeitig bleibt die Unsicherheit ueber `availability: unavailable` sichtbar.

Bei Tilt-Kontakten gilt kein Fail-Safe Tilt:

```yaml
state: "{{ states('binary_sensor.*_tilt_contact') == 'on' }}"
```

Unklare Tilt-Zustaende werden also nicht als gekippt gewertet, aber ueber `availability` sichtbar.

## Combined-State

Der Hauptsensor ist:

```text
sensor.opening_state_combined
```

Er erzeugt einen vierstelligen Code:

```text
Stelle 1: living_window_left
Stelle 2: living_window_right
Stelle 3: kitchen_patio_door
Stelle 4: hall_entry_door
```

Code-Legende:

```text
0 = closed
1 = tilted
2 = open
9 = unclear
```

Kernlogik pro Fenster/Tuer:

```jinja2
{% set ll = 9 if state_attr('binary_sensor.living_window_left_open_atomic', 'availability') != 'available'
  else 2 if is_state('binary_sensor.living_window_left_open_atomic', 'on')
  else 1 if is_state('binary_sensor.living_window_left_tilt_atomic', 'on')
  else 0 %}
```

Prioritaet:

1. Atomic nicht verfuegbar -> `9` / `unclear`
2. Open-Kontakt an -> `2` / `open`
3. Tilt-Kontakt an -> `1` / `tilted`
4. sonst -> `0` / `closed`

Die Etagentuer hat nur Open, kein Tilt:

```jinja2
{% set he = 9 if state_attr('binary_sensor.hall_entry_door_open_atomic', 'availability') != 'available'
  else 2 if is_state('binary_sensor.hall_entry_door_open_atomic', 'on')
  else 0 %}
```

Der finale State ist die Konkatenation:

```jinja2
{{ ll }}{{ lr }}{{ kp }}{{ he }}
```

Beispiel:

```text
0010
```

Bedeutet:

- Wohnzimmer links geschlossen
- Wohnzimmer rechts geschlossen
- Terrassentuer gekippt
- Etagentuer geschlossen

## Combined-Attribute

Der Combined-Sensor fuehrt den Code wieder in lesbare Attribute zurueck.

Beispiel:

```yaml
living_window_left: >
  {% if state_attr('binary_sensor.living_window_left_open_atomic', 'availability') != 'available' %}unclear
  {% elif is_state('binary_sensor.living_window_left_open_atomic', 'on') %}open
  {% elif is_state('binary_sensor.living_window_left_tilt_atomic', 'on') %}tilted
  {% else %}closed{% endif %}
living_window_left_open_source_state: "{{ state_attr('binary_sensor.living_window_left_open_atomic', 'source_state') }}"
living_window_left_tilt_source_state: "{{ state_attr('binary_sensor.living_window_left_tilt_atomic', 'source_state') }}"
```

Fachliche Attribute:

- `living_window_left`
- `living_window_right`
- `kitchen_patio_door`
- `hall_entry_door`
- `*_source_state`
- `any_open`
- `any_tilted`
- `any_unclear`
- `outside_opening_active`
- `unsafe_for_climate`
- `unsafe_for_rollo`
- `media_quiet_reason`

## Abgeleitete Binary-Sensoren

Aus dem Combined-Sensor werden mehrere fachliche Gate-Sensoren abgeleitet:

```yaml
- name: Opening Any Open Combined
  unique_id: opening_any_open_combined
  device_class: opening
  state: "{{ state_attr('sensor.opening_state_combined', 'any_open') in [true, 'true', 'True', 'on'] }}"

- name: Opening Any Tilted Combined
  unique_id: opening_any_tilted_combined
  device_class: opening
  state: "{{ state_attr('sensor.opening_state_combined', 'any_tilted') in [true, 'true', 'True', 'on'] }}"

- name: Opening Unsafe For Climate Combined
  unique_id: opening_unsafe_for_climate_combined
  device_class: problem
  state: "{{ state_attr('sensor.opening_state_combined', 'unsafe_for_climate') in [true, 'true', 'True', 'on'] }}"

- name: Opening Unsafe For Rollo Combined
  unique_id: opening_unsafe_for_rollo_combined
  device_class: problem
  state: "{{ state_attr('sensor.opening_state_combined', 'unsafe_for_rollo') in [true, 'true', 'True', 'on'] }}"
```

Diese Sensoren sind keine Raw-Atomics mehr. Sie sind Policy-/Combined-Ausgaben und duerfen beim Devices-Import nicht als Slots fuer neue Atomics verwendet werden.

## Rework-Schlussfolgerung fuer benni_core_devices

Die aktuelle Devices-Integration erzeugt bereits `sensor.<profile>_device_<slug>` und berechnet `powered`, `power_state`, `available`, `power_source`, `watt_disagrees` usw. Der Vertrag ist fuer echte Atomic-Abloesung aber noch zu flach.

Fehlende Bausteine:

- Raw-Slots muessen vollstaendig als Attribut sichtbar sein.
- Jeder Slot braucht `source_entity`, `source_state`, `source_available` und optional eine fachliche Rolle.
- Nicht nur Power/Watt, sondern alle zusammenhaengenden Rohentitaeten eines Geraets muessen in einem Atomic landen.
- Typen wie `tv` brauchen reichhaltige Typattribute, z. B. Media-State, App, Power-Plug, Netzwerk/WLAN, Wake-on-LAN, Companion-Player, Remote, Tracker.
- Der Device-Builder muss Raw-Entities auswaehlen lassen und darf alte YAML-Atomics nicht als Quellen bevorzugen.
- Import muss Raw-Entities importieren, nicht `*_atomic`, `*_combined` oder alte Toolbox-Sensoren.

## Zielbild fuer TV-Atomic

Ein TV-Device sollte nicht nur `powered` und `watt` liefern, sondern einen zusammenhaengenden Sensor:

```text
sensor.benni_device_tv
```

Moegliche Attribute:

- `device_type`
- `slug`
- `display_name`
- `powered`
- `power_state`
- `available`
- `power_source`
- `watt`
- `watt_disagrees`
- `media_player_state`
- `current_app`
- `source_entity`
- `slot_entities`
- `slot_states`
- `slot_available`
- `plug_switch_entity`
- `network_switch_entity`
- `wake_button_entity`
- `wake_mac`
- `remote_entity`
- `companion_media_player`
- `companion_tracker`
- `last_powered_change`
- `override_active`

Damit entspricht `sensor.benni_device_tv` fachlich dem bisherigen YAML-Atomic-Prinzip, nur nicht mehr als Template-YAML, sondern als Integrations-Atomic.

## Rework-Regel

Fuer `benni_core_devices` gilt:

```text
Raw-Entities rein -> ein reichhaltiger Device-Atomic raus -> Combined/Policy konsumiert diesen Atomic.
```

Nicht:

```text
YAML-Atomic rein -> Device-Atomic raus
```

Die Integration ersetzt die YAML-Atomics. Sie darf sie deshalb nicht als Grundlage importieren.
