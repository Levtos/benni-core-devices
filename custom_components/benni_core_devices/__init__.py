"""Benni Core Devices standalone Home Assistant integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DEVICES,
    DATA_COORDINATORS,
    DATA_WS_REGISTERED,
    DOMAIN,
    NAME,
    device_object_id_prefix,
    entry_profile,
    group_object_id_prefix,
)
from .coordinator import DeviceCoordinator
from .services import async_register_services, async_unregister_services
from .view import async_remove_view, async_setup_view
from .websocket_api import async_setup_websocket_api

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

HUB_IDENTIFIER = (DOMAIN, "hub")
GROUPS_HUB_IDENTIFIER = (DOMAIN, "groups_hub")


def _devices_conf(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    raw = entry.options.get(CONF_DEVICES)
    return dict(raw) if isinstance(raw, dict) else {}


def _device_identifier(slug: str) -> tuple[str, str]:
    return (DOMAIN, f"device:{slug}")


def _reconcile_devices(
    hass: HomeAssistant, entry: ConfigEntry, devices_conf: dict[str, dict[str, Any]]
) -> None:
    dev_reg = dr.async_get(hass)
    valid = {HUB_IDENTIFIER, GROUPS_HUB_IDENTIFIER} | {
        _device_identifier(slug) for slug in devices_conf
    }
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if not (set(device.identifiers) & valid):
            dev_reg.async_remove_device(device.id)

    profile = entry_profile(entry)
    valid_prefixes = (
        device_object_id_prefix(profile),
        group_object_id_prefix(profile),
    )
    ent_reg = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        object_id = entity.entity_id.split(".", 1)[1]
        if not object_id.startswith(valid_prefixes):
            ent_reg.async_remove(entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    profile = entry_profile(entry)
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={HUB_IDENTIFIER},
        name=f"{NAME} ({profile})",
        manufacturer="Benni Core",
        model="Device Core Hub",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={GROUPS_HUB_IDENTIFIER},
        name=f"{NAME} ({profile}) Light Groups",
        manufacturer="Benni Core",
        model="Light Groups Hub",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    devices_conf = _devices_conf(entry)
    _reconcile_devices(hass, entry, devices_conf)

    coordinators: dict[str, DeviceCoordinator] = {}
    for slug, conf in devices_conf.items():
        coordinator = DeviceCoordinator(hass, entry, {**conf, "slug": slug})
        await coordinator.async_load_stored()
        await coordinator.async_config_entry_first_refresh()
        coordinator.async_start_listeners()
        coordinators[slug] = coordinator

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = {DATA_COORDINATORS: coordinators}

    def _stop_all() -> None:
        for coordinator in coordinators.values():
            coordinator.async_stop_listeners()

    entry.async_on_unload(_stop_all)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_register_services(hass)
    await async_setup_view(hass)
    if not data.get(DATA_WS_REGISTERED):
        async_setup_websocket_api(hass)
        data[DATA_WS_REGISTERED] = True

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        bucket = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if isinstance(bucket, dict):
            coords = bucket.get(DATA_COORDINATORS)
            if isinstance(coords, dict):
                for coordinator in coords.values():
                    if isinstance(coordinator, DeviceCoordinator):
                        coordinator.async_stop_listeners()
        has_entries = any(isinstance(v, dict) for v in hass.data.get(DOMAIN, {}).values())
        if not has_entries:
            async_unregister_services(hass)
            async_remove_view(hass)
    return unloaded


async def _async_reload_on_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

