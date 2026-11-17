# Fi Light effects

Recovered from Fi Light Android `com.we.glight` version 1.458. Write
`FD MODE SPEED FC` to characteristic `0000ffc1-0000-1000-8000-00805f9b34fb`.

The native light exposes these in its Effect menu. The preset fixes both the
color and animation; arbitrary RGB plus pulse/blink is not established. Speed
is a separate byte (app range 1–31, inverse slider mapping). The Effect speed slider ranges from 1 (slowest) to 31 (fastest).
Wire speed is `32 - slider_value`; default 8 keeps the previous byte `18` hex.
The command table below uses that default speed. Speed is a remembered setting,
independent of brightness and the selected preset.

| Effect | Command at speed 24 |
| --- | --- |
| Pulse rainbow | `fd2518fc` |
| Pulse red | `fd2618fc` |
| Pulse green | `fd2718fc` |
| Pulse blue | `fd2818fc` |
| Pulse yellow | `fd2918fc` |
| Pulse cyan | `fd2a18fc` |
| Pulse purple | `fd2b18fc` |
| Pulse RGB white | `fd2c18fc` |
| Pulse red/green | `fd2d18fc` |
| Pulse red/blue | `fd2e18fc` |
| Pulse green/blue | `fd2f18fc` |
| Blink rainbow | `fd3018fc` |
| Blink red | `fd3118fc` |
| Blink green | `fd3218fc` |
| Blink blue | `fd3318fc` |
| Blink yellow | `fd3418fc` |
| Blink cyan | `fd3518fc` |
| Blink purple | `fd3618fc` |
| Blink RGB white | `fd3718fc` |
| Jump rainbow | `fd3818fc` |
| Pulse warm white | `fd5118fc` |
| Pulse cool white | `fd5218fc` |
| Pulse warm/cool white | `fd5318fc` |
| Blink warm white | `fd5418fc` |
| Blink cool white | `fd5518fc` |
| Blink warm/cool white | `fd5618fc` |
| Jump warm/cool white | `fd5718fc` |

Warm-white pulse and blink were visually confirmed in earlier testing. Purple
pulse, blue blink and red/blue pulse were also visually confirmed through the
native HA light during beta.2 validation. The remaining mappings come from the
app and are not individually hardware-verified. The tested fixture has a faulty
green channel.

Choose **Color** or select a color on the wheel to return to steady RGB.
White channel 1/2 and Both white channels return to steady white. Built-in
effect brightness is unverified and is not presented as adjustable.

The separate packet `28 RR GG BB W1 W2 00 MODE 29` handles static colors.
Sending it exits the built-in animation; it does not set an animation color.
