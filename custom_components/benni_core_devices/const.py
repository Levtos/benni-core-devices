"""Constants for the standalone Benni Core Devices integration.

This is the conservative standalone extraction of the Toolbox module
``benni_core_devices``. The HA-free rule constants, enums, config keys and
attribute contracts are intentionally kept aligned with the source module.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

DOMAIN: Final = "benni_core_devices"
NAME: Final = "Benni Core Devices"
STORAGE_VERSION: Final[int] = 1

# hass.data flags / entry buckets
DATA_COORDINATORS: Final = "coordinators"
DATA_WS_REGISTERED: Final = "_ws_registered"
DATA_VIEW_STATIC: Final = "_view_static_registered"
DATA_VIEW_PANEL: Final = "_view_panel_registered"


class DeviceType(str, Enum):
    """Supported physical device profiles."""

    TV = "tv"
    AV_RECEIVER = "av_receiver"
    CONSOLE = "console"
    SPEAKER = "speaker"
    PLUG = "plug"
    LIGHT = "light"
    COVER = "cover"
    CLIMATE = "climate"
    SENSOR_WRAPPER = "sensor_wrapper"


DEVICE_TYPE_SLUGS: Final[tuple[str, ...]] = tuple(t.value for t in DeviceType)

# Config / options keys
CONF_DEVICE_TYPE: Final[str] = "device_type"
CONF_SLUG: Final[str] = "slug"
CONF_DISPLAY_NAME: Final[str] = "display_name"
CONF_PROFILE: Final[str] = "profile"

PROFILE_BENNI: Final = "benni"
PROFILE_ELTERN: Final = "eltern"
PROFILES: Final = [PROFILE_BENNI, PROFILE_ELTERN]
DEFAULT_PROFILE: Final = PROFILE_BENNI
PROFILE_LABELS: Final = {PROFILE_BENNI: "Benni", PROFILE_ELTERN: "Eltern"}

CONF_INTEGRATION_ENTITY: Final[str] = "integration_entity"
CONF_POWER_ENTITY: Final[str] = "power_entity"
CONF_STATUS_ENTITY: Final[str] = "status_entity"
CONF_TITLE_ENTITY: Final[str] = "title_entity"
CONF_WATT_SENSOR: Final[str] = "watt_sensor"
CONF_WIFI_SENSOR: Final[str] = "wifi_sensor"
CONF_SWITCH_ENTITY: Final[str] = "switch_entity"
CONF_LIGHT_ENTITY: Final[str] = "light_entity"
CONF_COVER_ENTITY: Final[str] = "cover_entity"
CONF_POSITION_ENTITY: Final[str] = "position_entity"
CONF_CLIMATE_ENTITY: Final[str] = "climate_entity"
CONF_VALUE_ENTITY: Final[str] = "value_entity"

CONF_WATT_THRESHOLD_ON: Final[str] = "watt_threshold_on"
CONF_WATT_BUCKETS: Final[str] = "watt_buckets"
CONF_STICKY_HOLD_SECONDS: Final[str] = "sticky_hold_seconds"
CONF_EXPOSE_SECONDARY_SENSORS: Final[str] = "expose_secondary_sensors"
CONF_BULK_YAML: Final[str] = "bulk_yaml"
CONF_DEVICES: Final[str] = "devices"
CONF_LIGHT_GROUPS: Final[str] = "light_groups"
CONF_GROUP_MEMBERS: Final[str] = "members"
CONF_FIELDS: Final[str] = "fields"

CONF_WATT_OFF_OP: Final[str] = "watt_off_op"
CONF_WATT_OFF_VALUE: Final[str] = "watt_off_value"
CONF_WATT_IDLE_OP: Final[str] = "watt_idle_op"
CONF_WATT_IDLE_VALUE: Final[str] = "watt_idle_value"
CONF_WATT_PLAYING_OP: Final[str] = "watt_playing_op"
CONF_WATT_PLAYING_VALUE: Final[str] = "watt_playing_value"

WATT_OPERATOR_CHOICES: Final[tuple[str, ...]] = ("<", "<=", "=", ">", ">=")

DEFAULT_WATT_THRESHOLD_ON: Final[int] = 5
DEFAULT_STICKY_HOLD_SECONDS: Final[int] = 30
DEFAULT_EXPOSE_SECONDARY_SENSORS: Final[bool] = False
BOOT_INITIAL_PHASE_SECONDS: Final[int] = 30
AVAILABILITY_FRESHNESS_SECONDS: Final[int] = 600


class PowerState(str, Enum):
    OFF = "off"
    STANDBY = "standby"
    IDLE = "idle"
    PLAYING = "playing"
    UNKNOWN = "unknown"


POWER_STATE_SLUGS: Final[tuple[str, ...]] = tuple(s.value for s in PowerState)


class PowerSource(str, Enum):
    INTEGRATION = "integration"
    WATT_FALLBACK = "watt_fallback"
    STICKY_HOLD = "sticky_hold"
    OVERRIDE = "override"
    NONE = "none"


STORAGE_KEY_LAST_POWERED: Final[str] = "last_powered"
STORAGE_KEY_LAST_POWERED_CHANGE: Final[str] = "last_powered_change"
STORAGE_KEY_OVERRIDE: Final[str] = "override"
STORAGE_KEY_OVERRIDE_POWERED: Final[str] = "powered"
STORAGE_KEY_OVERRIDE_POWER_STATE: Final[str] = "power_state"
STORAGE_KEY_OVERRIDE_EXPIRES_AT: Final[str] = "expires_at"

SERVICE_SET_OVERRIDE: Final[str] = "set_override"
SERVICE_CLEAR_OVERRIDE: Final[str] = "clear_override"
ATTR_SLUG: Final[str] = "slug"
ATTR_POWERED: Final[str] = "powered"
ATTR_POWER_STATE: Final[str] = "power_state"
ATTR_EXPIRE_SECONDS: Final[str] = "expire_seconds"

UPDATE_INTERVAL_SECONDS: Final[int] = 60


def device_object_id_prefix(profile: str) -> str:
    """Object-id prefix for consolidated device sensors."""
    return f"{profile}_device_"


def group_object_id_prefix(profile: str) -> str:
    """Object-id prefix for light-group sensors."""
    return f"{profile}_light_group_"


def entry_profile(entry) -> str:
    """Return the stored profile for a config entry."""
    profile = entry.data.get(CONF_PROFILE, DEFAULT_PROFILE)
    return profile if profile in PROFILES else DEFAULT_PROFILE


def storage_key(entry_id: str, slug: str, profile: str) -> str:
    """Profile- and entry-scoped storage key for one device."""
    return f"{DOMAIN}_{profile}_state_{entry_id}_{slug}"


def unique_id(entry_id: str, *parts: str) -> str:
    """Standalone unique_id with a domain prefix."""
    suffix = "_".join(str(p) for p in parts if p is not None)
    return f"{DOMAIN}_{entry_id}_{suffix}"


PANEL_URL_PATH = "benni_core_devices"
PANEL_TITLE = "Core Devices"
PANEL_ICON = "mdi:devices"
FRONTEND_DIR_URL = "/benni_core_devices_app"
FRONTEND_ENTRY = f"{FRONTEND_DIR_URL}/main.js"
PANEL_ELEMENT = "bcd-app"

WS_GET_STATUS = f"{DOMAIN}/get_status"
WS_GET_CATALOG = f"{DOMAIN}/get_catalog"
WS_SET_DEVICE = f"{DOMAIN}/set_device"
WS_REMOVE_DEVICE = f"{DOMAIN}/remove_device"
WS_SET_GROUP = f"{DOMAIN}/set_group"
WS_REMOVE_GROUP = f"{DOMAIN}/remove_group"
WS_BULK_IMPORT = f"{DOMAIN}/bulk_import"

