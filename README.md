# Benni Core Devices

Standalone Home Assistant integration for the atomic physical-device layer.

The integration creates one consolidated sensor per physical device:

- `sensor.<profile>_device_<slug>`
- optional secondary sensors for power state, watt, powered and availability
- `sensor.<profile>_light_group_<slug>` for atomic light groups

For profile `benni`, the object IDs stay compatible with the former Toolbox
module, for example `sensor.benni_device_tv`. Profile `eltern` uses
`sensor.eltern_device_*`.

## Current Scope

This integration is currently a conservative extraction of the old Toolbox
`benni_core_devices` module. The core decision logic is intentionally unchanged.

It currently does three things well:

1. Computes a robust `powered` value from integration state, watt fallback,
   sticky hold and override.
2. Computes `power_state` from ordered watt buckets.
3. Exposes a stable main sensor with standard attributes and a small set of
   type-specific attributes.

It does **not yet fully replace rich YAML atomics**. The present attribute layer
is too small for devices like the TV stack, where a single physical device needs
to expose many related raw entities and capabilities.

## Config Entry Model

There is one config entry per Home Assistant instance.

The initial config flow only selects the route/profile:

- `benni`
- `eltern`

Device and light-group CRUD is done in the custom panel. The options flow remains
as an emergency fallback.

Options structure:

```yaml
devices:
  <slug>:
    device_type: tv
    display_name: TV
    fields: [...]
    integration_entity: media_player.example
    watt_sensor: sensor.example_power
    watt_threshold_on: 8
    sticky_hold_seconds: 30
    expose_secondary_sensors: true
    watt_buckets:
      - state: off
        op: <=
        value: 8
light_groups:
  <slug>:
    display_name: Living Lights
    members:
      - light.example
```

## Device Decision Logic

`logic.py` is HA-free and covered by pytest. The rule order is:

1. Active override wins.
2. Fresh integration slot decides `powered`.
3. Fresh watt slot decides `powered` using `watt_threshold_on`.
4. Sticky hold preserves the previous value outside the boot phase.
5. Otherwise `powered = null`.

Additional rules:

- `power_state` is always derived from watt buckets.
- First matching watt bucket wins.
- A bucket without `op`/`value` is a catch-all.
- `available` is true when at least one configured slot is fresh.
- Freshness window is 600 seconds.
- Boot phase is 30 seconds.
- Default sticky hold is 30 seconds.
- Default watt-on threshold is 5 W.
- `watt_disagrees` is true when integration says off but watt is above the
  threshold.

This logic should stay stable during the next rework. The rework should happen
around slots and attributes, not by changing the rule order.

## Current Slot Catalog

The current global slot catalog is:

| Slot | Domain | Current role |
| --- | --- | --- |
| `integration_entity` | `media_player` | Primary integration truth and raw state for media-like devices |
| `power_entity` | `binary_sensor` | Binary on/off truth, if a true raw binary source exists |
| `status_entity` | `sensor` | Status source for consoles |
| `title_entity` | `sensor` | Title source for consoles |
| `watt_sensor` | `sensor` | Numeric watt source |
| `wifi_sensor` | `binary_sensor` | Intended connectivity source |
| `switch_entity` | `switch` | Switch/plug source |
| `light_entity` | `light` | Light source |
| `cover_entity` | `cover` | Cover source |
| `position_entity` | `sensor` | Cover position source |
| `climate_entity` | `climate` | Climate source |
| `value_entity` | `sensor` | Generic sensor wrapper source |

Important distinction:

- `watt_sensor` is numeric power in watts.
- `power_entity` is a binary on/off source.

If the only available binary on/off entity is a YAML/template atomic, it should
not be imported. Use the raw `watt_sensor` and let this integration compute
`powered`.

## Current Device Types

Supported device types:

- `tv`
- `av_receiver`
- `console`
- `speaker`
- `plug`
- `light`
- `cover`
- `climate`
- `sensor_wrapper`

Device type profiles currently define:

- default fields shown in the builder
- integration slot
- state slot
- a small list of type-specific attributes

For example, `tv` currently defaults to:

