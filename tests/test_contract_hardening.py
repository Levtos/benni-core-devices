"""Guardrails for Core Devices contract hardening semantics."""

from __future__ import annotations

import bcd_combined as CB


def _src(key, role="custom", entity=None, required=True):
    return CB.CombinedSource(
        key=key,
        role=role,
        entity=entity or f"sensor.{key}",
        required=required,
    )


def _r(value, numeric=None, available=True, attrs=None):
    return CB.SourceReading(
        value=value,
        numeric=numeric,
        available=available,
        attributes=attrs or {},
    )


def _cfg(**kw):
    base = dict(slug="guardrail", display_name="Guardrail")
    base.update(kw)
    return CB.CombinedConfig(**base)


def _opening_field_hardening_cfg():
    return _cfg(
        output_type="enum",
        sources=(
            _src("living_left_open", "open_contact", "binary_sensor.living_window_left_open_contact"),
            _src("living_left_tilt", "tilt_contact", "binary_sensor.living_window_left_tilt_contact"),
            _src("living_right_open", "open_contact", "binary_sensor.living_window_right_open_contact"),
            _src("living_right_tilt", "tilt_contact", "binary_sensor.living_window_right_tilt_contact"),
            _src("kitchen_patio_open", "open_contact", "binary_sensor.kitchen_patio_door_open_contact"),
            _src("kitchen_patio_tilt", "tilt_contact", "binary_sensor.kitchen_patio_door_tilt_contact"),
            _src("hall_entry_door_contact", "open_contact", "binary_sensor.hall_entry_door_contact"),
        ),
        derived_values=(
            CB.DerivedValue(
                name="conflicting_open_and_tilt",
                kind="gate",
                expr='any([${living_left_open} == "on" and ${living_left_tilt} == "on", ${living_right_open} == "on" and ${living_right_tilt} == "on", ${kitchen_patio_open} == "on" and ${kitchen_patio_tilt} == "on"])',
                expose=True,
            ),
            CB.DerivedValue(
                name="living_window_left_code_digit",
                kind="enum",
                cases=(
                    CB.DerivedCase(when='${living_left_open} == "on" and ${living_left_tilt} == "on"', output="9"),
                    CB.DerivedCase(when="${living_left_open} == null", output="2"),
                    CB.DerivedCase(when='${living_left_open} == "on"', output="2"),
                    CB.DerivedCase(when='${living_left_tilt} == "on"', output="1"),
                ),
                default="0",
            ),
            CB.DerivedValue(
                name="living_window_right_code_digit",
                kind="enum",
                cases=(
                    CB.DerivedCase(when='${living_right_open} == "on" and ${living_right_tilt} == "on"', output="9"),
                    CB.DerivedCase(when="${living_right_open} == null", output="2"),
                    CB.DerivedCase(when='${living_right_open} == "on"', output="2"),
                    CB.DerivedCase(when='${living_right_tilt} == "on"', output="1"),
                ),
                default="0",
            ),
            CB.DerivedValue(
                name="kitchen_patio_door_code_digit",
                kind="enum",
                cases=(
                    CB.DerivedCase(when='${kitchen_patio_open} == "on" and ${kitchen_patio_tilt} == "on"', output="9"),
                    CB.DerivedCase(when="${kitchen_patio_open} == null", output="2"),
                    CB.DerivedCase(when='${kitchen_patio_open} == "on"', output="2"),
                    CB.DerivedCase(when='${kitchen_patio_tilt} == "on"', output="1"),
                ),
                default="0",
            ),
            CB.DerivedValue(
                name="hall_entry_door_code_digit",
                kind="enum",
                cases=(
                    CB.DerivedCase(when="${hall_entry_door_contact} == null", output="2"),
                    CB.DerivedCase(when='${hall_entry_door_contact} == "on"', output="2"),
                ),
                default="0",
            ),
            CB.DerivedValue(
                name="opening_code",
                kind="enum",
                default="${living_window_left_code_digit}${living_window_right_code_digit}${kitchen_patio_door_code_digit}${hall_entry_door_code_digit}",
                expose=True,
            ),
            CB.DerivedValue(name="apartment_opening_code", kind="enum", default="${opening_code}", expose=True),
            CB.DerivedValue(name="any_open", kind="gate", expr='any([${living_left_open} == "on", ${living_right_open} == "on", ${kitchen_patio_open} == "on", ${hall_entry_door_contact} == "on"])', expose=True),
            CB.DerivedValue(name="any_tilted", kind="gate", expr='any([${living_left_tilt} == "on", ${living_right_tilt} == "on", ${kitchen_patio_tilt} == "on"])', expose=True),
            CB.DerivedValue(name="stale_contacts", kind="gate", expr="any([${living_left_open} == null, ${living_left_tilt} == null, ${living_right_open} == null, ${living_right_tilt} == null, ${kitchen_patio_open} == null, ${kitchen_patio_tilt} == null, ${hall_entry_door_contact} == null])", expose=True),
            CB.DerivedValue(
                name="living_window_left",
                kind="enum",
                cases=(
                    CB.DerivedCase(when='${living_left_open} == "on" and ${living_left_tilt} == "on"', output="unclear"),
                    CB.DerivedCase(when='${living_left_open} == "on"', output="open"),
                    CB.DerivedCase(when='${living_left_tilt} == "on"', output="tilted"),
                    CB.DerivedCase(when="${living_left_open} == null or ${living_left_tilt} == null", output="stale"),
                ),
                default="closed",
                expose=True,
            ),
            CB.DerivedValue(
                name="living_window_right",
                kind="enum",
                cases=(
                    CB.DerivedCase(when='${living_right_open} == "on" and ${living_right_tilt} == "on"', output="unclear"),
                    CB.DerivedCase(when='${living_right_open} == "on"', output="open"),
                    CB.DerivedCase(when='${living_right_tilt} == "on"', output="tilted"),
                    CB.DerivedCase(when="${living_right_open} == null or ${living_right_tilt} == null", output="stale"),
                ),
                default="closed",
                expose=True,
            ),
            CB.DerivedValue(
                name="kitchen_patio_door",
                kind="enum",
                cases=(
                    CB.DerivedCase(when='${kitchen_patio_open} == "on" and ${kitchen_patio_tilt} == "on"', output="unclear"),
                    CB.DerivedCase(when='${kitchen_patio_open} == "on"', output="open"),
                    CB.DerivedCase(when='${kitchen_patio_tilt} == "on"', output="tilted"),
                    CB.DerivedCase(when="${kitchen_patio_open} == null or ${kitchen_patio_tilt} == null", output="stale"),
                ),
                default="closed",
                expose=True,
            ),
            CB.DerivedValue(
                name="hall_entry_door",
                kind="enum",
                cases=(
                    CB.DerivedCase(when='${hall_entry_door_contact} == "on"', output="open"),
                    CB.DerivedCase(when="${hall_entry_door_contact} == null", output="stale"),
                ),
                default="closed",
                expose=True,
            ),
            CB.DerivedValue(name="outside_any_open", kind="gate", expr='any([${living_window_left} == "open", ${living_window_right} == "open", ${kitchen_patio_door} == "open"])', expose=True),
            CB.DerivedValue(name="outside_any_tilted", kind="gate", expr='any([${living_window_left} == "tilted", ${living_window_right} == "tilted", ${kitchen_patio_door} == "tilted"])', expose=True),
            CB.DerivedValue(name="outside_any_active", kind="gate", expr="any([${outside_any_open}, ${outside_any_tilted}])", expose=True),
            CB.DerivedValue(name="outside_all_closed", kind="gate", expr='all([${living_window_left} == "closed", ${living_window_right} == "closed", ${kitchen_patio_door} == "closed"])', expose=True),
            CB.DerivedValue(name="entry_door_state", kind="enum", default="${hall_entry_door}", expose=True),
            CB.DerivedValue(name="entry_door_open", kind="gate", expr='${hall_entry_door} == "open"', expose=True),
            CB.DerivedValue(name="apartment_closed", kind="gate", expr='all([${outside_all_closed}, ${hall_entry_door} == "closed"])', expose=True),
            CB.DerivedValue(
                name="source_quality",
                kind="enum",
                cases=(
                    CB.DerivedCase(when="${stale_contacts} or ${conflicting_open_and_tilt}", output="degraded"),
                ),
                default="ok",
                expose=True,
            ),
            CB.DerivedValue(
                name="degraded_reason_hint",
                kind="enum",
                cases=(
                    CB.DerivedCase(when="${conflicting_open_and_tilt}", output="conflicting_open_and_tilt"),
                    CB.DerivedCase(when="${stale_contacts}", output="stale_required_source"),
                ),
                default="",
            ),
        ),
        rules=(
            CB.CombinedRule(source="conflicting_open_and_tilt", op="eq", value="on", output="unknown"),
            CB.CombinedRule(source="any_open", op="eq", value="on", output="open"),
            CB.CombinedRule(source="any_tilted", op="eq", value="on", output="tilted"),
            CB.CombinedRule(source="stale_contacts", op="eq", value="on", output="unknown"),
        ),
        default_output="closed",
    )


