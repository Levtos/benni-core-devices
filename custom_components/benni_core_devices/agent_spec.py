"""Agent-Briefing-Generator (HA-frei, testbar).

Erzeugt aus dem v2-Rollen-/Klassenkatalog ein selbsterklärendes Briefing für
eine frische Claude-Code-/Codex-Session mit MCP-Anbindung an HA:
- ``build_briefing(version, profile, export_yaml)`` → Markdown-Prompt
- ``build_json_schema()`` → JSON-Schema (draft-07) des Import-/Combined-Payloads

Der Generator löst KEINEN Agenten aus — er liefert nur Text/Schema zum Kopieren.
"""

from __future__ import annotations

from typing import Any

from .const import (
    COMBINED_OPERATOR_CHOICES,
    FAIL_SAFE_CHOICES,
    OUTPUT_TYPE_CHOICES,
)
from .device_types import (
    ALL_ATOMIC_CLASSES,
    ALL_ROLE_KEYS,
    ATOMIC_CLASSES,
    BLOCKED_SOURCE_SUFFIXES,
    ROLE_CATALOG,
)


def _role_table() -> str:
    rows = ["| role | bucket | domains | compute_relevant | derived_from |",
            "| --- | --- | --- | --- | --- |"]
    for spec in ROLE_CATALOG.values():
        domains = ", ".join(spec.domains) if spec.domains else ("text" if spec.kind == "text" else "—")
        derive = f"{spec.derive_from}.{spec.derive_attr}" if spec.derive_attr else "—"
        rows.append(f"| `{spec.key}` | {spec.bucket} | {domains} | "
                    f"{'yes' if spec.compute_relevant else 'no'} | {derive} |")
    return "\n".join(rows)


def _class_block(spec, profile: str) -> str:
    def fmt(roles):
        return ", ".join(f"`{r}`" for r in roles) if roles else "—"

    pd = spec.role_domain_overrides.get("primary_state")
    pd_txt = ", ".join(pd) if pd else (", ".join(ROLE_CATALOG["primary_state"].domains) if "primary_state" in ROLE_CATALOG else "—")
    meta = ", ".join(f"`{r}`" for r in spec.metadata_override_roles) or "—"
    beta = " *(Beta — nur Grundgerüst)*" if spec.beta else ""
    return (
        f"### `{spec.atomic_class}`{beta}\n"
        f"- variants: {fmt(spec.variants)}\n"
        f"- power_model: `{spec.power_model}`\n"
        f"- required: {fmt(spec.required_roles)} (mode: **{spec.required_mode}**)\n"
        f"- optional sources: {fmt(spec.optional_roles)}\n"
        f"- controls: {fmt(spec.control_roles)}\n"
        f"- metadata (auto-derived from primary_state; override only if separate entity): {meta}\n"
        f"- primary_state domains for this class: {pd_txt}\n"
        f"- fail_safe default: `{spec.fail_safe}`\n"
        f"- exposed attributes: {fmt(spec.extra_attributes)}\n"
    )


_DEVICE_EXAMPLE = """```yaml
devices:
  - slug: living_window_right          # a-z0-9_, unique
    atomic_class: opening
    variant: window
    display_name: "Wohnzimmer Fenster rechts"
    sources:
      - role: open_contact
        entity: binary_sensor.living_window_right_open
      - role: tilt_contact             # optional
        entity: binary_sensor.living_window_right_tilt
    controls: []
    metadata_sources: []               # almost always empty (derived)
    diagnostics:
      fail_safe: open

  - slug: living_tv
    atomic_class: media_device
    variant: tv
    display_name: "Wohnzimmer TV"
    sources:
      - role: primary_state            # media_player only
        entity: media_player.living_lgtv
      - role: power_meter
        entity: sensor.living_tv_plug_power
    controls:
      - role: power_switch
        entity: switch.living_tv_plug
      - role: wake_mac
        value: "58:96:0A:5E:E9:2E"     # text control: value, not entity
    diagnostics:
      fail_safe: hold_last
    watt_threshold_on: 8
    sticky_hold_seconds: 30
    watt_buckets:
      - {state: "off", op: "<=", value: 8}
      - {state: "idle", op: "<=", value: 35}
      - {state: "playing", op: ">", value: 35}

  - slug: kitchen_coffee
    atomic_class: power_device
    variant: plug
    display_name: "Kaffeemaschine"
    sources:
      - role: primary_state            # switch only
        entity: switch.kitchen_coffee
      - role: power_meter
        entity: sensor.kitchen_coffee_power
    diagnostics:
      fail_safe: "off"

  - slug: dwd_home_temperature
    atomic_class: environment
    variant: room_climate
    display_name: "DWD Home Temperature"
    sources:
      - role: temperature_source
        entity: weather.dwd_home
        attribute: temperature             # reads state_attr(entity, attribute)
    diagnostics:
      fail_safe: unknown
```"""

