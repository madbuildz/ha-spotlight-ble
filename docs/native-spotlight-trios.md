# Native Spotlight Trios

Each configured Spotlight Trio represents one three-head controller. Its light
panels have one Effects menu containing combinations such as **Christmas ·
Steady**, **Christmas · Blink**, **Red · Steady** or **White 3 · Steady**.
The menu contains 29 observed palettes/themes × 10 animation modes; all IDs are
known, but every possible combination has not been physically verified.

Choosing an entry sends the preset and animation together in one encrypted
packet split into the two required GATT writes. A controller can drive different
colors across its three heads using a theme. Independent head colors, arbitrary
RGB, dimming, effect speed and off commands remain unverified. Turning off through
HA raises an explicit unsupported-command error. These are protocol limitations,
not missing color-wheel or brightness helpers.

## Add or configure a controller

Use Settings → Devices & services → Add integration → Spotlight BLE. Select
Holiday ShowHome, give it a name and choose its Generic Bluetooth entity. Enter
the full advertised LA2 name, for example `LA2000012A1B2`; the protocol derives
the destination and batch byte from it. Repeat for each physical controller.
Configure on the integration entry changes this local mapping. See
[per-device setup and migration](per-device-setup.md).
