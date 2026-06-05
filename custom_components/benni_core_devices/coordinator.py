"""DataUpdateCoordinator für Benni Core · Devices.

Pro Device-Instanz ein Coordinator:
- liest alle konfigurierten Slot-Entities
- bridge HA-State → SlotReading
- ruft pure logic.compute_device()
- persistiert last_powered + Override über HA-Restarts
- registriert Service-Override / Clear via services_impl

Boot-Phase (R-DC-09): Coordinator merkt sich Start-Zeitpunkt;
logic.is_boot_phase() entscheidet ob Sticky-Hold greift.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.entity_registry import async_get as async_get_entities
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import logic
from .const import (
    CONF_DEVICE_TYPE,
    CONF_DISPLAY_NAME,
    CONF_EXPOSE_SECONDARY_SENSORS,
    CONF_FIELDS,
    CONF_SLUG,
    CONF_STICKY_HOLD_SECONDS,
    CONF_WAKE_MAC,
    CONF_WATT_BUCKETS,
    CONF_WATT_THRESHOLD_ON,
    DEFAULT_EXPOSE_SECONDARY_SENSORS,
    DEFAULT_STICKY_HOLD_SECONDS,
    DEFAULT_WATT_THRESHOLD_ON,
    DATA_COMBINEDS,
    DATA_COORDINATORS,
    DOMAIN,
    STORAGE_KEY_LAST_POWERED,
    STORAGE_KEY_LAST_POWERED_CHANGE,
    STORAGE_KEY_OVERRIDE,
    STORAGE_KEY_OVERRIDE_EXPIRES_AT,
    STORAGE_KEY_OVERRIDE_POWER_STATE,
    STORAGE_KEY_OVERRIDE_POWERED,
    STORAGE_VERSION,
    UPDATE_INTERVAL_SECONDS,
    DeviceType,
    entry_profile,
    storage_key,
)
from .attributes import build_main_attributes
from .device_types import ENTITY_SLOT_KEYS, DeviceTypeProfile, profile_for
from .logic import (
    DeviceConfig,
    DeviceInputs,
    DevicePersisted,
    DeviceResult,
    Override,
    SlotReading,
)

_LOGGER = logging.getLogger(__name__)


class DeviceCoordinator(DataUpdateCoordinator[DeviceResult]):
    """Treibt einen Device-Sensor."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, conf: dict[str, Any]
    ) -> None:
        slug = str(conf[CONF_SLUG])
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}_{slug}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.entry = entry
        self._conf = conf
        self._profile_name = entry_profile(entry)
        self._store = Store(
            hass,
            STORAGE_VERSION,
            storage_key(entry.entry_id, slug, self._profile_name),
        )
        self._persisted = DevicePersisted(
            last_powered=None,
            last_powered_change=None,
            override=None,
        )
        self._unsub_listeners: list[CALLBACK_TYPE] = []
        self._boot_start: datetime = dt_util.now()
        self._profile: DeviceTypeProfile = profile_for(self.device_type)
        # Letzter Inputs-Snapshot, damit der Sensor-Layer reiche Attribute
        # (Slot-Diagnose, Media, Measurements) ohne Re-Read bauen kann.
        self._last_inputs: DeviceInputs | None = None

    # ─────────────────────────────────────────────────────── Config Access

    def _c(self, key: str, default: Any = None) -> Any:
        return self._conf.get(key, default)

    @property
    def slug(self) -> str:
        return str(self._conf[CONF_SLUG])

    @property
    def display_name(self) -> str:
        return str(self._conf.get(CONF_DISPLAY_NAME) or self.slug)

    @property
    def profile_name(self) -> str:
        return self._profile_name

    @property
    def device_type(self) -> DeviceType:
        return DeviceType(self._conf[CONF_DEVICE_TYPE])

    @property
    def watt_threshold_on(self) -> int:
        return int(self._c(CONF_WATT_THRESHOLD_ON, DEFAULT_WATT_THRESHOLD_ON))

    @property
    def sticky_hold_seconds(self) -> int:
        return int(self._c(CONF_STICKY_HOLD_SECONDS, DEFAULT_STICKY_HOLD_SECONDS))

    @property
    def expose_secondary_sensors(self) -> bool:
        return bool(self._c(CONF_EXPOSE_SECONDARY_SENSORS, DEFAULT_EXPOSE_SECONDARY_SENSORS))

    @property
    def configured_slot_entities(self) -> dict[str, str]:
        """Slot-Key → Entity-ID, nur tatsächlich konfigurierte Entity-Slots.

        Text-Slots (z. B. ``wake_mac``) sind hier bewusst ausgenommen — sie
        sind keine HA-Entities und dürfen nicht als State gelesen werden.
        """
        out: dict[str, str] = {}
        for key in ENTITY_SLOT_KEYS:
            eid = self._conf.get(key)
            if eid:
                out[key] = str(eid)
        return out

    @property
    def fields(self) -> tuple[str, ...]:
        """Aktivierte Felder (auch leere) — für missing_sources-Diagnose."""
        raw = self._conf.get(CONF_FIELDS)
        if isinstance(raw, (list, tuple)):
            return tuple(str(k) for k in raw)
        # Fallback: aus den belegten Entity-Slots ableiten.
        return tuple(self.configured_slot_entities.keys())

    @property
    def wake_mac(self) -> str | None:
        value = self._conf.get(CONF_WAKE_MAC)
        return str(value) if value else None

    @property
    def watt_slot_key(self) -> str | None:
        """Welcher Slot-Key liefert den Watt-Sensor (für power_state R-DC-06)?"""
        from .const import CONF_WATT_SENSOR

        if CONF_WATT_SENSOR in self.configured_slot_entities:
            return CONF_WATT_SENSOR
        return None

    # ─────────────────────────────────────────────────────── Storage

    async def async_load_stored(self) -> None:
        raw = await self._store.async_load()
        if raw is None:
            return
        self._persisted = _persisted_from_dict(raw)

    async def _async_save(self) -> None:
        await self._store.async_save(_persisted_to_dict(self._persisted))

    # ─────────────────────────────────────────────────────── Lifecycle

    def async_start_listeners(self) -> None:
        watched = list(self.configured_slot_entities.values())
        if watched:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, watched, self._async_on_slot_change
                )
            )

    def async_stop_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    # ─────────────────────────────────────────────────────── Event-Handler

    @callback
    def _async_on_slot_change(self, _event: Event) -> None:
        self.hass.async_create_task(self._async_recompute_and_persist())

    async def _async_recompute_and_persist(self) -> None:
        result = self._compute()
        await self._persist_if_changed(result)
        self.async_set_updated_data(result)

    # ─────────────────────────────────────────────────────── Service-Hooks

    async def async_set_override(
        self,
        powered: bool | None,
        power_state: str | None,
        expire_seconds: int | None,
    ) -> DeviceResult:
        """R-DC-07: Override aktivieren."""
        now = dt_util.now()
        override = logic.build_override(powered, power_state, expire_seconds, now)
        self._persisted = DevicePersisted(
            last_powered=self._persisted.last_powered,
            last_powered_change=self._persisted.last_powered_change,
            override=override,
        )
        await self._async_save()
        result = self._compute()
        self.async_set_updated_data(result)
        return result

    async def async_clear_override(self) -> DeviceResult:
        """R-DC-07: Override entfernen."""
        self._persisted = DevicePersisted(
            last_powered=self._persisted.last_powered,
            last_powered_change=self._persisted.last_powered_change,
            override=None,
        )
        await self._async_save()
        result = self._compute()
        self.async_set_updated_data(result)
        return result

    # ─────────────────────────────────────────────────────── Compute

    async def _async_update_data(self) -> DeviceResult:
        return self._compute()

    def _compute(self) -> DeviceResult:
        now = dt_util.now()
        inputs = self._read_inputs(now)
        config = self._build_config()
        result = logic.compute_device(config, inputs, self._persisted, now)

        # Override-Expiry-Check: wenn aktiver Override gerade abgelaufen ist,
        # räume ihn auf (in Storage). Kein Race weil _persist_if_changed
        # sowieso wieder gesaved wird.
        if (
            self._persisted.override is not None
            and logic.is_override_expired(self._persisted.override, now)
        ):
            self._persisted = DevicePersisted(
                last_powered=self._persisted.last_powered,
                last_powered_change=self._persisted.last_powered_change,
                override=None,
            )

        return result

    async def _persist_if_changed(self, result: DeviceResult) -> None:
        if (
            result.powered == self._persisted.last_powered
            and result.last_powered_change == self._persisted.last_powered_change
        ):
            return
        self._persisted = DevicePersisted(
            last_powered=result.powered,
            last_powered_change=result.last_powered_change,
            override=self._persisted.override,
        )
        await self._async_save()

    def _build_config(self) -> DeviceConfig:
        slot_entities = self.configured_slot_entities
        return DeviceConfig(
            slug=self.slug,
            display_name=self.display_name,
            device_type=self.device_type.value,
            watt_threshold_on=self.watt_threshold_on,
            watt_buckets=logic.parse_watt_buckets(self._c(CONF_WATT_BUCKETS)),
            sticky_hold_seconds=self.sticky_hold_seconds,
            area_id=self._derive_area_id(),
            configured_slots=tuple(slot_entities.keys()),
            slot_entities=slot_entities,
            fields=self.fields,
            wake_mac=self.wake_mac,
        )

    @property
    def main_attributes(self) -> dict[str, Any]:
        """Vollständiges Attribut-Dict des Haupt-Sensors (Rich-Atomic-Layer).

        Eine Quelle der Wahrheit für sensor.py UND die WebSocket-API.
        """
        result = self.data
        if result is None or self._last_inputs is None:
            return {}
        return build_main_attributes(
            self._profile, self._build_config(), self._last_inputs, result
        )

    def _derive_area_id(self) -> str | None:
        """area_id aus HA-Area-Registry der Pflicht-Slot-Entity (OQ-5)."""
        slot_key = self._profile.integration_slot
        if not slot_key:
            return None
        eid = self.configured_slot_entities.get(slot_key)
        if not eid:
            return None
        ent_reg = async_get_entities(self.hass)
        entry = ent_reg.async_get(eid)
        if entry is None:
            return None
        # area_id kann direkt am Entity oder am Device hängen
        if entry.area_id:
            return entry.area_id
        if entry.device_id:
            from homeassistant.helpers.device_registry import async_get as async_get_devs

            dev_reg = async_get_devs(self.hass)
            dev = dev_reg.async_get(entry.device_id)
            if dev and dev.area_id:
                return dev.area_id
        return None

    def _read_inputs(self, now: datetime) -> DeviceInputs:
        slots: dict[str, SlotReading] = {}
        for slot_key, entity_id in self.configured_slot_entities.items():
            slots[slot_key] = self._read_slot(entity_id)
        inputs = DeviceInputs(
            slots=slots,
            integration_slot=self._profile.integration_slot,
            state_slot=self._profile.state_slot,
            watt_slot=self.watt_slot_key,
            boot_phase_active=logic.is_boot_phase(self._boot_start, now),
        )
        self._last_inputs = inputs
        return inputs

    def _read_slot(self, entity_id: str) -> SlotReading:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            return SlotReading(value=None)
        numeric: float | None = None
        try:
            numeric = float(state.state)
        except (TypeError, ValueError):
            numeric = None
        return SlotReading(
            value=state.state,
            numeric=numeric,
            attributes=dict(state.attributes),
            last_updated=state.last_updated,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Combined-Atomic-Coordinator (v0)
# ─────────────────────────────────────────────────────────────────────────────


class CombinedCoordinator(DataUpdateCoordinator):
    """Treibt einen Combined-Atomic-Sensor (First-Match-Wins, v0)."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, slug: str, raw_conf: dict
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}_combined_{slug}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        from .combined import CombinedConfig, parse_combined

        self.entry = entry
        self._slug = slug
        self._profile_name = entry_profile(entry)
        self._config = parse_combined(slug, raw_conf) or CombinedConfig(
            slug=slug, display_name=slug
        )
        self._unsub_listeners: list[CALLBACK_TYPE] = []
        self._last_readings: dict[str, Any] = {}

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def profile_name(self) -> str:
        return self._profile_name

    @property
    def config(self):
        return self._config

    @property
    def source_entities(self) -> list[str]:
        return [s.entity for s in self._config.sources if s.entity]

    def _read(self) -> dict[str, Any]:
        from .combined import SourceReading

        readings: dict[str, Any] = {}
        for src in self._config.sources:
            if not src.entity:
                continue
            state = self.hass.states.get(src.entity)
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
                readings[src.key] = SourceReading(value=None, available=False)
                continue
            numeric: float | None
            try:
                numeric = float(state.state)
            except (TypeError, ValueError):
                numeric = None
            readings[src.key] = SourceReading(
                value=state.state, numeric=numeric, available=True
            )
        return readings

    def _compute(self):
        from .combined import evaluate_combined

        self._last_readings = self._read()
        return evaluate_combined(self._config, self._last_readings)

    async def _async_update_data(self):
        return self._compute()

    def async_start_listeners(self) -> None:
        watched = self.source_entities
        if watched:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, watched, self._async_on_source_change
                )
            )

    def async_stop_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    @callback
    def _async_on_source_change(self, _event: Event) -> None:
        self.async_set_updated_data(self._compute())

    def derived_state(self, derived) -> bool | None:
        from .combined import evaluate_derived

        result = self.data
        if result is None:
            return None
        return evaluate_derived(derived, self._config, self._last_readings, result)

    @property
    def attributes(self) -> dict[str, Any]:
        result = self.data
        if result is None:
            return {}
        return {
            "slug": self._slug,
            "display_name": self._config.display_name,
            "output_type": self._config.output_type,
            "output": result.output,
            "reason": result.reason,
            "code_legend": dict(self._config.code_legend),
            "source_entities": result.source_entities,
            "source_states": result.source_states,
            "source_available": result.source_available,
            "missing_sources": result.missing_sources,
            "degraded": result.degraded,
            "degraded_reason": result.degraded_reason,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Lookup-Helper
# ─────────────────────────────────────────────────────────────────────────────


@callback
def combined_coordinators_for_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, "CombinedCoordinator"]:
    """Alle Combined-Coordinators (slug → coord) des Hub-Entries."""
    bucket = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not bucket:
        return {}
    coords = bucket.get(DATA_COMBINEDS)
    return coords if isinstance(coords, dict) else {}


@callback
def coordinators_for_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, DeviceCoordinator]:
    """Alle Device-Coordinators (slug → coord) des Hub-Entries."""
    bucket = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not bucket:
        return {}
    coords = bucket.get(DATA_COORDINATORS)
    return coords if isinstance(coords, dict) else {}


@callback
def all_coordinators(hass: HomeAssistant) -> list[DeviceCoordinator]:
    """Alle Device-Coordinators über alle Hub-Entries (Service-Resolution)."""
    out: list[DeviceCoordinator] = []
    for bucket in hass.data.get(DOMAIN, {}).values():
        if not isinstance(bucket, dict):
            continue
        coords = bucket.get(DATA_COORDINATORS)
        if isinstance(coords, dict):
            out.extend(c for c in coords.values() if isinstance(c, DeviceCoordinator))
    return out


@callback
def coordinator_by_slug(hass: HomeAssistant, slug: str) -> DeviceCoordinator | None:
    for c in all_coordinators(hass):
        if c.slug == slug:
            return c
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Persistenz-Codec
# ─────────────────────────────────────────────────────────────────────────────


def _persisted_to_dict(p: DevicePersisted) -> dict[str, Any]:
    out: dict[str, Any] = {
        STORAGE_KEY_LAST_POWERED: p.last_powered,
        STORAGE_KEY_LAST_POWERED_CHANGE: (
            p.last_powered_change.isoformat() if p.last_powered_change else None
        ),
        STORAGE_KEY_OVERRIDE: None,
    }
    if p.override is not None:
        out[STORAGE_KEY_OVERRIDE] = {
            STORAGE_KEY_OVERRIDE_POWERED: p.override.powered,
            STORAGE_KEY_OVERRIDE_POWER_STATE: p.override.power_state,
            STORAGE_KEY_OVERRIDE_EXPIRES_AT: (
                p.override.expires_at.isoformat() if p.override.expires_at else None
            ),
        }
    return out


def _persisted_from_dict(raw: dict[str, Any]) -> DevicePersisted:
    override_raw = raw.get(STORAGE_KEY_OVERRIDE)
    override: Override | None = None
    if isinstance(override_raw, dict):
        override = Override(
            powered=override_raw.get(STORAGE_KEY_OVERRIDE_POWERED),
            power_state=override_raw.get(STORAGE_KEY_OVERRIDE_POWER_STATE),
            expires_at=_parse_iso(
                override_raw.get(STORAGE_KEY_OVERRIDE_EXPIRES_AT)
            ),
        )
    return DevicePersisted(
        last_powered=raw.get(STORAGE_KEY_LAST_POWERED),
        last_powered_change=_parse_iso(raw.get(STORAGE_KEY_LAST_POWERED_CHANGE)),
        override=override,
    )


def _parse_iso(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None
