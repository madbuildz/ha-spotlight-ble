# Spotlight protocol notes

These findings come from app analysis and visually confirmed tests on November
14–15, 2026. They describe the tested devices, not every product using the apps.
The local `spotlight_ble_control` backend now generates fresh packets for the
Template Light helpers; see `home-assistant/templates/README.md`.

## ShowHome controllers

The identifiers below are fictional examples, not the identifiers of the tested lights.

| Controller | Mesh destination | Batch byte | Device type |
| --- | --- | --- | --- |
| LA2000012A1B2 | `0xA1B2` | `0x12` | `0x0002` |
| LA2000034C3D4 | `0xC3D4` | `0x34` | `0x0002` |

The last four name characters encode the hexadecimal mesh destination. Name
characters at zero-based positions 7–8 encode the hexadecimal batch byte. `LA2`
selects device type 2 in the analyzed app. BLE address and mesh destination are
different identifiers; a tested controller was observed at a changed BLE address after a later
power-on, so rediscover by advertised name rather than assuming its old MAC.

A tested steady-preset plaintext has 13 bytes:

| Bytes | Meaning |
| --- | --- |
| 0–1 | Mesh destination, little endian |
| 2 | Vendor data opcode `0x73` |
| 3 | Transaction nibble plus operation 3 |
| 4 | Batch byte |
| 5–6 | Device type, big endian (`00 02`) |
| 7 | Same transaction/operation tag |
| 8 | Effect: 1 = steady |
| 9 | Color/palette index |
| 10 | Speed/brightness-related byte; tested value 0 |
| 11–12 | Password-check bytes; tested value `00 00` |

This plaintext is not sent directly. The tested path uses CSRmesh encryption and
authentication with a fresh sequence number, then splits the resulting 27-byte
packet into a 20-byte low chunk and a 7-byte high chunk.

Write the chunks consecutively to:

- Low: `c4edc000-9daf-11e3-8003-00025b000b00`
- High: `c4edc000-9daf-11e3-8004-00025b000b00`

Use one HA script for both writes, with no deliberate delay between them.
Separate tool calls several seconds apart failed during one controller’s white tests. A
single script delivered both chunks in approximately 0.44 seconds and white
visibly worked. A successful GATT write alone does not confirm a visible change.

Selected palette indices: red 0, green 1, blue 2, purple 12, white presets 13–15,
spring 16, summer 17, autumn 18, winter 19, Christmas 20, Valentine's Day 21,
Independence Day 22, Thanksgiving 23, St. Patrick's Day 24, Halloween 25.
The app labels indices 13–15 White, ColdWhite, CoolWhite; the physical mapping
to warm/daylight/cool has not been established. One tested controller's index 15 was confirmed white.

Controller A passed red → blue → Christmas with different colors across the three heads
→ white through the ESP32 proxy. Controller B passed red → blue → green → white at about
12 seconds per color. Arbitrary independent RGB control of each wired head has
not been established; different head colors are verified through built-in themes.

## Connection recovery

The tested Generic Bluetooth integration retained BLE clients. A controller
could stop advertising while connected, then be marked unavailable when its
advertisements aged out. Some service calls reported success without a visible
result. Reusing a cached client after proxy reconnection also produced a missing
GATT characteristic error.

A software recovery that worked during tests:

1. Reload the ESPHome integration entry for the proxy to release retained links.
2. Wait for the target to advertise through that proxy again.
3. Reload the target Generic Bluetooth integration entry to clear its cached client.
4. Send a fresh packet with both chunks together.

Reloading the proxy briefly interrupts every Bluetooth connection through it.
This is a workaround, not a fix to Generic Bluetooth's connection handling. Avoid
routine light power cycles where a software recovery suffices.

## Fi Light single spotlight

The separately tested Fi Light uses an unencrypted nine-byte command on write
characteristic `FFC1`, under service `FFC0`; notifications are on `FFC2`.

```text
28 RR GG BB WW CW 00 MM 29
```

`MM=F0` selects RGB commands; `MM=0F` selects the two white channels. Red, blue,
purple, and both white channels were visually verified. Green appeared physically
faulty. White pulse (`fd5118fc`) and white blink (`fd5418fc`) effects also worked. These packets and characteristics are separate from the
ShowHome CSRmesh protocol.
