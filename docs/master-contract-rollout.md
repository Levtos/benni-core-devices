# Master Contract Rollout

Last updated: 2026-06-21
Scope: FLEET-108 / FLEET-129

## Purpose

Openings proved the master-contract model, but the next rollout must not be
cut by integration name. The primary cut is a real device or a real smart-home
function with its own identity.

Rule:

- Device/function masters own raw quirks and device-specific facts.
- Domain masters are later, smaller facades that consume device/function
  masters and expose domain-wide truth.
- A domain facade must not become a 100+ attribute bucket.
- Existing single Combineds may stay as compatibility surfaces during a
  migration, but they are not the target architecture.

## Current Live Inventory

Source: Einhornzentrale live state on 2026-06-21, filtered for
`benni_device_*`, `benni_atomic_*`, and `benni_combined_*`.

No live `benni_atomic_*` entities were found. The current public Core Devices
surface is `benni_device_*` plus `benni_combined_*`.

### Existing device contracts

Media / entertainment:

- `sensor.benni_device_living_pc`
- `sensor.benni_device_ps5`
- `sensor.benni_device_nintendo`
- `sensor.benni_device_living_tv`
- `sensor.benni_device_living_avr`
- `sensor.benni_device_living_homepods`
- `sensor.benni_device_living_appletv`
- `sensor.benni_device_living_switch_plug`
- `sensor.benni_device_living_subwoofer_plug`

Appliances / plugs:

- `sensor.benni_device_kitchen_coffee`
- `sensor.benni_device_kitchen_dishwasher`
- `sensor.benni_device_kitchen_dryer`
- `sensor.benni_device_kitchen_washing_machine`

Openings / cover:

- `sensor.benni_device_living_window_left`
- `sensor.benni_device_living_window_right`
- `sensor.benni_device_kitchen_patio_door`
- `sensor.benni_device_hall_entry_door`
- `sensor.benni_device_living_blind`
- `sensor.benni_device_living_blind_position`

Climate / light / environment:

- `sensor.benni_device_living_climate`
- `sensor.benni_device_kitchen_climate`
- `sensor.benni_device_bath_climate`
- `sensor.benni_device_garden_climate`
- `sensor.benni_device_garden_lux`
- `sensor.benni_device_living_lux`

Bath / safety / presence:

- `sensor.benni_device_bath_shower_vibration`
- `sensor.benni_device_bath_shower_vibration_battery`
- `sensor.benni_device_bath_vibration`
- `sensor.benni_device_hall_doorbell_vibration`
- `sensor.benni_device_hall_presence`
- `sensor.benni_device_hall_presence_motion_state`
- `sensor.benni_device_hall_smoke`
- `sensor.benni_device_hall_smoke_battery`
- `sensor.benni_device_living_smoke`
- `sensor.benni_device_living_smoke_battery`

Lights:

- `sensor.benni_device_bedroom_cabinet_strip`
- `sensor.benni_device_bedroom_wall_strip`
- `sensor.benni_device_hall_table_lamp`
- `sensor.benni_device_kitchen_ceiling_light_rgb_ring`
- `sensor.benni_device_kitchen_ceiling_light_white`
- `sensor.benni_device_living_cabinet_wall_strip`
- `sensor.benni_device_living_ceiling_light_rgb_ring`
- `sensor.benni_device_living_ceiling_light_white`
- `sensor.benni_device_living_desk_strip`
- `sensor.benni_device_living_sideboard_table_lamp`
- `sensor.benni_device_living_sofa_table_lamp`
- `sensor.benni_device_living_sofa_wall_strip`

Weather:

- `sensor.benni_device_weather_advance_warning_level`
- `sensor.benni_device_weather_cloud_coverage`
- `sensor.benni_device_weather_condition`
- `sensor.benni_device_weather_current_warning_level`
- `sensor.benni_device_weather_humidity`
- `sensor.benni_device_weather_season_astronomical`
- `sensor.benni_device_weather_season_meteorological`
- `sensor.benni_device_weather_temperature`
- `sensor.benni_device_weather_wind_speed`

### Existing combined clusters

Openings:

- `sensor.benni_combined_openings`
- Legacy compatibility: `sensor.benni_combined_opening_any_open`,
  `sensor.benni_combined_opening_any_open_or_tilted`,
  `sensor.benni_combined_opening_any_tilted`,
  `sensor.benni_combined_opening_outside_active`,
  `sensor.benni_combined_opening_state`,
  `sensor.benni_combined_opening_unsafe_for_climate`,
  `sensor.benni_combined_opening_unsafe_for_rollo`

Context:

