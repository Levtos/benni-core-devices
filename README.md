# Benni Core Devices

Standalone Home Assistant integration for the atomic device layer.

`benni_core_devices` consolidates raw HA entities per physical device into one
sensor with stable attributes:

- `sensor.<profile>_device_<slug>`
- optional secondary sensors for power state, watt, powered and availability
- `sensor.<profile>_light_group_<slug>` for atomic light groups

Profile routing is selected once in the config flow. For `benni`, entity IDs stay
compatible with the Toolbox extraction target, for example
`sensor.benni_device_tv`. The `eltern` route uses `sensor.eltern_device_*`.

The panel at `Benni Core Devices` provides the main CRUD workflow:

1. Create a sensor/device.
2. Select a device type.
3. Link raw slot entities.
4. Configure watt thresholds and buckets.
5. Save the atomic sensor.

Services:

- `benni_core_devices.set_override`
- `benni_core_devices.clear_override`

The pure rule logic is ported unchanged from the Toolbox module and covered by
the HA-free pytest suite in `tests/`.

