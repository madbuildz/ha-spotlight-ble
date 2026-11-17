# Spotlight BLE

Experimental Home Assistant integration for Fi Light floodlights and Holiday
ShowHome three-head spotlight controllers. Add only the devices you own—there
are no predefined Floodlight 1–4 or Trio 1–2 placeholders and no fixed device limit.

| Controller | Entities and controls | Limits |
| --- | --- | --- |
| Fi Light | One light: RGB, brightness, dual whites, 27 effect presets. One effect-speed slider on the same device. | Effect dimming and physical state readback are unverified. |
| Holiday ShowHome | One light for the three-head controller, with combined theme/palette and animation choices. | Off, dimming, arbitrary RGB, speed and individual-head commands are unverified. |

State remembers commands HA sent; phone-app changes are not synchronized back.
Compatibility is based on tested protocols, not every product using these apps.
See [protocol notes](docs/spotlight-protocol.md) and [Fi Light effects](docs/fi-light-effects.md).

## Install and add a device

1. Install **Generic Bluetooth** and add the physical Bluetooth device there.
2. In **HACS → Custom repositories**, add
   `https://github.com/madbuildz/ha-spotlight-ble` as an **Integration**.
3. Download **Spotlight BLE** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Spotlight BLE**.
5. Select the controller type, enter your own name and select its Generic
   Bluetooth entity. For ShowHome, also enter its full advertised `LA2…` name.
6. Repeat Add integration for each additional physical controller.

HACS installs reusable code; HA creates entities only after a device is added.
Each controller has its own configuration entry, entities and remembered state.
No templates, scripts or manually created helpers are required. Generic Bluetooth
provides transport through an HA adapter or ESPHome Bluetooth proxy. It must stay
enabled, though its connection sensor can be hidden.

Use **Configure** on a device’s integration entry to change its name or Bluetooth
target. Duplicate registrations of the same Bluetooth device are rejected. The
mapping is saved locally in HA; the repository contains no real device IDs or
credentials. Device count is not limited by this integration, but Bluetooth
adapters/proxies still have their own connection and radio limits.

This is a HACS custom repository, not a default-catalog integration. For manual
installation, copy `custom_components/spotlight_ble_control` into HA’s
`/config/custom_components/`, restart HA, then follow the same Add integration flow.

## Upgrade from fixed-slot releases

Configured legacy slots migrate to individual device entries. Existing assigned
light IDs, remembered settings and mesh counters are preserved. Unassigned
placeholder entities are disabled and hidden for rollback; no new empty devices
are created. An old installation with nothing assigned retains only an inert
migration marker, which creates no entities.

See [migration details](docs/per-device-setup.md),
[Floodlight controls](docs/native-floodlights.md), and
[ShowHome controls](docs/native-spotlight-trios.md). Historical exports under
`home-assistant/templates/` are not part of the current setup.

## Known limitations

Generic Bluetooth’s retained connections can become stale after proxy reconnects.
This integration reports transport failures but does not repair that upstream
connection behavior. Keep the phone app closed while HA is controlling a device.
Only a subset of the app-derived effects has been physically verified; a software
packet test is not proof of visible behavior on every device.

## ESPHome proxy

An optional Seeed Studio XIAO ESP32-C6 proxy package is at
`esphome/xiao-c6-proxy.yaml`. It selects an external antenna, which must be attached.
Wi-Fi/API/OTA secrets stay local. See [Device Builder setup](docs/setup.md).
HACS does not flash ESP32 firmware or automatically install these YAML files.

## Development

```sh
python -m pip install cryptography
python -m unittest discover -s tests -v
```

Tests cover recorded packet fixtures, command routing, configurable device counts,
config-flow validation, migration and persistent state using HA boundary doubles.
HA startup and config schemas also require real-instance validation.

[MIT license](LICENSE).