- `sensor.benni_combined_context_master`
- `sensor.benni_combined_context_presence_personal`
- `sensor.benni_combined_context_presence_household`
- `sensor.benni_combined_context_presence_band`
- `sensor.benni_combined_context_presence_transition`
- `sensor.benni_combined_context_presence_policy`
- `sensor.benni_combined_context_presence_home_equivalent`
- `sensor.benni_combined_context_presence_preheat_active`
- `sensor.benni_combined_context_external_coming_home`
- `sensor.benni_combined_context_bio_state`
- `sensor.benni_combined_context_bio_policy`
- `sensor.benni_combined_context_bio_presence_logic_ready`
- `sensor.benni_combined_context_bio_sleep_protection_active`
- `sensor.benni_combined_context_bio_sleep_request_safe`
- `sensor.benni_combined_context_bio_wake_candidate`
- `sensor.benni_combined_context_away_cuts_allowed`
- `sensor.benni_combined_context_day_state`
- `sensor.benni_combined_context_day_context`
- `sensor.benni_combined_context_activity_state`

Media:

- `sensor.benni_combined_media_context`
- `sensor.benni_combined_media_subcontext`
- `sensor.benni_combined_media_device`
- `sensor.benni_combined_media_gaming_source`
- `sensor.benni_combined_media_gaming_platform`
- `sensor.benni_combined_media_pc_game`
- `sensor.benni_combined_media_pc_gaming_active`
- `sensor.benni_combined_media_entertainment_active`
- `sensor.benni_combined_media_headset_active`
- `sensor.benni_combined_media_quiet_mode_active`
- `sensor.benni_combined_media_quiet_mode_reason`
- `sensor.benni_combined_media_scene`
- `sensor.benni_combined_media_notification_route`
- `sensor.benni_combined_media_doorbell_visual_priority`
- `sensor.benni_combined_media_light_entertainment_candidate`
- `sensor.benni_combined_media_bias_light_should_be_on`
- `sensor.benni_combined_media_plug_protection`
- `sensor.benni_combined_media_subwoofer_allowed`
- `sensor.benni_combined_media_subwoofer_should_be_on`
- `sensor.benni_combined_media_volume_policy`
- `sensor.benni_combined_media_volume_target_homepods`
- `sensor.benni_combined_media_volume_target_homepods_effective`
- `sensor.benni_combined_media_volume_target_denon`
- `sensor.benni_combined_media_volume_target_denon_effective`
- `sensor.benni_combined_media_logic_ready`

Plug / power:

- `sensor.benni_combined_plug_power_sources_ready`
- `sensor.benni_combined_plug_away_policy`
- `sensor.benni_combined_plug_away_policy_ready`
- `sensor.benni_combined_plug_policy_any_blocked`
- `sensor.benni_combined_plug_protected_active`
- `sensor.benni_combined_plug_switch_cut_candidate`
- `sensor.benni_combined_plug_policy_summary`
- `sensor.benni_combined_plug_policy_cut_candidates`
- `sensor.benni_combined_plug_policy_protected_devices`
- `sensor.benni_combined_plug_policy_toolbox_ready`

Climate:

- `sensor.benni_combined_climate_indoor_temperature`
- `sensor.benni_combined_climate_outdoor_feels_like_temperature`
- `sensor.benni_combined_climate_effective_outdoor_temperature`
- `sensor.benni_combined_climate_window_block`
- `sensor.benni_combined_climate_target_profile`

Light:

- `sensor.benni_combined_living_light_logic_ready`
- `sensor.benni_combined_living_light_lux_gate`
- `sensor.benni_combined_living_light_mode`
- `sensor.benni_combined_living_light_plan`
- `sensor.benni_combined_living_light_brightness_target`

Rollo:

- `sensor.benni_combined_living_rollo_mode`
- `sensor.benni_combined_living_rollo_target_position`
- `sensor.benni_combined_living_rollo_movement_needed`
- `sensor.benni_combined_living_rollo_policy_sources_problem`
- `sensor.benni_combined_living_rollo_heat_protect`
- `sensor.benni_combined_living_rollo_privacy_candidate`
- `sensor.benni_combined_living_rollo_glare_pc_candidate`
- `sensor.benni_combined_living_rollo_glare_tv_candidate`

Bath:

- `sensor.benni_combined_bath_humidity_delta`
- `sensor.benni_combined_bath_dew_point_approx`
- `sensor.benni_combined_bath_dew_point_delta`
- `sensor.benni_combined_bath_fan_mode`
- `sensor.benni_combined_bath_fan_logic_ready`
- `sensor.benni_combined_bath_fan_usage_hold`
- `sensor.benni_combined_bath_shower_active`
- `sensor.benni_combined_bath_shower_context`
- `sensor.benni_combined_bath_shower_sensor_health`
- `sensor.benni_combined_bath_toilet_active`

Weather:

- `sensor.benni_combined_weather_warning_level`
- `binary_sensor.benni_combined_weather_warning_level_warning_active`

## Target Cut

### First-class device/function masters

Build these before broad Media or Plug/Power facades:

