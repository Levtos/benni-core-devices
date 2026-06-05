"""Reicher Attribut- und Diagnose-Layer für Device-Atomics (Rich-Atomic-Rework).

HA-frei und in pytest testbar. Baut aus der reinen `DeviceConfig`/`DeviceInputs`/
`DeviceResult`-Welt das vollständige Attribut-Dict, das `sensor.py` und die
WebSocket-API am Haupt-Sensor ausgeben.

Vertrag (LH §4):
- Standard-Attribute bleiben unverändert erhalten.
- Generische Slot-Diagnose: `slot_entities`, `slot_states`, `slot_available`,
  `slot_roles`, `missing_sources`, `degraded`, `degraded_reason`,
  `atomic_quality`, `consumes`.
- Reiche Typ-Attribute (Media/Measurement/Capability), sofern Quellen da sind.

Die Power-Entscheidung (logic.compute_device) wird hier NICHT verändert — dies
ist reine Ableitung auf dem fertigen Ergebnis.
"""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_COMPANION_MEDIA_PLAYER,
    CONF_COMPANION_TRACKER,
    CONF_CURRENT_SENSOR,
    CONF_ENERGY_SENSOR,
    CONF_INTEGRATION_ENTITY,
    CONF_NETWORK_SWITCH_ENTITY,
    CONF_REMOTE_ENTITY,
    CONF_SWITCH_ENTITY,
    CONF_VOLTAGE_SENSOR,
    CONF_WAKE_BUTTON_ENTITY,
)
from .device_types import (
    ENTITY_SLOT_KEYS,
    SLOT_CATALOG,
    DeviceTypeProfile,
)
from .logic import DeviceConfig, DeviceInputs, DeviceResult

# Attribut-Schlüssel, die der Rich-Media-Block autoritativ erzeugt. Sie werden
# bei Bedarf gegen None aus dem Profil-Loop überschrieben.
_MEDIA_KEYS: frozenset[str] = frozenset(
    {
        "media_player_state",
        "current_app",
        "source",
        "media_title",
        "media_content_type",
        "volume_level",
        "is_volume_muted",
    }
)


def _slot_role(key: str) -> str:
    spec = SLOT_CATALOG.get(key)
    return spec.role if spec else ""


def _is_entity_slot(key: str) -> bool:
    return key in ENTITY_SLOT_KEYS


def _reading_available(reading: Any) -> bool:
    return reading is not None and reading.value is not None


def build_slot_diagnostics(
    config: DeviceConfig, inputs: DeviceInputs, result: DeviceResult
) -> dict[str, Any]:
    """Generische, typ-unabhängige Slot-Diagnose (LH §4).

    `config.fields` listet die aktivierten Slots (auch leere). `slot_entities`
    bildet Slot → Entity ab. Leere aktivierte Entity-Slots werden zu
    `missing_sources`; konfigurierte, aber unverfügbare Quellen zu `degraded`.
    """
    active_fields = list(config.fields)
    slot_entities: dict[str, str] = {}
    slot_states: dict[str, Any] = {}
    slot_available: dict[str, bool] = {}
    slot_roles: dict[str, str] = {}
    slot_last_changed: dict[str, Any] = {}
    missing_sources: list[str] = []
    unavailable_slots: list[str] = []

    for key in active_fields:
        role = _slot_role(key)
        if role:
            slot_roles[key] = role
        if not _is_entity_slot(key):
            # Text-Slot (z. B. wake_mac): kein Entity-State.
            continue
        entity = config.slot_entities.get(key)
        if not entity:
            missing_sources.append(key)
            continue
        reading = inputs.slots.get(key)
        available = _reading_available(reading)
        slot_entities[key] = entity
        slot_states[key] = reading.value if reading else None
        slot_available[key] = available
        if reading is not None and reading.last_updated is not None:
            slot_last_changed[key] = reading.last_updated
        if not available:
            unavailable_slots.append(key)

    degraded = bool(unavailable_slots) or result.watt_disagrees
    degraded_reason: list[str] = [f"{s}: unavailable" for s in unavailable_slots]
    if result.watt_disagrees:
        degraded_reason.append("watt_disagrees")
    for s in missing_sources:
        degraded_reason.append(f"{s}: missing entity")

    if not result.available:
        atomic_quality = "unavailable"
    elif degraded or missing_sources:
        atomic_quality = "degraded"
    else:
        atomic_quality = "ok"

    return {
        "slot_entities": slot_entities,
        "slot_states": slot_states,
        "slot_available": slot_available,
        "slot_roles": slot_roles,
        "slot_last_changed": slot_last_changed,
        "missing_sources": missing_sources,
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "atomic_quality": atomic_quality,
        "consumes": sorted(slot_entities.values()),
    }


def _standard_attributes(
    config: DeviceConfig, result: DeviceResult
) -> dict[str, Any]:
    """Die bestehenden Standard-Attribute — unverändert (LH §4 Bestandsschutz)."""
    return {
        "device_type": config.device_type,
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
        "area_id": config.area_id,
    }


def _apply_profile_extra_attributes(
    attrs: dict[str, Any], profile: DeviceTypeProfile, result: DeviceResult
) -> None:
    """Portiert die bisherige extra_attributes-Logik (Bestandsschutz)."""
    for key in profile.extra_attributes:
        if key == "watt":
            attrs[key] = result.watt
        elif key in ("media_player_state", "hvac_mode"):
            attrs[key] = result.raw_state if profile.state_slot else None
        elif key == "target_temperature":
            attrs[key] = result.extra.get("temperature")
        else:
            attrs[key] = result.extra.get(key)


