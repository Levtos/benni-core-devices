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
    CONF_ATTRIBUTE,
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
    CONF_MASTERS,
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
    WS_GET_CONTRACT_CATALOG,
    WS_GET_RAW_ENTITY_CATALOG,
    WS_GET_STATUS,
    WS_AGENT_SPEC,
    WS_REMOVE_COMBINED,
    WS_REMOVE_DEVICE,
    WS_REMOVE_GROUP,
    WS_SET_COMBINED,
    WS_SET_DEVICE,
    WS_SET_GROUP,
    combined_object_id_prefix,
    entry_profile,
    master_object_id_prefix,
)
from .contract_catalog import build_contract_catalog
from .coordinator import all_coordinators, combined_coordinators_for_entry, master_coordinators_for_entry
from .raw_entity_catalog import build_raw_entity_catalog, build_used_by_contracts
from .bulk_import import (
    apply_bulk,
    combined_derived_binary_sensor_entity_id,
    combined_report,
    combineds_from_options,
    devices_from_options,
    device_sensor_entity_id,
    export_yaml_from_options,
    groups_from_options,
    IMPORT_SOURCE_PAYLOAD,
    import_report,
    import_source_report,
    import_start_published_outputs,
    import_summary,
    masters_from_options,
    parse_bulk_payload,
    published_output_entity_ids,
    rollback_recommendation,
    source_warnings,
)
from .device_types import (
    ATOMIC_CLASSES,
    ROLE_CATALOG,
    slugify,
    unique_slug,
)


