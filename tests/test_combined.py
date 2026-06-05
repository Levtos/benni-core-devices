"""Tests für die Combined-Atomic-Engine v0 (combined.py)."""

from __future__ import annotations

import bcd_combined as CB
import bcd_const as C


def _r(value, numeric=None, available=True):
    return CB.SourceReading(value=value, numeric=numeric, available=available)


# ── Opening-Logik als Referenzfall (LH §6) ───────────────────────────────────


def _opening_config():
    return CB.CombinedConfig(
        slug="living_window_left",
        display_name="Living Window Left",
        output_type=C.OUTPUT_TYPE_CODE,
        sources=(
            CB.CombinedSource(key="open", role="open_contact", entity="binary_sensor.left_open"),
            CB.CombinedSource(key="tilt", role="tilt_contact", entity="binary_sensor.left_tilt"),
        ),
        rules=(
            CB.CombinedRule(source="open", op=C.COMBINED_OP_UNAVAILABLE, output=9, reason="open unclear"),
            CB.CombinedRule(source="open", op=C.COMBINED_OP_EQ, value="on", output=2, reason="open"),
            CB.CombinedRule(source="tilt", op=C.COMBINED_OP_EQ, value="on", output=1, reason="tilted"),
        ),
        default_output=0,
        default_reason="closed",
        code_legend={"0": "closed", "1": "tilted", "2": "open", "9": "unclear"},
    )


def test_opening_open_contact_unavailable_is_unclear():
    cfg = _opening_config()
    res = CB.evaluate_combined(cfg, {"open": _r(None, available=False), "tilt": _r("off")})
    assert res.state == "9"
    assert res.matched_rule == 0
    assert res.degraded is True


def test_opening_open_contact_on_is_open():
    cfg = _opening_config()
    res = CB.evaluate_combined(cfg, {"open": _r("on"), "tilt": _r("off")})
    assert res.state == "2"
    assert res.reason == "open"


def test_opening_tilt_on_is_tilted():
    cfg = _opening_config()
    res = CB.evaluate_combined(cfg, {"open": _r("off"), "tilt": _r("on")})
    assert res.state == "1"


def test_opening_default_is_closed():
    cfg = _opening_config()
    res = CB.evaluate_combined(cfg, {"open": _r("off"), "tilt": _r("off")})
    assert res.state == "0"
    assert res.matched_rule is None
    assert res.reason == "closed"


# ── Output-Typen ─────────────────────────────────────────────────────────────


def test_boolean_output_coercion():
    cfg = CB.CombinedConfig(
        slug="x", display_name="X", output_type=C.OUTPUT_TYPE_BOOLEAN,
        sources=(CB.CombinedSource(key="s", role="custom", entity="sensor.x"),),
        rules=(CB.CombinedRule(source="s", op=C.COMBINED_OP_EQ, value="on", output=True),),
        default_output=False,
    )
    assert CB.evaluate_combined(cfg, {"s": _r("on")}).state == "on"
    assert CB.evaluate_combined(cfg, {"s": _r("off")}).state == "off"


def test_number_output_coercion():
    assert CB.coerce_output(5, C.OUTPUT_TYPE_NUMBER) == "5"
    assert CB.coerce_output(5.5, C.OUTPUT_TYPE_NUMBER) == "5.5"
    assert CB.coerce_output("abc", C.OUTPUT_TYPE_NUMBER) == "abc"


def test_enum_output_passthrough():
    assert CB.coerce_output("open", C.OUTPUT_TYPE_ENUM) == "open"


# ── Numerische Bedingungen ───────────────────────────────────────────────────


