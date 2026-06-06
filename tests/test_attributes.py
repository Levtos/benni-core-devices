"""Tests für den rollenbasierten Attribut-Layer v2 (attributes.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcd_attributes as A
import bcd_device_types as DT
import bcd_logic as L

TZ = timezone(timedelta(hours=2))
NOW = datetime(2026, 6, 5, 20, 0, tzinfo=TZ)


def _b(role, entity=None, value=None):
    return DT.SourceBinding(role=role, entity=entity, value=value)


def _cfg(atomic_class="media_device", variant="tv", sources=(), controls=(), metadata=(), fail_safe="hold_last"):
    return DT.DeviceConfigV2(
        slug="tv", display_name="TV", atomic_class=atomic_class, variant=variant,
        sources=tuple(sources), controls=tuple(controls), metadata_sources=tuple(metadata),
        fail_safe=fail_safe,
    )


def _reading(value, numeric=None, attrs=None):
    return L.SlotReading(value=value, numeric=numeric, attributes=attrs or {},
                         last_updated=NOW if value is not None else None)


def _inputs(slots, state_slot="primary_state"):
    return L.DeviceInputs(slots=slots, integration_slot=state_slot, state_slot=state_slot,
                          watt_slot=None, boot_phase_active=False)


def _result(**kw):
    base = dict(state="on", powered=True, power_state="playing", power_source="integration",
                available=True, last_powered_change=None, override_active=False,
                watt_disagrees=False, watt=None, raw_state="on", extra={}, fail_safe_active=False)
    base.update(kw)
    return L.DeviceResult(**base)


# ── Rollen-Diagnose ──────────────────────────────────────────────────────────


def test_missing_required_when_no_source():
    cfg = _cfg(sources=())
    diag = A.build_slot_diagnostics(cfg, _inputs({}), _result(available=True))
    assert "primary_state" in diag["missing_required"]
    assert diag["atomic_quality"] == "degraded"


def test_degraded_when_source_unavailable():
    cfg = _cfg(sources=(_b("primary_state", "media_player.tv"),))
    diag = A.build_slot_diagnostics(cfg, _inputs({"primary_state": _reading(None)}), _result(available=False))
    assert diag["degraded"] is True
    assert diag["atomic_quality"] == "unavailable"


def test_source_maps_and_consumes():
    cfg = _cfg(sources=(_b("primary_state", "media_player.tv"), _b("power_meter", "sensor.tv_w")))
    inp = _inputs({"primary_state": _reading("playing"), "power_meter": _reading("12", numeric=12.0)})
    diag = A.build_slot_diagnostics(cfg, inp, _result(available=True))
    assert diag["source_entities"]["power_meter"] == "sensor.tv_w"
    assert diag["source_states"]["primary_state"] == "playing"
    assert diag["source_available"]["power_meter"] is True
    assert diag["consumes"] == ["media_player.tv", "sensor.tv_w"]
    assert diag["atomic_quality"] == "ok"
    assert "power_meter" in diag["source_roles"]


def test_fail_safe_active_marks_degraded():
    cfg = _cfg(sources=(_b("primary_state", "media_player.tv"),))
    inp = _inputs({"primary_state": _reading("playing")})
    diag = A.build_slot_diagnostics(cfg, inp, _result(available=True, fail_safe_active=True))
    assert diag["fail_safe_active"] is True
    assert diag["degraded"] is True


# ── Standard + Rich-Attribute ────────────────────────────────────────────────


def test_standard_attributes_v2():
    cfg = _cfg(sources=(_b("primary_state", "media_player.tv"),))
    attrs = A.build_main_attributes(cfg, _inputs({"primary_state": _reading("playing")}), _result(watt=42.0))
    assert attrs["atomic_class"] == "media_device"
    assert attrs["variant"] == "tv"
    assert attrs["powered"] is True
    assert attrs["fail_safe"] == "hold_last"
    assert attrs["watt"] == 42.0


def test_rich_media_attributes_from_primary_attrs():
    cfg = _cfg(sources=(_b("primary_state", "media_player.tv"),))
    media_attrs = {"app_id": "netflix", "source": "HDMI1", "media_title": "Show",
                   "volume_level": 0.4, "is_volume_muted": False}
    inp = _inputs({"primary_state": _reading("playing", attrs=media_attrs)})
    # result.extra spiegelt die Attribute der State-Quelle (wie compute_* es setzt)
    attrs = A.build_main_attributes(cfg, inp, _result(raw_state="playing", extra=media_attrs))
    assert attrs["media_state"] == "playing"
    assert attrs["current_app"] == "netflix"
    assert attrs["source"] == "HDMI1"
    assert attrs["media_title"] == "Show"
    assert attrs["volume_level"] == 0.4
    assert attrs["is_volume_muted"] is False


def test_metadata_source_overrides_primary_attr():
    # PS5-Title aus separater Quelle (metadata_sources/title_source)
    cfg = _cfg(atomic_class="console_device", variant="ps5",
               sources=(_b("status_source", "sensor.ps5_status"),),
               metadata=(_b("title_source", "sensor.ps5_title"),))
    inp = L.DeviceInputs(
        slots={"status_source": _reading("playing"), "title_source": _reading("Spiel X")},
        integration_slot="status_source", state_slot="status_source", watt_slot=None,
        boot_phase_active=False,
    )
    attrs = A.build_main_attributes(cfg, inp, _result(raw_state="playing"))
    assert attrs["title"] == "Spiel X"
    assert attrs["status"] == "playing"


def test_wake_mac_text_control_attribute():
    cfg = _cfg(sources=(_b("primary_state", "media_player.tv"),),
               controls=(_b("wake_mac", value="58:96:0A:5E:E9:2E"), _b("wake_button", "button.tv_wake")))
    attrs = A.build_main_attributes(cfg, _inputs({"primary_state": _reading("on")}), _result())
    assert attrs["wake_mac"] == "58:96:0A:5E:E9:2E"
    assert attrs["wake_button_entity"] == "button.tv_wake"
    assert attrs["wake_supported"] is True
    # wake_mac ist ein Control → nicht als source/missing_required
    assert "wake_mac" not in attrs["missing_required"]


def test_opening_attributes():
    cfg = _cfg(atomic_class="opening", variant="window", fail_safe="open",
               sources=(_b("open_contact", "binary_sensor.win_open"), _b("tilt_contact", "binary_sensor.win_tilt")))
    inp = L.DeviceInputs(
        slots={"open_contact": _reading("on"), "tilt_contact": _reading("off")},
        integration_slot="open_contact", state_slot="open_contact", watt_slot=None,
        boot_phase_active=False,
    )
    attrs = A.build_main_attributes(cfg, inp, _result(state="on", raw_state="on"))
    assert attrs["open"] is True
    assert attrs["tilted"] is False
    assert attrs["contact_state"] == "on"
