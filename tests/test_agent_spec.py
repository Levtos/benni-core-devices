"""Tests für den Agent-Briefing-Generator (agent_spec.py)."""

from __future__ import annotations

import bcd_agent_spec as AS
import bcd_device_types as DT


def test_briefing_contains_core_contract():
    md = AS.build_briefing("0.3.2", "benni", "devices: []\n")
    # Version + Profil
    assert "0.3.2" in md
    assert "benni" in md
    # Golden rules / blocked sources
    assert "_atomic" in md and "_combined" in md and "_gate" in md
    assert "benni_device_*" in md
    # Metadaten-Ableitung + Workflow
    assert "auto-derived" in md
    assert "dry_run" in md
    assert "set_combined" in md and "bulk_import" in md
    # Klassen + Rollen sind eingebettet
    assert "media_device" in md and "opening" in md
    assert "primary_state" in md and "open_contact" in md
    # Export-Kontext eingebettet
    assert "devices: []" in md


def test_briefing_lists_all_classes_and_roles():
    md = AS.build_briefing("0.3.2", "benni", "")
    for cls in DT.ALL_ATOMIC_CLASSES:
        assert cls in md, f"{cls} fehlt im Briefing"


def test_json_schema_shape():
    schema = AS.build_json_schema()
    assert schema["$schema"].startswith("http://json-schema.org/draft-07")
    device = schema["$defs"]["device"]
    assert device["properties"]["atomic_class"]["enum"] == list(DT.ALL_ATOMIC_CLASSES)
    assert device["properties"]["slug"]["pattern"] == "^[a-z0-9_]+$"
    binding = schema["$defs"]["binding"]
    assert "open_contact" in binding["properties"]["role"]["enum"]
    # required-Felder
    assert "slug" in device["required"] and "atomic_class" in device["required"]


def test_briefing_uses_profile_prefix():
    md = AS.build_briefing("0.3.2", "eltern", "")
    assert "eltern_device_*" in md
    assert "sensor.eltern_device_" in md
