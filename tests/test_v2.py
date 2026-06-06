"""Tests für v2: Rollen-Auflösung + passthrough/numeric + fail_safe (§12.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcd_device_types as DT
import bcd_logic as L

TZ = timezone(timedelta(hours=2))
NOW = datetime(2026, 6, 5, 20, 0, tzinfo=TZ)


def _b(role, entity=None, value=None):
    return DT.SourceBinding(role=role, entity=entity, value=value)


def _cfg(atomic_class, variant, sources=(), controls=()):
    return DT.DeviceConfigV2(slug="x", display_name="X", atomic_class=atomic_class,
                             variant=variant, sources=tuple(sources), controls=tuple(controls))


def _reading(value, numeric=None):
    return L.SlotReading(value=value, numeric=numeric, attributes={},
                         last_updated=NOW if value is not None else None)


def _inp(slots, integration_slot=None, state_slot=None, watt_slot=None):
    return L.DeviceInputs(slots=slots, integration_slot=integration_slot, state_slot=state_slot,
                          watt_slot=watt_slot, boot_phase_active=False)


def _lc(device_type="opening", fail_safe="hold_last"):
    return L.DeviceConfig(slug="x", display_name="X", device_type=device_type, fail_safe=fail_safe)


def _p(last_state=None, last_powered=None):
    return L.DevicePersisted(last_powered=last_powered, last_powered_change=None,
                             override=None, last_state=last_state)


# ── Rollen-Auflösung ─────────────────────────────────────────────────────────


def test_console_integration_role_prefers_network_presence():
    cfg = _cfg("console_device", "ps5",
               sources=(_b("status_source", "sensor.ps5"), _b("network_presence", "binary_sensor.ps5_net")))
    # integration_roles = (network_presence, status_source) → network bevorzugt
    assert cfg.integration_role() == "network_presence"
    assert cfg.state_role() == "status_source"


def test_console_required_mode_any():
    # nur network → ok (any); keine → alle fehlen
    cfg = _cfg("console_device", "ps5", sources=(_b("network_presence", "binary_sensor.ps5_net"),))
    assert cfg.missing_required() == []
    cfg2 = _cfg("console_device", "ps5", sources=())
    assert set(cfg2.missing_required()) == {"status_source", "network_presence"}


def test_power_device_roles():
    cfg = _cfg("power_device", "plug",
               sources=(_b("primary_state", "switch.plug"), _b("power_meter", "sensor.plug_w")))
    assert cfg.integration_role() == "primary_state"
    assert cfg.watt_role() == "power_meter"
    assert cfg.missing_required() == []  # any: primary_state present


def test_media_required_all():
    cfg = _cfg("media_device", "tv", sources=())
    assert cfg.missing_required() == ["primary_state"]


def test_environment_numeric_role_order():
    cfg = _cfg("environment", "room_climate",
               sources=(_b("humidity_source", "sensor.h"), _b("temperature_source", "sensor.t")))
    # numeric_roles bevorzugt temperature_source
    assert cfg.numeric_role() == "temperature_source"


# ── compute_passthrough ──────────────────────────────────────────────────────


def test_passthrough_fresh_uses_raw_state():
    inp = _inp({"open_contact": _reading("on")}, integration_slot="open_contact", state_slot="open_contact")
    r = L.compute_passthrough(_lc("opening", "open"), inp, _p(), NOW)
    assert r.state == "on"
    assert r.powered is True
    assert r.fail_safe_active is False


def test_passthrough_fail_safe_open_when_stale():
    inp = _inp({"open_contact": _reading(None)}, integration_slot="open_contact", state_slot="open_contact")
    r = L.compute_passthrough(_lc("opening", fail_safe="open"), inp, _p(), NOW)
    assert r.state == "open"
    assert r.fail_safe_active is True
    assert r.available is False


def test_passthrough_fail_safe_off():
    inp = _inp({"light_source": _reading(None)}, integration_slot="light_source", state_slot="light_source")
    r = L.compute_passthrough(_lc("light", fail_safe="off"), inp, _p(), NOW)
    assert r.state == "off"
    assert r.powered is False
    assert r.fail_safe_active is True


def test_passthrough_hold_last_uses_persisted_state():
    inp = _inp({"cover_source": _reading(None)}, integration_slot="cover_source", state_slot="cover_source")
    r = L.compute_passthrough(_lc("cover", fail_safe="hold_last"), inp, _p(last_state="open", last_powered=True), NOW)
    assert r.state == "open"
    assert r.fail_safe_active is True


def test_passthrough_override_wins():
    override = L.build_override(powered=True, power_state="on", expire_seconds=None, now=NOW)
    inp = _inp({"light_source": _reading("off")}, integration_slot="light_source", state_slot="light_source")
    r = L.compute_passthrough(_lc("light", "off"), inp,
                              L.DevicePersisted(last_powered=None, last_powered_change=None, override=override, last_state=None), NOW)
    assert r.override_active is True
    assert r.powered is True


# ── compute_numeric ──────────────────────────────────────────────────────────


def test_numeric_fresh_value_is_state():
    inp = _inp({"temperature_source": _reading("21.5", numeric=21.5)}, state_slot="temperature_source")
    r = L.compute_numeric(_lc("environment", "unknown"), inp, _p(), NOW)
    assert r.state == "21.5"
    assert r.available is True
    assert r.fail_safe_active is False


def test_numeric_fail_safe_unknown_when_stale():
    inp = _inp({"temperature_source": _reading(None)}, state_slot="temperature_source")
    r = L.compute_numeric(_lc("environment", fail_safe="unknown"), inp, _p(), NOW)
    assert r.state == "unknown"
    assert r.fail_safe_active is True


# ── parse_device_config ──────────────────────────────────────────────────────


def test_parse_device_config_roundtrip():
    raw = {
        "atomic_class": "media_device", "variant": "tv", "display_name": "Wohnzimmer TV",
        "sources": [{"role": "primary_state", "entity": "media_player.tv"},
                    {"role": "power_meter", "entity": "sensor.tv_w"}],
        "controls": [{"role": "wake_mac", "value": "AA:BB"}],
        "diagnostics": {"fail_safe": "hold_last"},
    }
    cfg = DT.parse_device_config("living_tv", raw)
    assert cfg is not None
    assert cfg.atomic_class == "media_device"
    assert cfg.integration_role() == "primary_state"
    assert cfg.value_for_role("wake_mac") == "AA:BB"


def test_parse_device_config_invalid_class_is_none():
    assert DT.parse_device_config("x", {"atomic_class": "nope"}) is None
    assert DT.parse_device_config("x", "notadict") is None


# ── v2.1: Domain-Scoping + Metadaten-Ableitung + Console online/offline ──────


def test_role_domain_override_per_class():
    assert DT.ATOMIC_CLASSES["media_device"].domains_for("primary_state") == ("media_player",)
    assert DT.ATOMIC_CLASSES["power_device"].domains_for("primary_state") == ("switch",)
    # nicht überschriebene Rolle fällt auf den Katalog zurück
    assert DT.ATOMIC_CLASSES["media_device"].domains_for("power_meter") == ("sensor",)


def test_metadata_roles_declare_derive_attr():
    assert DT.ROLE_CATALOG["title_source"].derive_attr == "media_title"
    assert DT.ROLE_CATALOG["app_source"].derive_attr == "app_id"
    assert DT.ROLE_CATALOG["volume_source"].derive_attr == "volume_level"


def test_class_role_allowlists_scoped():
    media = DT.ATOMIC_CLASSES["media_device"]
    # Standard-Builder zeigt nur diese Controls — nicht den ganzen Katalog
    assert "power_switch" in media.control_roles
    assert "open_contact" not in media.control_roles
    assert "title_source" in media.metadata_override_roles


def test_console_online_offline_truthy():
    cfg = L.DeviceConfig(slug="ps5", display_name="PS5", device_type="console_device")
    inp = _inp({"network_presence": _reading("online")},
               integration_slot="network_presence", state_slot="status_source")
    r = L.compute_device(cfg, inp, _p(), NOW)
    assert r.powered is True
    inp2 = _inp({"network_presence": _reading("offline")},
                integration_slot="network_presence", state_slot="status_source")
    r2 = L.compute_device(cfg, inp2, _p(), NOW)
    assert r2.powered is False
