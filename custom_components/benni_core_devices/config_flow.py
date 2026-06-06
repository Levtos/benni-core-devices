"""Config flow for Benni Core Devices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .builder import OptionsFlowHelper
from .const import (
    CONF_DEVICES,
    CONF_LIGHT_GROUPS,
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DOMAIN,
    NAME,
    PROFILE_LABELS,
    PROFILES,
)


def _profile_schema(default: str = DEFAULT_PROFILE) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PROFILE, default=default): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    mode=selector.SelectSelectorMode.LIST,
                    options=[
                        selector.SelectOptionDict(value=p, label=PROFILE_LABELS[p])
                        for p in PROFILES
                    ],
                )
            )
        }
    )


class BenniCoreDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=_profile_schema()
            )
        profile = user_input.get(CONF_PROFILE, DEFAULT_PROFILE)
        if profile not in PROFILES:
            return self.async_show_form(
                step_id="user",
                data_schema=_profile_schema(),
                errors={CONF_PROFILE: "invalid_profile"},
            )
        await self.async_set_unique_id(f"{DOMAIN}_{profile}_hub")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{NAME} ({PROFILE_LABELS[profile]})",
            data={CONF_PROFILE: profile},
            options={CONF_DEVICES: {}, CONF_LIGHT_GROUPS: {}},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BenniCoreDevicesOptionsFlow()


class BenniCoreDevicesOptionsFlow(OptionsFlow):
    """Minimal emergency CRUD fallback; primary UX is the custom panel."""

    @property
    def _helper(self) -> OptionsFlowHelper:
        helper = getattr(self, "__helper", None)
        if helper is None:
            helper = OptionsFlowHelper(self.hass, self.config_entry, self)
            setattr(self, "__helper", helper)
        return helper

    def __getattr__(self, name: str):
        if name.startswith("async_step_"):
            return getattr(self._helper, name)
        raise AttributeError(name)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self._helper.async_step_init(user_input)