def _entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _devices(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    return devices_from_options(entry.options)


def _groups(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    return groups_from_options(entry.options)


def _combineds(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    return combineds_from_options(entry.options)


def _masters(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    return masters_from_options(entry.options)


async def _update_options(hass: HomeAssistant, entry: ConfigEntry, options: dict[str, Any]) -> None:
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.config_entries.async_reload(entry.entry_id)


async def _integration_version(hass: HomeAssistant) -> str | None:
    try:
        from homeassistant.loader import async_get_integration

        return str((await async_get_integration(hass, DOMAIN)).version)
    except Exception:  # noqa: BLE001
        return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _published_outputs(entry: ConfigEntry) -> set[str]:
    profile = entry_profile(entry)
    return published_output_entity_ids(
        profile,
        _devices(entry),
        _combineds(entry),
        _groups(entry),
        _masters(entry),
    )


def _source_warnings(
    conf: dict[str, Any],
    profile: str,
    published_outputs: set[str] | frozenset[str] | None = None,
) -> list[str]:
    return source_warnings(conf, profile, published_outputs)


def _device_sensor_entity_id(profile: str, slug: str) -> str:
    return device_sensor_entity_id(profile, slug)


def _consumed_by_index(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for coord in [
        *combined_coordinators_for_entry(hass, entry).values(),
        *master_coordinators_for_entry(hass, entry).values(),
    ]:
        for src in coord.config.sources:
            if src.entity:
                index.setdefault(src.entity, []).append(coord.slug)
    return index


# ── STATUS ───────────────────────────────────────────────────────────────────


def _status(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    profile = entry_profile(entry)
    coord_by_slug = {c.slug: c for c in all_coordinators(hass)}
    consumed_by = _consumed_by_index(hass, entry)
    published_outputs = _published_outputs(entry)

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
            "warnings": _source_warnings(conf, profile, published_outputs),
            "consumed_by": consumed_by.get(sensor_id, []),
        })

    combineds = []
    for slug, coord in combined_coordinators_for_entry(hass, entry).items():
        result = coord.data
        derived = [{
            "slug": d.slug, "name": d.name, "object_id": d.object_id,
            "device_class": d.device_class,
            "state": coord.derived_state(d),
            "entity_id": combined_derived_binary_sensor_entity_id(profile, slug, d),
        } for d in coord.config.derived]
        combineds.append({
            "slug": slug, "display_name": coord.config.display_name,
            "entity_id": f"sensor.{combined_object_id_prefix(profile)}{slug}",
            "state": result.state if result else None,
            "output_type": coord.config.output_type,
            "config": _combineds(entry).get(slug, {}),
            "attrs": _json_safe(coord.attributes), "derived": derived,
        })

    masters = []
    for slug, coord in master_coordinators_for_entry(hass, entry).items():
        result = coord.data
        derived = [{
            "slug": d.slug, "name": d.name, "object_id": d.object_id,
            "device_class": d.device_class,
            "state": coord.derived_state(d),
            "entity_id": combined_derived_binary_sensor_entity_id(profile, slug, d, master=True),
        } for d in coord.config.derived]
        masters.append({
            "slug": slug, "display_name": coord.config.display_name,
            "entity_id": f"sensor.{master_object_id_prefix(profile)}{slug}",
            "state": result.state if result else None,
            "output_type": coord.config.output_type,
            "config": _masters(entry).get(slug, {}),
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
        "devices": devices, "combineds": combineds, "masters": masters, "groups": groups,
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
            "v1": {
                "functions": ["min", "max", "abs", "round(x[,n])", "clamp(x,lo,hi)", "any([...])", "all([...])", "not(x)"],
                "operators": ["+ - * /", "== != < <= > >=", "and or not"],
                "refs": "${source_key} | ${derived_name} | ${self}",
                "fail_safe": ["off", "open", "hold_last", "unknown"],
                "nodes": [
                    {"kind": "expr", "desc": "Zahl aus Formel", "example": {"name": "dew", "kind": "expr", "expr": "round(${t} - (100 - ${rh})/5, 1)"}},
                    {"kind": "gate", "desc": "Boolean aus Logik", "example": {"name": "unsafe", "kind": "gate", "expr": "any([${any_open}, ${any_tilt}])"}},
                    {"kind": "enum", "desc": "String/Enum aus geordneten Fällen", "example": {"name": "room", "kind": "enum", "cases": [{"when": "${open_a} == \"on\"", "output": "open"}], "default": "closed"}},
                    {"kind": "health", "desc": "ok|degraded|problem aus Atomic-Quellen", "example": {"name": "h", "kind": "health", "atomics": ["src_a", "src_b"]}},
                    {"kind": "latch", "desc": "Schmitt-Latch (set/reset, hält dazwischen)", "example": {"name": "dark", "kind": "latch", "set": "${lux} < 50", "reset": "${lux} >= 100", "fail_safe": "off"}},
                    {"kind": "previous", "desc": "eigener letzter Output via ${self}", "example": {"name": "prev", "kind": "previous"}},
                ],
                "note": "derived_values[] werden vor den first-match rules ausgewertet; rules/output dürfen ${derived} und ${self} referenzieren. Output kann '${name}' sein. Setze expose:true am Knoten oder top-level exposed_attributes:[name], um ausgewählte Knoten als flache Sensor-Attribute zu veröffentlichen. enum.cases sind first-match-wins. since/Timer = v1.1 (abgelehnt).",
            },
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
        if b.get(CONF_ATTRIBUTE):
            entry[CONF_ATTRIBUTE] = str(b[CONF_ATTRIBUTE])
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


async def run_bulk_import(
    hass: HomeAssistant,
    entry: ConfigEntry,
    payload: str,
    dry_run: bool,
    replace: bool = False,
    *,
    source_type: str = IMPORT_SOURCE_PAYLOAD,
    source_path: str | None = None,
    source_display_path: str | None = None,
) -> dict[str, Any]:
    """Geteilte Bulk-Import-Logik für WS-Command UND HA-Service (MCP-fähig).

    Raises ValueError/yaml.YAMLError bei ungültigem Payload.
    """
    valid, imported_groups, imported_combineds, imported_masters, removals = parse_bulk_payload(payload)
    profile = entry_profile(entry)
    published_outputs = import_start_published_outputs(
        entry.options, valid, imported_groups, imported_masters, profile, replace, removals
    )
    report = import_report(valid, profile, published_outputs)
    c_report = combined_report(imported_combineds, profile, published_outputs)
    m_report = combined_report(imported_masters, profile, published_outputs, master=True)
    summary = import_summary(
        valid,
        imported_groups,
        imported_combineds,
        imported_masters,
        removals,
    )
    base = {
        "report": report,
        "combined_report": c_report,
        "master_report": m_report,
        "combineds_in": len(imported_combineds),
        "masters_in": len(imported_masters),
        "removed": removals,
        "summary": summary,
        "source": import_source_report(
            payload,
            source_type,
            path=source_path,
            display_path=source_display_path,
        ),
        "integration_version": await _integration_version(hass),
        "rollback_recommendation": rollback_recommendation(replace),
    }
    if dry_run:
        return {
            "dry_run": True, "replace": replace,
            "devices": len(valid), "groups": len(imported_groups),
            "combineds": len(imported_combineds), "masters": len(imported_masters), **base,
        }
    devices, groups, combineds, masters = apply_bulk(
        entry.options,
        valid,
        imported_groups,
        imported_combineds,
        imported_masters,
        removals,
        replace,
    )
    await _update_options(hass, entry, {
        **entry.options,
        CONF_DEVICES: devices,
        CONF_LIGHT_GROUPS: groups,
        CONF_COMBINEDS: combineds,
        CONF_MASTERS: masters,
    })
    apply_summary = {
        **summary,
        "resulting": {
            "devices": len(devices),
            "groups": len(groups),
            "combineds": len(combineds),
            "masters": len(masters),
        },
    }
    return {
        "dry_run": False, "replace": replace,
        "devices": len(devices), "groups": len(groups),
        "combineds": len(combineds), "masters": len(masters),
        **base, "summary": apply_summary,
    }


def _contract_catalog(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    include_raw_config: bool = False,
) -> dict[str, Any]:
    profile = entry_profile(entry)
    return build_contract_catalog(
        profile,
        masters=_masters(entry),
        combineds=_combineds(entry),
        devices=_devices(entry),
        runtime_status=_status(hass, entry),
        include_raw_config=include_raw_config,
    )


def _state_registry_meta(hass: HomeAssistant, states: list[Any]) -> dict[str, dict[str, Any]]:
    """Best-effort registry metadata for the current HA state snapshot."""
    try:
        from homeassistant.helpers import area_registry as ar
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)
        area_reg = ar.async_get(hass)
    except Exception:  # noqa: BLE001
        return {}

    meta: dict[str, dict[str, Any]] = {}
    for state in states:
        entity_id = state.entity_id
        area_id = None
        device_id = None
        device_name = None
        platform = None
        area_name = None
        try:
            entity_entry = ent_reg.async_get(entity_id)
        except Exception:  # noqa: BLE001
            entity_entry = None
        if entity_entry is not None:
            area_id = getattr(entity_entry, "area_id", None)
            device_id = getattr(entity_entry, "device_id", None)
            platform = getattr(entity_entry, "platform", None)
        try:
            device = dev_reg.async_get(device_id) if device_id else None
        except Exception:  # noqa: BLE001
            device = None
        if device is not None:
            area_id = area_id or getattr(device, "area_id", None)
            device_name = getattr(device, "name_by_user", None) or getattr(device, "name", None)
        try:
            area = area_reg.async_get_area(area_id) if area_id else None
            area_name = getattr(area, "name", None) if area is not None else None
        except Exception:  # noqa: BLE001
            area_name = None
        meta[entity_id] = {
            "area_id": area_id,
            "area_name": area_name,
            "device_id": device_id,
            "device_name": device_name,
            "platform": platform,
            "integration": platform,
        }
    return meta


def _raw_entity_catalog(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    domain: str | list[str] | None = None,
    search: str | None = None,
    only_available: bool = False,
) -> dict[str, Any]:
    profile = entry_profile(entry)
    states = list(hass.states.async_all())
    used_by = build_used_by_contracts(
        profile,
        masters=_masters(entry),
        combineds=_combineds(entry),
        devices=_devices(entry),
    )
    return build_raw_entity_catalog(
        states,
        registry_meta=_state_registry_meta(hass, states),
        used_by_contracts=used_by,
        domain=domain,
        search=search,
        only_available=only_available,
    )


def _export_yaml(entry: ConfigEntry) -> str:
    return export_yaml_from_options(entry.options)


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
        vol.Required("type"): WS_GET_CONTRACT_CATALOG,
        vol.Optional("include_raw_config"): bool,
    })
    @websocket_api.async_response
    async def ws_get_contract_catalog(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        connection.send_result(
            msg["id"],
            _contract_catalog(
                hass,
                entry,
                include_raw_config=bool(msg.get("include_raw_config")),
            ),
        )

    @websocket_api.websocket_command({
        vol.Required("type"): WS_GET_RAW_ENTITY_CATALOG,
        vol.Optional("domain"): vol.Any(str, [str]),
        vol.Optional("search"): str,
        vol.Optional("only_available"): bool,
    })
    @websocket_api.async_response
    async def ws_get_raw_entity_catalog(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        connection.send_result(
            msg["id"],
            _raw_entity_catalog(
                hass,
                entry,
                domain=msg.get("domain"),
                search=msg.get("search"),
                only_available=bool(msg.get("only_available")),
            ),
        )

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
        published_outputs = published_output_entity_ids(
            entry_profile(entry), devices, _combineds(entry), _groups(entry), _masters(entry)
        )
        warnings = _source_warnings(conf, entry_profile(entry), published_outputs)
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
        vol.Optional("replace"): bool,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_bulk_import(hass, connection, msg) -> None:
        entry = _entry(hass)
        if entry is None:
            connection.send_error(msg["id"], "not_ready", "Benni Core Devices not loaded")
            return
        try:
            result = await run_bulk_import(
                hass, entry, msg["payload"],
                bool(msg.get("dry_run")), bool(msg.get("replace")),
            )
        except (TypeError, ValueError, yaml.YAMLError) as err:
            connection.send_error(msg["id"], "invalid_bulk", str(err))
            return
        connection.send_result(msg["id"], result)

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

    for cmd in (ws_get_status, ws_get_catalog, ws_get_contract_catalog,
                ws_get_raw_entity_catalog,
                ws_set_device, ws_remove_device,
                ws_set_combined, ws_remove_combined, ws_set_group, ws_remove_group,
                ws_bulk_import, ws_export_config, ws_agent_spec):
        websocket_api.async_register_command(hass, cmd)