def test_opening_unknown_or_unavailable_is_not_closed():
    cfg = _cfg(
        output_type="enum",
        sources=(
            _src("left_open", "opening_contact", "binary_sensor.left_open"),
            _src("left_tilt", "tilt_contact", "binary_sensor.left_tilt"),
        ),
        derived_values=(
            CB.DerivedValue(
                name="left_state",
                kind="enum",
                cases=(
                    CB.DerivedCase(when="${left_open} == null or ${left_tilt} == null", output="stale"),
                    CB.DerivedCase(when='${left_open} == "on"', output="open"),
                    CB.DerivedCase(when='${left_tilt} == "on"', output="tilted"),
                ),
                default="closed",
                expose=True,
            ),
            CB.DerivedValue(
                name="source_quality",
                kind="enum",
                cases=(CB.DerivedCase(when='${left_state} == "stale"', output="problem"),),
                default="ok",
                expose=True,
            ),
        ),
        rules=(
            CB.CombinedRule(source="left_state", op="eq", value="open", output="open"),
            CB.CombinedRule(source="left_state", op="eq", value="tilted", output="tilted"),
            CB.CombinedRule(source="source_quality", op="eq", value="problem", output="unknown"),
        ),
        default_output="closed",
    )

    res = CB.evaluate_combined(
        cfg,
        {
            "left_open": _r(None, available=False),
            "left_tilt": _r("off"),
        },
    )

    assert res.state == "unknown"
    assert res.state != "closed"
    assert res.derived["left_state"] == "stale"
    assert res.derived["source_quality"] == "problem"