def _fill(attrs: dict[str, Any], key: str, value: Any) -> None:
    """Setzt `key`, wenn noch nicht vorhanden ODER bisher None und value gesetzt."""
    if value is None:
        attrs.setdefault(key, None)
        return
    if key not in attrs or attrs[key] is None:
        attrs[key] = value


def _reading_for(inputs: DeviceInputs, key: str):
    return inputs.slots.get(key)


def _add_rich_attributes(
    attrs: dict[str, Any], config: DeviceConfig, inputs: DeviceInputs
) -> None:
    """Reiche Media-/Measurement-/Capability-Attribute, sofern Slots da sind."""
    fields = set(config.fields)

    # ── Media (über den integration_entity-Slot = Media Player) ─────────────
    if CONF_INTEGRATION_ENTITY in fields and config.slot_entities.get(
        CONF_INTEGRATION_ENTITY
    ):
        mp = _reading_for(inputs, CONF_INTEGRATION_ENTITY)
        if mp is not None:
            ma = mp.attributes or {}
            _fill(attrs, "media_player_state", mp.value)
            _fill(attrs, "current_app", ma.get("app_id") or ma.get("app_name"))
            _fill(attrs, "source", ma.get("source"))
            _fill(attrs, "media_title", ma.get("media_title"))
            _fill(attrs, "media_content_type", ma.get("media_content_type"))
            _fill(attrs, "volume_level", ma.get("volume_level"))
            _fill(attrs, "is_volume_muted", ma.get("is_volume_muted"))

    # ── Measurements ────────────────────────────────────────────────────────
    for slot_key, attr_key in (
        (CONF_CURRENT_SENSOR, "current"),
        (CONF_VOLTAGE_SENSOR, "voltage"),
        (CONF_ENERGY_SENSOR, "energy"),
    ):
        if slot_key in fields and config.slot_entities.get(slot_key):
            r = _reading_for(inputs, slot_key)
            if r is not None:
                _fill(attrs, attr_key, r.numeric if r.numeric is not None else r.value)

    # ── Capability / Network ────────────────────────────────────────────────
    if CONF_SWITCH_ENTITY in fields and config.slot_entities.get(CONF_SWITCH_ENTITY):
        r = _reading_for(inputs, CONF_SWITCH_ENTITY)
        _fill(attrs, "switch_state", r.value if r else None)
        _fill(attrs, "plug_switch_entity", config.slot_entities.get(CONF_SWITCH_ENTITY))

    if CONF_NETWORK_SWITCH_ENTITY in fields and config.slot_entities.get(
        CONF_NETWORK_SWITCH_ENTITY
    ):
        r = _reading_for(inputs, CONF_NETWORK_SWITCH_ENTITY)
        _fill(attrs, "network_access_state", r.value if r else None)
        _fill(
            attrs,
            "network_switch_entity",
            config.slot_entities.get(CONF_NETWORK_SWITCH_ENTITY),
        )

    if CONF_REMOTE_ENTITY in fields and config.slot_entities.get(CONF_REMOTE_ENTITY):
        r = _reading_for(inputs, CONF_REMOTE_ENTITY)
        _fill(attrs, "remote_state", r.value if r else None)
        _fill(attrs, "remote_entity", config.slot_entities.get(CONF_REMOTE_ENTITY))

    if CONF_COMPANION_MEDIA_PLAYER in fields and config.slot_entities.get(
        CONF_COMPANION_MEDIA_PLAYER
    ):
        r = _reading_for(inputs, CONF_COMPANION_MEDIA_PLAYER)
        _fill(
            attrs,
            "companion_media_player",
            config.slot_entities.get(CONF_COMPANION_MEDIA_PLAYER),
        )
        _fill(attrs, "companion_media_player_state", r.value if r else None)

    if CONF_COMPANION_TRACKER in fields and config.slot_entities.get(
        CONF_COMPANION_TRACKER
    ):
        r = _reading_for(inputs, CONF_COMPANION_TRACKER)
        _fill(
            attrs,
            "companion_tracker",
            config.slot_entities.get(CONF_COMPANION_TRACKER),
        )
        _fill(attrs, "companion_tracker_state", r.value if r else None)

    # ── Wake-on-LAN ─────────────────────────────────────────────────────────
    wake_button = config.slot_entities.get(CONF_WAKE_BUTTON_ENTITY)
    if CONF_WAKE_BUTTON_ENTITY in fields and wake_button:
        _fill(attrs, "wake_button_entity", wake_button)
    if config.wake_mac:
        _fill(attrs, "wake_mac", config.wake_mac)
    if wake_button or config.wake_mac:
        _fill(attrs, "wake_supported", True)


def build_main_attributes(
    profile: DeviceTypeProfile,
    config: DeviceConfig,
    inputs: DeviceInputs,
    result: DeviceResult,
) -> dict[str, Any]:
    """Vollständiges Attribut-Dict des Haupt-Sensors (eine Quelle der Wahrheit)."""
    attrs = _standard_attributes(config, result)
    _apply_profile_extra_attributes(attrs, profile, result)
    attrs.update(build_slot_diagnostics(config, inputs, result))
    _add_rich_attributes(attrs, config, inputs)
    return attrs
