"""Read-only raw Home Assistant entity catalog helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .const import (
    CONF_CONTROLS,
    CONF_ENTITY,
    CONF_METADATA_SOURCES,
    CONF_SOURCES,
    combined_object_id_prefix,
    device_object_id_prefix,
    master_object_id_prefix,
)

UNAVAILABLE_STATES = frozenset({"unknown", "unavailable", ""})


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _state_value(state: Any, key: str, fallback: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(key, fallback)
    return getattr(state, key, fallback)


def _state_entity_id(state: Any) -> str | None:
    entity_id = _state_value(state, "entity_id")
    return str(entity_id) if entity_id else None


def _state_attributes(state: Any) -> dict[str, Any]:
    return _as_dict(_state_value(state, "attributes", {}))


def _source_bindings(conf: dict[str, Any], *, include_device_buckets: bool = False) -> list[dict[str, Any]]:
    buckets = (CONF_SOURCES, CONF_CONTROLS, CONF_METADATA_SOURCES) if include_device_buckets else (CONF_SOURCES,)
    bindings: list[dict[str, Any]] = []
    for bucket in buckets:
        for item in conf.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            entity = item.get(CONF_ENTITY)
            if not entity:
                continue
            role = str(item.get("role") or item.get("key") or "").strip()
            key = str(item.get("key") or role).strip()
            bindings.append(
                {
                    "entity": str(entity),
                    "role": role or None,
                    "key": key or None,
                    "bucket": bucket,
                }
            )
    return bindings


def build_used_by_contracts(
    profile: str,
    *,
    masters: dict[str, dict[str, Any]] | None = None,
    combineds: dict[str, dict[str, Any]] | None = None,
    devices: dict[str, dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Map raw entity IDs to read-only contract/source references."""
    used_by: dict[str, list[dict[str, Any]]] = {}

    def add(entity_id: str, entry: dict[str, Any]) -> None:
        used_by.setdefault(entity_id, []).append(entry)

    for slug, conf in (masters or {}).items():
        if not isinstance(conf, dict):
            continue
        contract_entity_id = f"sensor.{master_object_id_prefix(profile)}{slug}"
        for source in _source_bindings(conf):
            add(
                source["entity"],
                {
                    "contract_entity_id": contract_entity_id,
                    "contract_kind": "master",
                    "slug": str(slug),
                    "role": source["role"],
                    "key": source["key"],
                },
            )
    for slug, conf in (combineds or {}).items():
        if not isinstance(conf, dict):
            continue
        contract_entity_id = f"sensor.{combined_object_id_prefix(profile)}{slug}"
        for source in _source_bindings(conf):
            add(
                source["entity"],
                {
                    "contract_entity_id": contract_entity_id,
                    "contract_kind": "legacy_combined",
                    "slug": str(slug),
                    "role": source["role"],
                    "key": source["key"],
                },
            )
    for slug, conf in (devices or {}).items():
        if not isinstance(conf, dict):
            continue
        contract_entity_id = f"sensor.{device_object_id_prefix(profile)}{slug}"
        for source in _source_bindings(conf, include_device_buckets=True):
            add(
                source["entity"],
                {
                    "contract_entity_id": contract_entity_id,
                    "contract_kind": "legacy_device",
                    "slug": str(slug),
                    "role": source["role"],
                    "key": source["key"],
                },
            )
    return used_by