def test_opening_field_hardening_separates_outside_from_entry_door():
    cfg = _opening_field_hardening_cfg()
    res = CB.evaluate_combined(
        cfg,
        {
            "living_left_open": _r("off"),
            "living_left_tilt": _r("off"),
            "living_right_open": _r("off"),
            "living_right_tilt": _r("off"),
            "kitchen_patio_open": _r("off"),
            "kitchen_patio_tilt": _r("off"),
            "hall_entry_door_contact": _r("on"),
        },
    )

    assert res.state == "open"
    assert res.derived["opening_code"] == "0002"
    assert res.derived["apartment_opening_code"] == "0002"
    assert res.derived["outside_any_open"] is False
    assert res.derived["outside_all_closed"] is True
    assert res.derived["entry_door_open"] is True
    assert res.derived["entry_door_state"] == "open"
    assert res.derived["apartment_closed"] is False


def test_opening_field_hardening_outside_open_and_tilt_are_separate():
    cfg = _opening_field_hardening_cfg()
    res = CB.evaluate_combined(
        cfg,
        {
            "living_left_open": _r("on"),
            "living_left_tilt": _r("off"),
            "living_right_open": _r("off"),
            "living_right_tilt": _r("on"),
            "kitchen_patio_open": _r("off"),
            "kitchen_patio_tilt": _r("off"),
            "hall_entry_door_contact": _r("off"),
        },
    )

    assert res.state == "open"
    assert res.derived["opening_code"] == "2100"
    assert res.derived["outside_any_open"] is True
    assert res.derived["outside_any_tilted"] is True
    assert res.derived["outside_any_active"] is True
    assert res.derived["outside_all_closed"] is False
    assert res.derived["apartment_closed"] is False


