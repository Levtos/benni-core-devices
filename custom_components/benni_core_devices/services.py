"""Services for Benni Core Devices."""

from __future__ import annotations

import functools
import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_DRY_RUN,
    ATTR_EXPIRE_SECONDS,
    ATTR_PAYLOAD,
    ATTR_POWER_STATE,
    ATTR_POWERED,
    ATTR_REPLACE,
    ATTR_SLUG,
    DOMAIN,
    POWER_STATE_SLUGS,
    SERVICE_BULK_IMPORT,
    SERVICE_CLEAR_OVERRIDE,
    SERVICE_EXPORT_CONFIG,
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

_BULK_IMPORT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PAYLOAD): str,
        vol.Optional(ATTR_DRY_RUN, default=True): bool,
        vol.Optional(ATTR_REPLACE, default=False): bool,
    }
)


async def _bulk_import(hass: HomeAssistant, call: ServiceCall) -> dict:
    """MCP-/Agenten-fähiger Import. Default dry_run=True (sicher)."""
    from .websocket_api import _entry, run_bulk_import

    entry = _entry(hass)
    if entry is None:
        raise HomeAssistantError("Benni Core Devices not loaded")
    try:
        return await run_bulk_import(
            hass, entry,
            call.data[ATTR_PAYLOAD],
            bool(call.data.get(ATTR_DRY_RUN, True)),
            bool(call.data.get(ATTR_REPLACE, False)),
        )
    except (TypeError, ValueError) as err:
        raise HomeAssistantError(str(err)) from err


async def _export_config(hass: HomeAssistant, call: ServiceCall) -> dict:
    from .websocket_api import _entry, _export_yaml

    entry = _entry(hass)
    if entry is None:
        raise HomeAssistantError("Benni Core Devices not loaded")
    return {"yaml": _export_yaml(entry)}


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
            DOMAIN, SERVICE_SET_OVERRIDE,
            functools.partial(_set_override, hass), schema=_SET_OVERRIDE_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_OVERRIDE):
        hass.services.async_register(
            DOMAIN, SERVICE_CLEAR_OVERRIDE,
            functools.partial(_clear_override, hass), schema=_CLEAR_OVERRIDE_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, SERVICE_BULK_IMPORT):
        hass.services.async_register(
            DOMAIN, SERVICE_BULK_IMPORT,
            functools.partial(_bulk_import, hass),
            schema=_BULK_IMPORT_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_EXPORT_CONFIG):
        hass.services.async_register(
            DOMAIN, SERVICE_EXPORT_CONFIG,
            functools.partial(_export_config, hass),
            supports_response=SupportsResponse.ONLY,
        )


def async_unregister_services(hass: HomeAssistant) -> None:
    for service in (
        SERVICE_SET_OVERRIDE, SERVICE_CLEAR_OVERRIDE,
        SERVICE_BULK_IMPORT, SERVICE_EXPORT_CONFIG,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

