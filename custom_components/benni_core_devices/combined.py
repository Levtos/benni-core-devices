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

from .const import (
    COMBINED_OP_EQ,
    COMBINED_OP_GE,
    COMBINED_OP_GT,
    COMBINED_OP_LE,
    COMBINED_OP_LT,
    COMBINED_OP_NE,
    COMBINED_OP_UNAVAILABLE,
    COMBINED_OPERATOR_CHOICES,
    OUTPUT_TYPE_BOOLEAN,
    OUTPUT_TYPE_CODE,
    OUTPUT_TYPE_ENUM,
    OUTPUT_TYPE_NUMBER,
)

# Werte, die als "an/wahr" gelten (für boolean-Output + Derived-Sensoren).
_TRUTHY = frozenset({"on", "true", "yes", "1", "open", "home", "playing", "active"})


# ─────────────────────────────────────────────────────────────────────────────
# DATEN-STRUKTUREN
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceReading:
    """Snapshot einer Combined-Quelle."""

    value: str | None
    numeric: float | None = None
    available: bool = True


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


def evaluate_combined(
    config: CombinedConfig, readings: dict[str, SourceReading]
) -> CombinedResult:
    """Wertet die First-Match-Wins-Regeln aus (LH §6)."""
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

    matched: int | None = None
    output = config.default_output
    reason = config.default_reason or "default"
    for index, rule in enumerate(config.rules):
        if _match(readings.get(rule.source), rule.op, rule.value):
            matched = index
            output = rule.output
            reason = rule.reason or _auto_reason(rule)
            break

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
    )


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

    legend = raw.get("code_legend")
    code_legend = dict(legend) if isinstance(legend, dict) else {}

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
    )