_COMBINED_EXAMPLE = """```yaml
# Combineds may live in the SAME bulk_import YAML under `combineds:`
# (dict slug -> config), OR be created individually via WS `set_combined`
# ({slug?, display_name, config}).
combineds:
  opening_state:
    display_name: "Opening State"
    output_type: code                  # enum | code | boolean | number
    sources:
      - {key: open, role: open_contact, entity: binary_sensor.left_open}
      - {key: tilt, role: tilt_contact, entity: binary_sensor.left_tilt}
      - {key: source_watt, role: watt, entity: sensor.benni_device_ps5, attribute: watt}
    rules:                             # first-match-wins, in order
      - {source: open, op: unavailable, output: 9, reason: "open unclear"}
      - {source: open, op: eq, value: "on", output: 2, reason: open}
      - {source: tilt, op: eq, value: "on", output: 1, reason: tilted}
    default_output: 0
    default_reason: closed
    code_legend: {"0": closed, "1": tilted, "2": open, "9": unclear}
    derived:
      - {slug: any_open, name: "Any Open", device_class: opening, target: open_contact, op: eq, value: "on"}
```"""


def build_briefing(version: str, profile: str, export_yaml: str) -> str:
    blocked = ", ".join(f"`*{s}`" for s in BLOCKED_SOURCE_SUFFIXES)
    own = f"`{profile}_device_*`, `{profile}_combined_*`, `{profile}_light_group_*`"
    classes = "\n".join(_class_block(ATOMIC_CLASSES[c], profile) for c in ALL_ATOMIC_CLASSES)
    return f"""# Benni Core Devices — Agent Briefing (Atomics + Combined)

Contract/integration version: **{version}** · profile (route): **{profile}**

You are authoring the **atomic + combined layer** of the Home Assistant custom
integration `benni_core_devices`. You have an MCP connection to this HA instance —
use it to discover raw entities. Follow this contract exactly; validate with
dry-run before applying.

## Golden rules
- Consume **only raw HA entities**. NEVER use as a source: entity_ids ending in
  {blocked}, or starting with this integration's own output {own}.
- **One physical device = one atomic** → `sensor.{profile}_device_<slug>`.
  Per-device, not per-feature.
- **Metadata is auto-derived** (title/app/source/volume/mute/artist/album) from the
  `primary_state` entity's attributes. Do NOT add `metadata_sources` unless a
  *separate* entity is required (rare, e.g. a dedicated console title sensor).
- `profile` is the route (benni/eltern), NOT the device subtype. Subtype = `variant`.
- `wake_mac` is a **text control** (`value:`), not an entity.
- For openings with two physical contacts, `battery_source` is a single optional
  entity — pick the primary contact's battery or omit.
- A binding may set `attribute:` next to `entity:`; then the source value is
  `state_attr(entity, attribute)` instead of the entity state. Use this for
  weather entities such as `weather.dwd_home` (`temperature`, `humidity`, ...)
  and for Combined sources reading attributes from published Core Devices outputs.

## Workflow
> Import/export is available **both** as WebSocket commands and as **HA services**
> (callable via MCP `ha_call_service`, with `return_response: true`):
> `benni_core_devices.export_config` → returns `{{yaml}}`.
> For MCP bridges that cannot pass service `data`, write the edited export YAML
> to `<config>/benni_core_devices/import.yaml`, then call the arg-less services
> `benni_core_devices.import_file_dry_run` and
> `benni_core_devices.import_file_apply` with `return_response: true`.
> The legacy `benni_core_devices.bulk_import` service still accepts
> `{{payload, dry_run, replace}}` and returns the same report. Add top-level
> `replace: true` to the import file for a clean slate.

1. **Read current config** (avoid duplicates): service `export_config` (MCP) or
   WS `benni_core_devices/export_config`.
2. **Discover** raw entities via the HA MCP tools (search/list/states).
3. **Draft** the devices YAML (schema below) and any combined configs.
4. **Validate devices**: service `import_file_dry_run` (MCP) or WS
   `benni_core_devices/bulk_import` with `dry_run: true`.
   Resolve every `missing_required` and `derived_sources` entry; note the resulting
   `entity_id`s.
5. **Apply devices**: service `import_file_apply` (MCP) or the same WS command
   with `dry_run: false`.
6. **Combineds**: either include a `combineds:` block in the bulk_import YAML
   (dict slug → config; validated by the same dry-run), or create each via WS
   `benni_core_devices/set_combined` `{{slug?, display_name, config}}`.

## Roles
{_role_table()}

## Atomic classes
{classes}
## Devices import YAML
{_DEVICE_EXAMPLE}

Runtime keys (`watt_threshold_on`, `sticky_hold_seconds`, `expose_secondary_sensors`,
`watt_buckets`) apply to `integration_watt_sticky` (media/audio/console) and
`watt_primary_sticky` (power) classes. For `watt_primary_sticky` the real power
(`power_meter`) decides powered/active; the plug switch is only a fallback when the
meter is stale, and `sticky_hold_seconds` bridges short zero-watt phases mid-cycle.

## Combined config
output_type: {", ".join(f"`{t}`" for t in OUTPUT_TYPE_CHOICES)} ·
operators: {", ".join(f"`{o}`" for o in COMBINED_OPERATOR_CHOICES)} ·
fail_safe: {", ".join(f"`{f}`" for f in FAIL_SAFE_CHOICES)}

{_COMBINED_EXAMPLE}

A derived binary sensor's `target` is `__output__`, a `derived_values` name,
a source `key`, or a role (any-match over sources of that role). Promoting a
derived value to its own entity is the exception for History/native-HA use; the
default is `expose`/`exposed_attributes`. Use optional `object_id` only when a
specific binary_sensor object id must stay stable.

### Combined v1 derived_values (optional, additive)
Named intermediate values, evaluated before the rules; rules/output may reference
`${{name}}` and `${{self}}` (own last output). Output may be `"${{name}}"`.
- `expr` (number): formula over `${{refs}}`, ops `+ - * /` `== != < <= > >=` `and or not`,
  funcs `min,max,abs,round(x[,n]),clamp(x,lo,hi)`. None-propagating (unavailable → fail_safe).
- `gate` (bool): same parser; `any([...])`/`all([...])`/`not(x)`.
- `enum` (string): ordered `cases: [{{when, output}}]`, first true wins, else `default`.
- `health`: `atomics: [src_key, ...]` → `ok|degraded|problem`.
- `latch`: `set:` / `reset:` gate-expressions (Schmitt hysteresis); holds between; `fail_safe`.
- `previous`: expose `${{self}}`.
fail_safe per node or config: `off|open|hold_last|unknown`. Timers/`since` = v1.1 (rejected).
Set `expose: true` on a node or top-level `exposed_attributes: [name, ...]` to publish
selected derived values as flat top-level attributes on the Combined/Fusion sensor.
Default is internal-only.
```yaml
  derived_values:
    - {{ name: any_open, kind: gate, expr: "any([${{open_a}}, ${{open_b}}])", expose: true }}
    - {{ name: room, kind: enum, cases: [{{ when: '${{open_a}} == "on"', output: open }}], default: closed, expose: true }}
    - {{ name: dew, kind: expr, expr: "round(${{t}} - (100 - ${{rh}})/5, 1)" }}
    - {{ name: dark, kind: latch, set: "${{lux}} < 50", reset: "${{lux}} >= 100", fail_safe: off }}
  exposed_attributes: [dew]
```

## Current configuration (export — do not duplicate)
```yaml
{export_yaml.strip() or "# (empty)"}
```
"""


