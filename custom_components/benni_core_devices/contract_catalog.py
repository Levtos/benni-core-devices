"""Read-only contract catalog helpers for Core Devices v1 preparation."""

from __future__ import annotations

from typing import Any

from .combined import exposed_derived_names, parse_combined
from .const import (
    CONF_ATOMIC_CLASS,
    CONF_ATTRIBUTE,
    CONF_CONTROLS,
    CONF_DISPLAY_NAME,
    CONF_ENTITY,
    CONF_METADATA_SOURCES,
    CONF_REQUIRED,
    CONF_SOURCES,
    CONF_VARIANT,
    combined_object_id_prefix,
    device_object_id_prefix,
    master_object_id_prefix,
)

CONTRACT_KIND_DEVICE_MASTER = "device_master"
CONTRACT_KIND_DOMAIN_MASTER = "domain_master"
CONTRACT_KIND_FUSION_CONTEXT = "fusion_context"
CONTRACT_KIND_MIXED = "mixed"
CONTRACT_KIND_UNKNOWN = "unknown"
CONTRACT_KINDS = {
    CONTRACT_KIND_DEVICE_MASTER,
    CONTRACT_KIND_DOMAIN_MASTER,
    CONTRACT_KIND_FUSION_CONTEXT,
    CONTRACT_KIND_MIXED,
    CONTRACT_KIND_UNKNOWN,
}

MIGRATION_STATUS_TARGET = "target"
MIGRATION_STATUS_LEGACY_BRIDGE = "legacy_bridge"
MIGRATION_STATUS_RETIRE_CANDIDATE = "retire_candidate"
MIGRATION_STATUS_UNKNOWN = "unknown"
MIGRATION_STATUSES = {
    MIGRATION_STATUS_TARGET,
    MIGRATION_STATUS_LEGACY_BRIDGE,
    MIGRATION_STATUS_RETIRE_CANDIDATE,
    MIGRATION_STATUS_UNKNOWN,
}

_DEVICE_MASTER_SLUGS = frozenset({"tv", "denon", "appletv", "ps5", "switch", "pc"})
_DOMAIN_MASTER_SLUGS = frozenset({"household_plug"})
_MIXED_MASTER_SLUGS = frozenset({"living_rollo"})


