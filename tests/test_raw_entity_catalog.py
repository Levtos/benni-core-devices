from datetime import datetime, timezone

import bcd_const as C
import bcd_raw_entity_catalog as RC


def _state(entity_id, state="on", attrs=None):
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    return {
        "entity_id": entity_id,
        "state": state,
        "attributes": attrs or {},
        "last_changed": now,
        "last_updated": now,
    }


def test_raw_entity_without_attributes_is_safe():
    catalog = RC.build_raw_entity_catalog([_state("sensor.plain", "42")])

    entity = catalog["entities"][0]

    assert entity["entity_id"] == "sensor.plain"
    assert entity["domain"] == "sensor"
    assert entity["available"] is True
    assert entity["device_class"] is None
    assert entity["friendly_name"] is None
    assert entity["candidate_roles"] == []
    assert entity["used_by_contracts"] == []
    assert entity["last_changed"] == "2026-01-02T03:04:05+00:00"


def test_candidate_roles_for_common_raw_sources():
    catalog = RC.build_raw_entity_catalog(
        [
            _state("sensor.tv_power", "12.5", {"device_class": "power", "unit_of_measurement": "W"}),
            _state("media_player.living_tv", "playing"),
            _state("binary_sensor.window_left", "on", {"device_class": "window"}),
            _state("switch.subwoofer", "off"),
            _state("cover.living", "open"),
            _state("climate.living", "heat"),
            _state("weather.home", "sunny"),
        ]
    )
    by_id = {item["entity_id"]: item for item in catalog["entities"]}

    assert "power_meter" in by_id["sensor.tv_power"]["candidate_roles"]
    assert by_id["media_player.living_tv"]["candidate_roles"] == ["media_player"]
    assert by_id["binary_sensor.window_left"]["candidate_roles"] == ["opening_contact"]
    assert by_id["switch.subwoofer"]["candidate_roles"] == ["switch_actuator"]
    assert by_id["cover.living"]["candidate_roles"] == ["cover"]
    assert by_id["climate.living"]["candidate_roles"] == ["climate"]
    assert by_id["weather.home"]["candidate_roles"] == ["weather"]


def test_used_by_contracts_are_derived_from_existing_configs():
    used_by = RC.build_used_by_contracts(
        "benni",
        masters={
            "tv": {
                "sources": [
                    {"key": "state", "role": "primary_state", "entity": "media_player.living_tv"},
                    {"key": "watt", "role": "power_meter", "entity": "sensor.tv_power"},
                ]
            }
        },
        combineds={
            "media_subwoofer": {
                "sources": [{"key": "tv", "role": "media_state", "entity": "sensor.benni_master_tv"}]
            }
        },
        devices={
            "old_tv": {
                "sources": [{"role": "primary_state", "entity": "media_player.living_tv"}],
                "controls": [{"role": "switch", "entity": "switch.tv_plug"}],
            }
        },
    )
    catalog = RC.build_raw_entity_catalog(
        [
            _state("media_player.living_tv"),
            _state("sensor.tv_power", "10", {"device_class": "power"}),
            _state("sensor.benni_master_tv", "active"),
            _state("switch.tv_plug"),
        ],
        used_by_contracts=used_by,
    )
    by_id = {item["entity_id"]: item for item in catalog["entities"]}

    tv_refs = by_id["media_player.living_tv"]["used_by_contracts"]
    assert {
        ("sensor.benni_master_tv", "master", "primary_state", "state"),
        ("sensor.benni_device_old_tv", "legacy_device", "primary_state", "primary_state"),
    } <= {
        (ref["contract_entity_id"], ref["contract_kind"], ref["role"], ref["key"])
        for ref in tv_refs
    }
    assert by_id["sensor.tv_power"]["used_by_contracts"][0]["role"] == "power_meter"
    assert by_id["sensor.benni_master_tv"]["used_by_contracts"][0]["contract_kind"] == "legacy_combined"
    assert by_id["switch.tv_plug"]["used_by_contracts"][0]["contract_kind"] == "legacy_device"


def test_raw_entity_catalog_filters_domain_search_and_availability():
    catalog = RC.build_raw_entity_catalog(
        [
            _state("sensor.tv_power", "12", {"friendly_name": "TV Power"}),
            _state("sensor.offline", "unavailable"),
            _state("media_player.tv", "playing", {"friendly_name": "Living TV"}),
        ],
        domain="sensor",
        search="power",
        only_available=True,
    )

    assert [item["entity_id"] for item in catalog["entities"]] == ["sensor.tv_power"]
    assert catalog["summary"] == {"entities": 1, "used": 0}
    assert catalog["filters"] == {
        "domain": ["sensor"],
        "search": "power",
        "only_available": True,
    }


def test_raw_entity_catalog_websocket_command_constant():
    assert C.WS_GET_RAW_ENTITY_CATALOG == "benni_core_devices/get_raw_entity_catalog"