```yaml
default_fields:
  - integration_entity
  - watt_sensor
  - wifi_sensor
integration_slot: integration_entity
state_slot: integration_entity
extra_attributes:
  - watt
  - current_app
  - wifi_online
  - media_player_state
```

## Current Entity Contract

Main device sensor:

```text
sensor.<profile>_device_<slug>
```

Standard attributes:

- `device_type`
- `slug`
- `display_name`
- `powered`
- `power_state`
- `available`
- `power_source`
- `last_powered_change`
- `override_active`
- `watt_disagrees`
- `area_id`

Type-specific attributes are currently sparse and mostly come from:

- `watt_sensor` for `watt`
- `state_slot` raw state for `media_player_state` / `hvac_mode`
- attributes on the state slot for selected keys

Current limitation: configured slots are not generally exposed as rich
attributes. For example, `switch_entity`, current/voltage/energy sensors,
Wake-on-LAN buttons, remotes and companion media players are not yet represented
well.

Light-group sensor:

```text
sensor.<profile>_light_group_<slug>
```

Attributes:

- `members`
- `entity_id`
- `member_count`
- `on_count`
- `any_on`

## Panel and WebSocket API

The custom panel is mounted as `Benni Core Devices`.

Current panel features:

- Device builder with persistent draft state.
- Searchable Home Assistant entity pickers for slots.
- Explicit edit workflow for existing devices.
- Light-group CRUD with searchable light picker.
- Bulk import.

WebSocket commands:

- `benni_core_devices/get_status`
- `benni_core_devices/get_catalog`
- `benni_core_devices/set_device`
- `benni_core_devices/remove_device`
- `benni_core_devices/set_group`
- `benni_core_devices/remove_group`
- `benni_core_devices/bulk_import`

The panel stays registered during config-entry reloads so saving/importing should
not navigate Home Assistant back to `/home/overview`.

## Services

```yaml
benni_core_devices.set_override:
  slug: tv
  powered: true
  power_state: playing
  expire_seconds: 300

benni_core_devices.clear_override:
  slug: tv
```

Overrides are persisted per device and survive restarts until cleared or expired.

Import/export services:

- `benni_core_devices.export_config` returns the current config as YAML.
- `benni_core_devices.bulk_import` accepts a YAML payload plus `dry_run` and
  `replace` for UI/WebSocket-capable clients.
- `benni_core_devices.import_file_dry_run` is arg-less for MCP bridges that
  cannot pass service `data`; it reads
  `<config>/benni_core_devices/import.yaml`, validates it, and returns the
  normal bulk-import report without writing.
- `benni_core_devices.import_file_apply` reads the same file and persists the
  import. Apply is never implicit.

The import file uses the exact `export_config` shape:

```yaml
devices: []
combineds: {}
light_groups: {}
```

Add top-level `replace: true` to the file for a clean-slate import. Without it,
the imported entries are merged into the existing devices, combineds and light
groups.

## Import Rules

Bulk import should reference raw Home Assistant entities only.

Do not import:

- YAML/template atomics
- `*_atomic` sensors
- old `bennis_toolbox` derived policy entities
- entities that this integration is supposed to replace

Prefer raw integration platforms such as:

- `webostv`
- `mqtt`
- `apple_tv`
- `fritz`
- `music_assistant`
- `wake_on_lan`

Example: current clean TV import with the existing slot model:

```yaml
- slug: tv
  device_type: tv
  display_name: TV
  integration_entity: media_player.living_lgtv
  watt_sensor: sensor.living_tv_plug_power
  switch_entity: switch.wohnbereich_steckdose_tv
  watt_threshold_on: 8
  sticky_hold_seconds: 30
  expose_secondary_sensors: true
  watt_buckets:
    - state: off
      op: <=
      value: 8
    - state: idle
      op: <=
      value: 35
    - state: playing
      op: ">"
      value: 35
```

This intentionally omits `power_entity` when the only candidate is an existing
YAML/template atomic.

Bindings may read an entity attribute instead of the entity state by adding
`attribute`. This is useful for integrations such as DWD weather, where numeric
values live on `weather.dwd_home` attributes:

```yaml
devices:
  - slug: dwd_home_temperature
    atomic_class: environment
    variant: room_climate
    display_name: DWD Home Temperature
    sources:
      - role: temperature_source
        entity: weather.dwd_home
        attribute: temperature
```

When `attribute` is set, the source value is `state_attr(entity, attribute)`.
If the attribute is missing or `None`, the source is treated as unavailable.

## Known Gap: Rich Atomic Attributes

The current implementation is not yet rich enough to fully replace the YAML
atomics.

The current Einhornzentrale opening/window logic is summarized as the concrete
reference for this rework in
[docs/opening-combined-rework.md](docs/opening-combined-rework.md).

Missing for a good TV atomic:

- raw current/voltage/energy attributes
- switch state as an attribute
- network/access state as an attribute
- Wake-on-LAN capability and MAC
- companion media player, for example Apple TV
- remote entity
- richer media attributes such as source, app, title, content type, volume and
  mute state
- generic `slot_entities`, `slot_states` and `slot_available` attributes

For the living TV, raw related entities discovered so far include:

```yaml
core:
  integration_entity: media_player.living_lgtv
  watt_sensor: sensor.living_tv_plug_power
  switch_entity: switch.wohnbereich_steckdose_tv

raw_candidates:
  current_sensor: sensor.living_tv_plug_current
  voltage_sensor: sensor.living_tv_plug_voltage
  energy_sensor: sensor.living_tv_plug_energy
  wake_button_entity: button.lgwebostv
  wake_mac: "58:96:0A:5E:E9:2E"
  fritz_wake_button: button.lgwebostv_wake_on_lan
  network_switch_entity: switch.lgwebostv_internetzugang_2
  companion_media_player: media_player.living_appletv
  remote_entity: remote.living_appletv
  companion_tracker: device_tracker.appletv
  companion_network_switch: switch.appletv_internetzugang
```

These should not be forced into the current slots if the semantics are wrong.
They should be supported by a small slot/attribute rework.

## Proposed Rework

Keep `logic.py` rule behavior stable. Extend the integration around it.

### 1. Add capability and raw-measurement slots

Candidate new slots:

| Slot | Domain/type | Purpose |
| --- | --- | --- |
| `current_sensor` | `sensor` | Current in A |
| `voltage_sensor` | `sensor` | Voltage in V |
| `energy_sensor` | `sensor` | Energy in kWh |
| `network_switch_entity` | `switch` | Internet/network access or online control |
| `wake_button_entity` | `button` | Entity that sends Wake-on-LAN |
| `wake_mac` | text | MAC used for Wake-on-LAN |
| `remote_entity` | `remote` | Remote entity for the physical device |
| `companion_media_player` | `media_player` | Related player, e.g. Apple TV |
| `companion_tracker` | `device_tracker` | Related network tracker |

### 2. Expose all configured slots generically

Add attributes to every device sensor:

```yaml
slot_entities:
  watt_sensor: sensor.living_tv_plug_power
slot_states:
  watt_sensor: "0"
slot_available:
  watt_sensor: true
```

This makes the sensor inspectable even before each type has perfect bespoke
attribute mapping.

### 3. Improve type-specific attributes

For `tv`, target attributes should include at least:

- `watt`
- `current`
- `voltage`
- `energy`
- `switch_state`
- `media_player_state`
- `source`
- `current_app`
- `media_title`
- `media_content_type`
- `volume_level`
- `is_volume_muted`
- `wake_supported`
- `wake_button_entity`
- `wake_mac`
- `network_access_state`
- `remote_state`
- `companion_media_player`
- `companion_media_player_state`

### 4. Update builder and import

The Device Builder and WebSocket catalog must expose the new slots. Bulk import
must preserve them.

### 5. Tests

Keep existing R-DC tests unchanged and add tests for:

- new slot validation / catalog entries
- generic slot attribute export
- TV-specific raw attribute mapping
- import payload preservation for new slots

## Verification

Current local test suite:

```text
50 passed
```

The suite currently covers the HA-free decision logic and device-type sanity.
It does not yet cover the planned rich attribute layer.