| Master | Target entity | Owns |
| --- | --- | --- |
| PS5 | `sensor.benni_combined_ps5` | PS5 state, media/game context, power/protection facts, source health |
| PC | `sensor.benni_combined_living_pc` or `sensor.benni_combined_pc` | PC state, gaming/game/headset context, power/protection facts |
| TV | `sensor.benni_combined_living_tv` or `sensor.benni_combined_tv` | TV state, input/media, notify capability, power/protection facts |
| Switch | `sensor.benni_combined_nintendo_switch` | Switch/dock/plug state, gaming context, power/protection facts |
| Denon | `sensor.benni_combined_living_denon` | AVR state, source, volume, route, protection facts |
| HomePods | `sensor.benni_combined_living_homepods` | MA group playback, radio/manual playback, volume, group health |
| Coffee | `sensor.benni_combined_kitchen_coffee` | Wake relevance, appliance state, plug/power facts |
| Washing machine | `sensor.benni_combined_kitchen_washing_machine` | Appliance cycle/protection state, plug/power facts |
| Dryer | `sensor.benni_combined_kitchen_dryer` | Appliance cycle/protection state, plug/power facts |
| Dishwasher | `sensor.benni_combined_kitchen_dishwasher` | Appliance cycle/protection state, plug/power facts |
| Bath | `sensor.benni_combined_bath` | Humidity, shower/toilet, fan decision, sensor health |
| Weather | `sensor.benni_combined_weather` | Conditions, warning levels, season, weather-derived gates |

Openings already has a domain/function master:

- `sensor.benni_combined_openings`

Light and Rollo are currently room/function scoped and can stay scoped while
they are consolidated:

- `sensor.benni_combined_living_light`
- `sensor.benni_combined_living_rollo`

### Later domain facades

Build these only after relevant device/function masters exist:

| Facade | Target entity | Consumes | Must not own |
| --- | --- | --- | --- |
| Media | `sensor.benni_combined_media` | PS5, PC, TV, Switch, Denon, HomePods, Context, Openings | raw PS5/PC/TV/Switch/Audio quirks |
| Plug/Power | `sensor.benni_combined_plug_power` | device masters with power/protection attrs, Context, Media | per-device media/power quirks |
| Context | `sensor.benni_combined_context` | presence/bio/day/activity sources plus selected device masters for wake/sleep evidence | media or plug policy details |
| Climate | `sensor.benni_combined_climate` | Weather, Openings, room climate devices, Context | opening details beyond consumed attrs |
| Light | `sensor.benni_combined_living_light` first, later area masters | Context, Media facade, Weather/Lux, light devices | media device quirks |
| Rollo | `sensor.benni_combined_living_rollo` first, later area masters | Openings, Weather, Media facade, Context, cover device | media device quirks |

## Implementation Pattern

Each master ticket must follow this shape:

1. Inventory raw/current sources.
2. Define the master contract:
   - one headline state
   - flat attributes
   - `degraded`, `degraded_reason`, `missing_sources` when applicable
   - fail-loud safety semantics
3. Add the master in Core Devices.
4. Add focused tests:
   - parse/import
   - source classification / published outputs
   - evaluation semantics
5. Release `benni-core-devices`.
6. Apply/import only when explicitly doing a live rollout.

Each binding ticket must follow this shape:

1. Find all consumers of old device/domain-specific singles.
2. Rebind consumers to `entity + attribute` on the master.
3. Keep old singles compatible during the migration.
4. Test policy repos and YAML/template consumers.
5. Release changed integrations.
6. Verify live only after explicit deploy/restart/reload approval.
7. Decide later whether old singles are retired, cancelled, or kept as native
   HA/history exceptions.

## Claude/Codex Handoff Rules

Every implementation card under FLEET-108 should be self-contained enough for
Claude Code or Codex to pick up without this chat:

- Link or reference this document.
- Name the target master entity.
- Name the old singles / current sources to inspect.
- State which repos are likely affected.
- State whether the card is a Core master build or a binding cutover.
- Do not deploy, reload, or restart Home Assistant without explicit user
  approval.
- Commit and release are allowed when code changed and tests pass.

## Current Board Status

FLEET-108 is the active rollout epic.

FLEET-129 is this inventory/slicing task.

Existing device-master starts:

- FLEET-130 / FLEET-131: PS5 master and bindings
- FLEET-132 / FLEET-133: PC master and bindings
- FLEET-134 / FLEET-135: TV master and bindings
- FLEET-136 / FLEET-137: Switch master and bindings
- FLEET-138 / FLEET-139: Denon master and bindings
- FLEET-140 / FLEET-141: HomePods master and bindings

Existing facade cards were intentionally reframed:

- FLEET-111 / FLEET-112: Media facade, after device masters
- FLEET-113 / FLEET-114: Plug/Power facade, after device masters

Further useful splits to create before implementation if needed:

- Appliance masters: coffee, dishwasher, dryer, washing machine
- Environment/function masters: weather, bath, living light, living rollo
- Facade bindings: context, climate, light, rollo, bath, weather