def test_opening_field_hardening_stale_sources_do_not_close_apartment():
    cfg = _opening_field_hardening_cfg()
    stale_outside = CB.evaluate_combined(
        cfg,
        {
            "living_left_open": _r(None, available=False),
            "living_left_tilt": _r("off"),
            "living_right_open": _r("off"),
            "living_right_tilt": _r("off"),
            "kitchen_patio_open": _r("off"),
            "kitchen_patio_tilt": _r("off"),
            "hall_entry_door_contact": _r("off"),
        },
    )
    stale_entry = CB.evaluate_combined(
        cfg,
        {
            "living_left_open": _r("off"),
            "living_left_tilt": _r("off"),
            "living_right_open": _r("off"),
            "living_right_tilt": _r("off"),
            "kitchen_patio_open": _r("off"),
            "kitchen_patio_tilt": _r("off"),
            "hall_entry_door_contact": _r(None, available=False),
        },
    )

    assert stale_outside.state == "unknown"
    assert stale_outside.derived["opening_code"] == "2000"
    assert stale_outside.derived["outside_all_closed"] is False
    assert stale_outside.derived["apartment_closed"] is False
    assert stale_outside.derived["source_quality"] == "degraded"
    assert stale_outside.degraded is True
    assert "stale_required_source" in stale_outside.degraded_reason
    assert stale_entry.state == "unknown"
    assert stale_entry.derived["opening_code"] == "0002"
    assert stale_entry.derived["entry_door_state"] == "stale"
    assert stale_entry.derived["entry_door_open"] is False
    assert stale_entry.derived["apartment_closed"] is False


def test_opening_field_hardening_conflict_is_visible_and_not_safe():
    cfg = _opening_field_hardening_cfg()
    res = CB.evaluate_combined(
        cfg,
        {
            "living_left_open": _r("on"),
            "living_left_tilt": _r("on"),
            "living_right_open": _r("off"),
            "living_right_tilt": _r("off"),
            "kitchen_patio_open": _r("off"),
            "kitchen_patio_tilt": _r("off"),
            "hall_entry_door_contact": _r("off"),
        },
    )

    assert res.state == "unknown"
    assert res.derived["opening_code"] == "9000"
    assert res.derived["living_window_left"] == "unclear"
    assert res.derived["conflicting_open_and_tilt"] is True
    assert res.derived["outside_all_closed"] is False
    assert res.derived["apartment_closed"] is False
    assert res.derived["source_quality"] == "degraded"
    assert res.degraded is True
    assert "conflicting_open_and_tilt" in res.degraded_reason


def test_media_context_missing_central_source_does_not_silently_idle():
    cfg = _cfg(
        output_type="enum",
        sources=(
            _src("source_pc_active", "pc_active", "sensor.benni_master_pc"),
            _src("source_switch_active", "switch_active", "sensor.benni_master_switch"),
        ),
        derived_values=(
            CB.DerivedValue(
                name="source_quality",
                kind="enum",
                cases=(
                    CB.DerivedCase(when="${source_switch_active} == null", output="degraded"),
                    CB.DerivedCase(when="${source_pc_active} == null", output="problem"),
                ),
                default="ok",
                expose=True,
            ),
        ),
        rules=(
            CB.CombinedRule(source="source_pc_active", op="eq", value="on", output="pc"),
            CB.CombinedRule(source="source_switch_active", op="eq", value="on", output="console_gaming"),
            CB.CombinedRule(source="source_quality", op="ne", value="ok", output="unknown"),
        ),
        default_output="idle",
    )

    pc_active = CB.evaluate_combined(
        cfg,
        {
            "source_pc_active": _r("on"),
            "source_switch_active": _r(None, available=False),
        },
    )
    no_active_with_stale_source = CB.evaluate_combined(
        cfg,
        {
            "source_pc_active": _r("off"),
            "source_switch_active": _r(None, available=False),
        },
    )

    assert pc_active.state == "pc"
    assert pc_active.derived["source_quality"] == "degraded"
    assert no_active_with_stale_source.state == "unknown"
    assert no_active_with_stale_source.state != "idle"


