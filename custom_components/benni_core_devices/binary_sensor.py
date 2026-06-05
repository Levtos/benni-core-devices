"""BinarySensor-Entities für Benni Core · Devices.

Nur aktiv wenn `expose_secondary_sensors=true`:
- `binary_sensor.benni_device_<slug>_powered`
- `binary_sensor.benni_device_<slug>_available`
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import device_object_id_prefix, unique_id
from .coordinator import DeviceCoordinator, coordinators_for_entry
from .logic import DeviceResult


def _object_id(profile: str, slug: str, suffix: str) -> str:
    return f"{device_object_id_prefix(profile)}{slug}_{suffix}"


async def async_get_entities(
    hass: HomeAssistant, entry: ConfigEntry, platform: str
) -> list[Entity]:
    if platform != Platform.BINARY_SENSOR:
        return []
    out: list[Entity] = []
    for coordinator in coordinators_for_entry(hass, entry).values():
        if not coordinator.expose_secondary_sensors:
            continue
        out.append(PoweredBinarySensor(coordinator, entry))
        out.append(AvailableBinarySensor(coordinator, entry))
    return out


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(await async_get_entities(hass, entry, Platform.BINARY_SENSOR))


class _BaseDeviceBinarySensor(
    CoordinatorEntity[DeviceCoordinator], BinarySensorEntity
):
    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: DeviceCoordinator,
        entry: ConfigEntry,
        *,
        suffix: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id(entry.entry_id, coordinator.slug, suffix)
        self._attr_name = name
        from .sensor import _device_info

        self._attr_device_info = _device_info(coordinator)
        self.entity_id = async_generate_entity_id(
            "binary_sensor.{}", _object_id(coordinator.profile_name, coordinator.slug, suffix),
            hass=coordinator.hass,
        )

    @property
    def _result(self) -> DeviceResult | None:
        return self.coordinator.data


class PoweredBinarySensor(_BaseDeviceBinarySensor):
    _attr_icon = "mdi:power-plug"

    def __init__(self, coordinator: DeviceCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            suffix="powered",
            name=f"{coordinator.display_name} Powered",
        )

    @property
    def is_on(self) -> bool | None:
        r = self._result
        return r.powered if r else None


class AvailableBinarySensor(_BaseDeviceBinarySensor):
    _attr_icon = "mdi:check-network"

    def __init__(self, coordinator: DeviceCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            suffix="available",
            name=f"{coordinator.display_name} Available",
        )

    @property
    def is_on(self) -> bool | None:
        r = self._result
        return r.available if r else None