def test_numeric_comparison_rules():
    cfg = CB.CombinedConfig(
        slug="t", display_name="T", output_type=C.OUTPUT_TYPE_ENUM,
        sources=(CB.CombinedSource(key="temp", role="temperature", entity="sensor.t"),),
        rules=(
            CB.CombinedRule(source="temp", op=C.COMBINED_OP_GE, value="25", output="hot"),
            CB.CombinedRule(source="temp", op=C.COMBINED_OP_LT, value="18", output="cold"),
        ),
        default_output="ok",
    )
    assert CB.evaluate_combined(cfg, {"temp": _r("26", numeric=26.0)}).state == "hot"
    assert CB.evaluate_combined(cfg, {"temp": _r("15", numeric=15.0)}).state == "cold"
    assert CB.evaluate_combined(cfg, {"temp": _r("20", numeric=20.0)}).state == "ok"


# ── Missing sources ──────────────────────────────────────────────────────────


def test_missing_source_when_entity_empty():
    cfg = CB.CombinedConfig(
        slug="m", display_name="M",
        sources=(CB.CombinedSource(key="s", role="custom", entity=None),),
        rules=(),
        default_output="x",
    )
    res = CB.evaluate_combined(cfg, {})
    assert "s" in res.missing_sources
    assert res.degraded is True


# ── Derived binary sensors ───────────────────────────────────────────────────


def test_derived_any_open_role_match():
    cfg = CB.CombinedConfig(
        slug="o", display_name="O",
        sources=(
            CB.CombinedSource(key="w1", role="open_contact", entity="binary_sensor.w1"),
            CB.CombinedSource(key="w2", role="open_contact", entity="binary_sensor.w2"),
        ),
        rules=(),
        default_output="0",
        derived=(
            CB.DerivedSensor(slug="any_open", name="Any Open", device_class="opening",
                             target="open_contact", op=C.COMBINED_OP_EQ, value="on"),
        ),
    )
    readings = {"w1": _r("off"), "w2": _r("on")}
    res = CB.evaluate_combined(cfg, readings)
    assert CB.evaluate_derived(cfg.derived[0], cfg, readings, res) is True
    readings = {"w1": _r("off"), "w2": _r("off")}
    res = CB.evaluate_combined(cfg, readings)
    assert CB.evaluate_derived(cfg.derived[0], cfg, readings, res) is False


def test_derived_against_output():
    cfg = CB.CombinedConfig(
        slug="o", display_name="O", output_type=C.OUTPUT_TYPE_CODE,
        sources=(CB.CombinedSource(key="s", role="open_contact", entity="binary_sensor.s"),),
        rules=(CB.CombinedRule(source="s", op=C.COMBINED_OP_UNAVAILABLE, output=9),),
        default_output=0,
        derived=(
            CB.DerivedSensor(slug="any_unclear", name="Any Unclear", device_class="problem",
                             target="__output__", op=C.COMBINED_OP_EQ, value="9"),
        ),
    )
    readings = {"s": _r(None, available=False)}
    res = CB.evaluate_combined(cfg, readings)
    assert res.state == "9"
    assert CB.evaluate_derived(cfg.derived[0], cfg, readings, res) is True


# ── Parsing ──────────────────────────────────────────────────────────────────


def test_parse_combined_roundtrip():
    raw = {
        "display_name": "Opening",
        "output_type": "code",
        "sources": [
            {"key": "open", "role": "open_contact", "entity": "binary_sensor.o"},
            {"role": "tilt_contact", "entity": "binary_sensor.t"},  # key from role
        ],
        "rules": [
            {"source": "open", "op": "unavailable", "output": 9},
            {"source": "open", "op": "eq", "value": "on", "output": 2},
            {"source": "bad", "op": "??", "output": 1},  # invalid op → skipped
        ],
        "default_output": 0,
        "code_legend": {"0": "closed"},
        "derived": [{"slug": "any_open", "target": "open_contact", "op": "eq", "value": "on"}],
    }
    cfg = CB.parse_combined("opening_state", raw)
    assert cfg is not None
    assert cfg.output_type == "code"
    assert len(cfg.sources) == 2
    assert cfg.sources[1].key == "tilt_contact"
    assert len(cfg.rules) == 2  # invalid op skipped
    assert cfg.derived[0].slug == "any_open"


def test_parse_combined_garbage_returns_none():
    assert CB.parse_combined("x", "not a dict") is None
