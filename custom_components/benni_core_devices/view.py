"""Custom panel registration for Benni Core Devices."""

from __future__ import annotations

import logging
import os

from aiohttp import web
from homeassistant.components.frontend import (
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    DATA_VIEW_PANEL,
    DATA_VIEW_STATIC,
    DOMAIN,
    FRONTEND_DIR_URL,
    FRONTEND_ENTRY,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
)

_LOGGER = logging.getLogger(__name__)

_BASE = os.path.dirname(__file__)
_APP_DIR = os.path.realpath(os.path.join(_BASE, "frontend", "app"))


def _cache_bust() -> str:
    """Cache-Bust-Token über ALLE App-Dateien (max mtime), nicht nur main.js.

    Der entkoppelt: ein Patch an einem Submodul (diagnose.js/styles.js) ändert
    den Token auch dann, wenn main.js unverändert bleibt.
    """
    latest = 0
    for base, _dirs, files in os.walk(_APP_DIR):
        for name in files:
            try:
                latest = max(latest, int(os.path.getmtime(os.path.join(base, name))))
            except OSError:
                pass
    return str(latest or 0)


class _AppStaticView(HomeAssistantView):
    """Liefert die Panel-App mit ``Cache-Control: no-cache`` aus.

    ES-Module erben den Cache-Bust-Query verschachtelter Imports NICHT
    (``diagnose.js`` → ``styles.js`` werden ohne ``?token`` geladen). Damit ein
    neues Release zuverlässig durchschlägt, erzwingen wir Revalidierung pro
    Abruf — der Browser holt geänderte Dateien (geänderte mtime) sofort frisch.
    """

    url = FRONTEND_DIR_URL + "/{path:.+}"
    name = "benni_core_devices:app"
    requires_auth = False

    async def get(self, request: web.Request, path: str) -> web.StreamResponse:
        rel = os.path.normpath(path).lstrip("/\\")
        full = os.path.realpath(os.path.join(_APP_DIR, rel))
        if not full.startswith(_APP_DIR + os.sep) or not os.path.isfile(full):
            return web.Response(status=404)
        resp = web.FileResponse(full)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


async def async_setup_view(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if not data.get(DATA_VIEW_STATIC):
        hass.http.register_view(_AppStaticView())
        data[DATA_VIEW_STATIC] = True

    if data.get(DATA_VIEW_PANEL):
        return
    async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL_PATH,
        require_admin=False,
        config={
            "_panel_custom": {
                "name": PANEL_ELEMENT,
                "module_url": f"{FRONTEND_ENTRY}?{_cache_bust()}",
            },
        },
    )
    data[DATA_VIEW_PANEL] = True


def async_remove_view(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if not data.get(DATA_VIEW_PANEL):
        return
    try:
        async_remove_panel(hass, PANEL_URL_PATH)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("panel remove skipped: %s", err)
    data[DATA_VIEW_PANEL] = False

