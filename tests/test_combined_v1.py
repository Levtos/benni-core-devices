"""Tests für Combined v1.0 (Expression-Engine + Nodes + Validierung)."""

from __future__ import annotations

import bcd_combined as CB
import bcd_combined_expr as E


# ── Expression-Engine ────────────────────────────────────────────────────────


def test_expr_arithmetic_none_div0():
    assert E.eval_expr("${a} + ${b}", {"a": 2, "b": 3}) == 5
    assert E.eval_expr("${a} / ${b}", {"a": 1, "b": 0}) is None       # div0 → None
    assert E.eval_expr("${a} + ${b}", {"a": None, "b": 3}) is None    # None-Propagation


def test_expr_functions():
    assert E.eval_expr("clamp(${x}, 0, 10)", {"x": 15}) == 10
    assert E.eval_expr("round(${x}, 1)", {"x": 3.14159}) == 3.1
    assert E.eval_expr("min(${a}, ${b}, ${c})", {"a": 3, "b": 1, "c": 2}) == 1
    assert E.eval_expr("max(${a}, ${b})", {"a": 3, "b": 7}) == 7
    assert E.eval_expr("clamp(${x}, 0, ${hi})", {"x": 5, "hi": None}) is None


def test_gate_trees():
    assert E.eval_expr("any([${a}, ${b}])", {"a": "off", "b": "on"}) is True
    assert E.eval_expr("all([${a}, ${b}])", {"a": "on", "b": "off"}) is False
    assert E.eval_expr("not(${a})", {"a": "off"}) is True
    assert E.eval_expr("${a} and ${b}", {"a": True, "b": False}) is False
    assert E.eval_expr("any([${a}, ${b}])", {"a": None, "b": "on"}) is None  # None-Prop
    assert E.eval_expr("${t} > 25", {"t": 26}) is True


def test_expr_string_compare():
    assert E.eval_expr('${m} == "tv"', {"m": "tv"}) is True
    assert E.eval_expr('${m} == "tv"', {"m": "appletv"}) is False


def test_dew_point_formula():
    v = E.eval_expr("${t} - (100 - ${rh}) / 5", {"t": 22.0, "rh": 60.0})
    assert abs(v - 14.0) < 1e-9


def test_expr_parse_error():
    import pytest
    with pytest.raises(E.ExprError):
        E.parse("${a} +")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _src(key, role="custom", entity="x"):
    return CB.CombinedSource(key=key, role=role, entity=entity)


def _r(value, numeric=None, available=True, attrs=None):
    return CB.SourceReading(value=value, numeric=numeric, available=available, attributes=attrs or {})


def _cfg(**kw):
    base = dict(slug="c", display_name="C")
    base.update(kw)
    return CB.CombinedConfig(**base)


# ── gate node ────────────────────────────────────────────────────────────────


def test_gate_node_unsafe_for_climate():
    cfg = _cfg(
        output_type="boolean",
        sources=(_src("open_a", "open_contact"), _src("tilt_a", "tilt_contact")),
        derived_values=(
            CB.DerivedValue(name="any_open", kind="gate", expr="any([${open_a}])"),
            CB.DerivedValue(name="any_tilt", kind="gate", expr="any([${tilt_a}])"),
            CB.DerivedValue(name="unsafe", kind="gate", expr="any([${any_open}, ${any_tilt}])"),
        ),
        rules=(CB.CombinedRule(source="unsafe", op="eq", value="on", output=True),),
        default_output=False,
    )
    res = CB.evaluate_combined(cfg, {"open_a": _r("on"), "tilt_a": _r("off")})
    assert res.derived["unsafe"] is True
    assert res.state == "on"


# ── expr node (number output via ${ref}) ─────────────────────────────────────


def test_expr_node_number_output():
    cfg = _cfg(
        output_type="number",
        sources=(_src("t"), _src("rh")),
        derived_values=(CB.DerivedValue(name="dew", kind="expr", expr="round(${t} - (100 - ${rh})/5, 1)"),),
        rules=(),
        default_output="${dew}",
    )
    res = CB.evaluate_combined(cfg, {"t": _r("22.0", 22.0), "rh": _r("60", 60.0)})
    assert res.state == "14"


# ── health node ──────────────────────────────────────────────────────────────


def test_health_node():
    cfg = _cfg(
        output_type="enum",
        sources=(_src("a"), _src("b")),
        derived_values=(CB.DerivedValue(name="h", kind="health", atomics=("a", "b")),),
        default_output="${h}",
    )
    ok = CB.evaluate_combined(cfg, {
        "a": _r("on", attrs={"atomic_quality": "ok"}),
        "b": _r("on", attrs={"atomic_quality": "degraded"}),
    })
    assert ok.state == "degraded"
    prob = CB.evaluate_combined(cfg, {
        "a": _r("on", attrs={"atomic_quality": "ok"}),
        "b": _r(None, available=False),
    })
    assert prob.state == "problem"


