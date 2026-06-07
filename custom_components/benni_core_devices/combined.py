"""Combined-Atomic-Engine v0 (LH §6).

Pure, HA-frei, in pytest testbar. Bildet einfache First-Match-Wins-/
Truth-Table-Logiken über mehrere Quellen ab — z. B. Opening/Fenster-Logik.

Bewusste v0-Grenzen: kein Timer, kein Latch, keine History. Nur:
- mehrere Quellen mit Rolle + Entity
- First-Match-Wins-Regelliste mit einfachen Bedingungen
- Default-Regel + Reason
- Output-Typen enum / code / boolean / number
- einfache abgeleitete Binary-Sensoren (Gate-/Policy-Ausgaben)

Der Coordinator liefert die `SourceReading`s (aus HA-States); diese Datei trifft
nur reine Entscheidungen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .combined_expr import ExprError, as_bool, as_num, eval_expr, func_names, parse, refs
from .const import (
    COMBINED_OP_EQ,
    COMBINED_OP_GE,
    COMBINED_OP_GT,
    COMBINED_OP_LE,
    COMBINED_OP_LT,
    COMBINED_OP_NE,
    COMBINED_OP_UNAVAILABLE,
    COMBINED_OPERATOR_CHOICES,
    FAIL_SAFE_HOLD_LAST,
    FAIL_SAFE_OFF,
    FAIL_SAFE_OPEN,
    FAIL_SAFE_UNKNOWN,
    OUTPUT_TYPE_BOOLEAN,
    OUTPUT_TYPE_CODE,
    OUTPUT_TYPE_ENUM,
    OUTPUT_TYPE_NUMBER,
)

# Werte, die als "an/wahr" gelten (für boolean-Output + Derived-Sensoren).
_TRUTHY = frozenset({"on", "true", "yes", "1", "open", "home", "playing", "active"})

# v1.0 Node-Arten in derived_values[].
NODE_EXPR = "expr"
NODE_GATE = "gate"
NODE_HEALTH = "health"
NODE_LATCH = "latch"
NODE_PREVIOUS = "previous"
NODE_KINDS = (NODE_EXPR, NODE_GATE, NODE_HEALTH, NODE_LATCH, NODE_PREVIOUS)
SELF_REF = "self"


# ─────────────────────────────────────────────────────────────────────────────
# DATEN-STRUKTUREN
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceReading:
    """Snapshot einer Combined-Quelle."""

    value: str | None
    numeric: float | None = None
    available: bool = True
    # Attribute der Quell-Entity (für health-Node: atomic_quality/degraded/…).
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CombinedSource:
    """Eine Eingangsquelle des Combined."""

    key: str          # eindeutig innerhalb des Combined (Referenz in Regeln)
    role: str         # fachliche Rolle (open_contact, tilt_contact, ...)
    entity: str | None = None  # Raw-Entity-ID


@dataclass(frozen=True)
class CombinedRule:
    """Eine First-Match-Wins-Regel."""

    source: str            # CombinedSource.key
    op: str                # COMBINED_OP_*
    value: str | None = None
    output: Any = None
    reason: str | None = None


@dataclass(frozen=True)
class DerivedSensor:
    """Abgeleiteter Binary-Sensor (Gate-/Policy-Ausgabe)."""

    slug: str
    name: str
    device_class: str | None = None
    # Ziel: ein konkreter source.key, eine Rolle (any-match), oder "__output__".
    target: str = "__output__"
    op: str = COMBINED_OP_EQ
    value: str | None = None


@dataclass(frozen=True)
class DerivedValue:
    """Benannter Zwischenwert (v1.0): expr | gate | health | latch | previous."""

    name: str
    kind: str
    expr: str | None = None          # expr/gate
    set_expr: str | None = None      # latch
    reset_expr: str | None = None    # latch
    atomics: tuple[str, ...] = ()    # health: konsumierte source-keys
    fail_safe: str | None = None     # off|open|hold_last|unknown (sonst config-Default)


@dataclass(frozen=True)
class CombinedConfig:
    """Konfiguration eines Combined-Atomics."""

    slug: str
    display_name: str
    output_type: str = OUTPUT_TYPE_ENUM
    sources: tuple[CombinedSource, ...] = ()
    rules: tuple[CombinedRule, ...] = ()
    default_output: Any = None
    default_reason: str | None = None
    code_legend: dict[str, Any] = field(default_factory=dict)
    derived: tuple[DerivedSensor, ...] = ()
    # v1.0:
    derived_values: tuple[DerivedValue, ...] = ()
    fail_safe: str = FAIL_SAFE_UNKNOWN


@dataclass(frozen=True)
class CombinedPersisted:
    """Persistenter Zustand pro Combined (v1.0b: last_state + latch/previous)."""

    last_state: str | None = None
    node_states: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CombinedResult:
    """Auswertungsergebnis eines Combined-Atomics."""

    state: str
    output: Any
    reason: str
    matched_rule: int | None
    source_entities: dict[str, str]
    source_states: dict[str, Any]
    source_available: dict[str, bool]
    missing_sources: list[str]
    degraded: bool
    degraded_reason: list[str]
    # v1.0:
    derived: dict[str, Any] = field(default_factory=dict)
    node_states: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# OPERATOR-AUSWERTUNG
# ─────────────────────────────────────────────────────────────────────────────


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _TRUTHY


def _match(reading: SourceReading | None, op: str, value: str | None) -> bool:
    """Wertet eine einzelne Bedingung aus."""
    unavailable = reading is None or not reading.available or reading.value is None
    if op == COMBINED_OP_UNAVAILABLE:
        return unavailable
    if unavailable:
        # eq/ne/numeric matchen nicht auf unverfügbaren Quellen.
        return False
    assert reading is not None
    if op == COMBINED_OP_EQ:
        return str(reading.value) == str(value)
    if op == COMBINED_OP_NE:
        return str(reading.value) != str(value)
    # numerische Vergleiche
    if op in (COMBINED_OP_LT, COMBINED_OP_LE, COMBINED_OP_GT, COMBINED_OP_GE):
        left = reading.numeric
        try:
            right = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
        if left is None:
            return False
        if op == COMBINED_OP_LT:
            return left < right
        if op == COMBINED_OP_LE:
            return left <= right
        if op == COMBINED_OP_GT:
            return left > right
        if op == COMBINED_OP_GE:
            return left >= right
    return False


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT-COERCION
# ─────────────────────────────────────────────────────────────────────────────


def coerce_output(output: Any, output_type: str) -> str:
    """Wandelt einen Regel-Output in den finalen State-String."""
    if output is None:
        return "unknown"
    if output_type == OUTPUT_TYPE_BOOLEAN:
        return "on" if _truthy(output) else "off"
    if output_type == OUTPUT_TYPE_NUMBER:
        try:
            num = float(output)
        except (TypeError, ValueError):
            return str(output)
        return str(int(num)) if num.is_integer() else str(num)
    # enum / code: roher String
    return str(output)


# ─────────────────────────────────────────────────────────────────────────────
# HAUPTAUSWERTUNG
# ─────────────────────────────────────────────────────────────────────────────


def _autoscalar(reading: SourceReading | None) -> Any:
    """Quelle → Skalar für die Expression-Engine (Zahl, Rohstring oder None)."""
    if reading is None or not reading.available or reading.value is None:
        return None
    if reading.numeric is not None:
        return reading.numeric
    return reading.value


def _wrap(value: Any) -> SourceReading:
    """Derived-Wert → SourceReading-artig (für die v0-Regel-Matcher)."""
    if value is None:
        return SourceReading(value=None, available=False)
    if isinstance(value, bool):
        return SourceReading(value=("on" if value else "off"), numeric=(1.0 if value else 0.0))
    if isinstance(value, (int, float)):
        return SourceReading(value=str(value), numeric=float(value))
    return SourceReading(value=str(value), numeric=as_num(value))


def _failsafe_value(kind: str, mode: str | None, prev: Any) -> Any:
    if mode == FAIL_SAFE_HOLD_LAST:
        return prev
    if kind in (NODE_GATE, NODE_LATCH):
        if mode == FAIL_SAFE_OFF:
            return False
        if mode == FAIL_SAFE_OPEN:
            return True
    return None


def _failsafe_output(mode: str, prev: Any) -> Any:
    if mode == FAIL_SAFE_HOLD_LAST:
        return prev
    if mode == FAIL_SAFE_OFF:
        return "off"
    if mode == FAIL_SAFE_OPEN:
        return "open"
    return None


def _derived_names(config: CombinedConfig) -> set[str]:
    return {d.name for d in config.derived_values}


def _node_dep_refs(dv: DerivedValue) -> set[str]:
    out: set[str] = set()
    for e in (dv.expr, dv.set_expr, dv.reset_expr):
        if e:
            try:
                out |= refs(parse(e))
            except ExprError:
                pass
    out |= set(dv.atomics)
    return out


def _ordered_derived(config: CombinedConfig) -> list[DerivedValue]:
    """Topo-Sort der derived_values nach Abhängigkeiten (DAG). Zyklus → Listenreihenfolge."""
    names = _derived_names(config)
    by_name = {d.name: d for d in config.derived_values}
    order: list[DerivedValue] = []
    state: dict[str, int] = {}  # 0=visiting, 1=done

    def visit(name: str) -> None:
        if state.get(name) == 1 or name not in by_name:
            return
        if state.get(name) == 0:
            return  # Zyklus — abbrechen, validate meldet es
        state[name] = 0
        dv = by_name[name]
        for dep in _node_dep_refs(dv):
            if dep in names:
                visit(dep)
        state[name] = 1
        order.append(dv)

    for d in config.derived_values:
        visit(d.name)
    # Falls durch Zyklus etwas fehlt: anhängen.
    for d in config.derived_values:
        if d not in order:
            order.append(d)
    return order


def _eval_node(
    dv: DerivedValue, env: dict[str, Any], readings: dict[str, SourceReading],
    config: CombinedConfig, prev_states: dict[str, Any],
) -> Any:
    fail_safe = dv.fail_safe or config.fail_safe
    prev = prev_states.get(dv.name)
    if dv.kind == NODE_EXPR:
        try:
            v = as_num(eval_expr(dv.expr or "", env))
        except ExprError:
            v = None
        return v if v is not None else _failsafe_value(NODE_EXPR, fail_safe, prev)
    if dv.kind == NODE_GATE:
        try:
            v = as_bool(eval_expr(dv.expr or "", env))
        except ExprError:
            v = None
        return v if v is not None else _failsafe_value(NODE_GATE, fail_safe, prev)
    if dv.kind == NODE_HEALTH:
        worst = "ok"
        for key in dv.atomics:
            r = readings.get(key)
            if r is None or not r.available or r.value is None:
                worst = "problem"
                break
            q = str(r.attributes.get("atomic_quality") or "ok")
            if q == "unavailable" or r.attributes.get("missing_required"):
                worst = "problem"
                break
            if q == "degraded" or r.attributes.get("degraded"):
                worst = "degraded"
        return worst
    if dv.kind == NODE_LATCH:
        set_v = reset_v = None
        try:
            set_v = as_bool(eval_expr(dv.set_expr or "false", env))
        except ExprError:
            set_v = None
        try:
            reset_v = as_bool(eval_expr(dv.reset_expr or "false", env))
        except ExprError:
            reset_v = None
        if set_v:
            return True
        if reset_v:
            return False
        if prev is not None:
            return bool(prev)
        return _failsafe_value(NODE_LATCH, fail_safe, prev)
    if dv.kind == NODE_PREVIOUS:
        return env.get(SELF_REF)
    return None


def _resolve(ref: str, readings: dict[str, SourceReading], env: dict[str, Any]) -> SourceReading | None:
    if ref in readings:
        return readings[ref]
    if ref in env:
        return _wrap(env[ref])
    return None


def _maybe_ref(output: Any, env: dict[str, Any]) -> Any:
    """Erlaubt Output ``"${name}"`` → löst auf einen derived/source-Wert auf."""
    if isinstance(output, str) and output.startswith("${") and output.endswith("}"):
        return env.get(output[2:-1].strip())
    return output


def evaluate_combined(
    config: CombinedConfig,
    readings: dict[str, SourceReading],
    persisted: "CombinedPersisted | None" = None,
    now: Any = None,
) -> CombinedResult:
    """Wertet derived_values (v1.0) + First-Match-Regeln (v0) aus."""
    source_entities: dict[str, str] = {}
    source_states: dict[str, Any] = {}
    source_available: dict[str, bool] = {}
    missing_sources: list[str] = []
    degraded_reason: list[str] = []

    for src in config.sources:
        if not src.entity:
            missing_sources.append(src.key)
            continue
        source_entities[src.key] = src.entity
        reading = readings.get(src.key)
        available = reading is not None and reading.available and reading.value is not None
        source_states[src.key] = reading.value if reading else None
        source_available[src.key] = available
        if not available:
            degraded_reason.append(f"{src.key}: unavailable")

    prev_state = persisted.last_state if persisted else None
    prev_nodes = dict(persisted.node_states) if persisted else {}

    # ── derived_values: env aufbauen + in Topo-Reihenfolge auswerten ────────
    env: dict[str, Any] = {src.key: _autoscalar(readings.get(src.key)) for src in config.sources}
    env[SELF_REF] = prev_state
    derived_out: dict[str, Any] = {}
    node_states: dict[str, Any] = {}
    for dv in _ordered_derived(config):
        val = _eval_node(dv, env, readings, config, prev_nodes)
        env[dv.name] = val
        derived_out[dv.name] = val
        node_states[dv.name] = val

    # ── Regeln (v0) — referenzieren Quellen, derived oder ${self} ───────────
    matched: int | None = None
    output = config.default_output
    reason = config.default_reason or "default"
    for index, rule in enumerate(config.rules):
        if _match(_resolve(rule.source, readings, env), rule.op, rule.value):
            matched = index
            output = rule.output
            reason = rule.reason or _auto_reason(rule)
            break

    output = _maybe_ref(output, env)
    if output is None:
        output = _failsafe_output(config.fail_safe, prev_state)

    degraded = bool(degraded_reason) or bool(missing_sources)
    for s in missing_sources:
        degraded_reason.append(f"{s}: missing entity")

    return CombinedResult(
        state=coerce_output(output, config.output_type),
        output=output,
        reason=reason,
        matched_rule=matched,
        source_entities=source_entities,
        source_states=source_states,
        source_available=source_available,
        missing_sources=missing_sources,
        degraded=degraded,
        degraded_reason=degraded_reason,
        derived=derived_out,
        node_states=node_states,
    )


def validate_combined_v1(config: CombinedConfig) -> list[str]:
    """Dry-Run-Validierung: Parse, unbekannte Refs, Zyklen, Zeit-Latch (since=v1.1)."""
    errors: list[str] = []
    names = _derived_names(config)
    source_keys = {s.key for s in config.sources}
    allowed = source_keys | names | {SELF_REF}

    def check_expr(label: str, e: str | None, is_latch: bool = False) -> None:
        if not e:
            return
        try:
            ast = parse(e)
        except ExprError as err:
            errors.append(f"{label}: Parse-Fehler: {err}")
            return
        for r in refs(ast):
            if r not in allowed:
                errors.append(f"{label}: unbekannte Referenz ${{{r}}}")
        v11 = func_names(ast) & {"since"}
        if v11:
            errors.append(
                f"{label}: '{sorted(v11)[0]}' ist v1.1 (Timer/Scheduling) — in v1.0 nicht erlaubt"
            )

    for dv in config.derived_values:
        if dv.kind not in NODE_KINDS:
            errors.append(f"{dv.name}: unbekannter Node-Typ {dv.kind!r}")
            continue
        if dv.kind in (NODE_EXPR, NODE_GATE):
            check_expr(dv.name, dv.expr)
        elif dv.kind == NODE_LATCH:
            check_expr(f"{dv.name}.set", dv.set_expr, is_latch=True)
            check_expr(f"{dv.name}.reset", dv.reset_expr, is_latch=True)
        elif dv.kind == NODE_HEALTH:
            for a in dv.atomics:
                if a not in source_keys:
                    errors.append(f"{dv.name}: health-Quelle {a!r} ist keine Source")

    # Zyklus-Erkennung
    by_name = {d.name: d for d in config.derived_values}
    visiting: set[str] = set()
    done: set[str] = set()

    def dfs(name: str, stack: list[str]) -> None:
        if name in done or name not in by_name:
            return
        if name in visiting:
            errors.append(f"Zyklus in derived_values: {' → '.join(stack + [name])}")
            return
        visiting.add(name)
        for dep in _node_dep_refs(by_name[name]):
            if dep in names:
                dfs(dep, stack + [name])
        visiting.discard(name)
        done.add(name)

    for d in config.derived_values:
        dfs(d.name, [])
    return errors


def _auto_reason(rule: CombinedRule) -> str:
    if rule.op == COMBINED_OP_UNAVAILABLE:
        return f"{rule.source} unavailable"
    return f"{rule.source} {rule.op} {rule.value}"


# ─────────────────────────────────────────────────────────────────────────────
# DERIVED BINARY SENSORS
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_derived(
    derived: DerivedSensor,
    config: CombinedConfig,
    readings: dict[str, SourceReading],
    result: CombinedResult,
) -> bool:
    """Wertet einen abgeleiteten Binary-Sensor aus.

    `target` kann sein:
    - "__output__" — vergleicht gegen den Combined-Output
    - ein source.key — vergleicht gegen diese eine Quelle
    - eine Rolle — any-match über alle Quellen dieser Rolle
    """
    if derived.target == "__output__":
        reading = SourceReading(value=result.state, numeric=None, available=True)
        return _match(reading, derived.op, derived.value)

    source_keys = {s.key for s in config.sources}
    if derived.target in source_keys:
        return _match(readings.get(derived.target), derived.op, derived.value)

    # Rolle → any-match
    role_keys = [s.key for s in config.sources if s.role == derived.target]
    return any(_match(readings.get(k), derived.op, derived.value) for k in role_keys)


# ─────────────────────────────────────────────────────────────────────────────
# PARSING (aus Storage / Import / WebSocket)
# ─────────────────────────────────────────────────────────────────────────────


def parse_combined(slug: str, raw: Any) -> CombinedConfig | None:
    """Parst eine gespeicherte Combined-Konfiguration robust.

    Ungültige Teile werden übersprungen statt zu crashen (LH §4: nie hart
    brechen). Returns None nur, wenn `raw` gar kein Mapping ist.
    """
    if not isinstance(raw, dict):
        return None
    output_type = raw.get("output_type", OUTPUT_TYPE_ENUM)
    if output_type not in (
        OUTPUT_TYPE_ENUM,
        OUTPUT_TYPE_CODE,
        OUTPUT_TYPE_BOOLEAN,
        OUTPUT_TYPE_NUMBER,
    ):
        output_type = OUTPUT_TYPE_ENUM

    sources: list[CombinedSource] = []
    for item in raw.get("sources") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or item.get("role") or "").strip()
        if not key:
            continue
        sources.append(
            CombinedSource(
                key=key,
                role=str(item.get("role") or "custom"),
                entity=(str(item["entity"]) if item.get("entity") else None),
            )
        )

    rules: list[CombinedRule] = []
    for item in raw.get("rules") or []:
        if not isinstance(item, dict):
            continue
        op = item.get("op")
        if op not in COMBINED_OPERATOR_CHOICES:
            continue
        src = str(item.get("source") or "").strip()
        if not src:
            continue
        rules.append(
            CombinedRule(
                source=src,
                op=op,
                value=(str(item["value"]) if item.get("value") is not None else None),
                output=item.get("output"),
                reason=(str(item["reason"]) if item.get("reason") else None),
            )
        )

    derived: list[DerivedSensor] = []
    for item in raw.get("derived") or []:
        if not isinstance(item, dict):
            continue
        dslug = str(item.get("slug") or "").strip()
        if not dslug:
            continue
        op = item.get("op") or COMBINED_OP_EQ
        if op not in COMBINED_OPERATOR_CHOICES:
            op = COMBINED_OP_EQ
        derived.append(
            DerivedSensor(
                slug=dslug,
                name=str(item.get("name") or dslug),
                device_class=(
                    str(item["device_class"]) if item.get("device_class") else None
                ),
                target=str(item.get("target") or "__output__"),
                op=op,
                value=(str(item["value"]) if item.get("value") is not None else None),
            )
        )

    derived_values: list[DerivedValue] = []
    for item in raw.get("derived_values") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        kind = str(item.get("kind") or "").strip()
        if not name or kind not in NODE_KINDS:
            continue
        atomics = item.get("atomics") or []
        derived_values.append(
            DerivedValue(
                name=name,
                kind=kind,
                expr=(str(item["expr"]) if item.get("expr") is not None else None),
                set_expr=(str(item["set"]) if item.get("set") is not None else None),
                reset_expr=(str(item["reset"]) if item.get("reset") is not None else None),
                atomics=tuple(str(a) for a in atomics if a),
                fail_safe=(str(item["fail_safe"]) if item.get("fail_safe") else None),
            )
        )

    legend = raw.get("code_legend")
    code_legend = dict(legend) if isinstance(legend, dict) else {}
    diagnostics = raw.get("diagnostics") if isinstance(raw.get("diagnostics"), dict) else {}
    fail_safe = str(raw.get("fail_safe") or diagnostics.get("fail_safe") or FAIL_SAFE_UNKNOWN)

    return CombinedConfig(
        slug=slug,
        display_name=str(raw.get("display_name") or slug),
        output_type=output_type,
        sources=tuple(sources),
        rules=tuple(rules),
        default_output=raw.get("default_output"),
        default_reason=(
            str(raw["default_reason"]) if raw.get("default_reason") else None
        ),
        code_legend=code_legend,
        derived=tuple(derived),
        derived_values=tuple(derived_values),
        fail_safe=fail_safe,
    )