def _clean_enum(value: Any, allowed: set[str], fallback: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else fallback


def infer_master_contract_kind(slug: str, conf: dict[str, Any]) -> str:
    """Return a conservative best-effort contract kind for a master."""
    configured = _clean_enum(conf.get("contract_kind"), CONTRACT_KINDS, "")
    if configured:
        return configured
    if slug in _DEVICE_MASTER_SLUGS:
        return CONTRACT_KIND_DEVICE_MASTER
    if slug in _DOMAIN_MASTER_SLUGS:
        return CONTRACT_KIND_DOMAIN_MASTER
    if slug in _MIXED_MASTER_SLUGS:
        return CONTRACT_KIND_MIXED
    return CONTRACT_KIND_UNKNOWN


def infer_master_migration_status(slug: str, conf: dict[str, Any]) -> str:
    """Return a conservative best-effort migration status for a master."""
    configured = _clean_enum(conf.get("migration_status"), MIGRATION_STATUSES, "")
    if configured:
        return configured
    if (
        slug in _DEVICE_MASTER_SLUGS
        or slug in _DOMAIN_MASTER_SLUGS
        or slug in _MIXED_MASTER_SLUGS
    ):
        return MIGRATION_STATUS_TARGET
    return MIGRATION_STATUS_UNKNOWN


def _combined_migration_status(slug: str, conf: dict[str, Any]) -> str:
    configured = _clean_enum(conf.get("migration_status"), MIGRATION_STATUSES, "")
    if configured:
        return configured
    if conf.get("retire_candidate") is True:
        return MIGRATION_STATUS_RETIRE_CANDIDATE
    if str(slug).startswith(("old_", "legacy_")):
        return MIGRATION_STATUS_RETIRE_CANDIDATE
    return MIGRATION_STATUS_LEGACY_BRIDGE


def _source_rows(conf: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in conf.get(CONF_SOURCES) or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or item.get("key") or "").strip()
        key = str(item.get("key") or role).strip()
        entity = item.get(CONF_ENTITY)
        required = bool(item.get(CONF_REQUIRED, True))
        row: dict[str, Any] = {
            "key": key,
            "role": role,
            "entity": str(entity) if entity else None,
            "required": required,
            "optional": not required,
        }
        if item.get(CONF_ATTRIBUTE):
            row[CONF_ATTRIBUTE] = str(item[CONF_ATTRIBUTE])
        rows.append(row)
    return rows


def _device_source_rows(conf: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in (CONF_SOURCES, CONF_CONTROLS, CONF_METADATA_SOURCES):
        for item in conf.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            if not role:
                continue
            entity = item.get(CONF_ENTITY)
            row: dict[str, Any] = {
                "key": role,
                "role": role,
                "entity": str(entity) if entity else None,
                "required": bool(item.get(CONF_REQUIRED, bucket == CONF_SOURCES)),
                "optional": not bool(item.get(CONF_REQUIRED, bucket == CONF_SOURCES)),
                "bucket": bucket,
            }
            if item.get(CONF_ATTRIBUTE):
                row[CONF_ATTRIBUTE] = str(item[CONF_ATTRIBUTE])
            rows.append(row)
    return rows


def _contract_refs(sources: list[dict[str, Any]], profile: str) -> list[str]:
    prefixes = (
        f"sensor.{master_object_id_prefix(profile)}",
        f"sensor.{combined_object_id_prefix(profile)}",
        f"sensor.{device_object_id_prefix(profile)}",
    )
    refs: list[str] = []
    for source in sources:
        entity = source.get("entity")
        if isinstance(entity, str) and entity.startswith(prefixes) and entity not in refs:
            refs.append(entity)
    return refs


def _legacy_aliases(conf: dict[str, Any]) -> list[str]:
    raw = conf.get("legacy_aliases") or conf.get("legacy_entities") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    return []


def _runtime_value(runtime: dict[str, Any], key: str, fallback: Any = None) -> Any:
    attrs = runtime.get("attrs")
    if isinstance(attrs, dict) and key in attrs:
        return attrs.get(key)
    return runtime.get(key, fallback)


def _runtime_degraded_reason(runtime: dict[str, Any]) -> list[str]:
    value = _runtime_value(runtime, "degraded_reason")
    if value is None:
        value = _runtime_value(runtime, "missing_sources")
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if value:
        return [str(value)]
    return []


def _runtime_list_count(runtime: dict[str, Any], key: str) -> int:
    value = _runtime_value(runtime, key)
    return len(value) if isinstance(value, list) else 0


def _runtime_by_slug(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if isinstance(item, dict) and item.get("slug"):
            out[str(item["slug"])] = item
    return out


def _attribute_count(conf: dict[str, Any]) -> int:
    cfg = parse_combined("_catalog", conf)
    if not cfg:
        return 0
    return len(exposed_derived_names(cfg))


def _master_entry(
    profile: str,
    slug: str,
    conf: dict[str, Any],
    runtime: dict[str, Any],
    *,
    include_raw_config: bool,
) -> dict[str, Any]:
    cfg = parse_combined(slug, conf)
    sources = _source_rows(conf)
    missing = _runtime_value(runtime, "missing_sources")
    if not isinstance(missing, list):
        missing = [
            source["key"] or source["role"]
            for source in sources
            if source.get("required") and not source.get("entity")
        ]
    item: dict[str, Any] = {
        "entity_id": runtime.get("entity_id") or f"sensor.{master_object_id_prefix(profile)}{slug}",
        "slug": slug,
        "display_name": conf.get(CONF_DISPLAY_NAME) or (cfg.display_name if cfg else slug),
        "contract_kind": infer_master_contract_kind(slug, conf),
        "migration_status": infer_master_migration_status(slug, conf),
        "source_count": len(sources),
        "required_source_count": sum(1 for source in sources if source.get("required")),
        "optional_source_count": sum(1 for source in sources if source.get("optional")),
        "missing_required_count": len(missing),
        "attribute_count": _attribute_count(conf),
        "source_quality": _runtime_value(runtime, "source_quality", "unknown"),
        "degraded": bool(_runtime_value(runtime, "degraded", False)),
        "degraded_reason": _runtime_degraded_reason(runtime),
        "sources": sources,
        "contract_refs": _contract_refs(sources, profile),
        "legacy_aliases": _legacy_aliases(conf),
    }
    if include_raw_config:
        item["raw_config"] = dict(conf)
    return item


def _combined_entry(
    profile: str,
    slug: str,
    conf: dict[str, Any],
    runtime: dict[str, Any],
    *,
    include_raw_config: bool,
) -> dict[str, Any]:
    cfg = parse_combined(slug, conf)
    sources = _source_rows(conf)
    item: dict[str, Any] = {
        "entity_id": runtime.get("entity_id") or f"sensor.{combined_object_id_prefix(profile)}{slug}",
        "slug": slug,
        "display_name": conf.get(CONF_DISPLAY_NAME) or (cfg.display_name if cfg else slug),
        "contract_kind": "legacy_combined",
        "migration_status": _combined_migration_status(slug, conf),
        "source_count": len(sources),
        "required_source_count": sum(1 for source in sources if source.get("required")),
        "optional_source_count": sum(1 for source in sources if source.get("optional")),
        "missing_required_count": _runtime_list_count(runtime, "missing_sources"),
        "attribute_count": _attribute_count(conf),
        "source_quality": _runtime_value(runtime, "source_quality", "unknown"),
        "degraded": bool(_runtime_value(runtime, "degraded", False)),
        "degraded_reason": _runtime_degraded_reason(runtime),
        "sources": sources,
        "contract_refs": _contract_refs(sources, profile),
        "legacy_aliases": _legacy_aliases(conf),
    }
    if include_raw_config:
        item["raw_config"] = dict(conf)
    return item


def _device_entry(
    profile: str,
    slug: str,
    conf: dict[str, Any],
    runtime: dict[str, Any],
    *,
    include_raw_config: bool,
) -> dict[str, Any]:
    sources = _device_source_rows(conf)
    item: dict[str, Any] = {
        "entity_id": runtime.get("entity_id") or f"sensor.{device_object_id_prefix(profile)}{slug}",
        "slug": slug,
        "display_name": conf.get(CONF_DISPLAY_NAME) or slug,
        "contract_kind": "legacy_device",
        "migration_status": MIGRATION_STATUS_LEGACY_BRIDGE,
        "atomic_class": conf.get(CONF_ATOMIC_CLASS),
        "variant": conf.get(CONF_VARIANT),
        "source_count": len(sources),
        "required_source_count": sum(1 for source in sources if source.get("required")),
        "optional_source_count": sum(1 for source in sources if source.get("optional")),
        "missing_required_count": _runtime_list_count(runtime, "missing_required"),
        "attribute_count": 0,
        "source_quality": _runtime_value(runtime, "atomic_quality", "unknown"),
        "degraded": bool(_runtime_value(runtime, "degraded", False)),
        "degraded_reason": _runtime_degraded_reason(runtime),
        "sources": sources,
        "contract_refs": _contract_refs(sources, profile),
        "legacy_aliases": _legacy_aliases(conf),
    }
    if include_raw_config:
        item["raw_config"] = dict(conf)
    return item


def build_contract_catalog(
    profile: str,
    *,
    masters: dict[str, dict[str, Any]] | None = None,
    combineds: dict[str, dict[str, Any]] | None = None,
    devices: dict[str, dict[str, Any]] | None = None,
    runtime_status: dict[str, Any] | None = None,
    include_raw_config: bool = False,
) -> dict[str, Any]:
    """Build a read-only v1 contract catalog from existing options/runtime data."""
    runtime_status = runtime_status or {}
    runtime_masters = _runtime_by_slug(runtime_status.get("masters"))
    runtime_combineds = _runtime_by_slug(runtime_status.get("combineds"))
    runtime_devices = _runtime_by_slug(runtime_status.get("devices"))
    master_items = [
        _master_entry(
            profile,
            str(slug),
            conf,
            runtime_masters.get(str(slug), {}),
            include_raw_config=include_raw_config,
        )
        for slug, conf in (masters or {}).items()
        if isinstance(conf, dict)
    ]
    combined_items = [
        _combined_entry(
            profile,
            str(slug),
            conf,
            runtime_combineds.get(str(slug), {}),
            include_raw_config=include_raw_config,
        )
        for slug, conf in (combineds or {}).items()
        if isinstance(conf, dict)
    ]
    device_items = [
        _device_entry(
            profile,
            str(slug),
            conf,
            runtime_devices.get(str(slug), {}),
            include_raw_config=include_raw_config,
        )
        for slug, conf in (devices or {}).items()
        if isinstance(conf, dict)
    ]
    return {
        "version": 1,
        "profile": profile,
        "masters": master_items,
        "legacy_devices": device_items,
        "legacy_combineds": combined_items,
        "summary": {
            "masters": len(master_items),
            "legacy_devices": len(device_items),
            "legacy_combineds": len(combined_items),
            "target_contracts": sum(
                1 for item in master_items if item["migration_status"] == MIGRATION_STATUS_TARGET
            ),
        },
    }
