"""Config- & Options-Flow für Benni Core · Devices v2 (Emergency-CRUD).

Primäre UX ist das Panel. Dieser Flow ist nur Notfall-CRUD und arbeitet
rollenbasiert: atomic_class → variant + display_name + Default-Rollen-Quellen.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
import yaml
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    AVAILABILITY_ANY_REQUIRED_OR_ANY_SOURCE,
    CONF_ATOMIC_CLASS,
    CONF_BULK_YAML,
    CONF_CONTROLS,
    CONF_DEVICES,
    CONF_DIAGNOSTICS,
    CONF_DISPLAY_NAME,
    CONF_ENTITY,
    CONF_FAIL_SAFE,
    CONF_AVAILABILITY_RULE,
    CONF_GROUP_MEMBERS,
    CONF_LIGHT_GROUPS,
    CONF_METADATA_SOURCES,
    CONF_ROLE,
    CONF_SOURCES,
    CONF_VALUE,
    CONF_VARIANT,
    DOMAIN,
    NAME,
)
from .device_types import (
    ATOMIC_CLASSES,
    ROLE_CATALOG,
    BUCKET_CONTROLS,
    BUCKET_METADATA,
    BUCKET_SOURCES,
    atomic_class_spec,
    slugify,
    unique_slug,
    validate_import_payload,
)

CONF_SLUG_KEY = "slug"


# ── Schemas ──────────────────────────────────────────────────────────────────


def _class_schema() -> vol.Schema:
    options = [
        selector.SelectOptionDict(value=spec.atomic_class, label=(spec.label or spec.atomic_class) + (" (Beta)" if spec.beta else ""))
        for spec in ATOMIC_CLASSES.values()
    ]
    return vol.Schema({
        vol.Required(CONF_ATOMIC_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
        )
    })


def _role_selector(role: str):
    spec = ROLE_CATALOG.get(role)
    if spec is None or spec.kind == "text" or not spec.domains:
        return selector.TextSelector()
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=list(spec.domains), multiple=False))


def _device_form_schema(atomic_class: str, defaults: dict[str, Any]) -> vol.Schema:
    spec = ATOMIC_CLASSES[atomic_class]
    fields: dict[Any, Any] = {
        vol.Required(CONF_DISPLAY_NAME, default=defaults.get(CONF_DISPLAY_NAME, "")): str,
    }
    if spec.variants:
        fields[vol.Required(CONF_VARIANT, default=defaults.get(CONF_VARIANT, spec.variants[0]))] = (
            selector.SelectSelector(selector.SelectSelectorConfig(options=list(spec.variants), mode=selector.SelectSelectorMode.DROPDOWN))
        )
    roles = spec.default_roles or spec.required_roles
    for role in roles:
        default = defaults.get(role)
        marker = vol.Optional(role, default=default) if default else vol.Optional(role)
        fields[marker] = _role_selector(role)
    return vol.Schema(fields)


def _build_conf(atomic_class: str, user_input: dict[str, Any]) -> dict[str, Any]:
    spec = ATOMIC_CLASSES[atomic_class]
    sources: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    roles = spec.default_roles or spec.required_roles
    for role in roles:
        val = user_input.get(role)
        if not val:
            continue
        rspec = ROLE_CATALOG.get(role)
        binding = {CONF_ROLE: role}
        if rspec and rspec.kind == "text":
            binding[CONF_VALUE] = str(val)
        else:
            binding[CONF_ENTITY] = str(val)
        bucket = rspec.bucket if rspec else BUCKET_SOURCES
        if bucket == BUCKET_CONTROLS:
            controls.append(binding)
        elif bucket == BUCKET_METADATA:
            metadata.append(binding)
        else:
            sources.append(binding)
    return {
        CONF_ATOMIC_CLASS: atomic_class,
        CONF_VARIANT: str(user_input.get(CONF_VARIANT) or (spec.variants[0] if spec.variants else "")),
        CONF_DISPLAY_NAME: str(user_input.get(CONF_DISPLAY_NAME, "")).strip(),
        CONF_SOURCES: sources,
        CONF_CONTROLS: controls,
        CONF_METADATA_SOURCES: metadata,
        CONF_DIAGNOSTICS: {CONF_FAIL_SAFE: spec.fail_safe, CONF_AVAILABILITY_RULE: AVAILABILITY_ANY_REQUIRED_OR_ANY_SOURCE},
    }


def _bulk_schema(default: str = "") -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_BULK_YAML, default=default): selector.TextSelector(selector.TextSelectorConfig(multiline=True))
    })


def _group_form_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_DISPLAY_NAME, default=defaults.get(CONF_DISPLAY_NAME, "")): str,
        vol.Required(CONF_GROUP_MEMBERS, default=defaults.get(CONF_GROUP_MEMBERS) or []): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="light", multiple=True)
        ),
    })


def _pick_schema(items: dict[str, dict[str, Any]]) -> vol.Schema:
    options = [selector.SelectOptionDict(value=slug, label=f"{conf.get(CONF_DISPLAY_NAME, slug)} ({slug})") for slug, conf in items.items()]
    return vol.Schema({vol.Required("slug"): selector.SelectSelector(selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST))})


# ── Config-Flow-Helper (Hub anlegen) ─────────────────────────────────────────


class ConfigFlowHelper:
    def __init__(self, hass: HomeAssistant, flow) -> None:
        self.hass = hass
        self.flow = flow

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self.flow.async_set_unique_id(f"{DOMAIN}_hub")
        self.flow._abort_if_unique_id_configured()
        return self.flow.async_create_entry(title=NAME, data={}, options={CONF_DEVICES: {}})


# ── Options-Flow-Helper ──────────────────────────────────────────────────────


class OptionsFlowHelper:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, flow: OptionsFlow) -> None:
        self.hass = hass
        self.entry = entry
        self.flow = flow
        self._atomic_class: str | None = None
        self._editing_slug: str | None = None
        self._editing_group_slug: str | None = None

    def _devices(self) -> dict[str, dict[str, Any]]:
        raw = self.entry.options.get(CONF_DEVICES)
        return dict(raw) if isinstance(raw, dict) else {}

    def _save_devices(self, devices: dict[str, dict[str, Any]]) -> FlowResult:
        return self.flow.async_create_entry(title="", data={**self.entry.options, CONF_DEVICES: devices})

    def _light_groups(self) -> dict[str, dict[str, Any]]:
        raw = self.entry.options.get(CONF_LIGHT_GROUPS)
        return dict(raw) if isinstance(raw, dict) else {}

    def _save_groups(self, groups: dict[str, dict[str, Any]]) -> FlowResult:
        return self.flow.async_create_entry(title="", data={**self.entry.options, CONF_LIGHT_GROUPS: groups})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.flow.async_show_menu(
            step_id="init",
            menu_options=["add_device", "edit_device", "remove_device", "bulk", "add_group", "edit_group", "remove_group"],
        )

    # devices
    async def async_step_add_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self._editing_slug = None
        self._atomic_class = None
        if not user_input:
            return self.flow.async_show_form(step_id="add_device", data_schema=_class_schema())
        ac = user_input.get(CONF_ATOMIC_CLASS)
        if ac not in ATOMIC_CLASSES:
            return self.flow.async_show_form(step_id="add_device", data_schema=_class_schema(), errors={CONF_ATOMIC_CLASS: "invalid"})
        self._atomic_class = ac
        return self.flow.async_show_form(step_id="device_form", data_schema=_device_form_schema(ac, {}))

    async def async_step_device_form(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        assert self._atomic_class is not None
        if user_input is None:
            return self.flow.async_show_form(step_id="device_form", data_schema=_device_form_schema(self._atomic_class, {}))
        display = str(user_input.get(CONF_DISPLAY_NAME, "")).strip()
        if not display:
            return self.flow.async_show_form(step_id="device_form", data_schema=_device_form_schema(self._atomic_class, user_input), errors={CONF_DISPLAY_NAME: "required"})
        conf = _build_conf(self._atomic_class, user_input)
        devices = self._devices()
        slug = self._editing_slug if (self._editing_slug and self._editing_slug in devices) else unique_slug(slugify(display) or "device", set(devices))
        devices[slug] = conf
        return self._save_devices(devices)

    async def async_step_edit_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        devices = self._devices()
        if not devices:
            return self.flow.async_abort(reason="no_devices")
        if user_input is None:
            return self.flow.async_show_form(step_id="edit_device", data_schema=_pick_schema(devices))
        slug = user_input["slug"]
        conf = devices.get(slug)
        if not conf:
            return self.flow.async_abort(reason="no_devices")
        self._editing_slug = slug
        self._atomic_class = conf.get(CONF_ATOMIC_CLASS)
        defaults: dict[str, Any] = {CONF_DISPLAY_NAME: conf.get(CONF_DISPLAY_NAME, slug), CONF_VARIANT: conf.get(CONF_VARIANT)}
        for bucket in (CONF_SOURCES, CONF_CONTROLS, CONF_METADATA_SOURCES):
            for b in conf.get(bucket, []) or []:
                if isinstance(b, dict) and b.get(CONF_ROLE):
                    defaults[b[CONF_ROLE]] = b.get(CONF_ENTITY) or b.get(CONF_VALUE)
        if self._atomic_class not in ATOMIC_CLASSES:
            return self.flow.async_abort(reason="no_devices")
        return self.flow.async_show_form(step_id="device_form", data_schema=_device_form_schema(self._atomic_class, defaults))

    async def async_step_remove_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        devices = self._devices()
        if not devices:
            return self.flow.async_abort(reason="no_devices")
        if user_input is None:
            return self.flow.async_show_form(step_id="remove_device", data_schema=_pick_schema(devices))
        devices.pop(user_input["slug"], None)
        return self._save_devices(devices)

    async def async_step_bulk(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is None:
            return self.flow.async_show_form(step_id="bulk", data_schema=_bulk_schema())
        raw = user_input.get(CONF_BULK_YAML, "")
        try:
            parsed = yaml.safe_load(raw) if raw and raw.strip() else None
        except yaml.YAMLError:
            return self.flow.async_show_form(step_id="bulk", data_schema=_bulk_schema(raw), errors={CONF_BULK_YAML: "invalid_yaml"})
        if isinstance(parsed, list):
            for d in parsed:
                if isinstance(d, dict) and not d.get(CONF_SLUG_KEY):
                    derived = slugify(str(d.get(CONF_DISPLAY_NAME, "")))
                    if derived:
                        d[CONF_SLUG_KEY] = derived
        valid, errors = validate_import_payload(parsed)
        if errors:
            return self.flow.async_show_form(step_id="bulk", data_schema=_bulk_schema(raw), errors={CONF_BULK_YAML: "bulk_invalid"}, description_placeholders={"errors": "\n".join(errors)})
        devices = self._devices()
        for d in valid:
            slug = d.pop(CONF_SLUG_KEY, None) or unique_slug(slugify(d.get(CONF_DISPLAY_NAME, "device")) or "device", set(devices))
            devices[slug] = d
        return self._save_devices(devices)

    # groups
    async def async_step_add_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self._editing_group_slug = None
        return self.flow.async_show_form(step_id="group_form", data_schema=_group_form_schema({}))

    async def async_step_group_form(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is None:
            return self.flow.async_show_form(step_id="group_form", data_schema=_group_form_schema({}))
        name = str(user_input.get(CONF_DISPLAY_NAME, "")).strip()
        members = [m for m in (user_input.get(CONF_GROUP_MEMBERS) or []) if m]
        errors: dict[str, str] = {}
        if not name:
            errors[CONF_DISPLAY_NAME] = "required"
        if not members:
            errors[CONF_GROUP_MEMBERS] = "required"
        if errors:
            return self.flow.async_show_form(step_id="group_form", data_schema=_group_form_schema(user_input), errors=errors)
        groups = self._light_groups()
        slug = self._editing_group_slug if (self._editing_group_slug and self._editing_group_slug in groups) else unique_slug(slugify(name) or "group", set(groups))
        groups[slug] = {CONF_DISPLAY_NAME: name, CONF_GROUP_MEMBERS: members}
        return self._save_groups(groups)

    async def async_step_edit_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        groups = self._light_groups()
        if not groups:
            return self.flow.async_abort(reason="no_groups")
        if user_input is None:
            return self.flow.async_show_form(step_id="edit_group", data_schema=_pick_schema(groups))
        slug = user_input["slug"]
        conf = groups.get(slug)
        if not conf:
            return self.flow.async_abort(reason="no_groups")
        self._editing_group_slug = slug
        return self.flow.async_show_form(step_id="group_form", data_schema=_group_form_schema(conf))

    async def async_step_remove_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        groups = self._light_groups()
        if not groups:
            return self.flow.async_abort(reason="no_groups")
        if user_input is None:
            return self.flow.async_show_form(step_id="remove_group", data_schema=_pick_schema(groups))
        groups.pop(user_input["slug"], None)
        return self._save_groups(groups)
