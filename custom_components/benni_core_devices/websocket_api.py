"""WebSocket API for the Benni Core Devices panel.

Liefert den Diagnose-Status (Devices + Combineds + Reverse-Lookups), den
Builder-Katalog (Slots/Gruppen/Operatoren/Output-Typen) sowie CRUD für Devices,
Combineds und Light-Groups. Import unterstützt Dry-Run mit Validierungsreport;
problematische Quellen (`*_atomic`/`*_combined`/derived) werden gewarnt.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import voluptuous as vol
import yaml
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .builder import _build_device_conf
from .const import (
    CONF_COMBINEDS,
    CONF_DEVICE_TYPE,
    CONF_DEVICES,
    CONF_DISPLAY_NAME,
    CONF_EXPOSE_SECONDARY_SENSORS,
    CONF_FIELDS,
    CONF_GROUP_MEMBERS,
    CONF_LIGHT_GROUPS,
    CONF_PROFILE,
    CONF_SLUG,
    CONF_STICKY_HOLD_SECONDS,
    CONF_WAKE_MAC,
    CONF_WATT_BUCKETS,
    CONF_WATT_THRESHOLD_ON,
    COMBINED_OPERATOR_CHOICES,
    COMBINED_ROLE_CHOICES,
    DEFAULT_EXPOSE_SECONDARY_SENSORS,
    DEFAULT_PROFILE,
    DEFAULT_STICKY_HOLD_SECONDS,
    DEFAULT_WATT_THRESHOLD_ON,
    DOMAIN,
    OUTPUT_TYPE_CHOICES,
    PROFILE_LABELS,
    WATT_OPERATOR_CHOICES,
    WS_BULK_IMPORT,
    WS_EXPORT_CONFIG,
    WS_GET_CATALOG,
    WS_GET_STATUS,
    WS_REMOVE_COMBINED,
    WS_REMOVE_DEVICE,
    WS_REMOVE_GROUP,
    WS_SET_COMBINED,
    WS_SET_DEVICE,
    WS_SET_GROUP,
    DeviceType,
    combined_object_id_prefix,
    device_object_id_prefix,
    entry_profile,
    group_object_id_prefix,
)
from .coordinator import all_coordinators, combined_coordinators_for_entry
from .device_types import (
    ALL_SLOT_KEYS,
    ENTITY_SLOT_KEYS,
    SLOT_CATALOG,
    SLOT_GROUP_LABELS,
    SLOT_GROUP_ORDER,
    classify_source_entity,
    default_fields,
    slugify,
    source_warning_text,
    unique_slug,
    validate_import_payload,
)

_SLOT_SCHEMA_FIELDS = {vol.Optional(key): str for key in ALL_SLOT_KEYS}


def _entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _devices(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    raw = entry.options.get(CONF_DEVICES)
    return dict(raw) if isinstance(raw, dict) else {}


def _groups(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    raw = entry.options.get(CONF_LIGHT_GROUPS)
    return dict(raw) if isinstance(raw, dict) else {}


def _combineds(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    raw = entry.options.get(CONF_COMBINEDS)
    return dict(raw) if isinstance(raw, dict) else {}


async def _update_options(
    hass: HomeAssistant, entry: ConfigEntry, options: dict[str, Any]
) -> None:
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.config_entries.async_reload(entry.entry_id)


def _json_safe(value: Any) -> Any:
    """Macht ein Attribut-Dict JSON-fähig (datetime → ISO-String)."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _own_prefixes(profile: str) -> tuple[str, ...]:
    return (
        device_object_id_prefix(profile),
        group_object_id_prefix(profile),
        combined_object_id_prefix(profile),
    )


def _source_warnings(conf: dict[str, Any], profile: str) -> list[str]:
    """Warnt bei problematischen Slot-Quellen (LH §5)."""
    own = _own_prefixes(profile)
    out: list[str] = []
    for key in ENTITY_SLOT_KEYS:
        eid = conf.get(key)
        if not eid:
            continue
        category = classify_source_entity(str(eid), own_prefixes=own)
        if category:
            out.append(source_warning_text(category, str(eid)))
    return out


def _device_sensor_entity_id(profile: str, slug: str) -> str:
    return f"sensor.{device_object_id_prefix(profile)}{slug}"


def _consumed_by_index(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, list[str]]:
    """Reverse-Lookup: device-sensor entity_id → Combined-Slugs, die ihn nutzen."""
    index: dict[str, list[str]] = {}
    for coord in combined_coordinators_for_entry(hass, entry).values():
        for src in coord.config.sources:
            if src.entity:
                index.setdefault(src.entity, []).append(coord.slug)
    return index


