"""Tests for the custom panel view setup."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import types


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "custom_components", "benni_core_devices")


def _load_view_with_ha_stubs(monkeypatch):
    aiohttp = types.ModuleType("aiohttp")
    web = types.ModuleType("aiohttp.web")
    web.FileResponse = object
    web.Response = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
    aiohttp.web = web

    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    frontend = types.ModuleType("homeassistant.components.frontend")
    http = types.ModuleType("homeassistant.components.http")
    core = types.ModuleType("homeassistant.core")

    frontend.async_register_built_in_panel = lambda *args, **kwargs: None
    frontend.async_remove_panel = lambda *args, **kwargs: None
    http.HomeAssistantView = type("HomeAssistantView", (), {})
    core.HomeAssistant = type("HomeAssistant", (), {})

    for name, module in {
        "aiohttp": aiohttp,
        "aiohttp.web": web,
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.frontend": frontend,
        "homeassistant.components.http": http,
        "homeassistant.core": core,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location(
        "bcd_pure_pkg.view", os.path.join(PKG_DIR, "view.py")
    )
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "bcd_pure_pkg.view", mod)
    spec.loader.exec_module(mod)
    return mod


def test_async_setup_view_runs_cache_bust_in_executor(monkeypatch):
    view = _load_view_with_ha_stubs(monkeypatch)
    calls = []

    class FakeHttp:
        def __init__(self):
            self.views = []

        def register_view(self, registered_view):
            self.views.append(registered_view)

    class FakeHass:
        def __init__(self):
            self.data = {}
            self.http = FakeHttp()
            self.executor_calls = []

        async def async_add_executor_job(self, func, *args):
            self.executor_calls.append((func, args))
            return "executor-token"

    def register_panel(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(view, "async_register_built_in_panel", register_panel)

    hass = FakeHass()
    asyncio.run(view.async_setup_view(hass))

    assert len(hass.http.views) == 1
    assert hass.executor_calls == [(view._cache_bust, ())]
    assert calls[0][1]["config"]["_panel_custom"]["module_url"].endswith(
        "?executor-token"
    )