def build_json_schema() -> dict[str, Any]:
    binding = {
        "type": "object",
        "required": ["role"],
        "properties": {
            "role": {"enum": list(ALL_ROLE_KEYS)},
            "entity": {"type": "string"},
            "attribute": {"type": "string"},
            "value": {"type": "string"},
            "required": {"type": "boolean"},
        },
        "additionalProperties": False,
    }
    device = {
        "type": "object",
        "required": ["slug", "atomic_class"],
        "properties": {
            "slug": {"type": "string", "pattern": "^[a-z0-9_]+$"},
            "atomic_class": {"enum": list(ALL_ATOMIC_CLASSES)},
            "variant": {"type": "string"},
            "display_name": {"type": "string"},
            "sources": {"type": "array", "items": {"$ref": "#/$defs/binding"}},
            "controls": {"type": "array", "items": {"$ref": "#/$defs/binding"}},
            "metadata_sources": {"type": "array", "items": {"$ref": "#/$defs/binding"}},
            "diagnostics": {
                "type": "object",
                "properties": {
                    "fail_safe": {"enum": list(FAIL_SAFE_CHOICES)},
                    "availability_rule": {"type": "string"},
                },
            },
            "watt_threshold_on": {"type": "integer"},
            "sticky_hold_seconds": {"type": "integer"},
            "expose_secondary_sensors": {"type": "boolean"},
            "watt_buckets": {"type": "array"},
        },
        "additionalProperties": True,
    }
    rule = {
        "type": "object",
        "required": ["source", "op"],
        "properties": {
            "source": {"type": "string"},
            "op": {"enum": list(COMBINED_OPERATOR_CHOICES)},
            "value": {},
            "output": {},
            "reason": {"type": "string"},
        },
    }
    derived_case = {
        "type": "object",
        "required": ["when", "output"],
        "properties": {
            "when": {"type": "string"},
            "output": {},
        },
    }
    derived_value = {
        "type": "object",
        "required": ["name", "kind"],
        "properties": {
            "name": {"type": "string"},
            "kind": {"enum": ["expr", "gate", "enum", "health", "latch", "previous"]},
            "expr": {"type": "string"},
            "cases": {"type": "array", "items": {"$ref": "#/$defs/derived_case"}},
            "default": {},
            "set": {"type": "string"},
            "reset": {"type": "string"},
            "atomics": {"type": "array", "items": {"type": "string"}},
            "fail_safe": {"enum": list(FAIL_SAFE_CHOICES)},
            "expose": {"type": "boolean"},
        },
    }
    derived_sensor = {
        "type": "object",
        "required": ["slug"],
        "properties": {
            "slug": {"type": "string", "pattern": "^[a-z0-9_]+$"},
            "name": {"type": "string"},
            "object_id": {"type": "string"},
            "device_class": {"type": "string"},
            "target": {"type": "string"},
            "op": {"enum": list(COMBINED_OPERATOR_CHOICES)},
            "value": {"type": "string"},
        },
    }
    combined_source = {
        "type": "object",
        "required": ["key"],
        "properties": {
            "key": {"type": "string"},
            "role": {"type": "string"},
            "entity": {"type": "string"},
            "attribute": {"type": "string"},
        },
        "additionalProperties": False,
    }
    combined_config = {
        "type": "object",
        "properties": {
            "output_type": {"enum": list(OUTPUT_TYPE_CHOICES)},
            "sources": {"type": "array", "items": {"$ref": "#/$defs/combined_source"}},
            "rules": {"type": "array", "items": {"$ref": "#/$defs/rule"}},
            "default_output": {},
            "default_reason": {"type": "string"},
            "code_legend": {"type": "object"},
            "derived": {"type": "array", "items": {"$ref": "#/$defs/derived_sensor"}},
            "derived_values": {"type": "array", "items": {"$ref": "#/$defs/derived_value"}},
            "exposed_attributes": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "benni_core_devices import payload",
        "type": "object",
        "properties": {
            "devices": {"type": "array", "items": {"$ref": "#/$defs/device"}},
        },
        "$defs": {
            "binding": binding,
            "device": device,
            "rule": rule,
            "derived_sensor": derived_sensor,
            "combined_source": combined_source,
            "derived_case": derived_case,
            "derived_value": derived_value,
            "combined_config": combined_config,
        },
    }
