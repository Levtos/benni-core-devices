"""WebSocket API for the Benni Core Devices panel (v2, rollenbasiert)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import voluptuous as vol
import yaml
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    AVAILABILITY_ANY_REQUIRED_OR_ANY_SOURCE,
    COMBINED_OPERATOR_CHOICES,
    COMBINED_ROLE_CHOICES,
    CONF_ATOMIC_CLASS,
    CONF_AVAILABILITY_RULE,
    CONF_COMBINEDS,
    CONF_CONTROLS,
    CONF_DEVICES,
    CONF_DIAGNOSTICS,
    CONF_DISPLAY_NAME,
    CONF_EXPOSE_SECONDARY_SENSORS,
    CONF_FAIL_SAFE,
    CONF_GROUP_MEMBERS,
    CONF_LIGHT_GROUPS,
    CONF_METADATA_SOURCES,
    CONF_PROFILE,
    CONF_SLUG,
    CONF_SOURCES,
    CONF_STICKY_HOLD_SECONDS,
    CONF_VARIANT,
    CONF_WATT_BUCKETS,
    CONF_WATT_THRESHOLD_ON,
    DEFAULT_EXPOSE_SECONDARY_SENSORS,
    DEFAULT_PROFILE,
    DEFAULT_STICKY_HOLD_SECONDS,
    DEFAULT_WATT_THRESHOLD_ON,
    DOMAIN,
    FAIL_SAFE_CHOICES,
    OUTPUT_TYPE_CHOICES,
    PROFILE_LABELS,
    WS_BULK_IMPORT,
    WS_EXPORT_CONFIG,
    WS_GET_CATALOG,
    WS_GET_STATUS,
    WS_AGENT_SPEC,
    WS_REMOVE_COMBINED,
    WS_REMOVE_DEVICE,
    WS_REMOVE_GROUP,
    WS_SET_COMBINED,
    WS_SET_DEVICE,
    WS_SET_GROUP,
    combined_object_id_prefix,
    device_object_id_prefix,
    entry_profile,
    group_object_id_prefix,
)
from .coordinator import all_coordinators, combined_coordinators_for_entry
from .device_types import (
    ATOMIC_CLASSES,
    ROLE_CATALOG,
    classify_source_entity,
    parse_device_config,
    slugify,
    source_warning_text,
    unique_slug,
    validate_import_payload,
)


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


async def _update_options(hass: HomeAssistant, entry: ConfigEntry, options: dict[str, Any]) -> None:
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.config_entries.async_reload(entry.entry_id)


def _json_safe(value: Any) -> Any:
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


def _conf_source_entities(conf: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for bucket in (CONF_SOURCES, CONF_CONTROLS, CONF_METADATA_SOURCES):
        for b in conf.get(bucket, []) or []:
            if isinstance(b, dict) and b.get("entity"):
                out.append(str(b["entity"]))
    return out


def _source_warnings(conf: dict[str, Any], profile: str) -> list[str]:
    own = _own_prefixes(profile)
    out: list[str] = []
    for eid in _conf_source_entities(conf):
        category = classify_source_entity(eid, own_prefixes=own)
        if category:
            out.append(source_warning_text(category, eid))
    return out


def _device_sensor_entity_id(profile: str, slug: str) -> str:
    return f"sensor.{device_object_id_prefix(profile)}{slug}"


def _consumed_by_index(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for coord in combined_coordinators_for_entry(hass, entry).values():
        for src in coord.config.sources:
            if src.entity:
                index.setdefault(src.entity, []).append(coord.slug)
    return index


# ── STATUS ───────────────────────────────────────────────────────────────────


def _status(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    profile = entry_profile(entry)
    coord_by_slug = {c.slug: c for c in all_coordinators(hass)}
    consumed_by = _consumed_by_index(hass, entry)

    devices = []
    for slug, conf in _devices(entry).items():
        coord = coord_by_slug.get(slug)
        result = coord.data if coord else None
        attrs = _json_safe(coord.main_attributes) if coord else {}
        sensor_id = _device_sensor_entity_id(profile, slug)
        devices.append({
            "slug": slug,
            "config": {**conf, CONF_SLUG: slug},
            "atomic_class": conf.get(CONF_ATOMIC_CLASS),
            "variant": conf.get(CONF_VARIANT),
            "entity_id": sensor_id,
            "state": result.state if result else None,
            "attrs": attrs,
            "warnings": _source_warnings(conf, profile),
            "consumed_by": consumed_by.get(sensor_id, []),
        })

    combineds = []
    for slug, coord in combined_coordinators_for_entry(hass, entry).items():
        result = coord.data
        derived = [{
            "slug": d.slug, "name": d.name, "device_class": d.device_class,
            "state": coord.derived_state(d),
            "entity_id": f"binary_sensor.{combined_object_id_prefix(profile)}{slug}_{d.slug}",
        } for d in coord.config.derived]
        combineds.append({
            "slug": slug, "display_name": coord.config.display_name,
            "entity_id": f"sensor.{combined_object_id_prefix(profile)}{slug}",
            "state": result.state if result else None,
            "output_type": coord.config.output_type,
            "config": _combineds(entry).get(slug, {}),
            "attrs": _json_safe(coord.attributes), "derived": derived,
        })

    groups = []
    for slug, conf in _groups(entry).items():
        members = [m for m in conf.get(CONF_GROUP_MEMBERS, []) if isinstance(m, str)]
        on = [m for m in members if (s := hass.states.get(m)) is not None and s.state == "on"]
        groups.append({
            "slug": slug, "display_name": conf.get(CONF_DISPLAY_NAME, slug),
            "members": members, "state": "on" if on else "off",
            "attrs": {"members": members, "entity_id": members, "member_count": len(members), "on_count": len(on), "any_on": bool(on)},
        })

    return {
        "profile": entry.data.get(CONF_PROFILE, DEFAULT_PROFILE),
        "profile_label": PROFILE_LABELS.get(entry.data.get(CONF_PROFILE, DEFAULT_PROFILE), profile),
        "entry_id": entry.entry_id,
        "devices": devices, "combineds": combineds, "groups": groups,
    }


# ── KATALOG ──────────────────────────────────────────────────────────────────


def _catalog() -> dict[str, Any]:
    return {
        "atomic_classes": [{
            "value": spec.atomic_class,
            "label": spec.label or spec.atomic_class,
            "icon": spec.icon,
            "variants": list(spec.variants),
            "power_model": spec.power_model,
            "integration_roles": list(spec.integration_roles),
            "state_role": spec.state_role,
            "required_roles": list(spec.required_roles),
            "required_mode": spec.required_mode,
            "default_roles": list(spec.default_roles or spec.required_roles),
            "optional_roles": list(spec.optional_roles),
            "control_roles": list(spec.control_roles),
            "metadata_override_roles": list(spec.metadata_override_roles),
            "role_domain_overrides": {k: list(v) for k, v in spec.role_domain_overrides.items()},
            "extra_attributes": list(spec.extra_attributes),
            "fail_safe": spec.fail_safe,
            "beta": spec.beta,
        } for spec in ATOMIC_CLASSES.values()],
        "role_catalog": {key: {
            "key": spec.key, "domains": list(spec.domains), "bucket": spec.bucket,
            "compute_relevant": spec.compute_relevant, "kind": spec.kind, "label": spec.label,
            "derive_attr": spec.derive_attr,
        } for key, spec in ROLE_CATALOG.items()},
        "fail_safe_choices": list(FAIL_SAFE_CHOICES),
        "availability_rules": [AVAILABILITY_ANY_REQUIRED_OR_ANY_SOURCE],
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


# ── DEVICE-CONF aus Message (v2) ─────────────────────────────────────────────


def _clean_bindings(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in raw or []:
        if not isinstance(b, dict):
            continue
        role = str(b.get("role") or "").strip()
        if not role:
            continue
        entry: dict[str, Any] = {"role": role}
        if b.get("entity"):
            entry["entity"] = str(b["entity"])
        if b.get("value"):
            entry["value"] = str(b["value"])
        if b.get("required"):
            entry["required"] = True
        out.append(entry)
    return out


def _device_conf_from_msg(msg: dict[str, Any], existing: set[str]) -> tuple[str, dict[str, Any]]:
    atomic_class = str(msg.get(CONF_ATOMIC_CLASS) or "").strip()
    if atomic_class not in ATOMIC_CLASSES:
        raise ValueError(f"unbekannte atomic_class {atomic_class!r}")
    spec = ATOMIC_CLASSES[atomic_class]
    display_name = str(msg.get(CONF_DISPLAY_NAME) or "").strip()
    if not display_name:
        raise ValueError("display_name is required")
    variant = str(msg.get(CONF_VARIANT) or (spec.variants[0] if spec.variants else "")).strip()
    diagnostics = {
        CONF_FAIL_SAFE: str(msg.get(CONF_FAIL_SAFE) or spec.fail_safe),
        CONF_AVAILABILITY_RULE: str(msg.get(CONF_AVAILABILITY_RULE) or AVAILABILITY_ANY_REQUIRED_OR_ANY_SOURCE),
    }
    conf: dict[str, Any] = {
        CONF_ATOMIC_CLASS: atomic_class,
        CONF_VARIANT: variant,
        CONF_DISPLAY_NAME: display_name,
        CONF_SOURCES: _clean_bindings(msg.get(CONF_SOURCES)),
        CONF_CONTROLS: _clean_bindings(msg.get(CONF_CONTROLS)),
        CONF_METADATA_SOURCES: _clean_bindings(msg.get(CONF_METADATA_SOURCES)),
        CONF_DIAGNOSTICS: diagnostics,
        CONF_WATT_THRESHOLD_ON: msg.get(CONF_WATT_THRESHOLD_ON, DEFAULT_WATT_THRESHOLD_ON),
        CONF_STICKY_HOLD_SECONDS: msg.get(CONF_STICKY_HOLD_SECONDS, DEFAULT_STICKY_HOLD_SECONDS),
        CONF_EXPOSE_SECONDARY_SENSORS: bool(msg.get(CONF_EXPOSE_SECONDARY_SENSORS, DEFAULT_EXPOSE_SECONDARY_SENSORS)),
    }
    if isinstance(msg.get(CONF_WATT_BUCKETS), list):
        conf[CONF_WATT_BUCKETS] = msg[CONF_WATT_BUCKETS]
    requested = str(msg.get(CONF_SLUG) or "").strip().lower()
    slug = requested or unique_slug(slugify(display_name) or "device", existing)
    return slug, conf


# ── BULK-IMPORT + DRY-RUN ────────────────────────────────────────────────────


def _normalize_combineds(raw: Any) -> dict[str, dict[str, Any]]:
    """Akzeptiert combineds als Dict {slug: conf} (Export-Format) oder Liste."""
    out: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for slug, conf in raw.items():
            if isinstance(conf, dict):
                out[str(slug)] = dict(conf)
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            slug = str(item.get(CONF_SLUG) or slugify(str(item.get(CONF_DISPLAY_NAME, "")))).strip()
            if not slug:
                continue
            if isinstance(item.get("config"), dict):
                conf = dict(item["config"])
                if item.get(CONF_DISPLAY_NAME):
                    conf[CONF_DISPLAY_NAME] = item[CONF_DISPLAY_NAME]
            else:
                conf = {k: v for k, v in item.items() if k != CONF_SLUG}
            out[slug] = conf
    return out


def _parse_bulk(
    raw: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    parsed = yaml.safe_load(raw) if raw and raw.strip() else None
    if isinstance(parsed, dict):
        devices = parsed.get(CONF_DEVICES, [])
        groups = parsed.get(CONF_LIGHT_GROUPS, {})
        combineds_raw = parsed.get(CONF_COMBINEDS, {})
    else:
        devices = parsed
        groups = {}
        combineds_raw = {}
    valid: list[dict[str, Any]] = []
    if devices:  # Geräte sind optional, wenn nur Combineds importiert werden.
        if isinstance(devices, list):
            for item in devices:
                if isinstance(item, dict) and not item.get(CONF_SLUG):
                    derived = slugify(str(item.get(CONF_DISPLAY_NAME, "")))
                    if derived:
                        item[CONF_SLUG] = derived
        valid, errors = validate_import_payload(devices)
        if errors:
            raise ValueError("\n".join(errors))
    combineds = _normalize_combineds(combineds_raw)
    return valid, (groups if isinstance(groups, dict) else {}), combineds


def _import_report(valid: list[dict[str, Any]], profile: str) -> list[dict[str, Any]]:
    own = _own_prefixes(profile)
    report: list[dict[str, Any]] = []
    for d in valid:
        slug = str(d.get(CONF_SLUG))
        cfg = parse_device_config(slug, d)
        missing = cfg.missing_required() if cfg else ["<invalid>"]
        derived_sources = []
        for eid in _conf_source_entities(d):
            cat = classify_source_entity(eid, own_prefixes=own)
            if cat:
                derived_sources.append(source_warning_text(cat, eid))
        report.append({
            "slug": slug,
            "atomic_class": d.get(CONF_ATOMIC_CLASS),
            "variant": d.get(CONF_VARIANT),
            "entity_id": _device_sensor_entity_id(profile, slug),
            "missing_required": missing,
            "derived_sources": derived_sources,
            "accepted": not derived_sources,
        })
    return report


def _combined_report(combineds: dict[str, dict[str, Any]], profile: str) -> list[dict[str, Any]]:
    from .combined import parse_combined

    own = _own_prefixes(profile)
    rep: list[dict[str, Any]] = []
    for slug, conf in combineds.items():
        cfg = parse_combined(slug, conf)
        n = len(cfg.sources) if cfg else 0
        derived_sources = []
        for src in (cfg.sources if cfg else []):
            if src.entity:
                cat = classify_source_entity(src.entity, own_prefixes=own)
                if cat:
                    derived_sources.append(source_warning_text(cat, src.entity))
        rep.append({
            "slug": slug,
            "output_type": cfg.output_type if cfg else "?",
            "sources": n,
            "entity_id": f"sensor.{combined_object_id_prefix(profile)}{slug}",
            "derived_sources": derived_sources,
            "accepted": cfg is not None and not derived_sources,
        })
    return rep


def _apply_bulk(
    entry: ConfigEntry,
    valid: list[dict[str, Any]],
    imported_groups: dict[str, Any],
    imported_combineds: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    devices = _devices(entry)
    for item in valid:
        slug = str(item.pop(CONF_SLUG))
        devices[slug] = item
    groups = {**_groups(entry), **imported_groups}
    combineds = {**_combineds(entry), **imported_combineds}
    return devices, groups, combineds


def _export_yaml(entry: ConfigEntry) -> str:
    payload = {
        CONF_DEVICES: [{CONF_SLUG: slug, **conf} for slug, conf in _devices(entry).items()],
        CONF_COMBINEDS: _combineds(entry),
        CONF_LIGHT_GROUPS: _groups(entry),
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


# ── REGISTRATION ─────────────────────────────────────────────────────────────


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
        cat = _catalog()
        try:
            from homeassistant.loader import async_get_integration

            integration = await async_get_integration(hass, DOMAIN)
            cat["version"] = str(integration.version)
        except Exception:  # noqa: BLE001
            cat["version"] = "?"
        connection.send_result(msg["id"], cat)

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_DEVICE,
        vol.Optional(CONF_SLUG): str,
        vol.Optional(CONF_ATOMIC_CLASS): str,
        vol.Optional(CONF_VARIANT): str,
        vol.Optional(CONF_DISPLAY_NAME): str,
        vol.Optional(CONF_SOURCES): list,
        vol.Optional(CONF_CONTROLS): list,
        vol.Optional(CONF_METADATA_SOURCES): list,
        vol.Optional(CONF_FAIL_SAFE): str,
        vol.Optional(CONF_AVAILABILITY_RULE): str,
        vol.Optional(CONF_WATT_THRESHOLD_ON): vol.Any(int, float, str),
        vol.Optional(CONF_STICKY_HOLD_SECONDS): vol.Any(int, float, str),
        vol.Optional(CONF_EXPOSE_SECONDARY_SENSORS): bool,
        vol.Optional(CONF_WATT_BUCKETS): list,
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
        connection.send_result(msg["id"], {"slug": slug, "config": conf, "warnings": warnings})

    @websocket_api.websocket_command({vol.Required("type"): WS_REMOVE_DEVICE, vol.Required(CONF_SLUG): str})
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
        slug = str(msg.get(CONF_SLUG) or "").strip().lower() or unique_slug(slugify(display_name) or "combined", set(combineds))
        conf = dict(msg["config"])
        conf[CONF_DISPLAY_NAME] = display_name
        combineds[slug] = conf
        await _update_options(hass, entry, {**entry.options, CONF_COMBINEDS: combineds})
        connection.send_result(msg["id"], {"slug": slug})

    @websocket_api.websocket_command({vol.Required("type"): WS_REMOVE_COMBINED, vol.Required(CONF_SLUG): str})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_remove_combined(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        combineds = _combineds(entry)
        combineds.pop(msg[CONF_SLUG], None)
        await _update_options(hass, entry, {**entry.options, CONF_COMBINEDS: combineds})
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
        slug = str(msg.get(CONF_SLUG) or "").strip().lower() or unique_slug(slugify(display_name) or "group", set(groups))
        groups[slug] = {CONF_DISPLAY_NAME: display_name, CONF_GROUP_MEMBERS: members}
        await _update_options(hass, entry, {**entry.options, CONF_LIGHT_GROUPS: groups})
        connection.send_result(msg["id"], {"slug": slug})

    @websocket_api.websocket_command({vol.Required("type"): WS_REMOVE_GROUP, vol.Required(CONF_SLUG): str})
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
            imported_devices, imported_groups, imported_combineds = _parse_bulk(msg["payload"])
        except (TypeError, ValueError, yaml.YAMLError) as err:
            connection.send_error(msg["id"], "invalid_bulk", str(err))
            return
        profile = entry_profile(entry)
        report = _import_report(imported_devices, profile)
        combined_report = _combined_report(imported_combineds, profile)
        if msg.get("dry_run"):
            connection.send_result(msg["id"], {
                "dry_run": True,
                "devices": len(imported_devices),
                "groups": len(imported_groups),
                "combineds": len(imported_combineds),
                "report": report,
                "combined_report": combined_report,
            })
            return
        devices, groups, combineds = _apply_bulk(
            entry, imported_devices, imported_groups, imported_combineds
        )
        await _update_options(hass, entry, {
            **entry.options,
            CONF_DEVICES: devices,
            CONF_LIGHT_GROUPS: groups,
            CONF_COMBINEDS: combineds,
        })
        connection.send_result(msg["id"], {
            "dry_run": False,
            "devices": len(devices),
            "groups": len(groups),
            "combineds": len(combineds),
            "report": report,
            "combined_report": combined_report,
        })

    @websocket_api.websocket_command({vol.Required("type"): WS_EXPORT_CONFIG})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_export_config(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        connection.send_result(msg["id"], {"yaml": _export_yaml(entry)})

    @websocket_api.websocket_command({vol.Required("type"): WS_AGENT_SPEC})
    @websocket_api.async_response
    async def ws_agent_spec(hass, connection, msg) -> None:
        from .agent_spec import build_briefing, build_json_schema

        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        version = "?"
        try:
            from homeassistant.loader import async_get_integration

            version = str((await async_get_integration(hass, DOMAIN)).version)
        except Exception:  # noqa: BLE001
            pass
        profile = entry_profile(entry)
        connection.send_result(msg["id"], {
            "version": version,
            "markdown": build_briefing(version, profile, _export_yaml(entry)),
            "json_schema": build_json_schema(),
        })

    for cmd in (ws_get_status, ws_get_catalog, ws_set_device, ws_remove_device,
                ws_set_combined, ws_remove_combined, ws_set_group, ws_remove_group,
                ws_bulk_import, ws_export_config, ws_agent_spec):
        websocket_api.async_register_command(hass, cmd)