def candidate_roles_for_entity(entity_id: str, attrs: dict[str, Any]) -> list[str]:
    """Return conservative best-effort source role suggestions."""
    domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
    device_class = str(attrs.get("device_class") or "").lower()
    state_class = str(attrs.get("state_class") or "").lower()
    unit = str(attrs.get("unit_of_measurement") or "").lower()
    roles: list[str] = []

    def add(role: str) -> None:
        if role not in roles:
            roles.append(role)

    if domain == "sensor" and (
        device_class == "power"
        or unit in {"w", "kw"}
        or "power" in entity_id.lower()
    ):
        add("power_meter")
    if domain == "media_player":
        add("media_player")
    if domain == "binary_sensor" and device_class in {
        "opening",
        "window",
        "door",
        "garage_door",
    }:
        add("opening_contact")
    if domain == "switch":
        add("switch_actuator")
    if domain == "cover":
        add("cover")
    if domain == "climate":
        add("climate")
    if domain == "weather":
        add("weather")
    if domain == "sensor" and device_class == "temperature":
        add("temperature")
    if domain == "sensor" and device_class == "humidity":
        add("humidity")
    if domain == "sensor" and device_class == "energy":
        add("energy_meter")
    if domain == "sensor" and state_class == "measurement" and not roles:
        add("measurement")
    return roles


def raw_entity_entry(
    state: Any,
    *,
    registry_meta: dict[str, Any] | None = None,
    used_by_contracts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    entity_id = _state_entity_id(state)
    if not entity_id:
        return None
    attrs = _state_attributes(state)
    registry_meta = registry_meta or {}
    state_text = str(_state_value(state, "state", ""))
    return {
        "entity_id": entity_id,
        "domain": entity_id.split(".", 1)[0] if "." in entity_id else None,
        "state": state_text,
        "available": state_text not in UNAVAILABLE_STATES,
        "device_class": attrs.get("device_class"),
        "state_class": attrs.get("state_class"),
        "unit_of_measurement": attrs.get("unit_of_measurement"),
        "friendly_name": attrs.get("friendly_name"),
        "area_id": registry_meta.get("area_id"),
        "area_name": registry_meta.get("area_name"),
        "device_id": registry_meta.get("device_id"),
        "device_name": registry_meta.get("device_name"),
        "platform": registry_meta.get("platform"),
        "integration": registry_meta.get("integration") or registry_meta.get("platform"),
        "last_changed": _as_iso(_state_value(state, "last_changed")),
        "last_updated": _as_iso(_state_value(state, "last_updated")),
        "used_by_contracts": used_by_contracts or [],
        "candidate_roles": candidate_roles_for_entity(entity_id, attrs),
    }


def _matches_search(entity: dict[str, Any], search: str) -> bool:
    haystack = " ".join(
        str(entity.get(key) or "")
        for key in ("entity_id", "friendly_name", "device_name", "area_name", "platform")
    ).lower()
    return search.lower() in haystack


def build_raw_entity_catalog(
    states: list[Any] | tuple[Any, ...],
    *,
    registry_meta: dict[str, dict[str, Any]] | None = None,
    used_by_contracts: dict[str, list[dict[str, Any]]] | None = None,
    domain: str | list[str] | tuple[str, ...] | None = None,
    search: str | None = None,
    only_available: bool = False,
) -> dict[str, Any]:
    """Build a read-only raw HA entity catalog from a state snapshot."""
    registry_meta = registry_meta or {}
    used_by_contracts = used_by_contracts or {}
    if isinstance(domain, str):
        domains = {domain}
    elif isinstance(domain, (list, tuple)):
        domains = {str(item) for item in domain if item}
    else:
        domains = set()

    entities: list[dict[str, Any]] = []
    for state in states or []:
        entity_id = _state_entity_id(state)
        if not entity_id:
            continue
        item = raw_entity_entry(
            state,
            registry_meta=registry_meta.get(entity_id),
            used_by_contracts=used_by_contracts.get(entity_id, []),
        )
        if item is None:
            continue
        if domains and item["domain"] not in domains:
            continue
        if only_available and not item["available"]:
            continue
        if search and not _matches_search(item, search):
            continue
        entities.append(item)
    entities.sort(key=lambda item: str(item["entity_id"]))
    return {
        "version": 1,
        "entities": entities,
        "summary": {
            "entities": len(entities),
            "used": sum(1 for item in entities if item["used_by_contracts"]),
        },
        "filters": {
            "domain": sorted(domains),
            "search": search or None,
            "only_available": bool(only_available),
        },
    }
