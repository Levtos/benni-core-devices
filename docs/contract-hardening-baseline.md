# Contract Hardening Baseline

Status: `v0.5.0-alpha.9` preparation

Core Devices remains a contract layer:

Raw Home Assistant Entities
-> private Normalizer / Source Adapter
-> Device/Domain Masters
-> Fusion/Context Contracts
-> Policies
-> Apply Layer

This document fixes the baseline semantics for unknown values, source quality,
fallbacks, and future Last-Known-Good handling. It is intentionally a contract
specification and guardrail document. It does not migrate consumers, policies,
apply layers, Atomics, Combineds, or live configuration.

## Unknown Semantics

Unknown is a first-class contract state, not a cosmetic problem.

- `unknown`, `unavailable`, `None`, and missing required entities are stale
  evidence.
- Stale required evidence must not be normalized into a safe-looking value.
- `unknown` must not become `closed`, `off`, `inactive`, `locked`, `unlocked`,
  `0 W`, `sunny`, `rainy`, or `safe_to_cut`.
- If one source proves an unsafe or active condition, that condition may still
  win over other stale sources. Example: one open contact means Opening is
  `open` even if another contact is stale.
- If no source proves a concrete active/unsafe condition and required evidence
  is stale, the Master should expose `unknown` or a conservative blocking state.

## Source Quality

Every target Master/Contract should expose the same health vocabulary:

- `source_quality: ok`
  All required central sources are present, available, and known.
- `source_quality: degraded`
  The contract can still publish useful truth, but at least one optional or
  supporting source is stale, unavailable, or missing.
- `source_quality: problem`
  A central required source is stale, unavailable, missing, or contradictory
  enough that the contract cannot determine its main truth safely.

`degraded` is derived from `source_quality != "ok"`.

`degraded_reason` should be a stable list of short reason codes. Examples:

- `stale_required_source`
- `lock_source_unavailable`
- `battery_source_unavailable`
- `weather_source_unavailable`
- `source_switch_active: unavailable`
- `conflicting_open_and_tilt`

## Fallback vs Fail-Safe

Fallback means preserving useful contract output when enough evidence remains.
Fail-safe means refusing to publish a safe-looking value when evidence is not
trustworthy.

Allowed fallback:

- PC is active and Switch source is stale: Media Context may remain `pc`, while
  `source_quality` becomes `degraded`.
- Lock state is known and battery is stale: Door/Lock may remain `locked` or
  `unlocked`, while `source_quality` becomes `degraded`.
- One window is open and another source is stale: Opening remains `open`, while
  `source_quality` becomes `degraded`.

Required fail-safe:

- All Opening contacts stale: Opening is `unknown`, not `closed`.
- Lock source stale: Door/Lock is `unknown`, not `locked`.
- Weather source stale: Weather symbol is `unknown`, not `sunny` or `rainy`.
- Plug/power source stale: Power is unknown/degraded, not `off`, `0 W`, or
  `safe_to_cut`.
- No active media source is known and a central source is stale: Media Context
  should not silently become `idle`.

## Last-Known-Good / Grace Window

Last-Known-Good (LKG) and grace windows are a future stabilisation pattern, not
an implicit default.

Rules:

- LKG must be explicit per contract and per attribute.
- LKG must expose that it is using stale evidence, for example through
  `source_quality`, `degraded`, `degraded_reason`, and optionally
  `last_known_good_age_s`.
- LKG must have a bounded grace window.
- LKG must not be used for final apply permissions such as unlocking,
  plug-cut safety, blind movement clearance, or heating apply decisions.
- When LKG expires, the contract must fall back to `unknown` or a documented
  conservative state.

## Activity Context Target

Future target contract: `sensor.benni_activity_context`

This is a specification only. No runtime contract is introduced in alpha.9.

Target kind: `fusion_context`

Candidate state values:

- `sleep`
- `away`
- `home`
- `pc_general`
- `pc_gaming`
- `console_gaming`
- `tv`
- `music`
- `showering`
- `private_media`
- `unknown`

Ownership:

- Activity Context fuses stable Masters/Context contracts.
- It must not read raw media, opening, climate, plug, or presence quirks when
  a matching Master/Context exists.
- It may consume Media Context, Opening, Door/Lock, Climate Room Masters,
  Weather/Outdoor, and future presence/bio-state contracts.
- It must not own policy decisions such as heating mode, plug cut safety,
  audio target path, blind target position, or notification routing.

## Domain Rules

### Opening

Master: `sensor.benni_master_opening`

- Owns window/opening truth.
- Unknown contacts must not become `closed`.
- `open` wins over stale supporting evidence.
- `tilted` wins only when no source proves `open`.
- Blind and Climate may project Opening values but must not recalculate raw
  contact logic.
- Final blind movement clearance and heating pause are policy-owned.

### Climate Rooms

Masters:

- `sensor.benni_master_climate_living`
- `sensor.benni_master_climate_kitchen`
- `sensor.benni_master_climate_bath`

Rules:

- Own room climate truth such as temperature, humidity, thermostat state,
  HVAC mode, and room availability.
- Opening values may be projected from `sensor.benni_master_opening` only.
- Do not compute final target temperature, heating pause, eco/comfort/turbo
  decisions, or apply permissions in Core Devices.