# ── latch (Schmitt-Hysterese + hold + boot fail_safe) ────────────────────────


def test_latch_hysteresis_hold_and_boot():
    cfg = _cfg(
        output_type="boolean",
        sources=(_src("lux"),),
        derived_values=(CB.DerivedValue(name="dark", kind="latch",
                                        set_expr="${lux} < 50", reset_expr="${lux} >= 100",
                                        fail_safe="off"),),
        default_output="${dark}",
    )
    r1 = CB.evaluate_combined(cfg, {"lux": _r("30", 30.0)})
    assert r1.state == "on"
    p1 = CB.CombinedPersisted(last_state=r1.state, node_states=r1.node_states)
    r2 = CB.evaluate_combined(cfg, {"lux": _r("70", 70.0)}, persisted=p1)
    assert r2.state == "on"  # hält zwischen den Schwellen
    p2 = CB.CombinedPersisted(last_state=r2.state, node_states=r2.node_states)
    r3 = CB.evaluate_combined(cfg, {"lux": _r("120", 120.0)}, persisted=p2)
    assert r3.state == "off"
    # Boot ohne Persistenz, zwischen den Schwellen → fail_safe off
    r0 = CB.evaluate_combined(cfg, {"lux": _r("70", 70.0)})
    assert r0.state == "off"


# ── previous (${self}) über simulierten Restart ──────────────────────────────


def test_previous_self_sticky():
    cfg = _cfg(
        output_type="enum",
        sources=(_src("trigger"),),
        rules=(
            CB.CombinedRule(source="trigger", op="eq", value="on", output="active"),
            CB.CombinedRule(source="self", op="ne", value="", output="${self}"),
        ),
        default_output="idle",
    )
    r1 = CB.evaluate_combined(cfg, {"trigger": _r("on")})
    assert r1.state == "active"
    # Restart-Simulation: persisted last_state weiterreichen, trigger off
    p = CB.CombinedPersisted(last_state="active", node_states=r1.node_states)
    r2 = CB.evaluate_combined(cfg, {"trigger": _r("off")}, persisted=p)
    assert r2.state == "active"


# ── Validierung (Dry-Run) ────────────────────────────────────────────────────


def test_validate_rejects_cycle():
    cfg = _cfg(
        sources=(_src("a"),),
        derived_values=(
            CB.DerivedValue(name="x", kind="gate", expr="${y}"),
            CB.DerivedValue(name="y", kind="gate", expr="${x}"),
        ),
    )
    assert any("Zyklus" in e for e in CB.validate_combined_v1(cfg))


def test_validate_rejects_unknown_ref_and_parse():
    cfg = _cfg(
        sources=(_src("a"),),
        derived_values=(
            CB.DerivedValue(name="x", kind="gate", expr="${nope}"),
            CB.DerivedValue(name="y", kind="expr", expr="${a} +"),
        ),
    )
    errs = CB.validate_combined_v1(cfg)
    assert any("nope" in e for e in errs)
    assert any("Parse" in e for e in errs)


def test_validate_rejects_time_latch():
    cfg = _cfg(
        sources=(_src("a"),),
        derived_values=(CB.DerivedValue(name="l", kind="latch",
                                        set_expr="${a}", reset_expr="since(${a}) >= 3600"),),
    )
    # since() ist v1.0 nicht erlaubt → Fehler (unbekannte Funktion / v1.1)
    assert any("l.reset" in e for e in CB.validate_combined_v1(cfg))


def test_validate_clean_config_no_errors():
    cfg = _cfg(
        sources=(_src("open_a", "open_contact"),),
        derived_values=(CB.DerivedValue(name="any_open", kind="gate", expr="any([${open_a}])"),),
    )
    assert CB.validate_combined_v1(cfg) == []


# ── Parsing ──────────────────────────────────────────────────────────────────


def test_parse_derived_values_and_fail_safe():
    raw = {
        "display_name": "X", "output_type": "boolean",
        "sources": [{"key": "a", "role": "custom", "entity": "binary_sensor.a"}],
        "derived_values": [
            {"name": "g", "kind": "gate", "expr": "any([${a}])"},
            {"name": "l", "kind": "latch", "set": "${a}", "reset": "not(${a})", "fail_safe": "off"},
            {"name": "bad", "kind": "nope"},  # ungültig → übersprungen
        ],
        "fail_safe": "hold_last",
    }
    cfg = CB.parse_combined("x", raw)
    assert cfg.fail_safe == "hold_last"
    assert len(cfg.derived_values) == 2
    assert cfg.derived_values[0].kind == "gate"
    assert cfg.derived_values[1].set_expr == "${a}"
