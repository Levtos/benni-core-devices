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
        "masters": {},
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
    valid, groups, combineds, masters, removals = BI.parse_bulk_payload(exported)
    devices, new_groups, new_combineds, new_masters = BI.apply_bulk(
        {}, valid, groups, combineds, masters, removals
    )

    assert devices == _options()["devices"]
    assert new_groups == _options()["light_groups"]
    assert new_combineds == _options()["combineds"]
    assert new_masters == _options()["masters"]


def test_file_replace_flag_is_clean_slate():
    opts = _options()
    exported = json.dumps({
        "replace": True,
        "devices": [{"slug": slug, **conf} for slug, conf in opts["devices"].items()],
        "combineds": opts["combineds"],
        "masters": {"living_tv": {"display_name": "Living TV Master"}},
        "light_groups": opts["light_groups"],
    })
    current = {
        "devices": {"old": {"atomic_class": "light", "display_name": "Old"}},
        "combineds": {"old": {"display_name": "Old"}},
        "masters": {"old": {"display_name": "Old"}},
        "light_groups": {"old": {"display_name": "Old", "members": []}},
    }

    valid, groups, combineds, masters, removals = BI.parse_bulk_payload(exported)
    devices, new_groups, new_combineds, new_masters = BI.apply_bulk(
        current, valid, groups, combineds, masters, removals, replace=BI.replace_from_payload(exported)
    )

    assert devices == _options()["devices"]
    assert new_groups == _options()["light_groups"]
    assert new_combineds == _options()["combineds"]
    assert new_masters == {"living_tv": {"display_name": "Living TV Master"}}


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
        "masters": 0,
        "report": [],
        "combined_report": [],
        "master_report": [],
        "combineds_in": 0,
        "masters_in": 0,
        "error": "Import file not found",
    }


def test_published_output_entity_ids_include_secondary_combined_and_group_outputs():
    opts = _options()
    opts["devices"]["living_tv"]["expose_secondary_sensors"] = True
    opts["masters"]["living_tv"] = {
        "display_name": "Living TV Master",
        "derived": [
            {
                "slug": "blocks_cut",
                "name": "Blocks Cut",
                "target": "__output__",
                "op": "eq",
                "value": "active",
            }
        ],
    }
    opts["combineds"]["opening_state"]["derived"] = [
        {
            "slug": "blocks_climate",
            "object_id": "legacy_blocks_climate",
            "name": "Blocks Climate",
            "target": "__output__",
            "op": "eq",
            "value": "2",
        }
    ]

    published = BI.published_output_entity_ids(
        "benni",
        opts["devices"],
        opts["combineds"],
        opts["light_groups"],
        opts["masters"],
    )

    assert {
        "sensor.benni_device_living_tv",
        "binary_sensor.benni_device_living_tv_powered",
        "binary_sensor.benni_device_living_tv_available",
        "sensor.benni_device_living_tv_power_state",
        "sensor.benni_device_living_tv_watt",
        "sensor.benni_combined_opening_state",
        "binary_sensor.legacy_blocks_climate",
        "sensor.benni_master_living_tv",
        "binary_sensor.benni_master_living_tv_blocks_cut",
        "sensor.benni_light_group_living_lights",
    } <= published


def test_import_start_published_outputs_merges_imported_devices_and_existing_outputs():
    current = _options()
    current["masters"]["living_tv"] = {"display_name": "Living TV Master"}
    valid = [
        {
            "slug": "desk_plug",
            "atomic_class": "power_device",
            "sources": [{"role": "primary_state", "entity": "switch.desk_plug"}],
        }
    ]
    imported_groups = {
        "desk_lights": {"display_name": "Desk Lights", "members": ["light.desk"]}
    }

    published = BI.import_start_published_outputs(
        current, valid, imported_groups, {}, "benni", replace=False
    )

    assert "sensor.benni_device_desk_plug" in published
    assert "sensor.benni_combined_opening_state" in published
    assert "sensor.benni_master_living_tv" in published
    assert "sensor.benni_light_group_desk_lights" in published


