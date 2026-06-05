"""WebSocket API for the Benni Core Devices panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
import yaml
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .builder import _build_device_conf
from .const import (
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
    CONF_WATT_BUCKETS,
    CONF_WATT_THRESHOLD_ON,
    DEFAULT_EXPOSE_SECONDARY_SENSORS,
    DEFAULT_PROFILE,
    DEFAULT_STICKY_HOLD_SECONDS,
    DEFAULT_WATT_THRESHOLD_ON,
    DOMAIN,
    PROFILE_LABELS,
    WATT_OPERATOR_CHOICES,
    WS_BULK_IMPORT,
    WS_GET_CATALOG,
    WS_GET_STATUS,
    WS_REMOVE_DEVICE,
    WS_REMOVE_GROUP,
    WS_SET_DEVICE,
    WS_SET_GROUP,
    DeviceType,
)
from .coordinator import all_coordinators
from .device_types import (
    ALL_SLOT_KEYS,
    SLOT_CATALOG,
    default_fields,
    slugify,
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


async def _update_options(
    hass: HomeAssistant, entry: ConfigEntry, options: dict[str, Any]
) -> None:
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.config_entries.async_reload(entry.entry_id)


def _result_attrs(coord) -> dict[str, Any]:
    result = coord.data
    if result is None:
        return {}
    attrs: dict[str, Any] = {
        "device_type": coord.device_type.value,
        "slug": coord.slug,
        "display_name": coord.display_name,
        "powered": result.powered,
        "power_state": result.power_state,
        "available": result.available,
        "power_source": result.power_source,
        "last_powered_change": (
            result.last_powered_change.isoformat()
            if result.last_powered_change
            else None
        ),
        "override_active": result.override_active,
        "watt_disagrees": result.watt_disagrees,
        "area_id": coord._derive_area_id(),
        "watt": result.watt,
    }
    from .device_types import profile_for

    profile = profile_for(coord.device_type)
    for key in profile.extra_attributes:
        if key == "watt":
            attrs[key] = result.watt
        elif key in ("media_player_state", "hvac_mode"):
            attrs[key] = result.raw_state if profile.state_slot else None
        elif key == "target_temperature":
            attrs[key] = result.extra.get("temperature")
        else:
            attrs[key] = result.extra.get(key)
    return attrs


def _status(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coords = all_coordinators(hass)
    coord_by_slug = {coord.slug: coord for coord in coords}
    devices = []
    for slug, conf in _devices(entry).items():
        coord = coord_by_slug.get(slug)
        result = coord.data if coord else None
        devices.append(
            {
                "slug": slug,
                "config": {**conf, CONF_SLUG: slug},
                "state": result.state if result else None,
                "attrs": _result_attrs(coord) if coord else {},
                "slots": {
                    key: conf.get(key)
                    for key in ALL_SLOT_KEYS
                    if conf.get(key)
                },
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

    profile = entry.data.get(CONF_PROFILE, DEFAULT_PROFILE)
    return {
        "profile": profile,
        "profile_label": PROFILE_LABELS.get(profile, profile),
        "entry_id": entry.entry_id,
        "devices": devices,
        "groups": groups,
    }


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
            }
            for key, spec in SLOT_CATALOG.items()
        },
        "watt_operators": list(WATT_OPERATOR_CHOICES),
        "defaults": {
            "watt_threshold_on": DEFAULT_WATT_THRESHOLD_ON,
            "sticky_hold_seconds": DEFAULT_STICKY_HOLD_SECONDS,
            "expose_secondary_sensors": DEFAULT_EXPOSE_SECONDARY_SENSORS,
        },
    }


def _device_conf_from_msg(msg: dict[str, Any], existing: set[str]) -> tuple[str, dict[str, Any]]:
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
    requested = str(msg.get(CONF_SLUG) or "").strip().lower()
    if requested:
        slug = requested
    else:
        slug = unique_slug(slugify(display_name) or "device", existing)
    return slug, conf


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
        await _update_options(hass, entry, {**entry.options, CONF_DEVICES: devices})
        connection.send_result(msg["id"], {"slug": slug, "config": conf})

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
        devices = _devices(entry)
        for item in imported_devices:
            slug = str(item.pop(CONF_SLUG))
            field_keys = [key for key in ALL_SLOT_KEYS if item.get(key)]
            conf = {
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
        await _update_options(
            hass,
            entry,
            {**entry.options, CONF_DEVICES: devices, CONF_LIGHT_GROUPS: groups},
        )
        connection.send_result(
            msg["id"], {"devices": len(imported_devices), "groups": len(imported_groups)}
        )

    websocket_api.async_register_command(hass, ws_get_status)
    websocket_api.async_register_command(hass, ws_get_catalog)
    websocket_api.async_register_command(hass, ws_set_device)
    websocket_api.async_register_command(hass, ws_remove_device)
    websocket_api.async_register_command(hass, ws_set_group)
    websocket_api.async_register_command(hass, ws_remove_group)
    websocket_api.async_register_command(hass, ws_bulk_import)
