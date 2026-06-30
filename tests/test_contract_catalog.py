import bcd_const as C
import bcd_contract_catalog as CC


def test_contract_catalog_classifies_known_masters_and_keeps_legacy_separate():
    catalog = CC.build_contract_catalog(
        "benni",
        masters={
            "tv": {
                "display_name": "TV",
                "sources": [
                    {"key": "state", "role": "primary_state", "entity": "media_player.tv"},
                    {"key": "power", "role": "power_meter", "entity": "sensor.tv_power", "required": False},
                ],
                "derived_values": [
                    {"name": "is_active", "kind": "gate", "expr": "${state} == 'on'", "expose": True}
                ],
                "exposed_attributes": ["is_active"],
            },
            "living_rollo": {
                "display_name": "Living Rollo",
                "sources": [{"key": "cover", "role": "cover", "entity": "cover.living"}],
            },
        },
        combineds={
            "media_subwoofer_should_be_on": {
                "display_name": "Subwoofer Should Be On",
                "sources": [{"key": "media", "role": "media_state", "entity": "sensor.benni_master_tv"}],
            }
        },
        devices={
            "old_tv": {
                "display_name": "Old TV",
                "atomic_class": "media_device",
                "variant": "tv",
                "sources": [{"role": "primary_state", "entity": "media_player.tv"}],
            }
        },
    )

    tv = catalog["masters"][0]
    rollo = catalog["masters"][1]
    combined = catalog["legacy_combineds"][0]
    device = catalog["legacy_devices"][0]

    assert tv["entity_id"] == "sensor.benni_master_tv"
    assert tv["contract_kind"] == "device_master"
    assert tv["migration_status"] == "target"
    assert tv["source_count"] == 2
    assert tv["required_source_count"] == 1
    assert tv["optional_source_count"] == 1
    assert tv["attribute_count"] == 1
    assert rollo["contract_kind"] == "mixed"
    assert combined["contract_kind"] == "legacy_combined"
    assert combined["migration_status"] == "legacy_bridge"
    assert combined["contract_refs"] == ["sensor.benni_master_tv"]
    assert device["contract_kind"] == "legacy_device"
    assert device["migration_status"] == "legacy_bridge"
    assert catalog["summary"] == {
        "masters": 2,
        "legacy_devices": 1,
        "legacy_combineds": 1,
        "target_contracts": 2,
    }


def test_contract_catalog_uses_runtime_status_and_raw_config_is_opt_in():
    catalog = CC.build_contract_catalog(
        "benni",
        masters={
            "unknown_master": {
                "display_name": "Unknown Master",
                "contract_kind": "domain_master",
                "migration_status": "target",
                "legacy_aliases": ["sensor.benni_combined_unknown"],
                "sources": [{"key": "missing", "role": "custom"}],
            }
        },
        runtime_status={
            "masters": [
                {
                    "slug": "unknown_master",
                    "entity_id": "sensor.benni_master_unknown_master",
                    "attrs": {
                        "source_quality": "degraded",
                        "degraded": True,
                        "degraded_reason": ["missing source"],
                        "missing_sources": ["missing"],
                    },
                }
            ]
        },
        include_raw_config=True,
    )

    master = catalog["masters"][0]

    assert master["contract_kind"] == "domain_master"
    assert master["migration_status"] == "target"
    assert master["source_quality"] == "degraded"
    assert master["degraded"] is True
    assert master["degraded_reason"] == ["missing source"]
    assert master["missing_required_count"] == 1
    assert master["legacy_aliases"] == ["sensor.benni_combined_unknown"]
    assert master["raw_config"]["display_name"] == "Unknown Master"


def test_contract_catalog_leaves_unknown_master_unknown_without_hints():
    catalog = CC.build_contract_catalog(
        "benni",
        masters={"future_context": {"display_name": "Future Context"}},
    )

    master = catalog["masters"][0]

    assert master["contract_kind"] == "unknown"
    assert master["migration_status"] == "unknown"
    assert "raw_config" not in master


def test_contract_catalog_websocket_command_constant():
    assert C.WS_GET_CONTRACT_CATALOG == "benni_core_devices/get_contract_catalog"