def test_combined_report_accepts_published_core_sources():
    report = BI.combined_report(
        {
            "climate_gate": {
                "display_name": "Climate Gate",
                "sources": [
                    {
                        "key": "opening",
                        "role": "opening_state",
                        "entity": "sensor.benni_combined_opening_state",
                    },
                    {
                        "key": "blocked",
                        "role": "gate",
                        "entity": "binary_sensor.benni_combined_opening_state_blocks_climate",
                    },
                ],
                "default_output": "ok",
            }
        },
        "benni",
        {
            "sensor.benni_combined_opening_state",
            "binary_sensor.benni_combined_opening_state_blocks_climate",
        },
    )

    assert report[0]["accepted"] is True
    assert report[0]["derived_sources"] == []
    assert report[0]["source_blocks"] == []
    assert len(report[0]["accepted_sources"]) == 2


def test_combined_report_blocks_unpublished_own_outputs_as_forward_refs():
    report = BI.combined_report(
        {
            "climate_gate": {
                "display_name": "Climate Gate",
                "sources": [
                    {
                        "key": "future",
                        "role": "gate",
                        "entity": "sensor.benni_combined_future_gate",
                    }
                ],
                "default_output": "ok",
            }
        },
        "benni",
        set(),
    )

    assert report[0]["accepted"] is False
    assert report[0]["source_blocks"] == [
        "forward reference auf noch-nicht-publizierten Output: "
        "sensor.benni_combined_future_gate"
    ]
    assert report[0]["derived_sources"] == report[0]["source_blocks"]


def test_combined_report_allows_references_to_earlier_imported_combineds_only():
    report = BI.combined_report(
        {
            "first_gate": {
                "display_name": "First Gate",
                "default_output": "ok",
            },
            "second_gate": {
                "display_name": "Second Gate",
                "sources": [
                    {
                        "key": "first",
                        "role": "gate",
                        "entity": "sensor.benni_combined_first_gate",
                    }
                ],
                "default_output": "ok",
            },
        },
        "benni",
        set(),
    )

    assert report[0]["accepted"] is True
    assert report[1]["accepted"] is True
    assert report[1]["source_blocks"] == []
    assert report[1]["accepted_sources"] == [
        "sensor.benni_combined_first_gate: "
        "publizierter Core-Devices-Output als Fusion-Quelle akzeptiert"
    ]


def test_master_report_blocks_core_outputs_even_when_published():
    report = BI.combined_report(
        {
            "living_tv": {
                "display_name": "Living TV Master",
                "sources": [
                    {
                        "key": "old_atomic",
                        "role": "tv_device",
                        "entity": "sensor.benni_device_living_tv",
                    },
                    {
                        "key": "old_combined",
                        "role": "media_context",
                        "entity": "sensor.benni_combined_media_context",
                    },
                ],
                "default_output": "off",
            }
        },
        "benni",
        {
            "sensor.benni_device_living_tv",
            "sensor.benni_combined_media_context",
        },
        master=True,
    )

    assert report[0]["accepted"] is False
    assert report[0]["entity_id"] == "sensor.benni_master_living_tv"
    assert report[0]["source_blocks"] == [
        "sensor.benni_device_living_tv: von dieser Integration selbst erzeugte Quelle sollte nicht als Raw-Quelle dienen",
        "sensor.benni_combined_media_context: von dieser Integration selbst erzeugte Quelle sollte nicht als Raw-Quelle dienen",
    ]


def test_apply_bulk_removes_named_existing_outputs_in_merge_mode():
    current = _options()
    current["devices"]["old_device"] = {"display_name": "Old"}
    current["combineds"]["old_combined"] = {"display_name": "Old"}
    current["masters"]["old_master"] = {"display_name": "Old"}

    payload = json.dumps({
        "remove_devices": ["old_device"],
        "remove_combineds": ["old_combined"],
        "remove_masters": ["old_master"],
        "combineds": {"new_combined": {"display_name": "New"}},
    })

    valid, groups, combineds, masters, removals = BI.parse_bulk_payload(payload)
    devices, _groups, new_combineds, new_masters = BI.apply_bulk(
        current, valid, groups, combineds, masters, removals
    )

    assert "old_device" not in devices
    assert "old_combined" not in new_combineds
    assert "old_master" not in new_masters
    assert "new_combined" in new_combineds
