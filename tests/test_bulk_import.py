"""Tests for HA-free bulk import/export helpers."""

from __future__ import annotations

import json

import pytest

import bcd_bulk_import as BI


def _options():
    return {
        "devices": {
            "living_tv": {
                "atomic_class": "media_device",
                "variant": "tv",
                "display_name": "Wohnzimmer TV",
                "sources": [
                    {"role": "primary_state", "entity": "media_player.living_tv"},
                    {"role": "power_meter", "entity": "sensor.living_tv_power"},
                ],
                "controls": [{"role": "wake_mac", "value": "AA:BB:CC:DD:EE:FF"}],
                "metadata_sources": [],
                "diagnostics": {"fail_safe": "hold_last"},
                "watt_threshold_on": 8,
                "sticky_hold_seconds": 30,
            }
        },
        "combineds": {
            "opening_state": {
                "display_name": "Opening State",
                "output_type": "code",
                "sources": [
                    {"key": "open", "role": "open_contact", "entity": "binary_sensor.open"},
                    {"key": "tilt", "role": "tilt_contact", "entity": "binary_sensor.tilt"},
                ],
                "rules": [
                    {"source": "open", "op": "unavailable", "output": 9},
                    {"source": "open", "op": "eq", "value": "on", "output": 2},
                    {"source": "tilt", "op": "eq", "value": "on", "output": 1},
                ],
                "default_output": 0,
            }
        },
        "light_groups": {
            "living_lights": {
                "display_name": "Wohnzimmer Licht",
                "members": ["light.living_a", "light.living_b"],
            }
        },
    }


def test_export_yaml_round_trips_through_bulk_apply():
    exported = BI.export_yaml_from_options(_options())

    assert BI.replace_from_payload(exported) is False
    valid, groups, combineds = BI.parse_bulk_payload(exported)
    devices, new_groups, new_combineds = BI.apply_bulk({}, valid, groups, combineds)

    assert devices == _options()["devices"]
    assert new_groups == _options()["light_groups"]
    assert new_combineds == _options()["combineds"]


def test_file_replace_flag_is_clean_slate():
    opts = _options()
    exported = json.dumps({
        "replace": True,
        "devices": [{"slug": slug, **conf} for slug, conf in opts["devices"].items()],
        "combineds": opts["combineds"],
        "light_groups": opts["light_groups"],
    })
    current = {
        "devices": {"old": {"atomic_class": "light", "display_name": "Old"}},
        "combineds": {"old": {"display_name": "Old"}},
        "light_groups": {"old": {"display_name": "Old", "members": []}},
    }

    valid, groups, combineds = BI.parse_bulk_payload(exported)
    devices, new_groups, new_combineds = BI.apply_bulk(
        current, valid, groups, combineds, replace=BI.replace_from_payload(exported)
    )

    assert devices == _options()["devices"]
    assert new_groups == _options()["light_groups"]
    assert new_combineds == _options()["combineds"]


def test_replace_flag_must_be_boolean():
    with pytest.raises(ValueError, match="replace must be true or false"):
        BI.replace_from_payload(json.dumps({"replace": "true", "devices": []}))


def test_attribute_binding_requires_entity():
    payload = json.dumps({
        "devices": [{
            "slug": "dwd_home",
            "atomic_class": "environment",
            "sources": [{"role": "temperature_source", "attribute": "temperature"}],
        }]
    })

    with pytest.raises(ValueError, match="attribute braucht entity"):
        BI.parse_bulk_payload(payload)


def test_file_error_response_keeps_bulk_report_shape():
    response = BI.error_response(True, False, "Import file not found")

    assert response == {
        "dry_run": True,
        "replace": False,
        "devices": 0,
        "groups": 0,
        "combineds": 0,
        "report": [],
        "combined_report": [],
        "combineds_in": 0,
        "error": "Import file not found",
    }
