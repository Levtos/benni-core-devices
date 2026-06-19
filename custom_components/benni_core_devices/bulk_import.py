"""HA-free import/export helpers for Benni Core Devices."""

from __future__ import annotations

from typing import Any

import yaml

from .combined import exposed_derived_names, parse_combined, validate_combined_v1
from .const import (
    ATTR_REPLACE,
    CONF_ATOMIC_CLASS,
    CONF_COMBINEDS,
    CONF_CONTROLS,
    CONF_DEVICES,
    CONF_DISPLAY_NAME,
    CONF_EXPOSE_SECONDARY_SENSORS,
    CONF_GROUP_MEMBERS,
    CONF_LIGHT_GROUPS,
    CONF_METADATA_SOURCES,
    CONF_SLUG,
    CONF_SOURCES,
    CONF_VARIANT,
    combined_object_id_prefix,
    device_object_id_prefix,
    group_object_id_prefix,
)
from .device_types import (
    classify_source_entity,
    parse_device_config,
    slugify,
    source_warning_text,
    validate_import_payload,
)


IMPORT_FILE_PARTS = ("benni_core_devices", "import.yaml")
IMPORT_FILE_DISPLAY_PATH = "<config>/benni_core_devices/import.yaml"


def devices_from_options(options: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = options.get(CONF_DEVICES)
    return dict(raw) if isinstance(raw, dict) else {}


def groups_from_options(options: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = options.get(CONF_LIGHT_GROUPS)
    return dict(raw) if isinstance(raw, dict) else {}


def combineds_from_options(options: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = options.get(CONF_COMBINEDS)
    return dict(raw) if isinstance(raw, dict) else {}


def own_prefixes(profile: str) -> tuple[str, ...]:
    return (
        device_object_id_prefix(profile),
        group_object_id_prefix(profile),
        combined_object_id_prefix(profile),
    )


def conf_source_entities(conf: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for bucket in (CONF_SOURCES, CONF_CONTROLS, CONF_METADATA_SOURCES):
        for b in conf.get(bucket, []) or []:
            if isinstance(b, dict) and b.get("entity"):
                out.append(str(b["entity"]))
    return out


def source_warnings(
    conf: dict[str, Any],
    profile: str,
    published_outputs: set[str] | frozenset[str] | None = None,
) -> list[str]:
    own = own_prefixes(profile)
    out: list[str] = []
    for eid in conf_source_entities(conf):
        category = classify_source_entity(
            eid, own_prefixes=own, published_outputs=published_outputs
        )
        if category:
            out.append(source_warning_text(category, eid))
    return out


def device_sensor_entity_id(profile: str, slug: str) -> str:
    return f"sensor.{device_object_id_prefix(profile)}{slug}"


def combined_sensor_entity_id(profile: str, slug: str) -> str:
    return f"sensor.{combined_object_id_prefix(profile)}{slug}"


def group_sensor_entity_id(profile: str, slug: str) -> str:
    return f"sensor.{group_object_id_prefix(profile)}{slug}"


def _has_source_role(conf: dict[str, Any], role: str) -> bool:
    return any(
        isinstance(b, dict) and b.get("role") == role and b.get("entity")
        for b in conf.get(CONF_SOURCES, []) or []
    )


def _published_for_device(profile: str, slug: str, conf: dict[str, Any]) -> set[str]:
    prefix = device_object_id_prefix(profile)
    out = {device_sensor_entity_id(profile, slug)}
    if conf.get(CONF_EXPOSE_SECONDARY_SENSORS):
        out.add(f"binary_sensor.{prefix}{slug}_powered")
        out.add(f"binary_sensor.{prefix}{slug}_available")
        out.add(f"sensor.{prefix}{slug}_power_state")
        if _has_source_role(conf, "power_meter"):
            out.add(f"sensor.{prefix}{slug}_watt")
    return out


def _published_for_combined(profile: str, slug: str, conf: dict[str, Any]) -> set[str]:
    prefix = combined_object_id_prefix(profile)
    out = {combined_sensor_entity_id(profile, slug)}
    cfg = parse_combined(slug, conf)
    if cfg:
        out.update(f"binary_sensor.{prefix}{slug}_{d.slug}" for d in cfg.derived)
    return out


def published_output_entity_ids(
    profile: str,
    devices: dict[str, dict[str, Any]] | None = None,
    combineds: dict[str, dict[str, Any]] | None = None,
    groups: dict[str, dict[str, Any]] | None = None,
) -> set[str]:
    out: set[str] = set()
    for slug, conf in (devices or {}).items():
        if isinstance(conf, dict):
            out.update(_published_for_device(profile, str(slug), conf))
    for slug, conf in (combineds or {}).items():
        if isinstance(conf, dict):
            out.update(_published_for_combined(profile, str(slug), conf))
    for slug, conf in (groups or {}).items():
        if isinstance(conf, dict):
            out.add(group_sensor_entity_id(profile, str(slug)))
    return out


def import_start_published_outputs(
    current_options: dict[str, Any],
    valid: list[dict[str, Any]],
    imported_groups: dict[str, Any],
    profile: str,
    replace: bool,
) -> set[str]:
    devices = {} if replace else devices_from_options(current_options)
    for item in valid:
        slug = str(item.get(CONF_SLUG))
        devices[slug] = {k: v for k, v in item.items() if k != CONF_SLUG}
    groups = (
        dict(imported_groups)
        if replace
        else {**groups_from_options(current_options), **imported_groups}
    )
    combineds = {} if replace else combineds_from_options(current_options)
    return published_output_entity_ids(profile, devices, combineds, groups)


def normalize_combineds(raw: Any) -> dict[str, dict[str, Any]]:
    """Accept combineds as dict {slug: conf} (export format) or list."""
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


def parse_bulk_payload(
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
    if devices:  # Devices are optional when only combineds are imported.
        if isinstance(devices, list):
            for item in devices:
                if isinstance(item, dict) and not item.get(CONF_SLUG):
                    derived = slugify(str(item.get(CONF_DISPLAY_NAME, "")))
                    if derived:
                        item[CONF_SLUG] = derived
        valid, errors = validate_import_payload(devices)
        if errors:
            raise ValueError("\n".join(errors))
    combineds = normalize_combineds(combineds_raw)
    return valid, (groups if isinstance(groups, dict) else {}), combineds


def replace_from_payload(raw: str) -> bool:
    """Read optional top-level replace:true|false from an import YAML file."""
    parsed = yaml.safe_load(raw) if raw and raw.strip() else None
    if not isinstance(parsed, dict) or ATTR_REPLACE not in parsed:
        return False
    replace = parsed[ATTR_REPLACE]
    if not isinstance(replace, bool):
        raise ValueError("replace must be true or false")
    return replace


def import_report(
    valid: list[dict[str, Any]],
    profile: str,
    published_outputs: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    own = own_prefixes(profile)
    report: list[dict[str, Any]] = []
    for d in valid:
        slug = str(d.get(CONF_SLUG))
        cfg = parse_device_config(slug, d)
        missing = cfg.missing_required() if cfg else ["<invalid>"]
        derived_sources = []
        for eid in conf_source_entities(d):
            cat = classify_source_entity(
                eid, own_prefixes=own, published_outputs=published_outputs
            )
            if cat:
                derived_sources.append(source_warning_text(cat, eid))
        report.append({
            "slug": slug,
            "atomic_class": d.get(CONF_ATOMIC_CLASS),
            "variant": d.get(CONF_VARIANT),
            "entity_id": device_sensor_entity_id(profile, slug),
            "missing_required": missing,
            "derived_sources": derived_sources,
            "accepted": not derived_sources,
        })
    return report

def combined_report(
    combineds: dict[str, dict[str, Any]],
    profile: str,
    published_outputs: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    own = own_prefixes(profile)
    published = set(published_outputs or set())
    rep: list[dict[str, Any]] = []
    for slug, conf in combineds.items():
        cfg = parse_combined(slug, conf)
        n = len(cfg.sources) if cfg else 0
        validation = validate_combined_v1(cfg) if cfg else ["ungültige Config"]
        derived_sources: list[str] = []
        source_blocks: list[str] = []
        accepted_sources: list[str] = []
        if cfg:
            for src in cfg.sources:
                if not src.entity:
                    continue
                cat = classify_source_entity(
                    src.entity, own_prefixes=own, published_outputs=published
                )
                if not cat:
                    continue
                if cat == "published":
                    accepted_sources.append(
                        f"{src.entity}: publizierter Core-Devices-Output als Fusion-Quelle akzeptiert"
                    )
                else:
                    msg = source_warning_text(cat, src.entity)
                    reason = (
                        f"forward reference auf noch-nicht-publizierten Output: {src.entity}"
                        if cat == "unpublished" else msg
                    )
                    derived_sources.append(reason)
                    source_blocks.append(reason)
        rep.append({
            "slug": slug,
            "output_type": cfg.output_type if cfg else "?",
            "sources": n,
            "derived_values": len(cfg.derived_values) if cfg else 0,
            "exposed_attributes": list(exposed_derived_names(cfg)) if cfg else [],
            "entity_id": combined_sensor_entity_id(profile, slug),
            "derived_sources": derived_sources,
            "source_blocks": source_blocks,
            "accepted_sources": accepted_sources,
            "validation": validation,
            "accepted": cfg is not None and not validation and not source_blocks,
        })
        if isinstance(conf, dict):
            published.update(_published_for_combined(profile, str(slug), conf))
    return rep

def apply_bulk(
    current_options: dict[str, Any],
    valid: list[dict[str, Any]],
    imported_groups: dict[str, Any],
    imported_combineds: dict[str, Any],
    replace: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    # replace=True means clean slate: existing entries are not merged.
    devices = {} if replace else devices_from_options(current_options)
    for item in valid:
        slug = str(item.pop(CONF_SLUG))
        devices[slug] = item
    groups = dict(imported_groups) if replace else {**groups_from_options(current_options), **imported_groups}
    combineds = dict(imported_combineds) if replace else {**combineds_from_options(current_options), **imported_combineds}
    return devices, groups, combineds


def export_yaml_from_options(options: dict[str, Any]) -> str:
    payload = {
        CONF_DEVICES: [{CONF_SLUG: slug, **conf} for slug, conf in devices_from_options(options).items()],
        CONF_COMBINEDS: combineds_from_options(options),
        CONF_LIGHT_GROUPS: groups_from_options(options),
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def error_response(dry_run: bool, replace: bool, message: str) -> dict[str, Any]:
    return {
        "dry_run": dry_run,
        "replace": replace,
        "devices": 0,
        "groups": 0,
        "combineds": 0,
        "report": [],
        "combined_report": [],
        "combineds_in": 0,
        "error": message,
    }