def test_door_lock_unknown_source_is_not_locked_or_unlocked():
    cfg = _cfg(
        output_type="enum",
        sources=(_src("lock_state", "lock_state", "lock.aqara_smart_lock_u200"),),
        derived_values=(
            CB.DerivedValue(name="is_locked", kind="gate", expr='${lock_state} == "locked"', expose=True),
            CB.DerivedValue(name="is_unlocked", kind="gate", expr='${lock_state} == "unlocked"', expose=True),
            CB.DerivedValue(
                name="source_quality",
                kind="enum",
                cases=(CB.DerivedCase(when="${lock_state} == null", output="problem"),),
                default="ok",
                expose=True,
            ),
        ),
        rules=(
            CB.CombinedRule(source="source_quality", op="eq", value="problem", output="unknown"),
            CB.CombinedRule(source="lock_state", op="eq", value="locked", output="locked"),
            CB.CombinedRule(source="lock_state", op="eq", value="unlocked", output="unlocked"),
        ),
        default_output="unknown",
    )

    res = CB.evaluate_combined(cfg, {"lock_state": _r(None, available=False)})

    assert res.state == "unknown"
    assert res.derived["is_locked"] is False
    assert res.derived["is_unlocked"] is False
    assert res.derived["source_quality"] == "problem"


def test_plug_power_unknown_is_not_off_zero_or_safe_to_cut():
    cfg = _cfg(
        output_type="enum",
        sources=(
            _src("plug_state", "plug_state", "switch.living_plug"),
            _src("source_watt", "power_meter", "sensor.living_plug_power", required=False),
        ),
        derived_values=(
            CB.DerivedValue(name="watt", kind="expr", expr="${source_watt}", expose=True),
            CB.DerivedValue(name="meter_available", kind="gate", expr="${source_watt} != null", expose=True),
            CB.DerivedValue(
                name="source_quality",
                kind="enum",
                cases=(
                    CB.DerivedCase(when="${plug_state} == null", output="problem"),
                    CB.DerivedCase(when="${source_watt} == null", output="degraded"),
                ),
                default="ok",
                expose=True,
            ),
        ),
        rules=(
            CB.CombinedRule(source="source_quality", op="eq", value="problem", output="unknown"),
            CB.CombinedRule(source="plug_state", op="eq", value="on", output="powered"),
            CB.CombinedRule(source="plug_state", op="eq", value="off", output="idle"),
        ),
        default_output="unknown",
    )

    res = CB.evaluate_combined(
        cfg,
        {
            "plug_state": _r(None, available=False),
            "source_watt": _r(None, available=False),
        },
    )

    assert res.state == "unknown"
    assert res.state not in {"off", "idle", "safe_to_cut"}
    assert res.derived["watt"] is None
    assert res.derived["watt"] != 0
    assert res.derived["meter_available"] is False
    assert res.derived["source_quality"] == "problem"


def test_weather_unknown_symbol_remains_unknown_not_sunny_or_rainy():
    cfg = _cfg(
        output_type="enum",
        sources=(_src("weather_symbol_source", "weather", "weather.dwd_home"),),
        derived_values=(
            CB.DerivedValue(
                name="weather_symbol_normalized",
                kind="enum",
                cases=(
                    CB.DerivedCase(when='${weather_symbol_source} == "sunny"', output="sunny"),
                    CB.DerivedCase(when='${weather_symbol_source} == "rainy"', output="rainy"),
                    CB.DerivedCase(when='${weather_symbol_source} == "pouring"', output="rainy"),
                    CB.DerivedCase(when='${weather_symbol_source} == "partlycloudy"', output="partlycloudy"),
                ),
                default="unknown",
                expose=True,
            ),
            CB.DerivedValue(
                name="is_sunny_hint",
                kind="gate",
                expr='${weather_symbol_normalized} == "sunny"',
                expose=True,
            ),
            CB.DerivedValue(
                name="is_rainy_hint",
                kind="gate",
                expr='${weather_symbol_normalized} == "rainy"',
                expose=True,
            ),
            CB.DerivedValue(
                name="source_quality",
                kind="enum",
                cases=(CB.DerivedCase(when="${weather_symbol_source} == null", output="problem"),),
                default="ok",
                expose=True,
            ),
        ),
        rules=(CB.CombinedRule(source="source_quality", op="eq", value="problem", output="unknown"),),
        default_output="${weather_symbol_normalized}",
    )

    res = CB.evaluate_combined(cfg, {"weather_symbol_source": _r(None, available=False)})

    assert res.state == "unknown"
    assert res.derived["weather_symbol_normalized"] == "unknown"
    assert res.derived["is_sunny_hint"] is False
    assert res.derived["is_rainy_hint"] is False
    assert res.derived["source_quality"] == "problem"
