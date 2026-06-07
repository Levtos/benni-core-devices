"""Rollenbasierter Attribut- & Diagnose-Layer für Device-Atomics v2 (HA-frei).

Baut aus ``DeviceConfigV2`` + ``DeviceInputs`` (Readings keyed by ROLE) +
``DeviceResult`` das Attribut-Dict des Haupt-Sensors:
- Standard-Attribute (powered/power_state/available/… + ``fail_safe_active``)
- Rollen-Diagnose (source_roles/entities/states/available, missing_required,
  degraded(_reason), atomic_quality, consumes)
- reiche Attribute pro ``atomic_class`` (``AtomicClassSpec.extra_attributes``)

Metadaten-Default: fehlt eine ``metadata_sources``-Rolle, wird der Wert aus den
Attributen der ``primary_state``-Entity gelesen (liegt in ``result.extra``).
"""

from __future__ import annotations

from typing import Any

from .device_types import DeviceConfigV2
from .logic import DeviceInputs, DeviceResult


def _truthy(value: Any) -> bool | None:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in ("on", "open", "home", "true", "1", "yes", "playing", "active", "heat", "cool"):
        return True
    if v in ("off", "closed", "not_home", "false", "0", "no", "idle", "standby", "unavailable", "unknown"):
        return False
    return None


def build_slot_diagnostics(
    config: DeviceConfigV2, inputs: DeviceInputs, result: DeviceResult
) -> dict[str, Any]:
    source_entities = config.source_entities()
    source_roles = list(source_entities.keys())
    source_states: dict[str, Any] = {}
    source_available: dict[str, bool] = {}
    unavailable: list[str] = []
    for role, entity in source_entities.items():
        reading = inputs.slots.get(role)
        available = reading is not None and reading.value is not None
        source_states[role] = reading.value if reading else None
        source_available[role] = available
        if not available:
            unavailable.append(role)

    missing_required = config.missing_required()
    degraded = bool(unavailable) or result.watt_disagrees or bool(missing_required) or result.fail_safe_active
    reason: list[str] = [f"{r}: unavailable" for r in unavailable]
    if result.watt_disagrees:
        reason.append("watt_disagrees")
    for r in missing_required:
        reason.append(f"{r}: missing required")
    if result.fail_safe_active:
        reason.append("fail_safe_active")

    if not result.available:
        quality = "unavailable"
    elif degraded:
        quality = "degraded"
    else:
        quality = "ok"

    return {
        "source_roles": source_roles,
        "source_entities": source_entities,
        "source_states": source_states,
        "source_available": source_available,
        "missing_required": missing_required,
        "degraded": degraded,
        "degraded_reason": reason,
        "atomic_quality": quality,
        "consumes": sorted(config.compute_entities().values()),
        "fail_safe_active": result.fail_safe_active,
    }


def _standard_attributes(config: DeviceConfigV2, result: DeviceResult) -> dict[str, Any]:
    return {
        "atomic_class": config.atomic_class,
        "variant": config.variant,
        "slug": config.slug,
        "display_name": config.display_name,
        "powered": result.powered,
        "power_state": result.power_state,
        "available": result.available,
        "power_source": result.power_source,
        "last_powered_change": result.last_powered_change,
        "override_active": result.override_active,
        "watt": result.watt,
        "watt_disagrees": result.watt_disagrees,
        "fail_safe": config.fail_safe,
    }


def _extra_attribute(
    key: str, config: DeviceConfigV2, inputs: DeviceInputs, result: DeviceResult
) -> Any:
    """Löst einen reichen Attribut-Schlüssel aus Rollen/Primary-Attrs auf."""
    extra = result.extra or {}

    def val(role: str) -> Any:
        r = inputs.slots.get(role)
        return r.value if r else None

    def num(role: str) -> Any:
        r = inputs.slots.get(role)
        return r.numeric if r else None

    def meta_or_attr(meta_role: str, *attr_keys: str) -> Any:
        v = val(meta_role)
        if v is not None:
            return v
        for ak in attr_keys:
            if extra.get(ak) is not None:
                return extra.get(ak)
        return None

    # Media / Audio
    if key == "media_state":
        return result.raw_state
    if key == "current_app":
        return meta_or_attr("app_source", "app_id", "app_name")
    if key == "source":
        return meta_or_attr("source_source", "source")
    if key == "media_title":
        return meta_or_attr("title_source", "media_title")
    if key == "title":
        return meta_or_attr("title_source", "media_title") or meta_or_attr("game_source")
    if key == "volume_level" or key == "volume":
        return meta_or_attr("volume_source", "volume_level")
    if key == "is_volume_muted" or key == "muted":
        return meta_or_attr("mute_source", "is_volume_muted")
    if key == "artist":
        return meta_or_attr("artist_source", "media_artist")
    if key == "album":
        return meta_or_attr("album_source", "media_album_name")
    if key == "track":
        return meta_or_attr("title_source", "media_title")
    if key == "sound_mode":
        return extra.get("sound_mode")
    if key == "network_online" or key == "online":
        return _truthy(val("network_presence"))
    if key == "status":
        return val("status_source")
    if key == "last_online":
        return None

    # Power device
    if key == "switch_on":
        return _truthy(result.raw_state if config.atomic_class == "power_device" else val("primary_state"))
    if key == "active":
        return result.powered
    if key == "watt":
        return result.watt
    if key == "energy":
        return num("energy_meter")
    if key == "current":
        return num("current_meter")
    if key == "voltage":
        return num("voltage_meter")

    # Opening
    if key == "open":
        return _truthy(val("open_contact"))
    if key == "tilted":
        return _truthy(val("tilt_contact"))
    if key == "contact_state":
        return val("open_contact")
    if key == "battery":
        return num("battery_source")

    # Environment / numeric
    if key == "temperature":
        return num("temperature_source")
    if key == "humidity":
        return num("humidity_source")
    if key == "pressure":
        return num("pressure_source")
    if key == "lux":
        return num("lux_source")
    if key == "fresh":
        return not result.fail_safe_active
    if key == "value":
        return val("value_source")

    # Light
    if key in ("brightness", "color_mode", "color_temp_kelvin", "rgb", "effect"):
        attr_map = {"rgb": "rgb_color"}
        return extra.get(attr_map.get(key, key))

    # Cover
    if key == "position":
        return val("position_source") or extra.get("current_position")
    if key in ("moving", "calibrated"):
        return None

    # Climate
    if key == "current_temperature":
        return extra.get("current_temperature")
    if key == "target_temperature":
        return extra.get("temperature")
    if key in ("hvac_action", "hvac_mode"):
        return extra.get(key) if key == "hvac_action" else result.raw_state

    # Fallback: aus den Primary-Attributen.
    return extra.get(key)


def build_main_attributes(
    config: DeviceConfigV2, inputs: DeviceInputs, result: DeviceResult
) -> dict[str, Any]:
    attrs = _standard_attributes(config, result)
    spec = config.spec
    if spec:
        for key in spec.extra_attributes:
            attrs[key] = _extra_attribute(key, config, inputs, result)
    attrs.update(build_slot_diagnostics(config, inputs, result))
    # Text-Controls (wake_mac) + Wake-Support als Attribute.
    wake_mac = config.value_for_role("wake_mac")
    wake_button = config.entity_for_role("wake_button")
    if wake_mac:
        attrs["wake_mac"] = wake_mac
    if wake_button:
        attrs["wake_button_entity"] = wake_button
    if wake_mac or wake_button:
        attrs["wake_supported"] = True
    return attrs
