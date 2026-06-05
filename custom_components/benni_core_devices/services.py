"""Services for Benni Core Devices."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    ATTR_EXPIRE_SECONDS,
    ATTR_POWER_STATE,
    ATTR_POWERED,
    ATTR_SLUG,
    DOMAIN,
    POWER_STATE_SLUGS,
    SERVICE_CLEAR_OVERRIDE,
    SERVICE_SET_OVERRIDE,
)
from .coordinator import coordinator_by_slug

_LOGGER = logging.getLogger(__name__)

_SET_OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SLUG): str,
        vol.Optional(ATTR_POWERED): vol.Any(bool, None),
        vol.Optional(ATTR_POWER_STATE): vol.Any(vol.In(POWER_STATE_SLUGS), None),
        vol.Optional(ATTR_EXPIRE_SECONDS): vol.Any(
            vol.All(int, vol.Range(min=1, max=86400 * 30)), None
        ),
    }
)

_CLEAR_OVERRIDE_SCHEMA = vol.Schema({vol.Required(ATTR_SLUG): str})


async def _set_override(hass: HomeAssistant, call: ServiceCall) -> None:
    slug = call.data[ATTR_SLUG]
    coord = coordinator_by_slug(hass, slug)
    if coord is None:
        _LOGGER.warning("set_override: unknown device slug %r", slug)
        return
    await coord.async_set_override(
        powered=call.data.get(ATTR_POWERED),
        power_state=call.data.get(ATTR_POWER_STATE),
        expire_seconds=call.data.get(ATTR_EXPIRE_SECONDS),
    )


async def _clear_override(hass: HomeAssistant, call: ServiceCall) -> None:
    slug = call.data[ATTR_SLUG]
    coord = coordinator_by_slug(hass, slug)
    if coord is None:
        _LOGGER.warning("clear_override: unknown device slug %r", slug)
        return
    await coord.async_clear_override()


def async_register_services(hass: HomeAssistant) -> None:
    if not hass.services.has_service(DOMAIN, SERVICE_SET_OVERRIDE):
        hass.services.async_register(
            DOMAIN, SERVICE_SET_OVERRIDE, _set_override, schema=_SET_OVERRIDE_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_OVERRIDE):
        hass.services.async_register(
            DOMAIN, SERVICE_CLEAR_OVERRIDE, _clear_override, schema=_CLEAR_OVERRIDE_SCHEMA
        )


def async_unregister_services(hass: HomeAssistant) -> None:
    for service in (SERVICE_SET_OVERRIDE, SERVICE_CLEAR_OVERRIDE):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