### Weather / Outdoor

Master: `sensor.benni_master_weather_outdoor`

Rules:

- Own outdoor/weather truth, including weather symbol/icon preservation.
- `unknown`/`unavailable` weather source must normalize to
  `weather_symbol_normalized: unknown`.
- Do not guess sunny/rainy/cloudy from missing data.
- Hints such as `is_sunny_hint` and `is_rainy_hint` are domain hints, not final
  Climate or Blind policy decisions.

### Door / Lock

Master: `sensor.benni_master_door_lock`

Rules:

- Own lock state truth for Aqara U200.
- Lock source unknown/unavailable must become contract state `unknown`.
- Unknown lock source must not become `locked` or `unlocked`.
- Battery unavailability may degrade source quality but must not override a
  known lock state.
- Door Policy and apply integrations own auto-lock/auto-unlock decisions and
  service calls.

### Household Plug / Power

Master: `sensor.benni_master_household_plug`

Rules:

- Own plug/power availability, watt values, total power, counts, and diagnostic
  facts.
- Unknown/unavailable watt or plug state must not become `off`, `0 W`, or
  `safe_to_cut`.
- Final cut permissions such as `power_cut_allowed` and `power_cut_unsafe`
  are policy-owned by plug policy logic.
- Apply/service calls remain outside Core Devices.

### Media Context

Contract: `sensor.benni_master_media_context`

Rules:

- Fusion/Context contract built from Media Device Masters.
- Must read existing Media Device Masters instead of duplicating raw media
  entity detection.
- If a central source is stale and no other source proves idle, do not silently
  publish `idle`.
- If another source proves an active context, preserve that context and expose
  degradation transparently.
- Media Policy owns subwoofer, target audio path, volume, and HomePod
  decisions.

### Switch

Master: `sensor.benni_master_switch`

Rules:

- Switch supply and watt evidence are device-owned.
- Watt source may be optional.
- Both supply and watt unknown/unavailable means Switch remains
  `unknown/problem`.
- Known supply with missing watt may be `degraded/supply_only`.
- Unknown/unavailable must not be normalized into inactive/off.

## Hardening Matrix

| Domain | Master/Contract | Existing Legacy/Combined | Policies/Consumers | Unknown/Fallback-Regel | LKG/Grace relevant? | Fail-safe Policy-Regel noetig? | Retire-Kandidaten | Offene Fragen / Plane-Karte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Opening | `sensor.benni_master_opening` | `sensor.benni_combined_openings` and split Opening Combineds | Blind, Climate, System/Readiness | Unknown contacts never become `closed`; proven `open` wins | Possible for short contact drops, explicit only | Blind/Climate must block or pause on unknown/open | Opening Combined chain after consumer migration | Window tilted semantics per room |
| Climate Rooms | `sensor.benni_master_climate_living`, `sensor.benni_master_climate_kitchen`, `sensor.benni_master_climate_bath` | Legacy Climate devices/Combineds | Climate Policy, Apply | Missing thermostat/temperature means degraded/problem, not comfort-ready | Possible for short sensor gaps | Climate Policy must own final heat pause and targets | Legacy room Climate shims after policy migration | Opening projection timing |
| Weather/Outdoor | `sensor.benni_master_weather_outdoor` | Weather/Lux Combineds | Climate Policy, Blind/Rollo, Readiness | Unknown weather symbol remains `unknown` | Possible for weather provider hiccups | Policies must not treat unknown as sunny/rainy | Weather/Lux shims after consumers migrate | Exact weather symbol taxonomy |
| Door/Lock | `sensor.benni_master_door_lock` | Legacy lock/door helpers, if any | Door Policy, Automations, Dashboards | Unknown lock source becomes `unknown`, not locked/unlocked | Very limited; explicit only | Door Policy must block risky auto-actions on unknown | Legacy lock status helpers | Door contact belongs to Opening, not Door/Lock |
| Household Plug/Power | `sensor.benni_master_household_plug` | Plug/Power Combineds | Plug Policy, Media Policy, Readiness | Unknown power stays unknown/degraded, not `0 W` or safe | Possible for meter gaps, explicit only | Plug Policy owns final cut permission | Plug protection Combineds | Which meters are central vs optional |
| Media Context | `sensor.benni_master_media_context` | Media Combineds | Media State, Media Policy, Plug Policy | Missing central source cannot silently become idle; proven active context may remain degraded | Useful for brief media source gaps | Policies own final audio/subwoofer/plug decisions | Media context/protection Combineds | Activity Context split |
| Switch | `sensor.benni_master_switch` | Legacy Switch helpers, if any | Media Context, Plug Policy | Both supply and watt stale means `unknown/problem`; supply-only is degraded | Possible for watt meter gaps | Plug/Media Policy must not assume inactive on unknown | Old switch state shims | Live source availability issue documented separately |

## No-Go Rules

- Do not create new Atomics.
- Do not create new Combineds.
- Do not migrate consumers as incidental hardening work.
- Do not put policy decisions into Masters.
- Do not make Apply decisions in Core Devices.
- Do not hide source degradation by publishing safe-looking defaults.
- Do not use LKG without explicit contract fields and bounded expiry.
