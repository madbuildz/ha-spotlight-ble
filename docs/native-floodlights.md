# Native Floodlights

Each configured Fi Light device is a native `light` entity. Open its more-info panel for power,
brightness, the color wheel and an **Effect** selector:

- Color: steady RGB, using the remembered color.
- White channel 1, White channel 2, Both white channels: dimmable white modes.
- 27 built-in effects: pulse/blink in red, green, blue, yellow, cyan, purple,
  RGB white and rainbow; mixed-color pulses; warm/cool white effects and jumps.

Effects use the app's fixed color-and-animation combinations, not the selected
RGB color. **Color** returns to the remembered steady RGB color. Selecting any
color on the wheel exits the effect. Each Floodlight device also has an **Effect speed** slider: 1 is slowest and 31
is fastest. Its default is 8, preserving the earlier wire speed 24 (`0x18`).
Changing speed while an effect is running updates that effect. While the light
is off or solid, it only saves the speed for the next effect; it does not turn
the light on. Speed is retained independently for each slot. Effect dimming is unverified, so the light
reports on/off-only adjustment while an effect is active. Return to a solid mode
to use brightness. Older action names `White pulse` and `White blink` remain
aliases for `Pulse warm white` and `Blink warm white`.

All 27 IDs come from the official Fi Light Android app. Warm-white pulse/blink,
purple pulse, blue blink and red/blue pulse have been visually verified on the
tested hardware; effects involving green may be affected
by that unit's damaged green channel. See [effect command table](fi-light-effects.md).

The standard white button selects Both white channels. No calibrated Kelvin
range is claimed. Picking an RGB color leaves the current white/effect mode.
Color and brightness in one service call produce one complete BLE packet.
State is the last command sent by HA; phone-app changes are not read back.

## Add or configure a light

Use Settings → Devices & services → Add integration → Spotlight BLE. Select
Fi Light, name it and choose its Generic Bluetooth entity. Repeat for each actual
light; no placeholders are created. Configure on its integration entry changes
the mapping. See [per-device setup and migration](per-device-setup.md).
