"""Rollen- und Klassenkatalog für Benni Core · Devices v2 (HA-frei).

Ersetzt das alte ``device_type`` + flache ``SLOT_CATALOG``-Modell durch:
- ``ROLE_CATALOG``     — globaler Rollenkatalog (sources/controls/metadata)
- ``ATOMIC_CLASSES``   — fachliche Geräteklassen mit ``variant``-Liste + power_model
- ``SourceBinding`` / ``DeviceConfigV2`` — persistiertes Conf-Modell (Rollen)
- Auflösungs-Helper, die der Coordinator nutzt, um Rollen → Compute-Inputs zu
  mappen (``logic.DeviceConfig`` + ``DeviceInputs`` bleiben unverändert).

HA-frei und vollständig in pytest testbar. ``profile`` ist NICHT Teil dieses
Modells — die Geräte-Unterart heißt ``variant``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final

from .const import (
    AVAILABILITY_ANY_REQUIRED_OR_ANY_SOURCE,
    CONF_ATOMIC_CLASS,
    CONF_AVAILABILITY_RULE,
    CONF_CONTROLS,
    CONF_DISPLAY_NAME,
    CONF_ENTITY,
    CONF_EXPOSE_SECONDARY_SENSORS,
    CONF_FAIL_SAFE,
    CONF_METADATA_SOURCES,
    CONF_REQUIRED,
    CONF_ROLE,
    CONF_SLUG,
    CONF_SOURCES,
    CONF_STICKY_HOLD_SECONDS,
    CONF_VALUE,
    CONF_VARIANT,
    CONF_WATT_BUCKETS,
    CONF_WATT_THRESHOLD_ON,
    DEFAULT_AVAILABILITY_RULE,
    DEFAULT_STICKY_HOLD_SECONDS,
    DEFAULT_WATT_THRESHOLD_ON,
    FAIL_SAFE_HOLD_LAST,
    FAIL_SAFE_OFF,
    FAIL_SAFE_OPEN,
    FAIL_SAFE_UNKNOWN,
    POWER_MODEL_INTEGRATION_WATT_STICKY,
    POWER_MODEL_NUMERIC,
    POWER_MODEL_PASSTHROUGH,
    AtomicClass,
)

# Buckets, in die Rollen einsortiert sind.
BUCKET_SOURCES: Final[str] = "sources"
BUCKET_CONTROLS: Final[str] = "controls"
BUCKET_METADATA: Final[str] = "metadata_sources"


# ─────────────────────────────────────────────────────────────────────────────
# ROLLEN-KATALOG (§6)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RoleSpec:
    key: str
    domains: tuple[str, ...]
    bucket: str
    compute_relevant: bool = False
    kind: str = "entity"  # "entity" | "text"
    label: str = ""


def _r(key, domains, bucket, compute_relevant=False, kind="entity", label=""):
    return RoleSpec(key, domains, bucket, compute_relevant, kind, label or key)


ROLE_CATALOG: Final[dict[str, RoleSpec]] = {s.key: s for s in (
    # sources — compute-/state-relevant
    _r("primary_state", ("media_player", "light", "cover", "climate", "switch", "binary_sensor", "sensor"), BUCKET_SOURCES, True, label="Hauptzustand"),
    _r("power_meter", ("sensor",), BUCKET_SOURCES, True, label="Watt-Messung"),
    _r("status_source", ("sensor", "binary_sensor"), BUCKET_SOURCES, True, label="Status"),
    _r("network_presence", ("binary_sensor", "device_tracker"), BUCKET_SOURCES, True, label="Netzwerk-Präsenz"),
    _r("activity_source", ("binary_sensor", "sensor"), BUCKET_SOURCES, True, label="Aktivität"),
    _r("open_contact", ("binary_sensor",), BUCKET_SOURCES, True, label="Öffnungskontakt"),
    _r("tilt_contact", ("binary_sensor",), BUCKET_SOURCES, True, label="Kipp-Kontakt"),
    _r("light_source", ("light",), BUCKET_SOURCES, True, label="Licht"),
    _r("cover_source", ("cover",), BUCKET_SOURCES, True, label="Rollo / Cover"),
    _r("position_source", ("sensor", "cover"), BUCKET_SOURCES, False, label="Position"),
    _r("climate_source", ("climate",), BUCKET_SOURCES, True, label="Thermostat"),
    _r("temperature_source", ("sensor",), BUCKET_SOURCES, True, label="Temperatur"),
    _r("humidity_source", ("sensor",), BUCKET_SOURCES, True, label="Luftfeuchte"),
    _r("pressure_source", ("sensor",), BUCKET_SOURCES, True, label="Druck"),
    _r("lux_source", ("sensor",), BUCKET_SOURCES, True, label="Helligkeit (lux)"),
    _r("value_source", ("sensor",), BUCKET_SOURCES, True, label="Wert"),
    _r("battery_source", ("sensor",), BUCKET_SOURCES, False, label="Batterie"),
    _r("energy_meter", ("sensor",), BUCKET_SOURCES, False, label="Energie (kWh)"),
    _r("current_meter", ("sensor",), BUCKET_SOURCES, False, label="Strom (A)"),
    _r("voltage_meter", ("sensor",), BUCKET_SOURCES, False, label="Spannung (V)"),
    # controls — Capability-only (Attribut)
    _r("power_switch", ("switch",), BUCKET_CONTROLS, False, label="Steckdose / Schalter"),
    _r("network_switch", ("switch",), BUCKET_CONTROLS, False, label="Netzwerk-Schalter"),
    _r("remote_control", ("remote",), BUCKET_CONTROLS, False, label="Fernbedienung"),
    _r("wake_button", ("button",), BUCKET_CONTROLS, False, label="Wake-Button"),
    _r("wake_mac", (), BUCKET_CONTROLS, False, kind="text", label="Wake-on-LAN MAC"),
    # metadata_sources — Attribut-Anreicherung aus separater Entity
    _r("title_source", ("sensor", "media_player"), BUCKET_METADATA, False, label="Titel"),
    _r("app_source", ("sensor", "media_player"), BUCKET_METADATA, False, label="App"),
    _r("source_source", ("sensor", "media_player"), BUCKET_METADATA, False, label="Quelle/Input"),
    _r("volume_source", ("sensor", "media_player"), BUCKET_METADATA, False, label="Lautstärke"),
    _r("mute_source", ("sensor", "media_player"), BUCKET_METADATA, False, label="Mute"),
    _r("artist_source", ("sensor", "media_player"), BUCKET_METADATA, False, label="Artist"),
    _r("album_source", ("sensor", "media_player"), BUCKET_METADATA, False, label="Album"),
    _r("game_source", ("sensor", "media_player"), BUCKET_METADATA, False, label="Spiel"),
    _r("companion_media", ("media_player",), BUCKET_METADATA, False, label="Companion Player"),
    _r("network_tracker", ("device_tracker",), BUCKET_METADATA, False, label="Companion Tracker"),
)}

ALL_ROLE_KEYS: Final[tuple[str, ...]] = tuple(ROLE_CATALOG.keys())


def role_spec(role: str) -> RoleSpec | None:
    return ROLE_CATALOG.get(role)


def role_bucket(role: str) -> str:
    spec = ROLE_CATALOG.get(role)
    return spec.bucket if spec else BUCKET_SOURCES


# ─────────────────────────────────────────────────────────────────────────────
# ATOMIC-CLASS-KATALOG (§5)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AtomicClassSpec:
    atomic_class: str
    variants: tuple[str, ...]
    power_model: str
    integration_roles: tuple[str, ...]
    state_role: str | None
    required_roles: tuple[str, ...]
    required_mode: str = "all"            # "all" | "any"
    fail_safe: str = FAIL_SAFE_HOLD_LAST
    extra_attributes: tuple[str, ...] = ()
    stateful: bool = True
    # Bevorzugte Default-Rollen für den Builder (zus. zu required).
    default_roles: tuple[str, ...] = ()
    # Reihenfolge für den primären Messwert (nur numeric).
    numeric_roles: tuple[str, ...] = ()
    beta: bool = False
    icon: str = "mdi:shape"
    label: str = ""


def _cls(spec: AtomicClassSpec) -> AtomicClassSpec:
    return spec


ATOMIC_CLASSES: Final[dict[str, AtomicClassSpec]] = {c.atomic_class: c for c in (
    AtomicClassSpec(
        atomic_class=AtomicClass.MEDIA_DEVICE.value,
        variants=("tv", "apple_tv", "streaming_box"),
        power_model=POWER_MODEL_INTEGRATION_WATT_STICKY,
        integration_roles=("primary_state",), state_role="primary_state",
        required_roles=("primary_state",), required_mode="all",
        fail_safe=FAIL_SAFE_HOLD_LAST,
        extra_attributes=("media_state", "current_app", "source", "media_title", "volume_level", "is_volume_muted", "watt", "network_online"),
        default_roles=("primary_state", "power_meter", "network_presence"),
        icon="mdi:television", label="Media Device",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.AUDIO_ENDPOINT.value,
        variants=("avr", "speaker", "speaker_group"),
        power_model=POWER_MODEL_INTEGRATION_WATT_STICKY,
        integration_roles=("primary_state",), state_role="primary_state",
        required_roles=("primary_state",), required_mode="all",
        fail_safe=FAIL_SAFE_HOLD_LAST,
        extra_attributes=("source", "sound_mode", "volume", "muted", "track", "artist", "album"),
        default_roles=("primary_state", "power_meter"),
        icon="mdi:speaker", label="Audio Endpoint",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.CONSOLE_DEVICE.value,
        variants=("ps5", "nintendo"),
        power_model=POWER_MODEL_INTEGRATION_WATT_STICKY,
        integration_roles=("network_presence", "status_source"), state_role="status_source",
        required_roles=("status_source", "network_presence"), required_mode="any",
        fail_safe=FAIL_SAFE_OFF,
        extra_attributes=("online", "status", "title", "watt", "last_online"),
        default_roles=("status_source", "network_presence", "power_meter"),
        icon="mdi:gamepad-variant", label="Console",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.POWER_DEVICE.value,
        variants=("plug", "pc", "subwoofer", "appliance"),
        power_model=POWER_MODEL_INTEGRATION_WATT_STICKY,
        integration_roles=("primary_state",), state_role=None,
        required_roles=("primary_state", "power_meter"), required_mode="any",
        fail_safe=FAIL_SAFE_OFF,
        extra_attributes=("switch_on", "active", "watt", "energy"),
        stateful=False,
        default_roles=("primary_state", "power_meter"),
        icon="mdi:power-socket-de", label="Power Device",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.OPENING.value,
        variants=("window", "door", "patio_door"),
        power_model=POWER_MODEL_PASSTHROUGH,
        integration_roles=("open_contact",), state_role="open_contact",
        required_roles=("open_contact",), required_mode="all",
        fail_safe=FAIL_SAFE_OPEN,
        extra_attributes=("open", "tilted", "contact_state", "battery"),
        default_roles=("open_contact", "tilt_contact"),
        icon="mdi:window-open-variant", label="Opening",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.ENVIRONMENT.value,
        variants=("room_climate", "lux"),
        power_model=POWER_MODEL_NUMERIC,
        integration_roles=(), state_role=None,
        required_roles=("temperature_source", "humidity_source", "pressure_source", "lux_source", "value_source"),
        required_mode="any",
        fail_safe=FAIL_SAFE_UNKNOWN,
        extra_attributes=("temperature", "humidity", "pressure", "lux", "battery", "fresh"),
        stateful=False,
        numeric_roles=("temperature_source", "lux_source", "humidity_source", "pressure_source", "value_source"),
        default_roles=("temperature_source", "humidity_source"),
        icon="mdi:thermometer", label="Environment",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.LIGHT.value,
        variants=("single",),
        power_model=POWER_MODEL_PASSTHROUGH,
        integration_roles=("light_source",), state_role="light_source",
        required_roles=("light_source",), required_mode="all",
        fail_safe=FAIL_SAFE_OFF,
        extra_attributes=("brightness", "color_mode", "color_temp_kelvin", "rgb", "effect"),
        default_roles=("light_source",),
        icon="mdi:lightbulb", label="Light",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.COVER.value,
        variants=("blind",),
        power_model=POWER_MODEL_PASSTHROUGH,
        integration_roles=("cover_source",), state_role="cover_source",
        required_roles=("cover_source",), required_mode="all",
        fail_safe=FAIL_SAFE_HOLD_LAST,
        extra_attributes=("position", "moving", "calibrated"),
        default_roles=("cover_source", "position_source"),
        icon="mdi:window-shutter", label="Cover",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.CLIMATE_DEVICE.value,
        variants=("thermostat",),
        power_model=POWER_MODEL_PASSTHROUGH,
        integration_roles=("climate_source",), state_role="climate_source",
        required_roles=("climate_source",), required_mode="all",
        fail_safe=FAIL_SAFE_HOLD_LAST,
        extra_attributes=("current_temperature", "target_temperature", "hvac_action", "hvac_mode"),
        default_roles=("climate_source",),
        icon="mdi:thermostat", label="Climate",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.GENERIC_EXPERT.value,
        variants=("adapter",),
        power_model=POWER_MODEL_PASSTHROUGH,
        integration_roles=("value_source",), state_role="value_source",
        required_roles=("value_source",), required_mode="all",
        fail_safe=FAIL_SAFE_UNKNOWN,
        extra_attributes=("value",),
        default_roles=("value_source",),
        icon="mdi:tune-vertical", label="Generic / Expert",
    ),
    # ── Beta/Expert: nur vorbereitet, keine Tiefe ──────────────────────────
    AtomicClassSpec(
        atomic_class=AtomicClass.PRESENCE_PERSON.value, variants=("person",),
        power_model=POWER_MODEL_PASSTHROUGH, integration_roles=("network_presence",),
        state_role="network_presence", required_roles=("network_presence",),
        fail_safe=FAIL_SAFE_UNKNOWN, extra_attributes=(), default_roles=("network_presence",),
        beta=True, icon="mdi:account", label="Presence (Beta)",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.MOBILE_DASHBOARD.value, variants=("tablet",),
        power_model=POWER_MODEL_PASSTHROUGH, integration_roles=("value_source",),
        state_role="value_source", required_roles=("value_source",),
        fail_safe=FAIL_SAFE_UNKNOWN, extra_attributes=(), default_roles=("value_source",),
        beta=True, icon="mdi:tablet-dashboard", label="Mobile Dashboard (Beta)",
    ),
    AtomicClassSpec(
        atomic_class=AtomicClass.NETWORK_SERVICE.value, variants=("service",),
        power_model=POWER_MODEL_PASSTHROUGH, integration_roles=("status_source",),
        state_role="status_source", required_roles=("status_source",),
        fail_safe=FAIL_SAFE_UNKNOWN, extra_attributes=(), default_roles=("status_source",),
        beta=True, icon="mdi:server-network", label="Network Service (Beta)",
    ),
)}

ALL_ATOMIC_CLASSES: Final[tuple[str, ...]] = tuple(ATOMIC_CLASSES.keys())


def atomic_class_spec(atomic_class: AtomicClass | str) -> AtomicClassSpec | None:
    key = atomic_class.value if isinstance(atomic_class, AtomicClass) else str(atomic_class)
    return ATOMIC_CLASSES.get(key)


# ─────────────────────────────────────────────────────────────────────────────
# v2 CONF-MODELL
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceBinding:
    role: str
    entity: str | None = None
    value: str | None = None      # nur Text-Controls (wake_mac)
    required: bool = False


@dataclass(frozen=True)
class DeviceConfigV2:
    slug: str
    display_name: str
    atomic_class: str
    variant: str
    sources: tuple[SourceBinding, ...] = ()
    controls: tuple[SourceBinding, ...] = ()
    metadata_sources: tuple[SourceBinding, ...] = ()
    availability_rule: str = DEFAULT_AVAILABILITY_RULE
    fail_safe: str = FAIL_SAFE_HOLD_LAST
    watt_threshold_on: int = DEFAULT_WATT_THRESHOLD_ON
    sticky_hold_seconds: int = DEFAULT_STICKY_HOLD_SECONDS
    expose_secondary_sensors: bool = False
    watt_buckets: tuple[dict[str, Any], ...] = ()

    @property
    def spec(self) -> AtomicClassSpec | None:
        return atomic_class_spec(self.atomic_class)

    # ── Rollen-Auflösung (HA-frei) ─────────────────────────────────────────

    def all_bindings(self) -> tuple[SourceBinding, ...]:
        return self.sources + self.controls + self.metadata_sources

    def entity_for_role(self, role: str) -> str | None:
        for b in self.all_bindings():
            if b.role == role and b.entity:
                return b.entity
        return None

    def value_for_role(self, role: str) -> str | None:
        for b in self.all_bindings():
            if b.role == role and b.value:
                return b.value
        return None

    def source_entities(self) -> dict[str, str]:
        """Rolle → Entity für alle entity-basierten Quellen (sources-Bucket)."""
        out: dict[str, str] = {}
        for b in self.sources:
            if b.entity:
                out[b.role] = b.entity
        return out

    def compute_entities(self) -> dict[str, str]:
        """Alle entity-basierten Bindings (alle Buckets) — Rolle → Entity.

        Wird vom Coordinator gelesen, um Readings + Diagnose zu bauen.
        """
        out: dict[str, str] = {}
        for b in self.all_bindings():
            if b.entity:
                out[b.role] = b.entity
        return out

    def integration_role(self) -> str | None:
        spec = self.spec
        if not spec:
            return None
        configured = self.source_entities()
        for role in spec.integration_roles:
            if role in configured:
                return role
        return None

    def state_role(self) -> str | None:
        spec = self.spec
        if not spec or not spec.state_role:
            return None
        return spec.state_role if spec.state_role in self.source_entities() else None

    def watt_role(self) -> str | None:
        return "power_meter" if "power_meter" in self.source_entities() else None

    def numeric_role(self) -> str | None:
        spec = self.spec
        if not spec:
            return None
        configured = self.source_entities()
        order = spec.numeric_roles or spec.required_roles
        for role in order:
            if role in configured:
                return role
        return None

    def missing_required(self) -> list[str]:
        """Pflichtrollen ohne konfigurierte Entity (gemäß required_mode)."""
        spec = self.spec
        if not spec or not spec.required_roles:
            return []
        configured = set(self.source_entities().keys())
        # text-Controls (wake_mac) ggf. ebenfalls als 'gesetzt' werten
        for b in self.all_bindings():
            if b.value:
                configured.add(b.role)
        if spec.required_mode == "any":
            return [] if any(r in configured for r in spec.required_roles) else list(spec.required_roles)
        return [r for r in spec.required_roles if r not in configured]


# ─────────────────────────────────────────────────────────────────────────────
# PARSING (Storage / Import / WebSocket → DeviceConfigV2)
# ─────────────────────────────────────────────────────────────────────────────


def _parse_bindings(raw: Any) -> tuple[SourceBinding, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[SourceBinding] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get(CONF_ROLE) or "").strip()
        if not role:
            continue
        out.append(SourceBinding(
            role=role,
            entity=(str(item[CONF_ENTITY]) if item.get(CONF_ENTITY) else None),
            value=(str(item[CONF_VALUE]) if item.get(CONF_VALUE) else None),
            required=bool(item.get(CONF_REQUIRED, False)),
        ))
    return tuple(out)


def parse_device_config(slug: str, raw: Any) -> DeviceConfigV2 | None:
    """Parst ein gespeichertes v2-Device-Dict. Robust gegen Müll (→ None)."""
    if not isinstance(raw, dict):
        return None
    atomic_class = str(raw.get(CONF_ATOMIC_CLASS) or "").strip()
    if atomic_class not in ATOMIC_CLASSES:
        return None
    variant = str(raw.get(CONF_VARIANT) or "").strip()
    spec = ATOMIC_CLASSES[atomic_class]
    diagnostics = raw.get("diagnostics") if isinstance(raw.get("diagnostics"), dict) else {}
    fail_safe = str(diagnostics.get(CONF_FAIL_SAFE) or raw.get(CONF_FAIL_SAFE) or spec.fail_safe)
    availability = str(diagnostics.get(CONF_AVAILABILITY_RULE) or raw.get(CONF_AVAILABILITY_RULE) or DEFAULT_AVAILABILITY_RULE)
    buckets = raw.get(CONF_WATT_BUCKETS)
    return DeviceConfigV2(
        slug=slug,
        display_name=str(raw.get(CONF_DISPLAY_NAME) or slug),
        atomic_class=atomic_class,
        variant=variant or (spec.variants[0] if spec.variants else ""),
        sources=_parse_bindings(raw.get(CONF_SOURCES)),
        controls=_parse_bindings(raw.get(CONF_CONTROLS)),
        metadata_sources=_parse_bindings(raw.get(CONF_METADATA_SOURCES)),
        availability_rule=availability,
        fail_safe=fail_safe,
        watt_threshold_on=int(raw.get(CONF_WATT_THRESHOLD_ON, DEFAULT_WATT_THRESHOLD_ON) or DEFAULT_WATT_THRESHOLD_ON),
        sticky_hold_seconds=int(raw.get(CONF_STICKY_HOLD_SECONDS, DEFAULT_STICKY_HOLD_SECONDS) or DEFAULT_STICKY_HOLD_SECONDS),
        expose_secondary_sensors=bool(raw.get(CONF_EXPOSE_SECONDARY_SENSORS, False)),
        watt_buckets=tuple(buckets) if isinstance(buckets, list) else (),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SLUG + SOURCE-CLASSIFIER (unverändert übernommen)
# ─────────────────────────────────────────────────────────────────────────────

SLUG_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]+$")
_TRANSLIT: Final[dict[str, str]] = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def is_valid_slug(slug: str) -> bool:
    return bool(slug) and bool(SLUG_RE.match(slug))


def slugify(text: str) -> str:
    out = []
    prev_us = False
    for ch in str(text).strip().lower():
        if ch.isalnum() and ch.isascii():
            out.append(ch); prev_us = False
        elif ch in (" ", "-", "_", ".", "/"):
            if not prev_us:
                out.append("_"); prev_us = True
        elif ch in _TRANSLIT:
            out.append(_TRANSLIT[ch]); prev_us = False
    return "".join(out).strip("_")


def unique_slug(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


BLOCKED_SOURCE_SUFFIXES: Final[tuple[str, ...]] = ("_atomic", "_combined", "_gate")


def classify_source_entity(entity_id: Any, *, own_prefixes: tuple[str, ...] = ()) -> str | None:
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
    labels = {
        "atomic": "alte YAML-Atomic-Quelle",
        "combined": "Combined-/Policy-Quelle",
        "gate": "abgeleitete Gate-Quelle",
        "own": "von dieser Integration selbst erzeugte Quelle",
    }
    return f"{entity_id}: {labels.get(category, category)} sollte nicht als Raw-Quelle dienen"


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT-VALIDIERUNG (v2)
# ─────────────────────────────────────────────────────────────────────────────


def validate_import_device(d: Any) -> str | None:
    if not isinstance(d, dict):
        return "Eintrag ist kein Mapping"
    slug = str(d.get(CONF_SLUG, "")).strip().lower()
    if not is_valid_slug(slug):
        return f"ungültiger slug: {d.get(CONF_SLUG)!r}"
    atomic_class = d.get(CONF_ATOMIC_CLASS)
    if atomic_class not in ATOMIC_CLASSES:
        return f"{slug}: unbekannte atomic_class {atomic_class!r}"
    return None


def validate_import_payload(devices: Any) -> tuple[list[dict[str, Any]], list[str]]:
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
        if not normalized.get(CONF_DISPLAY_NAME):
            normalized[CONF_DISPLAY_NAME] = slug
        valid.append(normalized)
    return (valid, errors)
