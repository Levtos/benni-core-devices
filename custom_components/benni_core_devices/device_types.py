"""Device-Typ-Profile + globaler Slot-Katalog (LH §6, v0.2-Redesign).

Neues Modell (Feld-Maske):
- Es gibt EINEN globalen Slot-Katalog (`SLOT_CATALOG`) mit allen möglichen
  Feldern und breiten (nicht typ-gebundenen) Entity-Domains.
- Der Config-Flow lässt den User pro Device frei wählen, welche Felder er
  belegen will (Multi-Select). Gewählte Felder werden zu Pflicht-Pickern.
- Der `device_type` steuert nur noch die Attribut-Semantik: welcher Slot die
  Integration-Truth liefert (R-DC-01), welcher den raw-State trägt, welche
  Extra-Attribute am Haupt-Sensor erscheinen — plus die Default-Vorauswahl
  der Felder in der Maske.

HA-frei — wird im Config-Flow und in der Logik benutzt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_COMPANION_MEDIA_PLAYER,
    CONF_COMPANION_TRACKER,
    CONF_COVER_ENTITY,
    CONF_CURRENT_SENSOR,
    CONF_DEVICE_TYPE,
    CONF_ENERGY_SENSOR,
    CONF_INTEGRATION_ENTITY,
    CONF_LIGHT_ENTITY,
    CONF_NETWORK_SWITCH_ENTITY,
    CONF_POSITION_ENTITY,
    CONF_POWER_ENTITY,
    CONF_REMOTE_ENTITY,
    CONF_SLUG,
    CONF_STATUS_ENTITY,
    CONF_SWITCH_ENTITY,
    CONF_TITLE_ENTITY,
    CONF_VALUE_ENTITY,
    CONF_VOLTAGE_SENSOR,
    CONF_WAKE_BUTTON_ENTITY,
    CONF_WAKE_MAC,
    CONF_WATT_SENSOR,
    CONF_WIFI_SENSOR,
    DeviceType,
)

# UX-Fachbereiche für den Atomic Builder (LH §7.2). Slots werden danach
# gruppiert dargestellt — keine endlose Checkbox-Liste mehr.
SLOT_GROUP_BASICS: Final[str] = "basics"
SLOT_GROUP_POWER: Final[str] = "power"
SLOT_GROUP_MEDIA_NETWORK: Final[str] = "media_network"
SLOT_GROUP_MEASUREMENTS: Final[str] = "measurements"
SLOT_GROUP_ADVANCED: Final[str] = "advanced"

SLOT_GROUP_ORDER: Final[tuple[str, ...]] = (
    SLOT_GROUP_BASICS,
    SLOT_GROUP_POWER,
    SLOT_GROUP_MEDIA_NETWORK,
    SLOT_GROUP_MEASUREMENTS,
    SLOT_GROUP_ADVANCED,
)

SLOT_GROUP_LABELS: Final[dict[str, str]] = {
    SLOT_GROUP_BASICS: "Basics",
    SLOT_GROUP_POWER: "Power & Fallbacks",
    SLOT_GROUP_MEDIA_NETWORK: "Media & Network",
    SLOT_GROUP_MEASUREMENTS: "Measurements",
    SLOT_GROUP_ADVANCED: "Advanced",
}


@dataclass(frozen=True)
class SlotSpec:
    """Definition eines Slots im globalen Katalog.

    `domains` ist ein breiter, nicht typ-gebundener Filter für den
    Entity-Picker. Bewusst großzügig — der User soll jede plausible Entity
    wählen können, nicht nur bestehende Atomics.

    `group` ordnet den Slot einem UX-Fachbereich im Atomic Builder zu.
    `role` ist die fachliche Rolle, die der Slot im Atomic spielt (für das
    `slot_roles`-Attribut). `kind` unterscheidet Entity-Slots von Text-Slots
    (z. B. `wake_mac`), die NICHT als HA-Entity gelesen werden dürfen.
    """

    key: str
    domains: tuple[str, ...]
    description: str = ""
    group: str = SLOT_GROUP_BASICS
    role: str = ""
    kind: str = "entity"  # "entity" | "text"


# ─────────────────────────────────────────────────────────────────────────────
# GLOBALER SLOT-KATALOG — alle Felder, breite Domains, typ-unabhängig
# ─────────────────────────────────────────────────────────────────────────────

SLOT_CATALOG: Final[dict[str, SlotSpec]] = {
    # ── Basics: Integration-Truth + State-Quellen ───────────────────────────
    CONF_INTEGRATION_ENTITY: SlotSpec(
        CONF_INTEGRATION_ENTITY, ("media_player",), "Media Player",
        group=SLOT_GROUP_BASICS, role="integration",
    ),
    CONF_POWER_ENTITY: SlotSpec(
        CONF_POWER_ENTITY, ("binary_sensor",), "An/Aus-Sensor",
        group=SLOT_GROUP_BASICS, role="power_binary",
    ),
    CONF_STATUS_ENTITY: SlotSpec(
        CONF_STATUS_ENTITY, ("sensor",), "Status-Sensor",
        group=SLOT_GROUP_BASICS, role="status",
    ),
    CONF_TITLE_ENTITY: SlotSpec(
        CONF_TITLE_ENTITY, ("sensor",), "Titel-Sensor",
        group=SLOT_GROUP_BASICS, role="title",
    ),
    CONF_SWITCH_ENTITY: SlotSpec(
        CONF_SWITCH_ENTITY, ("switch",), "Schalter / Steckdose",
        group=SLOT_GROUP_BASICS, role="switch",
    ),
    CONF_LIGHT_ENTITY: SlotSpec(
        CONF_LIGHT_ENTITY, ("light",), "Licht",
        group=SLOT_GROUP_BASICS, role="light",
    ),
    CONF_COVER_ENTITY: SlotSpec(
        CONF_COVER_ENTITY, ("cover",), "Rollo / Cover",
        group=SLOT_GROUP_BASICS, role="cover",
    ),
    CONF_POSITION_ENTITY: SlotSpec(
        CONF_POSITION_ENTITY, ("sensor",), "Positions-Sensor",
        group=SLOT_GROUP_BASICS, role="position",
    ),
    CONF_CLIMATE_ENTITY: SlotSpec(
        CONF_CLIMATE_ENTITY, ("climate",), "Thermostat / Klima",
        group=SLOT_GROUP_BASICS, role="climate",
    ),
    CONF_VALUE_ENTITY: SlotSpec(
        CONF_VALUE_ENTITY, ("sensor",), "Wert-Sensor",
        group=SLOT_GROUP_BASICS, role="value",
    ),
    # ── Power & Fallbacks ───────────────────────────────────────────────────
    CONF_WATT_SENSOR: SlotSpec(
        CONF_WATT_SENSOR, ("sensor",), "Watt-Sensor",
        group=SLOT_GROUP_POWER, role="watt",
    ),
    # ── Measurements: zusätzliche Roh-Messwerte ─────────────────────────────
    CONF_CURRENT_SENSOR: SlotSpec(
        CONF_CURRENT_SENSOR, ("sensor",), "Strom-Sensor (A)",
        group=SLOT_GROUP_MEASUREMENTS, role="current",
    ),
    CONF_VOLTAGE_SENSOR: SlotSpec(
        CONF_VOLTAGE_SENSOR, ("sensor",), "Spannungs-Sensor (V)",
        group=SLOT_GROUP_MEASUREMENTS, role="voltage",
    ),
    CONF_ENERGY_SENSOR: SlotSpec(
        CONF_ENERGY_SENSOR, ("sensor",), "Energie-Sensor (kWh)",
        group=SLOT_GROUP_MEASUREMENTS, role="energy",
    ),
    # ── Media & Network: Konnektivität + Companion-Geräte ───────────────────
    CONF_WIFI_SENSOR: SlotSpec(
        CONF_WIFI_SENSOR, ("binary_sensor",), "WLAN-Status",
        group=SLOT_GROUP_MEDIA_NETWORK, role="wifi",
    ),
    CONF_NETWORK_SWITCH_ENTITY: SlotSpec(
        CONF_NETWORK_SWITCH_ENTITY, ("switch",), "Netzwerk-/Internetzugang",
        group=SLOT_GROUP_MEDIA_NETWORK, role="network_access",
    ),
    CONF_WAKE_BUTTON_ENTITY: SlotSpec(
        CONF_WAKE_BUTTON_ENTITY, ("button",), "Wake-on-LAN Button",
        group=SLOT_GROUP_MEDIA_NETWORK, role="wake_button",
    ),
    CONF_WAKE_MAC: SlotSpec(
        CONF_WAKE_MAC, (), "Wake-on-LAN MAC",
        group=SLOT_GROUP_MEDIA_NETWORK, role="wake_mac", kind="text",
    ),
    CONF_REMOTE_ENTITY: SlotSpec(
        CONF_REMOTE_ENTITY, ("remote",), "Fernbedienung",
        group=SLOT_GROUP_MEDIA_NETWORK, role="remote",
    ),
    CONF_COMPANION_MEDIA_PLAYER: SlotSpec(
        CONF_COMPANION_MEDIA_PLAYER, ("media_player",), "Companion Media Player",
        group=SLOT_GROUP_MEDIA_NETWORK, role="companion_media_player",
    ),
    CONF_COMPANION_TRACKER: SlotSpec(
        CONF_COMPANION_TRACKER, ("device_tracker",), "Companion Tracker",
        group=SLOT_GROUP_MEDIA_NETWORK, role="companion_tracker",
    ),
}

# Entity-Slots, die der Coordinator als HA-State lesen darf (Text-Slots wie
# wake_mac sind ausgenommen).
ENTITY_SLOT_KEYS: Final[tuple[str, ...]] = tuple(
    key for key, spec in SLOT_CATALOG.items() if spec.kind == "entity"
)
TEXT_SLOT_KEYS: Final[tuple[str, ...]] = tuple(
    key for key, spec in SLOT_CATALOG.items() if spec.kind == "text"
)

ALL_SLOT_KEYS: Final[tuple[str, ...]] = tuple(SLOT_CATALOG.keys())


def slot_spec(key: str) -> SlotSpec | None:
    return SLOT_CATALOG.get(key)


# ─────────────────────────────────────────────────────────────────────────────
# DEVICE-TYP-PROFILE — nur noch Semantik + Default-Feldvorauswahl
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeviceTypeProfile:
    """Profil eines Device-Typs (Semantik, nicht Pflicht-Enforcement)."""

    device_type: DeviceType
    # Default-Vorauswahl der Felder in der Maske (vorab angehakt).
    default_fields: tuple[str, ...]
    # Welcher Slot liefert die Integration-Truth für R-DC-01 (Stufe 1)?
    integration_slot: str | None
    # Welcher Slot trägt den raw-State (z.B. media_player-State)?
    state_slot: str | None
    # Typspezifische Attribut-Schlüssel am Haupt-Sensor.
    extra_attributes: tuple[str, ...] = field(default_factory=tuple)
    # Stateful (semantischer State über powered hinaus)?
    stateful: bool = False


_TV = DeviceTypeProfile(
    device_type=DeviceType.TV,
    default_fields=(CONF_INTEGRATION_ENTITY, CONF_WATT_SENSOR, CONF_WIFI_SENSOR),
    integration_slot=CONF_INTEGRATION_ENTITY,
    state_slot=CONF_INTEGRATION_ENTITY,
    extra_attributes=(
        "watt",
        "media_player_state",
        "current_app",
        "source",
        "media_title",
        "media_content_type",
        "volume_level",
        "is_volume_muted",
    ),
    stateful=True,
)

_AV_RECEIVER = DeviceTypeProfile(
    device_type=DeviceType.AV_RECEIVER,
    default_fields=(CONF_INTEGRATION_ENTITY, CONF_WATT_SENSOR, CONF_WIFI_SENSOR),
    integration_slot=CONF_INTEGRATION_ENTITY,
    state_slot=CONF_INTEGRATION_ENTITY,
    extra_attributes=("watt", "current_source", "volume", "wifi_online", "media_player_state"),
    stateful=True,
)

_CONSOLE = DeviceTypeProfile(
    device_type=DeviceType.CONSOLE,
    default_fields=(CONF_POWER_ENTITY, CONF_STATUS_ENTITY, CONF_TITLE_ENTITY, CONF_WATT_SENSOR),
    integration_slot=CONF_POWER_ENTITY,
    state_slot=CONF_STATUS_ENTITY,
    extra_attributes=("status", "title", "watt"),
    stateful=True,
)

_SPEAKER = DeviceTypeProfile(
    device_type=DeviceType.SPEAKER,
    default_fields=(CONF_INTEGRATION_ENTITY, CONF_WIFI_SENSOR),
    integration_slot=CONF_INTEGRATION_ENTITY,
    state_slot=CONF_INTEGRATION_ENTITY,
    extra_attributes=("media_player_state", "current_track", "volume", "wifi_online"),
    stateful=True,
)

_PLUG = DeviceTypeProfile(
    device_type=DeviceType.PLUG,
    default_fields=(CONF_SWITCH_ENTITY, CONF_WATT_SENSOR),
    integration_slot=CONF_SWITCH_ENTITY,
    state_slot=None,
    extra_attributes=("watt",),
    stateful=False,
)

_LIGHT = DeviceTypeProfile(
    device_type=DeviceType.LIGHT,
    default_fields=(CONF_LIGHT_ENTITY,),
    integration_slot=CONF_LIGHT_ENTITY,
    state_slot=CONF_LIGHT_ENTITY,
    extra_attributes=("brightness", "color_temp", "rgb"),
    stateful=True,
)

_COVER = DeviceTypeProfile(
    device_type=DeviceType.COVER,
    default_fields=(CONF_COVER_ENTITY, CONF_POSITION_ENTITY),
    integration_slot=CONF_COVER_ENTITY,
    state_slot=CONF_COVER_ENTITY,
    extra_attributes=("position", "cover_state"),
    stateful=True,
)

_CLIMATE = DeviceTypeProfile(
    device_type=DeviceType.CLIMATE,
    default_fields=(CONF_CLIMATE_ENTITY,),
    integration_slot=CONF_CLIMATE_ENTITY,
    state_slot=CONF_CLIMATE_ENTITY,
    # Nur geräte-inhärente Wahrheiten — KEIN comfort/eco-Urteil (das macht
    # benni_climate_policy, weil es current_temp gegen einen Sollwert +
    # Kontext bewertet). hvac_mode = State, Rest aus den climate-Attributen.
    extra_attributes=(
        "current_temperature",
        "target_temperature",
        "hvac_action",
        "hvac_mode",
    ),
    stateful=True,
)

_SENSOR_WRAPPER = DeviceTypeProfile(
    device_type=DeviceType.SENSOR_WRAPPER,
    default_fields=(CONF_VALUE_ENTITY,),
    integration_slot=CONF_VALUE_ENTITY,
    state_slot=CONF_VALUE_ENTITY,
    extra_attributes=("value", "unit"),
    stateful=False,
)


PROFILES: Final[dict[DeviceType, DeviceTypeProfile]] = {
    DeviceType.TV: _TV,
    DeviceType.AV_RECEIVER: _AV_RECEIVER,
    DeviceType.CONSOLE: _CONSOLE,
    DeviceType.SPEAKER: _SPEAKER,
    DeviceType.PLUG: _PLUG,
    DeviceType.LIGHT: _LIGHT,
    DeviceType.COVER: _COVER,
    DeviceType.CLIMATE: _CLIMATE,
    DeviceType.SENSOR_WRAPPER: _SENSOR_WRAPPER,
}


def profile_for(device_type: DeviceType | str) -> DeviceTypeProfile:
    dt = device_type if isinstance(device_type, DeviceType) else DeviceType(device_type)
    return PROFILES[dt]


def default_fields(device_type: DeviceType | str) -> tuple[str, ...]:
    return profile_for(device_type).default_fields


# ─────────────────────────────────────────────────────────────────────────────
# SLUG + IMPORT-VALIDIERUNG (HA-frei, testbar)
# ─────────────────────────────────────────────────────────────────────────────

import re

SLUG_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]+$")


def is_valid_slug(slug: str) -> bool:
    return bool(slug) and bool(SLUG_RE.match(slug))


def slugify(text: str) -> str:
    """Wandelt einen Anzeigenamen in einen slug (a-z0-9_) um.

    'Wohnzimmer TV' → 'wohnzimmer_tv'. Mehrfache/führende/trailing
    Trennzeichen werden zu einem Unterstrich kollabiert.
    """
    out = []
    prev_us = False
    for ch in text.strip().lower():
        if ch.isalnum() and ch.isascii():
            out.append(ch)
            prev_us = False
        elif ch in (" ", "-", "_", ".", "/"):
            if not prev_us:
                out.append("_")
                prev_us = True
        # alles andere (Umlaute etc.) — simple Transliteration der häufigsten
        elif ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
            prev_us = False
    return "".join(out).strip("_")


_TRANSLIT: Final[dict[str, str]] = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
}


def unique_slug(base: str, existing: set[str]) -> str:
    """Stellt Eindeutigkeit her: hängt _2, _3, … an falls nötig."""
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE-CLASSIFIER — erkennt problematische Quellen (LH §5)
# ─────────────────────────────────────────────────────────────────────────────

# Object-id-Suffixe, die auf abgeleitete / nicht-rohe Quellen hindeuten.
# Diese dürfen NICHT still als Raw-Slot übernommen werden — die Integration
# soll genau diese Schicht selbst erzeugen.
BLOCKED_SOURCE_SUFFIXES: Final[tuple[str, ...]] = (
    "_atomic",
    "_combined",
    "_gate",
)


def classify_source_entity(
    entity_id: Any, *, own_prefixes: tuple[str, ...] = ()
) -> str | None:
    """Klassifiziert eine als Slot gewählte Entity (LH §5).

    Returns eine Warn-Kategorie wenn die Quelle nicht roh ist, sonst None:
    - "atomic"   — endet auf `_atomic` (alte YAML-Atomics)
    - "combined" — endet auf `_combined`
    - "gate"     — endet auf `_gate` (abgeleitete Gate-/Policy-Ausgaben)
    - "own"      — von dieser Integration selbst erzeugt (rückkopplungsgefährdet)

    HA-frei: arbeitet rein auf dem entity_id-String.
    """
    if not isinstance(entity_id, str) or "." not in entity_id:
        return None
    object_id = entity_id.split(".", 1)[1]
    for prefix in own_prefixes:
        if prefix and object_id.startswith(prefix):
            return "own"
    for suffix in BLOCKED_SOURCE_SUFFIXES:
        if object_id.endswith(suffix):
            return suffix.strip("_")
    return None


def source_warning_text(category: str, entity_id: str) -> str:
    """Lesbare Warnung für eine problematische Quelle."""
    labels = {
        "atomic": "alte YAML-Atomic-Quelle",
        "combined": "Combined-/Policy-Quelle",
        "gate": "abgeleitete Gate-Quelle",
        "own": "von dieser Integration selbst erzeugte Quelle",
    }
    label = labels.get(category, category)
    return f"{entity_id}: {label} sollte nicht als Raw-Slot dienen"


def validate_import_device(d: Any) -> str | None:
    """Validiert EIN Device-Dict aus dem Bulk-Import (R-DC-08).

    Neues Modell: nur slug + gültiger device_type sind Pflicht. Slots sind
    alle optional (was nicht da ist, ist okay). Unbekannte Slot-Keys werden
    ignoriert. Returns None bei OK, sonst eine Fehlerbeschreibung.
    """
    if not isinstance(d, dict):
        return "Eintrag ist kein Mapping"
    slug = str(d.get(CONF_SLUG, "")).strip().lower()
    if not is_valid_slug(slug):
        return f"ungültiger slug: {d.get(CONF_SLUG)!r}"
    dt_raw = d.get(CONF_DEVICE_TYPE)
    try:
        DeviceType(dt_raw)
    except (ValueError, TypeError):
        return f"{slug}: unbekannter device_type {dt_raw!r}"
    return None


def validate_import_payload(
    devices: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Validiert die gesamte Bulk-Import-Liste (strict / all-or-nothing).

    Returns (valid_devices, errors). Bei nicht-leerer errors-Liste sollte der
    Aufrufer NICHTS anlegen.
    """
    if not isinstance(devices, list) or not devices:
        return ([], ["devices ist keine nicht-leere Liste"])
    errors: list[str] = []
    valid: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, d in enumerate(devices):
        err = validate_import_device(d)
        if err:
            errors.append(f"#{idx + 1}: {err}")
            continue
        slug = str(d[CONF_SLUG]).strip().lower()
        if slug in seen:
            errors.append(f"#{idx + 1}: doppelter slug {slug!r}")
            continue
        seen.add(slug)
        normalized = dict(d)
        normalized[CONF_SLUG] = slug
        from .const import CONF_DISPLAY_NAME

        if not normalized.get(CONF_DISPLAY_NAME):
            normalized[CONF_DISPLAY_NAME] = slug
        valid.append(normalized)
    return (valid, errors)
