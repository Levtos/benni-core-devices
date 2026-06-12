"""HA-free slot reading helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .logic import SlotReading


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def slot_reading_from_values(
    state_value: Any,
    attributes: dict[str, Any] | None = None,
    *,
    attribute: str | None = None,
    last_updated: datetime | None = None,
) -> SlotReading:
    """Build a SlotReading from an entity state or one of its attributes."""
    attrs = dict(attributes or {})
    raw = attrs.get(attribute) if attribute else state_value
    if raw is None:
        return SlotReading(value=None, attributes=attrs, last_updated=last_updated)
    return SlotReading(
        value=str(raw),
        numeric=_numeric(raw),
        attributes=attrs,
        last_updated=last_updated,
    )
