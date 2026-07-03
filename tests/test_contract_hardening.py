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
