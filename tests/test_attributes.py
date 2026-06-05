"""Tests für den Rich-Atomic-Attribut-Layer (attributes.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcd_attributes as A
import bcd_const as C
import bcd_device_types as DT
import bcd_logic as L

TZ = timezone(timedelta(hours=2))
NOW = datetime(2026, 6, 5, 20, 0, tzinfo=TZ)


def _reading(value, numeric=None, attrs=None, age_s=0):
    return L.SlotReading(
        value=value,
        numeric=numeric,
        attributes=attrs or {},
        last_updated=NOW - timedelta(seconds=age_s) if value is not None else None,
    )


def _result(**kw):
    base = dict(
        state="on",
        powered=True,
        power_state="playing",
        power_source="integration",
        available=True,
        last_powered_change=None,
        override_active=False,
        watt_disagrees=False,
        watt=None,
        raw_state="on",
        extra={},
    )
    base.update(kw)
    return L.DeviceResult(**base)


def _config(**kw):
    base = dict(
        slug="tv",
        display_name="TV",
        device_type="tv",
        slot_entities={},
        fields=(),
    )
    base.update(kw)
    return L.DeviceConfig(**base)


def _inputs(slots, **kw):
    base = dict(
        slots=slots,
        integration_slot="integration_entity",
        state_slot="integration_entity",
        watt_slot=None,
        boot_phase_active=False,
    )
    base.update(kw)
    return L.DeviceInputs(**base)


# ── Slot-Diagnose ────────────────────────────────────────────────────────────


def test_missing_source_when_field_active_without_entity():
    cfg = _config(fields=("integration_entity", "watt_sensor"), slot_entities={
        "integration_entity": "media_player.tv",
    })
    inp = _inputs({"integration_entity": _reading("playing")})
    diag = A.build_slot_diagnostics(cfg, inp, _result(available=True))
    assert "watt_sensor" in diag["missing_sources"]
    assert diag["atomic_quality"] == "degraded"


def test_degraded_when_configured_source_unavailable():
    cfg = _config(fields=("integration_entity",), slot_entities={
        "integration_entity": "media_player.tv",
    })
    inp = _inputs({"integration_entity": _reading(None)})
    diag = A.build_slot_diagnostics(cfg, inp, _result(available=False))
    assert diag["degraded"] is True
    assert any("integration_entity" in r for r in diag["degraded_reason"])
    assert diag["atomic_quality"] == "unavailable"


def test_slot_maps_and_consumes_populated():
    cfg = _config(
        fields=("integration_entity", "switch_entity"),
        slot_entities={
            "integration_entity": "media_player.tv",
            "switch_entity": "switch.tv_plug",
        },
    )
    inp = _inputs({
        "integration_entity": _reading("playing"),
        "switch_entity": _reading("on"),
    })
    diag = A.build_slot_diagnostics(cfg, inp, _result(available=True))
    assert diag["slot_entities"]["switch_entity"] == "switch.tv_plug"
    assert diag["slot_states"]["integration_entity"] == "playing"
    assert diag["slot_available"]["switch_entity"] is True
    assert diag["slot_roles"]["switch_entity"] == "switch"
    assert diag["consumes"] == ["media_player.tv", "switch.tv_plug"]
    assert diag["atomic_quality"] == "ok"


def test_ok_quality_when_all_present_and_fresh():
    cfg = _config(fields=("integration_entity",), slot_entities={
        "integration_entity": "media_player.tv",
    })
    inp = _inputs({"integration_entity": _reading("playing")})
    diag = A.build_slot_diagnostics(cfg, inp, _result(available=True))
    assert diag["degraded"] is False
    assert diag["missing_sources"] == []
    assert diag["atomic_quality"] == "ok"


# ── Standard-Attribute bleiben erhalten ──────────────────────────────────────


def test_standard_attributes_preserved():
    profile = DT.profile_for(C.DeviceType.TV)
    cfg = _config(fields=(), slot_entities={}, area_id="wohnzimmer")
    inp = _inputs({})
    attrs = A.build_main_attributes(profile, cfg, inp, _result(watt=42.0))
    for key in (
        "device_type", "slug", "display_name", "powered", "power_state",
        "available", "power_source", "last_powered_change", "override_active",
        "watt_disagrees", "area_id",
    ):
        assert key in attrs
    assert attrs["area_id"] == "wohnzimmer"
    assert attrs["watt"] == 42.0


# ── Rich-Media-Attribute ─────────────────────────────────────────────────────


def test_rich_media_attributes_present_when_media_player_configured():
    profile = DT.profile_for(C.DeviceType.TV)
    cfg = _config(
        fields=("integration_entity",),
        slot_entities={"integration_entity": "media_player.tv"},
    )
    media_attrs = {
        "app_id": "netflix",
        "source": "HDMI1",
        "media_title": "Some Show",
        "media_content_type": "tvshow",
        "volume_level": 0.4,
        "is_volume_muted": False,
    }
    inp = _inputs({"integration_entity": _reading("playing", attrs=media_attrs)})
    attrs = A.build_main_attributes(profile, cfg, inp, _result(raw_state="playing"))
    assert attrs["media_player_state"] == "playing"
    assert attrs["current_app"] == "netflix"
    assert attrs["source"] == "HDMI1"
    assert attrs["media_title"] == "Some Show"
    assert attrs["volume_level"] == 0.4
    assert attrs["is_volume_muted"] is False


def test_capability_and_measurement_attributes():
    profile = DT.profile_for(C.DeviceType.TV)
    cfg = _config(
        fields=(
            "switch_entity", "network_switch_entity", "current_sensor",
            "wake_button_entity",
        ),
        slot_entities={
            "switch_entity": "switch.tv_plug",
            "network_switch_entity": "switch.tv_net",
            "current_sensor": "sensor.tv_current",
            "wake_button_entity": "button.tv_wake",
        },
        wake_mac="58:96:0A:5E:E9:2E",
    )
    inp = _inputs({
        "switch_entity": _reading("on"),
        "network_switch_entity": _reading("off"),
        "current_sensor": _reading("0.5", numeric=0.5),
    })
    attrs = A.build_main_attributes(profile, cfg, inp, _result())
    assert attrs["switch_state"] == "on"
    assert attrs["plug_switch_entity"] == "switch.tv_plug"
    assert attrs["network_access_state"] == "off"
    assert attrs["current"] == 0.5
    assert attrs["wake_supported"] is True
    assert attrs["wake_mac"] == "58:96:0A:5E:E9:2E"
    assert attrs["wake_button_entity"] == "button.tv_wake"


def test_wake_mac_text_slot_not_treated_as_missing_source():
    cfg = _config(fields=("wake_mac",), slot_entities={}, wake_mac="AA:BB")
    inp = _inputs({})
    diag = A.build_slot_diagnostics(cfg, inp, _result(available=True))
    # wake_mac ist ein Text-Slot → darf NICHT als missing_source erscheinen
    assert "wake_mac" not in diag["missing_sources"]