# ─────────────────────────────────────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────────────────────────────────────


def _status(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    profile = entry_profile(entry)
    coords = all_coordinators(hass)
    coord_by_slug = {coord.slug: coord for coord in coords}
    consumed_by = _consumed_by_index(hass, entry)

    devices = []
    for slug, conf in _devices(entry).items():
        coord = coord_by_slug.get(slug)
        result = coord.data if coord else None
        attrs = _json_safe(coord.main_attributes) if coord else {}
        sensor_id = _device_sensor_entity_id(profile, slug)
        devices.append(
            {
                "slug": slug,
                "config": {**conf, CONF_SLUG: slug},
                "entity_id": sensor_id,
                "state": result.state if result else None,
                "attrs": attrs,
                "slots": {
                    key: conf.get(key)
                    for key in ALL_SLOT_KEYS
                    if conf.get(key)
                },
                "warnings": _source_warnings(conf, profile),
                "consumed_by": consumed_by.get(sensor_id, []),
            }
        )

    combineds = []
    for slug, coord in combined_coordinators_for_entry(hass, entry).items():
        result = coord.data
        derived = [
            {
                "slug": d.slug,
                "name": d.name,
                "device_class": d.device_class,
                "state": coord.derived_state(d),
                "entity_id": (
                    f"binary_sensor.{combined_object_id_prefix(profile)}{slug}_{d.slug}"
                ),
            }
            for d in coord.config.derived
        ]
        combineds.append(
            {
                "slug": slug,
                "display_name": coord.config.display_name,
                "entity_id": f"sensor.{combined_object_id_prefix(profile)}{slug}",
                "state": result.state if result else None,
                "output_type": coord.config.output_type,
                "config": _combineds(entry).get(slug, {}),
                "attrs": _json_safe(coord.attributes),
                "derived": derived,
            }
        )

    groups = []
    for slug, conf in _groups(entry).items():
        members = [m for m in conf.get(CONF_GROUP_MEMBERS, []) if isinstance(m, str)]
        on = [
            m
            for m in members
            if (state := hass.states.get(m)) is not None and state.state == "on"
        ]
        groups.append(
            {
                "slug": slug,
                "display_name": conf.get(CONF_DISPLAY_NAME, slug),
                "members": members,
                "state": "on" if on else "off",
                "attrs": {
                    "members": members,
                    "entity_id": members,
                    "member_count": len(members),
                    "on_count": len(on),
                    "any_on": bool(on),
                },
            }
        )

    return {
        "profile": entry.data.get(CONF_PROFILE, DEFAULT_PROFILE),
        "profile_label": PROFILE_LABELS.get(
            entry.data.get(CONF_PROFILE, DEFAULT_PROFILE), profile
        ),
        "entry_id": entry.entry_id,
        "devices": devices,
        "combineds": combineds,
        "groups": groups,
    }


# ─────────────────────────────────────────────────────────────────────────────
# KATALOG
# ─────────────────────────────────────────────────────────────────────────────


def _catalog() -> dict[str, Any]:
    return {
        "device_types": [
            {
                "value": dt.value,
                "label": dt.value.replace("_", " ").title(),
                "default_fields": list(default_fields(dt)),
            }
            for dt in DeviceType
        ],
        "slot_catalog": {
            key: {
                "key": spec.key,
                "domains": list(spec.domains),
                "label": spec.description,
                "group": spec.group,
                "role": spec.role,
                "kind": spec.kind,
            }
            for key, spec in SLOT_CATALOG.items()
        },
        "slot_groups": [
            {"key": g, "label": SLOT_GROUP_LABELS.get(g, g)} for g in SLOT_GROUP_ORDER
        ],
        "watt_operators": list(WATT_OPERATOR_CHOICES),
        "combined": {
            "operators": list(COMBINED_OPERATOR_CHOICES),
            "output_types": list(OUTPUT_TYPE_CHOICES),
            "roles": list(COMBINED_ROLE_CHOICES),
        },
        "defaults": {
            "watt_threshold_on": DEFAULT_WATT_THRESHOLD_ON,
            "sticky_hold_seconds": DEFAULT_STICKY_HOLD_SECONDS,
            "expose_secondary_sensors": DEFAULT_EXPOSE_SECONDARY_SENSORS,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# DEVICE-CONF aus Message
# ─────────────────────────────────────────────────────────────────────────────


def _device_conf_from_msg(
    msg: dict[str, Any], existing: set[str]
) -> tuple[str, dict[str, Any]]:
    raw_type = msg.get(CONF_DEVICE_TYPE)
    device_type = DeviceType(raw_type)
    display_name = str(msg.get(CONF_DISPLAY_NAME) or msg.get("name") or "").strip()
    if not display_name:
        raise ValueError("display_name is required")
    fields = [key for key in (msg.get(CONF_FIELDS) or []) if key in SLOT_CATALOG]
    slots = msg.get("slots") if isinstance(msg.get("slots"), dict) else {}
    slot_values = {key: slots.get(key, msg.get(key)) for key in fields}
    runtime = {
        CONF_WATT_THRESHOLD_ON: msg.get(CONF_WATT_THRESHOLD_ON, DEFAULT_WATT_THRESHOLD_ON),
        CONF_STICKY_HOLD_SECONDS: msg.get(CONF_STICKY_HOLD_SECONDS, DEFAULT_STICKY_HOLD_SECONDS),
        CONF_EXPOSE_SECONDARY_SENSORS: msg.get(
            CONF_EXPOSE_SECONDARY_SENSORS, DEFAULT_EXPOSE_SECONDARY_SENSORS
        ),
    }
    conf = _build_device_conf(device_type, display_name, fields, slot_values, runtime)
    if isinstance(msg.get(CONF_WATT_BUCKETS), list):
        conf[CONF_WATT_BUCKETS] = msg[CONF_WATT_BUCKETS]
    # wake_mac ist ein Text-Slot (keine Entity) — separat übernehmen.
    wake_mac = slots.get(CONF_WAKE_MAC) or msg.get(CONF_WAKE_MAC)
    if wake_mac and CONF_WAKE_MAC in fields:
        conf[CONF_WAKE_MAC] = str(wake_mac)
    requested = str(msg.get(CONF_SLUG) or "").strip().lower()
    if requested:
        slug = requested
    else:
        slug = unique_slug(slugify(display_name) or "device", existing)
    return slug, conf


# ─────────────────────────────────────────────────────────────────────────────
# BULK-IMPORT + DRY-RUN-REPORT
# ─────────────────────────────────────────────────────────────────────────────


def _parse_bulk(raw: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    parsed = yaml.safe_load(raw) if raw and raw.strip() else None
    if isinstance(parsed, dict):
        devices = parsed.get(CONF_DEVICES, [])
        groups = parsed.get(CONF_LIGHT_GROUPS, {})
    else:
        devices = parsed
        groups = {}
    if isinstance(devices, list):
        for item in devices:
            if isinstance(item, dict) and not item.get(CONF_SLUG):
                derived = slugify(str(item.get(CONF_DISPLAY_NAME, "")))
                if derived:
                    item[CONF_SLUG] = derived
    valid, errors = validate_import_payload(devices)
    if errors:
        raise ValueError("\n".join(errors))
    valid_groups = groups if isinstance(groups, dict) else {}
    return valid, valid_groups


def _import_report(
    valid: list[dict[str, Any]], profile: str
) -> list[dict[str, Any]]:
    """Pro Device ein Vorschau-Eintrag (LH §5 Dry-Run)."""
    own = _own_prefixes(profile)
    report: list[dict[str, Any]] = []
    for d in valid:
        slug = str(d.get(CONF_SLUG))
        active_fields = [k for k in (d.get(CONF_FIELDS) or []) if k in SLOT_CATALOG]
        # Felder, die als Slot-Keys mitgegeben wurden (auch ohne CONF_FIELDS).
        slot_keys = [k for k in ALL_SLOT_KEYS if d.get(k)]
        unknown_slots = [
            k for k in d
            if k not in SLOT_CATALOG
            and k not in (
                CONF_SLUG, CONF_DEVICE_TYPE, CONF_DISPLAY_NAME, CONF_FIELDS,
                CONF_WATT_THRESHOLD_ON, CONF_STICKY_HOLD_SECONDS,
                CONF_EXPOSE_SECONDARY_SENSORS, CONF_WATT_BUCKETS,
            )
        ]
        missing_entities = [
            k for k in active_fields
            if SLOT_CATALOG[k].kind == "entity" and not d.get(k)
        ]
        derived_sources = []
        for k in slot_keys:
            if SLOT_CATALOG[k].kind != "entity":
                continue
            category = classify_source_entity(str(d[k]), own_prefixes=own)
            if category:
                derived_sources.append(source_warning_text(category, str(d[k])))
        report.append(
            {
                "slug": slug,
                "device_type": d.get(CONF_DEVICE_TYPE),
                "entity_id": _device_sensor_entity_id(profile, slug),
                "slots": {k: d[k] for k in slot_keys},
                "unknown_slots": unknown_slots,
                "missing_entities": missing_entities,
                "derived_sources": derived_sources,
                "accepted": not derived_sources,
            }
        )
    return report


def _apply_bulk(
    entry: ConfigEntry,
    valid: list[dict[str, Any]],
    imported_groups: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    devices = _devices(entry)
    for item in valid:
        slug = str(item.get(CONF_SLUG))
        field_keys = [key for key in ALL_SLOT_KEYS if item.get(key)]
        conf: dict[str, Any] = {
            CONF_DEVICE_TYPE: item[CONF_DEVICE_TYPE],
            CONF_DISPLAY_NAME: item.get(CONF_DISPLAY_NAME, slug),
            CONF_FIELDS: field_keys,
        }
        for key in field_keys:
            conf[key] = item[key]
        for key in (
            CONF_WATT_THRESHOLD_ON,
            CONF_STICKY_HOLD_SECONDS,
            CONF_EXPOSE_SECONDARY_SENSORS,
            CONF_WATT_BUCKETS,
        ):
            if key in item:
                conf[key] = item[key]
        devices[slug] = conf
    groups = {**_groups(entry), **imported_groups}
    return devices, groups


def _export_yaml(entry: ConfigEntry) -> str:
    payload = {
        CONF_DEVICES: [
            {CONF_SLUG: slug, **conf} for slug, conf in _devices(entry).items()
        ],
        CONF_COMBINEDS: _combineds(entry),
        CONF_LIGHT_GROUPS: _groups(entry),
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────


def async_setup_websocket_api(hass: HomeAssistant) -> None:
    @websocket_api.websocket_command({vol.Required("type"): WS_GET_STATUS})
    @websocket_api.async_response
    async def ws_get_status(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        connection.send_result(msg["id"], _status(hass, entry))

    @websocket_api.websocket_command({vol.Required("type"): WS_GET_CATALOG})
    @websocket_api.async_response
    async def ws_get_catalog(hass, connection, msg) -> None:
        connection.send_result(msg["id"], _catalog())

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_DEVICE,
        vol.Optional(CONF_SLUG): str,
        vol.Optional(CONF_DEVICE_TYPE): str,
        vol.Optional(CONF_DISPLAY_NAME): str,
        vol.Optional("name"): str,
        vol.Optional(CONF_FIELDS): [str],
        vol.Optional("slots"): dict,
        vol.Optional(CONF_WATT_THRESHOLD_ON): vol.Any(int, float, str),
        vol.Optional(CONF_STICKY_HOLD_SECONDS): vol.Any(int, float, str),
        vol.Optional(CONF_EXPOSE_SECONDARY_SENSORS): bool,
        vol.Optional(CONF_WATT_BUCKETS): list,
        vol.Optional(CONF_WAKE_MAC): str,
        **_SLOT_SCHEMA_FIELDS,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_device(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        devices = _devices(entry)
        try:
            slug, conf = _device_conf_from_msg(msg, set(devices))
        except (TypeError, ValueError) as err:
            connection.send_error(msg["id"], "invalid_device", str(err))
            return
        devices[slug] = conf
        warnings = _source_warnings(conf, entry_profile(entry))
        await _update_options(hass, entry, {**entry.options, CONF_DEVICES: devices})
        connection.send_result(
            msg["id"], {"slug": slug, "config": conf, "warnings": warnings}
        )

    @websocket_api.websocket_command({
        vol.Required("type"): WS_REMOVE_DEVICE,
        vol.Required(CONF_SLUG): str,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_remove_device(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        devices = _devices(entry)
        devices.pop(msg[CONF_SLUG], None)
        await _update_options(hass, entry, {**entry.options, CONF_DEVICES: devices})
        connection.send_result(msg["id"], {"removed": msg[CONF_SLUG]})

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_COMBINED,
        vol.Optional(CONF_SLUG): str,
        vol.Required(CONF_DISPLAY_NAME): str,
        vol.Required("config"): dict,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_combined(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        display_name = str(msg.get(CONF_DISPLAY_NAME) or "").strip()
        if not display_name:
            connection.send_error(msg["id"], "invalid_combined", "display_name is required")
            return
        combineds = _combineds(entry)
        slug = str(msg.get(CONF_SLUG) or "").strip().lower()
        if not slug:
            slug = unique_slug(slugify(display_name) or "combined", set(combineds))
        conf = dict(msg["config"])
        conf[CONF_DISPLAY_NAME] = display_name
        combineds[slug] = conf
        await _update_options(
            hass, entry, {**entry.options, CONF_COMBINEDS: combineds}
        )
        connection.send_result(msg["id"], {"slug": slug})

    @websocket_api.websocket_command({
        vol.Required("type"): WS_REMOVE_COMBINED,
        vol.Required(CONF_SLUG): str,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_remove_combined(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        combineds = _combineds(entry)
        combineds.pop(msg[CONF_SLUG], None)
        await _update_options(
            hass, entry, {**entry.options, CONF_COMBINEDS: combineds}
        )
        connection.send_result(msg["id"], {"removed": msg[CONF_SLUG]})

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_GROUP,
        vol.Optional(CONF_SLUG): str,
        vol.Optional(CONF_DISPLAY_NAME): str,
        vol.Optional("name"): str,
        vol.Optional(CONF_GROUP_MEMBERS): [str],
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_group(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        display_name = str(msg.get(CONF_DISPLAY_NAME) or msg.get("name") or "").strip()
        members = [m for m in (msg.get(CONF_GROUP_MEMBERS) or []) if isinstance(m, str)]
        if not display_name or not members:
            connection.send_error(msg["id"], "invalid_group", "display_name and members are required")
            return
        groups = _groups(entry)
        slug = str(msg.get(CONF_SLUG) or "").strip().lower()
        if not slug:
            slug = unique_slug(slugify(display_name) or "group", set(groups))
        groups[slug] = {CONF_DISPLAY_NAME: display_name, CONF_GROUP_MEMBERS: members}
        await _update_options(hass, entry, {**entry.options, CONF_LIGHT_GROUPS: groups})
        connection.send_result(msg["id"], {"slug": slug})

    @websocket_api.websocket_command({
        vol.Required("type"): WS_REMOVE_GROUP,
        vol.Required(CONF_SLUG): str,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_remove_group(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        groups = _groups(entry)
        groups.pop(msg[CONF_SLUG], None)
        await _update_options(hass, entry, {**entry.options, CONF_LIGHT_GROUPS: groups})
        connection.send_result(msg["id"], {"removed": msg[CONF_SLUG]})

    @websocket_api.websocket_command({
        vol.Required("type"): WS_BULK_IMPORT,
        vol.Required("payload"): str,
        vol.Optional("dry_run"): bool,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_bulk_import(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        try:
            imported_devices, imported_groups = _parse_bulk(msg["payload"])
        except (TypeError, ValueError, yaml.YAMLError) as err:
            connection.send_error(msg["id"], "invalid_bulk", str(err))
            return
        profile = entry_profile(entry)
        report = _import_report(imported_devices, profile)
        if msg.get("dry_run"):
            connection.send_result(
                msg["id"],
                {
                    "dry_run": True,
                    "devices": len(imported_devices),
                    "groups": len(imported_groups),
                    "report": report,
                },
            )
            return
        devices, groups = _apply_bulk(entry, imported_devices, imported_groups)
        await _update_options(
            hass,
            entry,
            {**entry.options, CONF_DEVICES: devices, CONF_LIGHT_GROUPS: groups},
        )
        connection.send_result(
            msg["id"],
            {
                "dry_run": False,
                "devices": len(imported_devices),
                "groups": len(imported_groups),
                "report": report,
            },
        )

    @websocket_api.websocket_command({vol.Required("type"): WS_EXPORT_CONFIG})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_export_config(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        connection.send_result(msg["id"], {"yaml": _export_yaml(entry)})

    websocket_api.async_register_command(hass, ws_get_status)
    websocket_api.async_register_command(hass, ws_get_catalog)
    websocket_api.async_register_command(hass, ws_set_device)
    websocket_api.async_register_command(hass, ws_remove_device)
    websocket_api.async_register_command(hass, ws_set_combined)
    websocket_api.async_register_command(hass, ws_remove_combined)
    websocket_api.async_register_command(hass, ws_set_group)
    websocket_api.async_register_command(hass, ws_remove_group)
    websocket_api.async_register_command(hass, ws_bulk_import)
    websocket_api.async_register_command(hass, ws_export_config)
